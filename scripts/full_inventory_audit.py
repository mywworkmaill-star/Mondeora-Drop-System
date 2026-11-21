"""Ground-truth audit: for EVERY inventory_item SKU on eBay, fetch its current
aspects (from inventory_item) and its live offer/listing status (from offer-by-sku).
Writes one JSON line per SKU to data/audit/full_inventory_audit.jsonl as it goes,
so a timeout loses no completed work. Never guesses a SKU pattern - reads the
real, paginated list of SKUs directly from eBay.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'audit' / 'full_inventory_audit.jsonl'
OUT.parent.mkdir(parents=True, exist_ok=True)

ebay = eBayAPIClient()

# 1. Paginate all inventory item SKUs (ground truth from eBay, not a guess).
all_skus = []
limit, offset = 100, 0
while True:
    resp = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={'limit': limit, 'offset': offset})
    items = resp.get('inventoryItems', [])
    all_skus.extend(i.get('sku') for i in items if i.get('sku'))
    total = resp.get('total', 0)
    if not items or offset + limit >= total:
        break
    offset += limit
print(f'Total SKUs on eBay: {len(all_skus)}', flush=True)

# Resume support: skip SKUs already recorded in a previous (interrupted) run.
done = set()
if OUT.exists():
    with OUT.open('r', encoding='utf-8') as f:
        for line in f:
            try:
                done.add(json.loads(line)['sku'])
            except Exception:
                pass
print(f'Already recorded (resume): {len(done)}', flush=True)

with OUT.open('a', encoding='utf-8') as f:
    for i, sku in enumerate(all_skus):
        if sku in done:
            continue
        record = {'sku': sku}
        try:
            item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            product_obj = item.get('product') or {}
            record['aspects'] = product_obj.get('aspects') or {}
            record['aspect_count'] = len(record['aspects'])
            record['image_count'] = len(product_obj.get('imageUrls') or [])
            record['title'] = product_obj.get('title')
        except Exception as ex:
            record['inventory_error'] = f'{type(ex).__name__}: {ex}'[:200]
        try:
            offer_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
            offers = offer_resp.get('offers', [])
            if offers:
                o = offers[0]
                record['offer_id'] = o.get('offerId')
                record['offer_status'] = o.get('status')
                record['listing_id'] = (o.get('listing') or {}).get('listingId')
                record['listing_status'] = (o.get('listing') or {}).get('listingStatus')
                record['category_id'] = o.get('categoryId')
            else:
                record['offer_status'] = 'NO_OFFER'
        except Exception as ex:
            record['offer_error'] = f'{type(ex).__name__}: {ex}'[:200]
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
        f.flush()
        if (i + 1) % 20 == 0:
            print(f'{i + 1}/{len(all_skus)} done', flush=True)

print('AUDIT COMPLETE', flush=True)
