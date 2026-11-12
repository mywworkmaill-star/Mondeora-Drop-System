"""Usage: python311 recategorize_listing.py <pid> [--live] [--aspect Name=Value ...]"""
import json, sqlite3, sys
sys.path.insert(0, '.')
from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import publish
pid = sys.argv[1]
extra = {a.split('=', 1)[0]: [a.split('=', 1)[1]] for a in sys.argv[2:] if '=' in a}
ship = float(sqlite3.connect('data/dropshipping.db').execute('select shipping_cost from products where aliexpress_product_id=?', (pid,)).fetchone()[0] or 1.99)
print(json.dumps(publish.recategorize(AliExpressAPIClient(), eBayAPIClient(), pid, ship, extra, dry_run='--live' not in sys.argv), ensure_ascii=False, indent=1, default=str))
