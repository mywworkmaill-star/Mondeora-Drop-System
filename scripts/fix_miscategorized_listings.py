"""One-off fix for 4 live listings found miscategorized (category name was
literally copy-pasted into the 'Produktart' aspect value - a real, confirmed
bug in whatever code created these 4 listings outside the normal pipeline).
Changes: offer categoryId -> correct category (manually reviewed against
eBay's own get_category_suggestions alternatives, since auto-resolution alone
picked an equally wrong category for one of these - see ebay-category-resolution
skill), inventory_item_group shared aspects (real Produktart from eBay's own
category picklist, real Material), and per-SKU Breite/Höhe/Länge from real
AliExpress package/product dimensions (never invented).
"""
import sys
import json
import time
sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.api.aliexpress_client import AliExpressAPIClient
from src.listing_quality import source

ebay = eBayAPIClient()
ali = AliExpressAPIClient()

FIXES = {
    '1005006266383463': {
        'listing_id': '860143554598', 'new_category': '43504',
        'group_aspects': {'Marke': ['Markenlos'], 'Produktart': ['Aufbewahrungstasche']},
        'shared_dims': (19, 13, 8),  # real package_info_dto (Laenge,Breite,Hoehe)
    },
    '1005012861205757': {
        'listing_id': '860143553992', 'new_category': '46283',
        'group_aspects': {'Marke': ['Markenlos'], 'Produktart': ['Topfdeckelhalter'], 'Material': ['Kunststoff']},
        'shared_dims': (15, 13, 3),
    },
    '1005005995498062': {
        'listing_id': '860143553444', 'new_category': '63690',
        'group_aspects': {'Hersteller': ['Markenlos'], 'Material': ['Nylon']},
        'shared_dims': None,  # 63690 only requires Hersteller
    },
}


def fix_product(pid, cfg):
    print(f'=== {pid} ===', flush=True)
    grp_key = 'GRP-' + pid
    group = ebay._request('GET', f'/sell/inventory/v1/inventory_item_group/{grp_key}')
    before_aspects = dict(group.get('aspects') or {})
    group_aspects = dict(cfg['group_aspects'])
    # Hata 40: eBay's offer-level required-aspect validation (triggered on ANY
    # offer PUT, e.g. a category change) checks the GROUP's shared aspects, not
    # just the per-SKU inventory_item - even for aspects that ARE variation-
    # enabled (Laenge/Breite/Hoehe vary per SKU, but a representative value must
    # still sit in the group's aspects or every offer PUT 400s with "<aspect>
    # fehlt", cycling through each missing one across repeated retries).
    rep_dims = cfg.get('shared_dims')
    if rep_dims is None and 'per_sku_dims' in cfg:
        rep_dims = next(iter(cfg['per_sku_dims'].values()))
    if rep_dims:
        length, width, height = rep_dims
        group_aspects.setdefault('Länge', [f'{length} cm'])
        group_aspects.setdefault('Breite', [f'{width} cm'])
        group_aspects.setdefault('Höhe', [f'{height} cm'])
    group['aspects'] = group_aspects
    ebay._request('PUT', f'/sell/inventory/v1/inventory_item_group/{grp_key}', json=group)
    print('  group aspects:', before_aspects, '->', group_aspects)
    time.sleep(10)  # let eBay's aspect index catch up before offer PUTs re-validate

    # find every SKU belonging to this listing from the ground-truth audit
    audit = [json.loads(l) for l in open('data/audit/full_inventory_audit.jsonl', encoding='utf-8')]
    skus = [r['sku'] for r in audit if r.get('listing_id') == cfg['listing_id']]
    print('  sku sayisi:', len(skus))

    for sku in skus:
        item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
        aspects = dict((item.get('product') or {}).get('aspects') or {})
        dims = cfg.get('shared_dims')
        if 'per_sku_dims' in cfg:
            sku_id = sku.rsplit('-', 1)[-1]
            dims = cfg['per_sku_dims'].get(sku_id)
        if dims:
            length, width, height = dims
            aspects['Länge'] = [f'{length} cm']
            aspects['Breite'] = [f'{width} cm']
            aspects['Höhe'] = [f'{height} cm']
        for k, v in cfg['group_aspects'].items():
            aspects[k] = v
        item.setdefault('product', {})['aspects'] = aspects
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=item)

        offer_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
        offers = offer_resp.get('offers', [])
        if not offers:
            print('  !! offer yok:', sku)
            continue
        offer_id = offers[0]['offerId']
        offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        old_cat = offer.get('categoryId')
        offer['categoryId'] = cfg['new_category']
        for field in ('offerId', 'status', 'listing'):
            offer.pop(field, None)
        ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=offer)
        print(f'  {sku}: kategori {old_cat} -> {cfg["new_category"]}, dims={dims}')

    verify = ebay._request('GET', f'/sell/inventory/v1/inventory_item_group/{grp_key}')
    print('  dogrulama group aspects:', verify.get('aspects'))


if __name__ == '__main__':
    for pid, cfg in FIXES.items():
        try:
            fix_product(pid, cfg)
        except Exception as ex:
            print(f'!!! {pid} HATA: {type(ex).__name__}: {ex}', flush=True)
        print(flush=True)
    print('ALL DONE', flush=True)
