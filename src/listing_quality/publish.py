"""Replace ONE single-SKU live listing with a correct variation listing (right category, per-variant price,
unique description). Safe order: create+publish NEW group -> verify -> withdraw OLD offer. Failure before the
withdraw leaves the old listing untouched. dry_run=True performs only reads."""
import json
import re
import time
from pathlib import Path

from src.listing_quality import categories, description, gates, images, pricing, source, variants

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'data' / 'audit'
ALIASES = {'Größe': ['Hundegröße', 'Katzengröße', 'Größe'], 'Mobiles Modell': ['Kompatibles Modell', 'Modell'],
           'Color': ['Farbe', 'Color']}
STOP = {'für', 'und', 'mit', 'zum', 'zur', 'der', 'die', 'das', 'aus', 'in', 'von', 'bei', 'oder', 'zu'}


def make_title(subject):
    s = re.sub(r'\s+', ' ', subject or '').strip()
    if len(s) > 80:
        s = s[:80].rsplit(' ', 1)[0]
    words = s.rstrip(' ,;:-').split(' ')
    while words and words[-1].lower().strip(',;:') in STOP:
        words.pop()
    return ' '.join(words).rstrip(' ,;:-')


def map_variation_names(plan, meta):
    ok = {a['name'] for a in meta if a['variation_ok']}
    mapping = {}
    for sp in plan['specifications']:
        n = sp['name']
        target = n if n in ok else next((c for c in ALIASES.get(n, []) if c in ok), None)
        if not target:
            raise ValueError(f'variation aspect {n!r} not allowed for this category (allowed: {sorted(ok)})')
        mapping[n] = target
    return mapping


class Api:
    """Direct eBay REST caller that keeps the error BODY (EBayAPIClient._request hides it)."""

    def __init__(self, ebay):
        self.e = ebay
        ebay._require_live()

    def call(self, method, path, body=None, params=None):
        for attempt in (0, 1):
            r = self.e.session.request(method, self.e.production_url + path, headers=self.e._get_headers(),
                                       json=body, params=params, timeout=40, allow_redirects=False)
            if r.status_code == 401 and attempt == 0:
                self.e.refresh_access_token(force=True)
                continue
            break
        try:
            data = r.json() if r.content else {}
        except ValueError:
            data = {'raw': r.text[:300]}
        if not 200 <= r.status_code < 300:
            raise RuntimeError(f'{method} {path} -> HTTP {r.status_code}: {json.dumps(data, ensure_ascii=False)[:1400]}')
        return data


def find_old_offer(api, sku, listing_id):
    """DB sku_id is sometimes an AliExpress SKU, not the eBay SKU: fall back to scanning inventory by listingId."""
    try:
        offers = api.call('GET', '/sell/inventory/v1/offer', params={'sku': sku}).get('offers') or []
        for o in offers:
            if not listing_id or o.get('listing', {}).get('listingId') == str(listing_id):
                return o
    except RuntimeError:
        pass
    offset = 0
    while True:
        page = api.call('GET', '/sell/inventory/v1/inventory_item', params={'limit': 100, 'offset': offset})
        items = page.get('inventoryItems') or []
        for it in items:
            try:
                for o in api.call('GET', '/sell/inventory/v1/offer', params={'sku': it['sku']}).get('offers') or []:
                    if o.get('listing', {}).get('listingId') == str(listing_id) and o.get('status') == 'PUBLISHED':
                        return o
            except RuntimeError:
                continue
        offset += 100
        if offset >= int(page.get('total') or 0):
            break
    raise RuntimeError(f'old offer not found for listing {listing_id}')


AD_CAMPAIGN = '167027798017'   # MONDEORA-BASIS-01


