"""Offline safety regressions. Synthetic data is not product approval."""
import json
from unittest.mock import Mock

from src.listing_quality import auto_fix, publish, source, gates

GOOD_TITLE = 'Dokumenten Organizer aus Metall für Büro Schreibtisch Ablage Ordner Papier'


def test_title_generator_uses_its_real_single_argument_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_fix, 'LOG_DIR', tmp_path)
    monkeypatch.setattr(source, 'fetch_raw', lambda *a, **kw: {'ae_item_base_info_dto': {'subject': GOOD_TITLE}})
    calls = []
    def generate(subject):
        calls.append(subject)
        return GOOD_TITLE
    monkeypatch.setattr(publish, 'make_title', generate)
    result = auto_fix.auto_fix_title(Mock(), Mock(), '1005001234567', 'Kurz')
    assert result['success'] is True
    assert calls == [GOOD_TITLE]


def test_sku_alone_never_authorizes_a_live_title_revision(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_fix, 'LOG_DIR', tmp_path)
    monkeypatch.setattr(source, 'fetch_raw', lambda *a, **kw: {'ae_item_base_info_dto': {'subject': GOOD_TITLE}})
    monkeypatch.setattr(publish, 'make_title', lambda *a, **kw: GOOD_TITLE)
    ebay = Mock()
    ebay._request.return_value = {'product': {'title': 'Kurz'}}
    result = auto_fix.auto_fix_title(ebay, Mock(), '1005001234567', 'Kurz', sku='AE-1005001234567-1200001234567')
    assert result['success'] is False
    assert result['api_updated'] is False
    assert not ebay._request.called
    assert result['error'] == 'verified_prepared_revision_required'


def test_aspects_are_source_facts_not_invented_brand_condition_or_part_number(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_fix, 'LOG_DIR', tmp_path)
    monkeypatch.setattr(source, 'fetch_raw', lambda *a, **kw: {})
    monkeypatch.setattr(source, 'properties', lambda raw: [('Material', 'Metall')])
    result = auto_fix.auto_fill_aspects(None, Mock(), '1005001234567', {})
    assert result['new_aspects'] == {'Material': ['Metall']}
    assert result['success'] is False


def test_provider_error_text_never_enters_result_or_log(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_fix, 'LOG_DIR', tmp_path)
    def unavailable(*a, **kw):
        raise RuntimeError('synthetic-provider-secret-do-not-log')
    monkeypatch.setattr(source, 'fetch_raw', unavailable)
    result = auto_fix.auto_fix_title(None, Mock(), '1005001234567', 'Kurz')
    assert result['success'] is False
    assert 'synthetic-provider-secret' not in json.dumps(result)
    assert 'synthetic-provider-secret' not in ''.join(p.read_text(encoding='utf-8') for p in tmp_path.glob('*.jsonl'))


def test_verified_revision_preserves_unrelated_inventory_and_reads_buyer_back(monkeypatch):
    from copy import deepcopy
    from datetime import datetime, timezone
    from src import runtime
    from src.listing_quality import listing_evidence, ready_workflow, ready_plan
    from test_ready_launch import artifact
    saved = artifact()
    saved['config_fingerprint'] = 'hypothetical-current-config'
    monkeypatch.setattr(ready_plan, 'config_fingerprint', lambda: 'hypothetical-current-config')
    saved['st']['title'] = GOOD_TITLE
    sku = saved['st']['plan']['variants'][0]['sku']
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    monkeypatch.setattr(ready_workflow, 'read_readiness', lambda: {
        'ready_for_live': True, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'checks': [{'name': 'scoped_test_prerequisite', 'passed': True}]})
    monkeypatch.setattr(runtime, 'require_writes', lambda: None)  # Fake transport only.
    class Backend:
        def __init__(self):
            self.inv = {'product': {'title': 'Old title', 'description': 'Preserve description'},
                        'condition': 'NEW', 'availability': {'shipToLocationAvailability': {'quantity': 2}}}
            self.calls = []
        def _request(self, method, path, **kwargs):
            self.calls.append((method, path))
            if path.endswith('/offer'):
                return {'offers': [{'sku': sku, 'marketplaceId': 'EBAY_DE', 'status': 'PUBLISHED',
                                    'offerId': '100000', 'listing': {'listingId': '860000000001'}}]}
            if path.startswith('/buy/'):
                return {'title': self.inv['product']['title']}
            if method == 'PUT':
                self.inv = deepcopy(kwargs['json'])
                return {}
            return deepcopy(self.inv)
    backend = Backend()
    out = auto_fix._apply_verified_change(backend, '1005000000000', sku, 'title', GOOD_TITLE, saved)
    assert out == {'api_updated': True, 'verified': True}
    assert backend.inv['product']['description'] == 'Preserve description'
    assert backend.inv['availability']['shipToLocationAvailability']['quantity'] == 2
    assert backend.calls[-1][1].startswith('/buy/browse/')


def test_global_readiness_failure_still_denies_valid_document_review(monkeypatch):
    import pytest
    from src.listing_quality import listing_evidence, ready_workflow
    from test_ready_launch import artifact
    saved = artifact()
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    monkeypatch.setattr(ready_workflow, 'read_readiness', lambda: {})
    ebay = Mock()
    with pytest.raises(ValueError, match='current_readiness_not_verified'):
        auto_fix._apply_verified_change(ebay, '1005000000000', saved['st']['plan']['variants'][0]['sku'],
                                        'title', saved['st']['title'], saved)
    assert not ebay._request.called


def test_revision_rejects_configuration_drift_before_any_api_call(monkeypatch):
    import pytest
    from datetime import datetime, timezone
    from src.listing_quality import listing_evidence, ready_plan, ready_workflow
    from test_ready_launch import artifact
    saved = artifact()
    saved['config_fingerprint'] = 'old-test-config'
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    monkeypatch.setattr(ready_plan, 'config_fingerprint', lambda: 'new-test-config')
    monkeypatch.setattr(ready_workflow, 'read_readiness', lambda: {
        'ready_for_live': True, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'checks': [{'name': 'test_prerequisite', 'passed': True}]})
    ebay = Mock()
    with pytest.raises(ValueError, match='configuration_changed'):
        auto_fix._apply_verified_change(ebay, '1005000000000', saved['st']['plan']['variants'][0]['sku'],
                                        'title', saved['st']['title'], saved)
    assert not ebay._request.called
