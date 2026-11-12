"""Read-only verification of converted listings (+ optional --fix-ads to add missing ads).
Checks per product: every variant offer PUBLISHED, one shared listing id == DB ebay_item_id, category, price vs DB,
ad present."""
import json
import sqlite3
import sys

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import publish

fix = '--fix-ads' in sys.argv
e = eBayAPIClient()
api = publish.Api(e)
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row
bad = 0
for p in db.execute('select * from products where is_listed=1 and id in (select distinct product_id from product_variants) order by id'):
    vs = [r for r in db.execute('select * from product_variants where product_id=?', (p['id'],)).fetchall() if r['qty'] is not None]
    probs, lids, cats = [], set(), set()
    for v in vs:
        try:
            o = api.call('GET', '/sell/inventory/v1/offer', params={'sku': v['sku']})['offers'][0]
        except Exception as ex:
            probs.append(f"{v['sku']}: {str(ex)[:80]}")
            continue
        if o.get('status') != 'PUBLISHED':
            probs.append(f"{v['sku']} status {o.get('status')}")
        lids.add(o.get('listing', {}).get('listingId'))
        cats.add(o.get('categoryId'))
        if abs(float(o['pricingSummary']['price']['value']) - v['price']) > 0.005:
            probs.append(f"{v['sku']} price mismatch")
    # LABEL check: what eBay shows must equal what we computed from the seller's own definition names (DB copy)
    group_vals = {}
    for v in vs:
        try:
            it = api.call('GET', '/sell/inventory/v1/inventory_item/' + v['sku'])
        except Exception:
            continue
        want = json.loads(v['aspects'] or '{}')
        have = {k: (it['product']['aspects'].get(k) or [None])[0] for k in want}
        if have != want:
            probs.append(f"{v['sku'][-8:]} label on eBay {have} != {want}")
        for k, val in want.items():
            group_vals.setdefault(k, set()).add(val)
    if len(vs) > 1:
        try:
            g = api.call('GET', f"/sell/inventory/v1/inventory_item_group/GRP-{p['aliexpress_product_id']}")
            spec = {sp['name']: set(sp['values']) for sp in g['variesBy']['specifications']}
            if spec != group_vals:
                probs.append(f'group spec {spec} != items {group_vals}')
        except Exception as ex:
            probs.append(f'group read failed {str(ex)[:60]}')
    if lids != {p['ebay_item_id']}:
        probs.append(f"listing ids {lids} != db {p['ebay_item_id']}")
    if cats != {str(p['category_id'])}:
        probs.append(f"category {cats} != db {p['category_id']}")
    ad = 'unknown'
    try:
        r = api.call('GET', f'/sell/marketing/v1/ad_campaign/{publish.AD_CAMPAIGN}/ad',
                     params={'listing_ids': p['ebay_item_id']})
        ad = 'yes' if r.get('ads') else 'NO'
    except Exception as ex:
        ad = f'err {str(ex)[:60]}'
    if ad == 'NO' and fix:
        ad = 'added: ' + publish.add_ad(api, p['ebay_item_id'])
    print(f"#{p['id']} listing {p['ebay_item_id']} cat {p['category_id']} variants {len(vs)} ad={ad} ->",
          'OK' if not probs else probs)
    bad += bool(probs)
print('PROBLEMS:', bad)