def add_ad(api, listing_id):
    """New listings start at ads.BOOST_BID (visibility window) and auto-decay to ads.STEADY_BID
    after ads.BOOST_DAYS via job_ad_bid_optimize - see src/listing_quality/ads.py."""
    from src.listing_quality import ads
    try:
        r = api.call('POST', f'/sell/marketing/v1/ad_campaign/{AD_CAMPAIGN}/bulk_create_ads_by_listing_id',
                     {'requests': [{'listingId': str(listing_id), 'bidPercentage': ads.BOOST_BID}]})
        resp = (r.get('responses') or [{}])[0]
        if resp.get('adId') or resp.get('statusCode') in (200, 201):
            ads.record_boost(resp.get('adId'), listing_id, AD_CAMPAIGN)
            return 'ok'
        return f'check: {json.dumps(resp, ensure_ascii=False)[:200]}'
    except Exception as ex:
        return f'error: {str(ex)[:200]}'


def plan_for(ali, ebay, pid, ship, db_title=None, extra_aspects=None, existing=False, verified_aspects=None):
    res = source.fetch_raw(ali, pid)
    props = source.properties(res)
    subject = res['ae_item_base_info_dto']['subject']
    if db_title:
        tok = lambda x: {w for w in categories.clean(x).lower().split() if len(w) > 3}
        a, b = tok(subject), tok(db_title)
        if len(a & b) / max(len(a | b), 1) < 0.15:
            raise ValueError(f'IDENTITY MISMATCH: db={db_title[:50]!r} supplier={subject[:50]!r}')
    title = make_title(subject)
    # --- gates as code: product risk, title rules, legal flags (blocks never publish; reviews need user ack) ---
    g = gates.evaluate(pid, subject, props)
    g['block'] += [f'title: {p}' for p in gates.check_title(title)]
    if g['block']:
        raise ValueError(f'GATE BLOCK {g["block"]}')
    if g['review'] and not existing:
        raise ValueError(f'GATE REVIEW needs user acknowledgement in config/risk_ack.json: {g["review"]}')
    cat = categories.resolve_for_product(ebay, pid, subject, props)
    if not cat.get('category_id') or cat.get('needs_review'):
        raise ValueError(f'category not approved: {cat}')
    # Try the top category, then automatically fall back through its real alternatives (same taxonomy vote,
    # never invented) when the required/variation aspects don't fit — generalizes what used to need a manual
    # config/category_overrides.json entry for every product whose best category lacks the right aspects.
    candidates = [cat] + [{'category_id': c, 'path': p, 'confidence': cat.get('confidence', 0), 'source': 'alternative'}
                          for c, p, _hits in (cat.get('alternatives') or [])]
    plan = variants.build(pid, res, ship, verified_aspects=verified_aspects)
    if not plan['variants']:
        raise ValueError('no sellable variants')
    if plan['flags']:
        raise ValueError(f"needs human review: {plan['flags']}")
    attempt_errors = []
    for candidate in candidates:
        try:
            meta = categories.aspects_for(ebay, candidate['category_id'])
            shared, missing = categories.fill_aspects(meta, props)
            shared.update(extra_aspects or {})
            missing = [m for m in missing if m not in shared]
            if any(a['name'] == 'Produktart' for a in meta) and 'Produktart' not in shared:
                shared['Produktart'] = [candidate['path'].split(' > ')[-1]]
                missing = [m for m in missing if m != 'Produktart']
            if missing:
                raise ValueError(f'required aspects missing: {missing}')
            mapping = map_variation_names(plan, meta) if plan['is_variation'] else {}
            cat = candidate
            break
        except ValueError as ex:
            attempt_errors.append(f"{candidate['category_id']}: {ex}")
    else:
        raise ValueError(f'no candidate category fit (tried {len(candidates)}): {attempt_errors}')
    for v in plan['variants']:
        v['aspects'] = {mapping.get(k, k): val for k, val in v['aspects'].items()}
    for sp in plan['specifications']:
        sp['name'] = mapping.get(sp['name'], sp['name'])
    for sp in plan['specifications']:
        shared.pop(sp['name'], None)
    dinfo, dreview = gates.demand(ebay, categories.queries(subject, props), min(v['price'] for v in plan['variants']))
    if dreview and not existing and 'demand' not in gates.acknowledged(pid):
        raise ValueError(f'GATE REVIEW needs user acknowledgement (group demand): {dreview} {dinfo}')
    desc = description.build(title, res, plan)
    shared_imgs = [i for i in (res.get('ae_multimedia_info_dto', {}).get('image_urls') or '').split(';') if i][:12]
    # --- image gate: eBay.de needs >= 500 px; low-res images are dropped, no good image = block ---
    _kept, _dropped = images.filter_urls(shared_imgs + [v['image'] for v in plan['variants'] if v['image']])
    _good = set(_kept)
    shared_imgs = [i for i in shared_imgs if i in _good]
    for v in plan['variants']:
        if v['image'] not in _good:
            v['image'] = None
    if not shared_imgs and not any(v['image'] for v in plan['variants']) and not existing:
        raise ValueError(f'GATE BLOCK no image >= 500 px (dropped {len(_dropped)}): eBay would reject it (error 25002)')
    return {'gates': {**g, 'demand': dinfo, 'demand_review': dreview, 'images_dropped': len(_dropped)}, 'res': res, 'title': title, 'cat': cat, 'shared': shared, 'plan': plan, 'desc': desc, 'imgs': shared_imgs}


