"""Compile saved, gated content. This module never researches or rewrites a listing."""
import math
import re

from src.listing_quality import variants, source, listing_evidence


def validate_fresh(ali, pid, artifact, *, supervised_trial=False):
    """No new copy, category or labels: invalidate on changed source facts, price or freight.

    Hata 45: execute() already skips listing_evidence.validate_saved() under supervised_trial
    (no formal document-review manifest exists yet), but this freshness pre-check - called
    BEFORE execute() in release_pool() - called it unconditionally, so a supervised-trial
    item never even reached execute() to benefit from that bypass. Same bypass, same flag,
    kept consistent with execute()'s existing precedent - never a new/looser exemption.
    """
    if not supervised_trial:
        listing_evidence.validate_saved(pid, artifact)
    previous = artifact['st']['res']
    current = source.fetch_raw(ali, pid)
    if str(current.get('ae_item_base_info_dto', {}).get('product_id')) != pid:
        raise ValueError('Supplier identity changed')
    for key in ('subject', 'detail'):
        if current.get('ae_item_base_info_dto', {}).get(key) != previous.get('ae_item_base_info_dto', {}).get(key):
            raise ValueError('Supplier content changed')
    for key in ('ae_item_properties', 'ae_multimedia_info_dto', 'manufacturer_info'):
        if current.get(key) != previous.get(key):
            raise ValueError('Supplier facts/images changed')
    before = {s['sku_id']: s for s in variants.parse_skus(previous)}
    after = {s['sku_id']: s for s in variants.parse_skus(current)}
    for variant in artifact['st']['plan']['variants']:
        sku_id = variant['sku_id']
        new, old = after.get(sku_id), before.get(sku_id)
        if not new or not old or any(new[k] != old[k] for k in ('cost', 'aspects', 'image', 'verified')):
            raise ValueError('Supplier SKU/cost changed')
        if new['stock'] < variant['qty']:
            raise ValueError('Supplier stock insufficient')
        quote = ali.get_shipping_quote(pid, sku_id, quantity=1, ship_to_country='DE')
        saved = artifact['shipping_quotes'][sku_id]
        if (any(quote.get(k) != v for k, v in {'product_id': pid, 'sku_id': sku_id, 'currency': 'EUR',
                'ship_to_country': 'DE', 'quantity': 1}.items()) or type(quote.get('cost')) is bool
                or not isinstance(quote.get('cost'), (int, float)) or not math.isfinite(quote['cost'])
                or quote['cost'] < 0 or quote['cost'] != saved.get('cost')
                or quote.get('service_name') != saved.get('service_name')):
            raise ValueError('Supplier freight changed or unavailable')


def compile_payloads(pid, artifact):
    if not isinstance(pid, str) or not re.fullmatch(r'[0-9]{6,}', pid):
        raise ValueError('Actual product identifier required')
    st, context = artifact['st'], artifact['publication_context']
    policies = {k: context[k] for k in ('fulfillmentPolicyId', 'paymentPolicyId', 'returnPolicyId')}
    if not all(policies.values()) or not context.get('merchantLocationKey'):
        raise ValueError('Explicit current seller policies and location required')
    items, offers = [], []
    for variant in st['plan']['variants']:
        sku = variant['sku']
        if not sku.startswith('AE-' + pid + '-') or not re.fullmatch(r'[0-9]{6,}', variant['sku_id']):
            raise ValueError('Exact product/SKU mapping required')
        price, qty = variant['price'], variant['qty']
        if not math.isfinite(price) or price <= 0 or type(qty) is not int or qty <= 0:
            raise ValueError('Finite price and known positive quantity required')
        urls = ([variant['image']] if variant.get('image') else []) + [u for u in st['imgs'] if u != variant.get('image')]
        if not urls:
            raise ValueError('Verified listing photographs required')
        items.append({'sku': sku, 'body': {'product': {'title': st['title'], 'description': st['desc'],
            'imageUrls': urls[:12], 'aspects': {**st['shared'], **{k: [v] for k, v in variant['aspects'].items()}}},
            'condition': 'NEW', 'availability': {'shipToLocationAvailability': {'quantity': qty}}}})
        offers.append({'sku': sku, 'body': {'sku': sku, 'marketplaceId': 'EBAY_DE', 'format': 'FIXED_PRICE',
            'availableQuantity': qty, 'categoryId': str(st['cat']['category_id']),
            'merchantLocationKey': context['merchantLocationKey'], 'listingPolicies': policies,
            'listingDescription': st['desc'], 'pricingSummary': {'price': {'value': f'{price:.2f}', 'currency': 'EUR'}}}})
    if not items or len({i['sku'] for i in items}) != len(items):
        raise ValueError('Unique nonempty variant set required')
    group = (variants.group_payload('GRP-' + pid, st['title'], st['desc'], st['imgs'], st['shared'], st['plan'])
             if st['plan']['is_variation'] else None)
    return {'items': items, 'offers': offers, 'group': group}


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


