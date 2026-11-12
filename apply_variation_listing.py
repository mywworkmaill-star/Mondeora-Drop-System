"""Usage: python311 apply_variation_listing.py <pid|all> [--live]   (default = dry-run, read-only)
Per product: identity check -> plan (category/aspects/variants/price/description) -> publish -> verify -> withdraw old."""
import json
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, '.')
from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import categories, publish

live = '--live' in sys.argv
target = sys.argv[1]
extra = {a.split('=', 1)[0]: [a.split('=', 1)[1]] for a in sys.argv[2:] if '=' in a}
ali, ebay = AliExpressAPIClient(), eBayAPIClient()
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row
rows = db.execute('select * from products where is_listed=1 and aliexpress_product_id not like "MANUAL-%" order by id').fetchall()
if target != 'all':
    rows = [r for r in rows if r['aliexpress_product_id'] == target]
done = Path = None
results = []
for row in rows:
    pid = row['aliexpress_product_id']
    if db.execute('select 1 from product_variants where product_id=?', (row['id'],)).fetchone():
        results.append((row['id'], 'SKIP already converted')); continue
    try:
        tok = lambda x: {w for w in categories.clean(x).lower().split() if len(w) > 3}
        out = publish.apply(ali, ebay, pid, row['sku_id'], float(row['shipping_cost'] or 1.99), dry_run=not live,
                            db_title=row['title'], old_listing_id=row['ebay_item_id'], extra_aspects=extra)
        state = out.pop('_state', None)
        if live and state:
            now = datetime.now().isoformat()
            plan = state['plan']
            first = plan['variants'][0]
            db.execute('create table if not exists product_variants (id integer primary key autoincrement, product_id integer, '
                       'sku text unique, ali_sku_id text, aspects text, cost real, price real, qty integer, updated_at text)')
            for v in plan['variants']:
                db.execute('insert or replace into product_variants (product_id, sku, ali_sku_id, aspects, cost, price, qty, updated_at) '
                           'values (?,?,?,?,?,?,?,?)', (row['id'], v['sku'], v['sku_id'], json.dumps(v['aspects'], ensure_ascii=False),
                                                       v['cost'], v['price'], v['qty'], now))
            db.execute('update products set ebay_item_id=?, category_id=?, description=?, ebay_price=?, sku_id=?, aliexpress_price=?, '
                       'title=?, updated_at=? where id=?', (out['new_listing_id'], state['category_id'], state['desc'], first['price'],
                                                           first['sku_id'], first['cost'], out['title'], now, row['id']))
            db.commit()
        results.append((row['id'], 'OK', {k: out.get(k) for k in ('new_listing_id', 'old_listing_id', 'variants', 'price_range', 'min_net', 'category', 'ad', 'new_status')}))
    except Exception as ex:
        results.append((row['id'], 'BLOCKED/FAILED', str(ex)[:400]))
    print(results[-1], flush=True)
print('SUMMARY', sum(1 for r in results if r[1] == 'OK'), 'ok /', len(results))