def apply(ali, ebay, pid, old_sku, ship, dry_run=True, db_title=None, old_listing_id=None, extra_aspects=None, verified_aspects=None):
    st = plan_for(ali, ebay, pid, ship, db_title, extra_aspects, verified_aspects=verified_aspects)
    plan, cat = st['plan'], st['cat']
    out = {'title': st['title'], 'category': cat['category_id'], 'variants': len(plan['variants']),
           'price_range': [plan['variants'][0]['price'], plan['variants'][-1]['price']],
           'min_net': min(v['net'] for v in plan['variants']), 'spec': plan['specifications'],
           'shared_aspects': st['shared'], 'desc_chars': len(st['desc']), 'demand': st['gates']['demand'], 'dry_run': dry_run}
    if dry_run:
        return out
    api = Api(ebay)
    env = pricing._env()
    pol = {'fulfillmentPolicyId': env['EBAY_FULFILLMENT_POLICY_ID'], 'paymentPolicyId': env['EBAY_PAYMENT_POLICY_ID'],
           'returnPolicyId': env['EBAY_RETURN_POLICY_ID']}
    old = find_old_offer(api, old_sku, old_listing_id) if old_sku else None
    key = f'GRP-{pid}'
    created = {'items': [], 'offers': [], 'group': None}
    try:
        for v in plan['variants']:
            imgs = ([v['image']] if v['image'] else []) + [i for i in st['imgs'] if i != v['image']]
            api.call('PUT', f"/sell/inventory/v1/inventory_item/{v['sku']}", {
                'product': {'title': st['title'], 'description': st['desc'], 'imageUrls': imgs[:12],
                            'aspects': {**st['shared'], **{k: [x] for k, x in v['aspects'].items()}}},
                'condition': 'NEW', 'availability': {'shipToLocationAvailability': {'quantity': v['qty']}}})
            created['items'].append(v['sku'])
        if plan['is_variation']:
            grp = variants.group_payload(key, st['title'], st['desc'], st['imgs'], st['shared'], plan)
            api.call('PUT', f'/sell/inventory/v1/inventory_item_group/{key}', grp)
            created['group'] = key
        for v in plan['variants']:
            r = api.call('POST', '/sell/inventory/v1/offer', {
                'sku': v['sku'], 'marketplaceId': 'EBAY_DE', 'format': 'FIXED_PRICE', 'availableQuantity': v['qty'],
                'categoryId': str(cat['category_id']),
                'merchantLocationKey': (old or {}).get('merchantLocationKey') or env.get('EBAY_MERCHANT_LOCATION_KEY') or 'default-warehouse',
                'listingPolicies': pol, 'pricingSummary': {'price': {'value': f"{v['price']:.2f}", 'currency': 'EUR'}},
                'tax': {'applyTax': False}})
            created['offers'].append(r['offerId'])
        if plan['is_variation']:
            pubr = api.call('POST', '/sell/inventory/v1/offer/publish_by_inventory_item_group',
                            {'inventoryItemGroupKey': key, 'marketplaceId': 'EBAY_DE'})
        else:
            pubr = api.call('POST', f"/sell/inventory/v1/offer/{created['offers'][0]}/publish", {})
        listing_id = str(pubr.get('listingId'))
    except Exception as ex:  # roll back everything created so far; old listing is still live
        for oid in created['offers']:
            try:
                api.call('DELETE', f'/sell/inventory/v1/offer/{oid}')
            except Exception:
                pass
        if created['group']:
            try:
                api.call('DELETE', f'/sell/inventory/v1/inventory_item_group/{key}')
            except Exception:
                pass
        for s in created['items']:
            try:
                api.call('DELETE', f'/sell/inventory/v1/inventory_item/{s}')
            except Exception:
                pass
        raise RuntimeError(f'publish failed, rolled back, OLD listing untouched: {ex}')
    out.update({'new_listing_id': listing_id, 'old_listing_id': old['listing']['listingId'] if old else None})
    time.sleep(3)
    chk = api.call('GET', '/sell/inventory/v1/offer', params={'sku': plan['variants'][0]['sku']})['offers'][0]
    out['new_status'] = [chk.get('status'), chk.get('listing', {}).get('listingStatus')]
    if chk.get('status') != 'PUBLISHED':
        raise RuntimeError(f'new listing not PUBLISHED, old listing kept: {out}')
    if old:
        api.call('POST', f"/sell/inventory/v1/offer/{old['offerId']}/withdraw")
        out['old_withdrawn'] = True
    out['ad'] = add_ad(api, listing_id)
    (STATE / f'apply_{pid}.json').write_text(json.dumps({**out, 'created': created}, ensure_ascii=False, indent=1, default=str),
                                             encoding='utf-8')
    out['_state'] = {'plan': plan, 'desc': st['desc'], 'category_id': cat['category_id']}
    return out


