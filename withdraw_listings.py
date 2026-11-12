"""Withdraw listings that must not stay live (wrong product / restricted). Safe: refuses when anything was sold. Reversible
(offers stay in the inventory; re-publish possible). Usage: python withdraw_listings.py <db_id> [<db_id> ...] [--live]"""
import json
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import publish

live = '--live' in sys.argv
ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
api = publish.Api(eBayAPIClient())
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row
for pid in ids:
    p = db.execute('select * from products where id=?', (pid,)).fetchone()
    skus = [r[0] for r in db.execute('select sku from product_variants where product_id=?', (pid,))]
    if not skus:
        # No tracked variants in our DB: discover every real offer sharing this product's AliExpress id
        # (covers both a true single-SKU listing and a legacy multi-SKU listing that was never grouped
        # via inventory_item_group — never guess, only use SKUs that actually exist on eBay).
        offset, skus = 0, []
        while True:
            page = api.call('GET', '/sell/inventory/v1/inventory_item', params={'limit': 100, 'offset': offset})
            for it in page.get('inventoryItems') or []:
                if p['aliexpress_product_id'] in it['sku']:
                    skus.append(it['sku'])
            offset += 100
            if offset >= int(page.get('total') or 0):
                break
        if not skus:
            o = publish.find_old_offer(api, p['sku_id'], p['ebay_item_id'])
            skus = [o['sku']]
    offers = []
    for s in skus:
        try:
            offers.append(api.call('GET', '/sell/inventory/v1/offer', params={'sku': s})['offers'][0])
        except Exception:
            pass   # inventory item exists but has no offer (never published) — nothing to withdraw
    sold = sum(int(o.get('listing', {}).get('soldQuantity') or 0) for o in offers)
    print(f"#{pid} listing {p['ebay_item_id']} offers={len(offers)} sold={sold} status={[o['status'] for o in offers][:3]}")
    if sold:
        print('   REFUSED: has sales, handle manually'); continue
    if not live:
        print('   dry-run'); continue
    for o in offers:
        if o['status'] == 'PUBLISHED':
            api.call('POST', f"/sell/inventory/v1/offer/{o['offerId']}/withdraw")
    chk = []
    for o in offers:
        try:
            chk.append(api.call('GET', '/sell/inventory/v1/offer', params={'sku': o['sku']})['offers'][0]['status'])
        except Exception:
            chk.append('UNKNOWN')
    print('   after:', set(chk))
    if set(chk) <= {'UNPUBLISHED', 'ENDED'}:
        db.execute("update products set is_listed=0, status='withdrawn_by_policy', updated_at=? where id=?", (datetime.now().isoformat(), pid))
        db.commit()
        print('   DB updated')
