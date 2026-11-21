"""Scoped document ingestion into a real builder contract, all data hypothetical."""
from datetime import timedelta
import hashlib
import json

from test_ready_plan import hypothetical_listing, NOW, report
from test_listing_evidence import KEY, sign


def test_builder_consumes_reviewed_documents_without_waiving_other_gates(hypothetical_listing, tmp_path):
    f = hypothetical_listing
    from src.listing_quality import listing_evidence
    first = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    st = first['artifact']['st']
    directory = tmp_path / 'data/listing_evidence'
    (directory / 'documents').mkdir(parents=True)
    document = directory / 'documents/test-review.txt'
    document.write_text('HYPOTHETICAL OFFLINE DOCUMENT ONLY', encoding='utf-8')
    scope = {'product_id': f['pid'], 'sku_ids': sorted(f['skus']), 'marketplace': 'EBAY_DE', 'currency': 'EUR',
             'content_sha256': listing_evidence.scope_digest(f['pid'], st)}
    records = [sign({'requirement': requirement, 'decision': 'approved', 'reviewed_by': 'test-only',
                     'reviewed_at': NOW.isoformat(), 'expires_at': (NOW + timedelta(hours=1)).isoformat(),
                     'scope': scope, 'documents': [{'path': document.name,
                        'sha256': hashlib.sha256(document.read_bytes()).hexdigest()}]})
               for requirement in listing_evidence.DOCUMENT_REQUIREMENTS]
    (directory / 'manifest.json').write_text(json.dumps({'version': 1, 'records': records}), encoding='utf-8')
    f['cfg'].update(LISTING_EVIDENCE_HMAC_KEY=KEY.hex(), LISTING_EVIDENCE_FILE='data/listing_evidence/manifest.json')
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert result['artifact']['document_evidence']['missing_blockers'] == []
    assert not set(listing_evidence.DOCUMENT_REQUIREMENTS.values()).intersection(result['blockers'])
    assert {'demand_unverified', 'complete_cost_profit_unverified', 'freight_estimate_only'} <= set(result['blockers'])
    assert any(b.startswith('quality_') for b in result['blockers'])


def test_publication_refuses_missing_document_evidence_before_any_api_call():
    import pytest
    from src.listing_quality import ready_launch
    from test_ready_launch import artifact, FakeApi
    saved = artifact()
    saved['payloads'] = ready_launch.compile_payloads('1005000000000', saved)
    api = FakeApi()
    with pytest.raises(ValueError, match='document_evidence'):
        ready_launch.execute(None, '1005000000000', saved, api=api)
    assert api.calls == []


def test_freshness_refuses_missing_document_evidence_before_supplier_reads():
    import pytest
    from src.listing_quality import ready_launch
    from test_ready_launch import artifact
    class NoReads:
        def _request(self, *args, **kwargs):
            raise AssertionError('Unnecessary supplier read before evidence gate')
    with pytest.raises(ValueError, match='document_evidence'):
        ready_launch.validate_fresh(NoReads(), '1005000000000', artifact())