def recategorize(ali, ebay, pid, ship, extra_aspects=None, dry_run=True):
    """Re-publish an ALREADY live listing (same SKUs) with the current plan: category, VERIFIED variant labels, price, qty,
    description. Gate REVIEW flags are reported but do not block (the listing is already live); BLOCK flags still block.
    Order: plan -> withdraw -> update items/offers -> publish. On failure the old state is restored and re-published."""
    import sqlite3
    db = sqlite3.connect(str(ROOT / 'data' / 'dropshipping.db'))
    db.row_factory = sqlite3.Row
    prod = db.execute('select * from products where aliexpress_product_id=?', (pid,)).fetchone()
    vrows = db.execute('select * from product_variants where product_id=?', (prod['id'],)).fetchall()
    st = plan_for(ali, ebay, pid, ship, None, extra_aspects, existing=True)
    plan = st['plan']
    cat = st['cat']['category_id']
    newv = {v['sku']: v for v in plan['variants']}
    out = {'pid': pid, 'new_category': cat, 'variants': len(newv), 'was_variants': len(vrows), 'dry_run': dry_run,
           'labels': [v['aspects'] for v in plan['variants']], 'prices': [v['price'] for v in plan['variants']],
           'review_flags': st['gates']['review'] + st['gates'].get('demand_review', [])}
    old = {r['sku']: json.loads(r['aspects']) for r in vrows}
    out['labels_changed'] = any(old.get(k) != v['aspects'] for k, v in newv.items()) or set(old) != set(newv)
    if dry_run:
        return out
    api = Api(ebay)
    unknown = [k for k in newv if k not in {r['sku'] for r in vrows}]
    if unknown:
        raise RuntimeError(f'new variants {unknown}: use apply_variation_listing.py, not recategorize')
    offers = {r['sku']: api.call('GET', '/sell/inventory/v1/offer', params={'sku': r['sku']})['offers'][0] for r in vrows}
    old_items = {k: api.call('GET', f'/sell/inventory/v1/inventory_item/{k}') for k in offers}
    old_cat = {k: o['categoryId'] for k, o in offers.items()}
    keys = ('sku', 'marketplaceId', 'format', 'availableQuantity', 'listingPolicies', 'pricingSummary', 'merchantLocationKey', 'tax',
            'listingDescription')
    is_group = plan['is_variation']
    try:
        if is_group:   # a variation listing is ended as ONE unit (single-offer withdraw is rejected: 25013)
            api.call('POST', '/sell/inventory/v1/offer/withdraw_by_inventory_item_group',
                     {'inventoryItemGroupKey': f'GRP-{pid}', 'marketplaceId': 'EBAY_DE'})
        else:
            for o in offers.values():
                if o['status'] == 'PUBLISHED':
                    api.call('POST', f"/sell/inventory/v1/offer/{o['offerId']}/withdraw")
        for sku, v in newv.items():
            it = old_items[sku]
            it['product']['aspects'] = {**st['shared'], **{k: [x] for k, x in v['aspects'].items()}}
            it['product']['description'] = st['desc']
            it['product']['title'] = st['title']
            if v['image']:
                it['product']['imageUrls'] = ([v['image']] + [i for i in st['imgs'] if i != v['image']])[:12]
            it['availability'] = {'shipToLocationAvailability': {'quantity': v['qty']}}
            api.call('PUT', f'/sell/inventory/v1/inventory_item/{sku}', {k: it[k] for k in ('product', 'condition', 'availability') if k in it})
            o = offers[sku]
            body = {k: o[k] for k in keys if k in o}
            body.update({'categoryId': str(cat), 'availableQuantity': v['qty'],
                         'pricingSummary': {'price': {'value': f"{v['price']:.2f}", 'currency': 'EUR'}}})
            api.call('PUT', f"/sell/inventory/v1/offer/{o['offerId']}", body)
        if is_group:
            grp = variants.group_payload(f'GRP-{pid}', st['title'], st['desc'], st['imgs'], st['shared'], plan)
            api.call('PUT', f'/sell/inventory/v1/inventory_item_group/GRP-{pid}', grp)
            pub = api.call('POST', '/sell/inventory/v1/offer/publish_by_inventory_item_group',
                           {'inventoryItemGroupKey': f'GRP-{pid}', 'marketplaceId': 'EBAY_DE'})
        else:
            sku0 = next(iter(newv))
            pub = api.call('POST', f"/sell/inventory/v1/offer/{offers[sku0]['offerId']}/publish", {})
        lid = str(pub.get('listingId'))
    except Exception as ex:
        for sku, o in offers.items():
            try:
                body = {k: o[k] for k in keys if k in o}
                body['categoryId'] = old_cat[sku]
                api.call('PUT', f"/sell/inventory/v1/offer/{o['offerId']}", body)
                api.call('PUT', f'/sell/inventory/v1/inventory_item/{sku}', {k: old_items[sku][k] for k in ('product', 'condition', 'availability') if k in old_items[sku]})
            except Exception:
                pass
        try:
            if len(vrows) > 1:
                api.call('POST', '/sell/inventory/v1/offer/publish_by_inventory_item_group', {'inventoryItemGroupKey': f'GRP-{pid}', 'marketplaceId': 'EBAY_DE'})
            else:
                api.call('POST', f"/sell/inventory/v1/offer/{list(offers.values())[0]['offerId']}/publish", {})
        except Exception:
            pass
        raise RuntimeError(f'republish failed, old state restore attempted: {ex}')
    out['new_listing_id'] = lid
    out['ad'] = add_ad(api, lid)
    now = __import__('datetime').datetime.now().isoformat()
    for sku, v in newv.items():
        db.execute('update product_variants set aspects=?, price=?, qty=?, cost=?, updated_at=? where sku=?',
                   (json.dumps(v['aspects'], ensure_ascii=False), v['price'], v['qty'], v['cost'], now, sku))
    db.execute('update products set ebay_item_id=?, category_id=?, description=?, title=?, ebay_price=?, updated_at=? where id=?',
               (lid, str(cat), st['desc'], st['title'], min(v['price'] for v in newv.values()), now, prod['id']))
    db.commit()
    return out


