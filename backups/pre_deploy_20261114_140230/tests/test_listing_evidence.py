"""Hypothetical signed-review fixtures only; no production approvals or keys."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import importlib
import importlib.util
import json

import pytest

NOW = datetime(2026, 11, 14, 11, tzinfo=timezone.utc)
KEY = bytes([25]) * 32
PID = '1005001234567'
SKU = '1200001234567'


def module():
    assert importlib.util.find_spec('src.listing_quality.listing_evidence') is not None, 'Scoped reviewed-document adapter must exist'
    return importlib.import_module('src.listing_quality.listing_evidence')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sign(record):
    record['signature'] = hmac.new(KEY, canonical({k: v for k, v in record.items() if k != 'signature'}), hashlib.sha256).hexdigest()
    return record


@pytest.fixture
def reviewed_bundle(tmp_path, monkeypatch):
    from src import runtime
    manifest = tmp_path / 'data/listing_evidence/manifest.json'
    docs = manifest.parent / 'documents'
    docs.mkdir(parents=True)
    document = docs / 'hypothetical-review.txt'
    document.write_text('OFFLINE TEST DOCUMENT; NOT A SUPPLIER OR LEGAL APPROVAL.', encoding='utf-8')
    st = {'title': 'Hypothetical test', 'desc': 'Offline only', 'cat': {'category_id': '12345'},
          'shared': {}, 'imgs': ['https://example.invalid/test.jpg'],
          'res': {'ae_item_base_info_dto': {'product_id': PID}},
          'plan': {'variants': [{'sku_id': SKU, 'cost': 12, 'price': 40, 'qty': 1}]}, 'gates': {}}
    cfg = {'LISTING_EVIDENCE_FILE': 'data/listing_evidence/manifest.json', 'LISTING_EVIDENCE_HMAC_KEY': KEY.hex()}
    monkeypatch.setattr(runtime, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(runtime, 'read_config', lambda: dict(cfg))
    return {'manifest': manifest, 'document': document, 'st': st, 'cfg': cfg}


def save_bundle(f):
    m = module()
    records = []
    for requirement in m.DOCUMENT_REQUIREMENTS:
        record = {'requirement': requirement, 'decision': 'approved', 'reviewed_by': 'offline-test-reviewer',
                  'reviewed_at': NOW.isoformat(), 'expires_at': (NOW + timedelta(hours=12)).isoformat(),
                  'scope': {'product_id': PID, 'sku_ids': [SKU], 'marketplace': 'EBAY_DE', 'currency': 'EUR',
                            'content_sha256': m.scope_digest(PID, f['st'])},
                  'documents': [{'path': 'hypothetical-review.txt', 'sha256': hashlib.sha256(f['document'].read_bytes()).hexdigest()}]}
        records.append(sign(record))
    f['manifest'].write_text(json.dumps({'version': 1, 'records': records}), encoding='utf-8')
    return records


def test_signed_review_requires_scoped_document_and_never_clears_finance_or_demand(reviewed_bundle):
    f = reviewed_bundle
    records = save_bundle(f)
    result = module().verify_product(PID, f['st'], now=NOW)
    assert result['missing_blockers'] == []
    assert set(result['satisfied_blockers']) == set(module().DOCUMENT_REQUIREMENTS.values())
    assert len(result['accepted_requirements']) == 5
    assert 'complete_cost_profit_unverified' not in result['satisfied_blockers']
    assert 'demand_unverified' not in result['satisfied_blockers']
    assert result['basis'] == 'authenticated_scoped_document_review'
    assert KEY.hex() not in json.dumps(result)
    assert 'OFFLINE TEST DOCUMENT' not in json.dumps(result)


@pytest.mark.parametrize('mutation', [
    'no_key', 'bad_signature', 'document_changed', 'expired', 'future', 'wrong_sku',
    'wrong_content', 'duplicate_review', 'missing_document', 'path_escape',
    'self_asserted_boolean', 'rejected_review',
])
def test_untrusted_or_stale_reviews_do_not_clear_blockers(reviewed_bundle, mutation):
    f = reviewed_bundle
    records = save_bundle(f)
    if mutation == 'no_key':
        f['cfg'].pop('LISTING_EVIDENCE_HMAC_KEY')
    elif mutation == 'document_changed':
        f['document'].write_text('Altered hypothetical document', encoding='utf-8')
    elif mutation == 'missing_document':
        f['document'].unlink()
    else:
        for record in records:
            if mutation == 'bad_signature':
                record['signature'] = '0' * 64
            elif mutation == 'expired':
                record['expires_at'] = NOW.isoformat()
                sign(record)
            elif mutation == 'future':
                record['reviewed_at'] = (NOW + timedelta(minutes=1)).isoformat()
                sign(record)
            elif mutation == 'wrong_sku':
                record['scope']['sku_ids'] = ['1200009999999']
                sign(record)
            elif mutation == 'wrong_content':
                record['scope']['content_sha256'] = '0' * 64
                sign(record)
            elif mutation == 'path_escape':
                record['documents'][0]['path'] = '../manifest.json'
                sign(record)
            elif mutation == 'self_asserted_boolean':
                record['verified'] = True
                sign(record)
            elif mutation == 'rejected_review':
                record['decision'] = 'rejected'
                sign(record)
        if mutation == 'duplicate_review':
            records += deepcopy(records)
        f['manifest'].write_text(json.dumps({'version': 1, 'records': records}), encoding='utf-8')
    result = module().verify_product(PID, f['st'], now=NOW)
    assert result['satisfied_blockers'] == []
    assert set(result['missing_blockers']) == set(module().DOCUMENT_REQUIREMENTS.values())


def test_saved_evidence_is_revalidated_instead_of_trusting_cached_success(reviewed_bundle):
    f = reviewed_bundle
    save_bundle(f)
    result = module().verify_product(PID, f['st'], now=NOW)
    artifact = {'st': f['st'], 'document_evidence': result}
    assert module().validate_saved(PID, artifact, now=NOW)['missing_blockers'] == []
    f['document'].write_text('Changed after preparation', encoding='utf-8')
    with pytest.raises(ValueError, match='document_evidence_changed'):
        module().validate_saved(PID, artifact, now=NOW)