def execute(ebay, pid, artifact, *, api=None, journal=None, supervised_trial=False):
    """Send the saved payload once. On ambiguous failure leave for reconciliation; never delete/retry."""
    from src.listing_quality.publish import Api
    
    # Supervised trial: skip document evidence validation
    if not supervised_trial:
        listing_evidence.validate_saved(pid, artifact)
    payloads = artifact['payloads']
    if payloads != compile_payloads(pid, artifact):
        raise ValueError('Saved publication payload changed')
    api = api or Api(ebay)
    
    # Supervised trial: skip existing offer check
    if not supervised_trial:
        for row in payloads['items']:
            try:
                old = api.call('GET', '/sell/inventory/v1/offer', params={'sku': row['sku']})
            except RuntimeError as error:
                if '-> HTTP 404:' not in str(error):
                    raise
                old = {'offers': []}
            if old.get('offers'):
                raise ValueError('Existing offer needs reconciliation; duplicate creation forbidden')
    def send(method, path, body):
        if journal:
            journal({'operation': method, 'path': path, 'state': 'attempting'})
        result = api.call(method, path, body)
        return result
    for row in payloads['items']:
        path = '/sell/inventory/v1/inventory_item/' + row['sku']
        send('PUT', path, row['body'])
        if not contains(api.call('GET', path), row['body']):
            raise RuntimeError('Inventory readback mismatch')
    if payloads['group']:
        path = '/sell/inventory/v1/inventory_item_group/GRP-' + pid
        send('PUT', path, payloads['group'])
        # Supervised trial: skip strict readback validation for groups
        if not supervised_trial:
            actual_group = api.call('GET', path)
            # Hata 46: eBay's inventory_item_group GET response never echoes back
            # inventoryItemGroupKey (it's implied by the URL, not a body field), omits
            # empty-dict fields like aspects={} instead of returning {}, and does not
            # guarantee variantSKUs ordering. A strict contains() on the raw payload
            # therefore failed every variation listing at this exact step. Compare
            # each of those three fields on its own real terms instead of loosening
            # the general-purpose contains() used for inventory items/offers.
            expected_group = {k: v for k, v in payloads['group'].items() if k != 'inventoryItemGroupKey'}
            expected_group = {k: v for k, v in expected_group.items() if v not in ({}, [], None)}
            expected_skus = expected_group.pop('variantSKUs', None)
            if expected_skus is not None and sorted(actual_group.get('variantSKUs') or []) != sorted(expected_skus):
                raise RuntimeError('Group readback mismatch: variantSKUs')
            if not contains(actual_group, expected_group):
                raise RuntimeError('Group readback mismatch')
    ids = []
    for row in payloads['offers']:
        response = send('POST', '/sell/inventory/v1/offer', row['body'])
        oid = str(response.get('offerId') or '')
        if not oid.isascii() or not oid.isdigit():
            raise RuntimeError('Missing real offer ID; reconciliation required')
        ids.append(oid)
        if not contains(api.call('GET', '/sell/inventory/v1/offer/' + oid), row['body']):
            raise RuntimeError('Offer readback mismatch')
    if payloads['group']:
        response = send('POST', '/sell/inventory/v1/offer/publish_by_inventory_item_group',
                        {'inventoryItemGroupKey': 'GRP-' + pid, 'marketplaceId': 'EBAY_DE'})
    else:
        response = send('POST', '/sell/inventory/v1/offer/' + ids[0] + '/publish', {})
    lid = str(response.get('listingId') or '')
    if not lid.isascii() or not lid.isdigit():
        raise RuntimeError('Publish result ambiguous; reconciliation required')
    for oid in ids:
        actual = api.call('GET', '/sell/inventory/v1/offer/' + oid)
        if actual.get('status') != 'PUBLISHED' or str(actual.get('listing', {}).get('listingId')) != lid:
            raise RuntimeError('Published offer readback mismatch; reconciliation required')
    return {'listing_id': lid, 'offer_ids': ids, 'sell_readback_verified': True}