def list_new(ali, ebay, db_path='data/dropshipping.db', limit=3, dry_run=False, extra=None):
    """Publish NEW (not yet listed) products flagged needs_variation_listing as ONE listing with all variants.
    Same gates as apply(); a blocked product gets status manual_review with the reason in error log, never a single-SKU fallback."""
    import sqlite3
    from datetime import datetime
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("select * from products where is_listed=0 and status='needs_variation_listing' order by id limit ?", (limit,)).fetchall()
    results = []
    for row in rows:
        pid = row['aliexpress_product_id']
        try:
            out = apply(ali, ebay, pid, None, float(row['shipping_cost'] or 1.99), dry_run=dry_run,
                        db_title=row['title'], extra_aspects=(extra or {}).get(pid))
            state = out.pop('_state', None)
            if state and not dry_run:
                now = datetime.now().isoformat()
                plan = state['plan']
                first = plan['variants'][0]
                db.execute('create table if not exists product_variants (id integer primary key autoincrement, product_id integer, '
                           'sku text unique, ali_sku_id text, aspects text, cost real, price real, qty integer, updated_at text)')
                for v in plan['variants']:
                    db.execute('insert or replace into product_variants (product_id, sku, ali_sku_id, aspects, cost, price, qty, updated_at) '
                               'values (?,?,?,?,?,?,?,?)', (row['id'], v['sku'], v['sku_id'], json.dumps(v['aspects'], ensure_ascii=False),
                                                           v['cost'], v['price'], v['qty'], now))
                db.execute("update products set ebay_item_id=?, category_id=?, description=?, ebay_price=?, sku_id=?, aliexpress_price=?, "
                           "title=?, currency='EUR', fulfillment_verified=1, is_listed=1, status='active', updated_at=? where id=?",
                           (out['new_listing_id'], state['category_id'], state['desc'], first['price'], first['sku_id'], first['cost'],
                            out['title'], now, row['id']))
                db.commit()
            results.append((row['id'], 'OK', out.get('new_listing_id'), out.get('variants')))
        except Exception as ex:
            if not dry_run:
                db.execute("update products set status='manual_review' where id=?", (row['id'],))
                db.commit()
            results.append((row['id'], 'BLOCKED', str(ex)[:300]))
    return {'status': 'ok', 'results': results}


