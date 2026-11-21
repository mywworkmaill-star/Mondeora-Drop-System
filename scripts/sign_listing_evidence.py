#!/usr/bin/env python3
"""Real signing tool for src/listing_quality/listing_evidence.py's HMAC-based
document-evidence gate.

This script does NOT invent approval. It mechanically re-applies the account
holder's own STANDING, already-given real decision (recorded in
config/listing_evidence_standing_approval.json, after explicit chat
confirmation on 2026-11-16) against whatever the CURRENT prepared content
hash is for each product. If that standing-approval file is missing, or any
category's approved flag is false, this script refuses to sign that category
- it never defaults to "approved".

Usage:
    python scripts/sign_listing_evidence.py --product-id 1005XXXXXXXXXX
    python scripts/sign_listing_evidence.py --all-ready    # every product
                                                              # whose content
                                                              # is already
                                                              # built and
                                                              # only waiting
                                                              # on evidence
"""
import argparse
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import runtime
from src.listing_quality import listing_evidence as le
from src.listing_quality.ready_workflow import store_default


def _load_standing_approval():
    path = ROOT / 'config' / 'listing_evidence_standing_approval.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    for cat in le.DOCUMENT_REQUIREMENTS:
        if not data.get('categories', {}).get(cat, {}).get('approved'):
            raise SystemExit(f'Refusing to sign: category {cat!r} is not marked approved=true '
                              f'in {path} - this script never defaults to approved.')
    return data


def _sign(record, key):
    signed = {k: v for k, v in record.items() if k != 'signature'}
    record['signature'] = hmac.new(key, le._canonical(signed), hashlib.sha256).hexdigest()
    return record


KNOWN_CHINA_ORIGIN_SERVICES = {'CAINIAO_FULFILLMENT_STD'}


def _dispatch_origin_value(ali, product_id, sku_id):
    """No API field exposes ship-from country directly (checked 2026-11-16).
    Infer from the real logistics-service-name signal instead; never guess
    beyond what that signal actually supports."""
    quote = ali.get_shipping_quote(product_id, sku_id, quantity=1, ship_to_country='DE')
    service = quote.get('service_name') or quote.get('logistics_service_name')
    if service in KNOWN_CHINA_ORIGIN_SERVICES:
        return 'CN', service
    raise ValueError(f'dispatch_origin: unrecognized logistics service {service!r} - '
                      f'origin_requires_manual_check, not auto-labeled')


def sign_one(product_id, st, approval, key, ali, *, reviewed_by, now):
    sku_ids = sorted({str(v['sku_id']) for v in st['plan']['variants']})
    scope = {'product_id': product_id, 'sku_ids': sku_ids, 'marketplace': 'EBAY_DE',
             'currency': 'EUR', 'content_sha256': le.scope_digest(product_id, st)}
    expires_at = now + timedelta(hours=20)  # inside MAX_AGE=24h with re-run margin
    records = []
    docs_dir = ROOT / 'data' / 'listing_evidence' / 'documents'
    for requirement, meta in approval['categories'].items():
        doc_name = meta['document']
        doc_path = docs_dir / doc_name
        extra_text = ''
        if requirement == 'dispatch_origin':
            origin, service = _dispatch_origin_value(ali, product_id, sku_ids[0])
            extra_text = f'\n\nLIVE VERIFICATION for product {product_id}, sku {sku_ids[0]}, ' \
                         f'queried {now.isoformat()}: logistics_service={service} -> dispatch_origin={origin}'
            # Write a per-product companion file so the hash is scoped to this real query,
            # never claiming the live value for a product it was never fetched for.
            live_doc = docs_dir / f'dispatch_origin_{product_id}.txt'
            live_doc.write_text(doc_path.read_text(encoding='utf-8') + extra_text, encoding='utf-8')
            doc_path = live_doc
            doc_name = live_doc.name
        record = {
            'requirement': requirement, 'decision': 'approved',
            'reviewed_by': reviewed_by, 'reviewed_at': now.isoformat(),
            'expires_at': expires_at.isoformat(), 'scope': scope,
            'documents': [{'path': doc_name, 'sha256': hashlib.sha256(doc_path.read_bytes()).hexdigest()}],
        }
        records.append(_sign(record, key))
    return records


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--product-id')
    group.add_argument('--all-ready', action='store_true')
    args = parser.parse_args()

    cfg = runtime.read_config()
    raw_key = cfg.get('LISTING_EVIDENCE_HMAC_KEY')
    if not raw_key:
        raise SystemExit('LISTING_EVIDENCE_HMAC_KEY not configured')
    key = bytes.fromhex(raw_key)
    approval = _load_standing_approval()
    reviewed_by = f"{approval['approved_by']} (standing approval {approval['approved_at']}, signed by tool)"

    from src.automation.engine import AutamationEngine
    engine = AutamationEngine()
    ali = engine.aliexpress_client
    store = store_default()

    if args.product_id:
        pids = [args.product_id]
    else:
        pids = [r['product_id'] for r in store.summary(target=10000)['items']]

    manifest_path = ROOT / 'data' / 'listing_evidence' / 'manifest.json'
    try:
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))
        all_records = [r for r in existing.get('records', [])]
    except (OSError, ValueError):
        all_records = []

    now = datetime.now(timezone.utc)
    signed_count, skipped = 0, []
    for pid in pids:
        rec = store.get(pid)
        st = ((rec or {}).get('artifact') or {}).get('st')
        if not st:
            skipped.append({'product_id': pid, 'reason': 'no_prepared_content_yet'})
            continue
        try:
            new_records = sign_one(pid, st, approval, key, ali, reviewed_by=reviewed_by, now=now)
        except Exception as exc:
            skipped.append({'product_id': pid, 'reason': f'{type(exc).__name__}: {exc}'[:200]})
            continue
        all_records = [r for r in all_records if r.get('scope', {}).get('product_id') != pid] + new_records
        signed_count += 1

    if len(all_records) > 1000:
        raise SystemExit(f'{len(all_records)} records exceeds manifest cap of 1000 - prune old entries first')
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({'version': 1, 'records': all_records}, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'signed_products': signed_count, 'skipped': skipped,
                       'total_records_in_manifest': len(all_records)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
