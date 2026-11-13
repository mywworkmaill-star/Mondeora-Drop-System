"""Offline buffer workflow tests; fixtures are not real product evidence."""
from datetime import datetime, timezone
from src.listing_quality.ready_store import ReadyStore
from test_ready_launch import artifact


def test_preparation_counts_passed_plans_not_candidates(tmp_path):
    from src.listing_quality.ready_workflow import prepare_pool
    store = ReadyStore(tmp_path / 'ready.sqlite')
    rows = [{'aliexpress_product_id': str(1005000000000 + n)} for n in range(5)]
    calls = []
    def builder(ali, ebay, row, **kwargs):
        pid = row['aliexpress_product_id']
        calls.append(pid)
        a = artifact()
        a['config_fingerprint'] = 'test'
        a['st']['plan']['variants'][0]['sku'] = 'AE-' + pid + '-2000000000001'
        return {'product_id': pid, 'artifact': a, 'blockers': ['category_review'] if len(calls) == 1 else []}
    result = prepare_pool(None, None, rows, store, readiness={}, target=2, limit=5,
                          builder=builder, fingerprint='test')
    assert result['ready_count'] == 2
    assert result['shortfall'] == 0
    assert result['blocked_count'] == 1
    assert len(calls) == 3
    assert all(row['artifact'].get('payloads') for row in store.ready())


def test_release_requires_ten_fresh_ready_products_before_sending(tmp_path):
    from src.listing_quality.ready_workflow import release_pool
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put('1005000000000', artifact())
    calls = []
    result = release_pool(None, None, store, readiness={}, target=10,
        sender=lambda *a, **k: calls.append('write'), fingerprint='test')
    assert result['published_count'] == 0
    assert result['status'] == 'blocked'
    assert calls == []
    assert store.get('1005000000000')['status'] == 'ready'


def test_release_never_retries_ambiguous_side_effect(tmp_path):
    from src.listing_quality.ready_workflow import release_pool
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = artifact()
    a['config_fingerprint'] = 'test'
    store.put('1005000000000', a)
    calls = []
    def sender(*args, **kwargs):
        calls.append('write')
        raise TimeoutError('test only')
    now = datetime.now(timezone.utc)
    readiness = {'ready_for_live': True, 'generated_at': now.isoformat(),
                 'checks': [{'name': 'listing', 'passed': True}]}
    result = release_pool(None, None, store, readiness=readiness, target=1, fingerprint='test',
        freshness=lambda *a: None, sender=sender, buyer_check=lambda *a: None, persist=lambda *a: None)
    assert result['published_count'] == 0
    assert store.get('1005000000000')['status'] == 'needs_reconciliation'
    release_pool(None, None, store, readiness=readiness, target=1, fingerprint='test',
        freshness=lambda *a: None, sender=sender)
    assert calls == ['write']


def test_status_does_not_count_empty_blocked_artifacts_as_prepared(tmp_path):
    from src.listing_quality.ready_workflow import buffer_status
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put('1005000000000', {}, blockers=['missing_content'])
    result = buffer_status(store=store, readiness={})
    assert result['content_prepared_count'] == 0
    assert result['ready_count'] == 0
