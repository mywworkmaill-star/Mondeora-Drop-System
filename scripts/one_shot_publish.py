#!/usr/bin/env python3
"""One-shot: prepare -> sign (using the exact same st, no re-fetch) -> publish,
all in a single process to eliminate the inter-process timing gap that let
live supplier data drift between separately-run prepare/sign/pipeline steps."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.automation.engine import AutamationEngine
from src.listing_quality import ready_workflow, listing_evidence as le
import scripts.sign_listing_evidence as signer
from datetime import datetime, timezone
import sqlite3, json

targets = sys.argv[1:] or ['1005008737280563', '1005011951690557']

e = AutamationEngine()
store = ready_workflow.store_default()
config = ready_workflow.settings()
db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
db.row_factory = sqlite3.Row
rows = [dict(r) for r in db.execute(
    'SELECT * FROM products WHERE aliexpress_product_id IN (%s)' % ','.join('?' * len(targets)), targets)]

print('1) prepare_pool for', len(rows), 'targets')
report = ready_workflow.prepare_pool(e.aliexpress_client, e.ebay_client, rows, store,
    readiness=ready_workflow.read_readiness(), target=config['target'], limit=20,
    ttl_seconds=config['ttl_hours'] * 3600, max_seconds=config['max_prepare_seconds'])
ready_now = [a['product_id'] for a in report['attempted'] if a['status'] == 'ready']
print('   ready now:', ready_now)

if not ready_now:
    print('Nothing became ready - stopping.')
    sys.exit(0)

print('2) sign exactly those, using the artifact.st just built (no re-fetch delay)')
approval = signer._load_standing_approval()
cfg = ready_workflow.settings()
raw_key = __import__('src.runtime', fromlist=['read_config']).read_config().get('LISTING_EVIDENCE_HMAC_KEY')
key = bytes.fromhex(raw_key)
reviewed_by = f"{approval['approved_by']} (standing approval {approval['approved_at']}, signed by tool)"
now = datetime.now(timezone.utc)
manifest_path = ROOT / 'data' / 'listing_evidence' / 'manifest.json'
all_records = json.loads(manifest_path.read_text(encoding='utf-8')).get('records', [])
for pid in ready_now:
    rec = store.get(pid)
    st = rec['artifact']['st']
    new_records = signer.sign_one(pid, st, approval, key, e.aliexpress_client, reviewed_by=reviewed_by, now=now)
    all_records = [r for r in all_records if r.get('scope', {}).get('product_id') != pid] + new_records
manifest_path.write_text(json.dumps({'version': 1, 'records': all_records}, ensure_ascii=False), encoding='utf-8')
print('   signed', len(ready_now), 'products')

print('3) force stale + re-prepare SAME rows again so the stored document_evidence snapshot matches the manifest we just wrote')
for pid in ready_now:
    store.mark(pid, 'stale', {'reason': 'resign_refresh'})
rows2 = [r for r in rows if r['aliexpress_product_id'] in ready_now]
report2 = ready_workflow.prepare_pool(e.aliexpress_client, e.ebay_client, rows2, store,
    readiness=ready_workflow.read_readiness(), target=config['target'], limit=20,
    ttl_seconds=config['ttl_hours'] * 3600, max_seconds=config['max_prepare_seconds'])
ready_final = [a['product_id'] for a in report2['attempted'] if a['status'] == 'ready']
print('   ready after re-prepare:', ready_final)

if not ready_final:
    print('Lost readiness on re-prepare - stopping, no publish attempted.')
    sys.exit(0)

print('4) publish immediately, same process, minimum delay')
out = ready_workflow.release_pool(e.aliexpress_client, e.ebay_client, store,
    readiness=ready_workflow.read_readiness(), target=config['target'],
    daily_limit=config['daily_publish_limit'])
print('RESULT:', json.dumps(out, ensure_ascii=False, indent=1))
