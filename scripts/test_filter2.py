#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.listing_quality.ready_plan import build_prepared
from src.readiness import build_report
from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayRESTClient
from src.runtime import read_config
import sqlite3

cfg = read_config()
ali = AliExpressAPIClient(cfg['ALIEXPRESS_APP_KEY'], cfg['ALIEXPRESS_APP_SECRET'])
ali.access_token = cfg['ALIEXPRESS_ACCESS_TOKEN']
ebay = eBayRESTClient(cfg['EBAY_ACCESS_TOKEN'])

db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
db.row_factory = sqlite3.Row
row = db.execute('SELECT * FROM products WHERE aliexpress_product_id = ?', ('1005007115825846',)).fetchone()

readiness = build_report(live=True)
print(f'Readiness TYPE: {type(readiness)}')
print(f'Readiness supervised_trial: {readiness.get("ready_for_supervised_trial")}')
print(f'Readiness live: {readiness.get("ready_for_live")}')

# Test condition
condition = readiness and readiness.get('ready_for_supervised_trial') and not readiness.get('ready_for_live')
print(f'\nCondition TEST: {condition}')

print(f'\nCalling build_prepared()...')
try:
    result = build_prepared(ali, ebay, dict(row), readiness=readiness)
    print(f'\nReturned blockers ({len(result["blockers"])}):')
    for b in result["blockers"][:5]:
        print(f'  - {b}')
        
    if len(result["blockers"]) == 0:
        print(f'\n✅ FILTERING WORKED!')
    else:
        print(f'\n❌ Blockers still present')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