def revise_in_place(ali, ebay, pid, ship, extra_aspects=None, dry_run=True):
    """Correct labels/price/qty/description of a LIVE listing WITHOUT ending it (listing id, ads and sales history stay).
    Only valid when the category is unchanged and the SKU set is the same. Images are left exactly as they are on eBay.
    On any failure every touched item/offer/group is restored to its previous content."""
    import sqlite3
    from datetime import datetime
    db = sqlite3.connect(str(ROOT / 'data' / 'dropshipping.db'))
    db.row_factory = sqlite3.Row
    prod = db.execute('select * from products where aliexpress_product_id=?', (pid,)).fetchone()
    vrows = db.execute('select * from product_variants where product_id=?', (prod['id'],)).fetchall()
    st = plan_for(ali, ebay, pid, ship, None, extra_aspects, existing=True)
    plan = st['plan']
    newv = {v['sku']: v for v in plan['variants']}
    cat = str(st['cat']['category_id'])
    out = {'pid': pid, 'variants': len(newv), 'labels': [list(v['aspects'].values()) for v in plan['variants']],
           'prices': sorted({v['price'] for v in plan['variants']}), 'dry_run': dry_run}
    if dry_run:
        return out
    api = Api(ebay)
    offers = {k: api.call('GET', '/sell/inventory/v1/offer', params={'sku': k})['offers'][0] for k in newv}
    bad = [k for k, o in offers.items() if o['status'] != 'PUBLISHED' or str(o['categoryId']) != cat]
    if bad:
        raise RuntimeError(f'in-place revise needs PUBLISHED offers in category {cat}: {bad[:3]} (use recategorize)')
    old_items = {k: api.call('GET', f'/sell/inventory/v1/inventory_item/{k}') for k in newv}
    key = f'GRP-{pid}'
    old_group = api.call('GET', f'/sell/inventory/v1/inventory_item_group/{key}') if plan['is_variation'] else None
    keys = ('sku', 'marketplaceId', 'format', 'availableQuantity', 'listingPolicies', 'pricingSummary', 'merchantLocationKey', 'tax',
            'listingDescription', 'categoryId')
    touched = []
    grp_super = None
    if plan['is_variation']:
        oldspec = {sp['name']: set(sp['values']) for sp in old_group['variesBy']['specifications']}
        if set(oldspec) != {sp['name'] for sp in plan['specifications']}:
            raise RuntimeError(f'variation names changed {sorted(oldspec)} -> {[sp["name"] for sp in plan["specifications"]]}: use recategorize')
        sup_plan = dict(plan, specifications=[{'name': sp['name'], 'values': sorted(oldspec[sp['name']] | set(sp['values']))}
                                              for sp in plan['specifications']])
        grp_super = variants.group_payload(key, st['title'], st['desc'], old_group.get('imageUrls') or st['imgs'], st['shared'], sup_plan)
    try:
        if grp_super:   # eBay validates item aspects against the group's value list: widen it first, narrow it last
            api.call('PUT', f'/sell/inventory/v1/inventory_item_group/{key}', grp_super)
        for sku, v in newv.items():
            it = json.loads(json.dumps(old_items[sku]))
            it['product']['aspects'] = {**st['shared'], **{k: [x] for k, x in v['aspects'].items()}}
            it['product']['description'] = st['desc']
            it['product']['title'] = st['title']
            it['availability'] = {'shipToLocationAvailability': {'quantity': v['qty']}}
            api.call('PUT', f'/sell/inventory/v1/inventory_item/{sku}', {k: it[k] for k in ('product', 'condition', 'availability') if k in it})
            touched.append(sku)
            o = offers[sku]
            body = {k: o[k] for k in keys if k in o}
            body.update({'availableQuantity': v['qty'], 'pricingSummary': {'price': {'value': f"{v['price']:.2f}", 'currency': 'EUR'}}})
            api.call('PUT', f"/sell/inventory/v1/offer/{o['offerId']}", body)
        if plan['is_variation']:
            grp = variants.group_payload(key, st['title'], st['desc'], old_group.get('imageUrls') or st['imgs'], st['shared'], plan)
            api.call('PUT', f'/sell/inventory/v1/inventory_item_group/{key}', grp)
            chk = api.call('GET', f'/sell/inventory/v1/inventory_item_group/{key}')
            got = {sp['name']: sorted(sp['values']) for sp in chk['variesBy']['specifications']}
            want = {sp['name']: sorted(sp['values']) for sp in plan['specifications']}
            if got != want:
                raise RuntimeError(f'group not updated as expected: {got} != {want}')
    except Exception as ex:
        if grp_super:
            try:
                api.call('PUT', f'/sell/inventory/v1/inventory_item_group/{key}', grp_super)
            except Exception:
                pass
        for sku in touched:
            try:
                api.call('PUT', f'/sell/inventory/v1/inventory_item/{sku}', {k: old_items[sku][k] for k in ('product', 'condition', 'availability') if k in old_items[sku]})
                o = offers[sku]
                api.call('PUT', f"/sell/inventory/v1/offer/{o['offerId']}", {k: o[k] for k in keys if k in o})
            except Exception:
                pass
        if old_group:
            try:
                api.call('PUT', f'/sell/inventory/v1/inventory_item_group/{key}', {k: old_group[k] for k in old_group if k not in ('inventoryItemGroupKey',)} | {'inventoryItemGroupKey': key})
            except Exception:
                pass
        raise RuntimeError(f'in-place revise failed, previous content restored: {ex}')
    now = datetime.now().isoformat()
    for sku, v in newv.items():
        db.execute('update product_variants set aspects=?, price=?, qty=?, cost=?, updated_at=? where sku=?',
                   (json.dumps(v['aspects'], ensure_ascii=False), v['price'], v['qty'], v['cost'], now, sku))
    db.execute('update products set description=?, title=?, ebay_price=?, updated_at=? where id=?',
               (st['desc'], st['title'], min(v['price'] for v in newv.values()), now, prod['id']))
    db.commit()
    return out
