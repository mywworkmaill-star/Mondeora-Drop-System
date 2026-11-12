import json
import sqlite3
import sys

sys.path.insert(0, '.')
from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import publish

live = '--live' in sys.argv
only = {a for a in sys.argv[1:] if a.isdigit()}
inplace = '--inplace' in sys.argv
fn = publish.revise_in_place if inplace else publish.recategorize
EXTRA = {'1005006848509888': {'Modell': ['Mini-Handgerät']}}   # user-approved value for the required aspect
ali, ebay = AliExpressAPIClient(), eBayAPIClient()
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row
rows = db.execute("select * from products where is_listed=1 and id in (select distinct product_id from product_variants) order by id").fetchall()
for r in rows:
    if only and str(r['id']) not in only:
        continue
    try:
        o = fn(ali, ebay, r['aliexpress_product_id'], float(r['shipping_cost'] or 1.99), EXTRA.get(r['aliexpress_product_id']), dry_run=not live)
        print(f"#{r['id']} n={o['variants']} prices={sorted(set(o['prices']))[:4]} {'(in place)' if inplace else ''}")
        print('    labels:', [list(l.values()) if isinstance(l, dict) else l for l in o['labels']][:8])
        if o.get('review_flags'):
            print('    review(not blocking, already live):', o['review_flags'])
        if live:
            print('    ->', o.get('new_listing_id'), 'ad', o.get('ad'))
    except Exception as ex:
        print(f"#{r['id']} BLOCKED: {str(ex)[:1500]}")
