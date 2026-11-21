"""Offline contract tests: the audit may write its own JSON, never its sources."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
import sqlite3
import pytest
from urllib.parse import unquote

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def module():
    return importlib.import_module('src.listing_quality.standards')


def aspect(name, *, required=False, values=None, variations=False):
    return {'localizedAspectName': name, 'aspectConstraint': {
        'aspectRequired': required, 'aspectMode': 'SELECTION_ONLY' if values is not None else 'FREE_TEXT',
        'aspectEnabledForVariations': variations},
        'aspectValues': [{'localizedValue': value} for value in (values or [])]}


class Ebay:
    def __init__(self, skus=('shop/one', 'free-form SKU?2')):
        self.items = {sku: {'sku': sku, 'product': {'aspects': {'Produktart': ['Box']}}} for sku in skus}
        self.offers = {sku: [{'offerId': 'offer-' + str(i), 'categoryId': '123',
                              'listing': {'listingId': 'listing-' + str(i), 'listingStatus': 'ACTIVE'}}]
                       for i, sku in enumerate(skus)}
        self.metadata = {'123': [aspect('Produktart', required=True, values=['Box'])]}
        self.names = {'123': 'Aufbewahrungsboxen'}
        self.calls = []
        self.fail = {}
        self.page_size = 1

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, deepcopy(kwargs)))
        assert method == 'GET', 'Audit attempted a non-GET request'
        params = kwargs.get('params', {})
        for (stage, target), error in self.fail.items():
            if ((stage == 'offer' and path.endswith('/offer') and params.get('sku') == target)
                    or (stage == 'item' and path.endswith('/inventory_item/' + target))
                    or (stage == 'metadata' and path.endswith('/get_item_aspects_for_category'))
                    or (stage == 'snapshot' and path.endswith('/inventory_item'))):
                raise error
        if path.endswith('/inventory_item'):
            offset = params.get('offset', 0)
            items = list(self.items.values())
            return {'inventoryItems': deepcopy(items[offset:offset + self.page_size]), 'total': len(items)}
        if '/inventory_item/' in path:
            return deepcopy(self.items[unquote(path.rsplit('/', 1)[-1])])
        if path.endswith('/offer'):
            offers = self.offers.get(params['sku'], [])
            offset = params.get('offset', 0)
            return {'offers': deepcopy(offers[offset:offset + self.page_size]), 'total': len(offers)}
        if path.endswith('/get_item_aspects_for_category'):
            return {'aspects': deepcopy(self.metadata[params['category_id']])}
        if path.endswith('/get_category_subtree'):
            return {'categorySubtreeNode': {'category': {'categoryName': self.names[params['category_id']]}}}
        raise AssertionError('Unexpected GET')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def report(root):
    return read(root / 'data/audit/listing_standards_report.json')


def tasks(root):
    return read(root / 'data/audit/listing_review_queue.json')['tasks']


def test_paginated_snapshot_resumes_bounded_catalog_and_refreshes_next_cycle(tmp_path):
    api = Ebay()
    run = module().run_cycle
    first = run(api, tmp_path, max_items=1, now=NOW)
    assert first['status'] == 'partial'
    assert first['processed_this_run'] == 1
    assert first['catalog_total'] == 2
    assert first['processed_count'] == 1
    assert not first['complete']
    first_id = first['cycle_id']
    second = run(api, tmp_path, max_items=1, now=NOW)
    assert second['complete']
    assert second['processed_count'] == 2
    assert second['cycle_id'] == first_id
    assert second['status'] == 'action_required'
    assert len([c for c in api.calls if c[1].endswith('/inventory_item')]) == 4
    assert len([c for c in api.calls if c[1].endswith('/get_item_aspects_for_category')]) == 1
    third = run(api, tmp_path, max_items=1, now=NOW)
    assert third['cycle_id'] != first_id
    assert len([c for c in api.calls if c[1].endswith('/get_item_aspects_for_category')]) == 2
    assert all(c[0] == 'GET' for c in api.calls)
    json.dumps(third, allow_nan=False)
    assert {item['sku'] for item in report(tmp_path)['items']} <= set(api.items)


def test_exact_taxonomy_fields_empty_values_picklists_and_local_quality_target(tmp_path):
    api = Ebay(('sku-A',))
    api.metadata['123'] = [aspect('Produktart', required=True, values=['Box']),
                           aspect('Laenge', required=True), aspect('Material', values=['Holz']),
                           aspect('Farbe'), aspect('Hersteller')]
    api.items['sku-A']['product']['aspects'] = {
        'Produktart': ['Aufbewahrungsboxen'], 'Länge': ['20 cm'], 'Material': ['Plastik'],
        'Farbe': [' '], 'Hersteller': [], 'fake one': ['value'], 'fake two': ['value'],
        'fake three': ['value'], 'fake four': ['value'], 'fake five': ['value'], 'fake six': ['value']}
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['complete'] and out['status'] == 'action_required'
    row = report(tmp_path)['items'][0]
    findings = {(t['field'], t['code']) for t in tasks(tmp_path)}
    assert ('Laenge', 'missing_required_aspect') in findings
    assert ('Farbe', 'empty_optional_aspect') in findings
    assert ('Hersteller', 'empty_optional_aspect') in findings
    assert ('Produktart', 'category_name_leaked_into_aspect') in findings
    assert ('Produktart', 'closed_picklist_invalid') in findings
    assert ('Material', 'closed_picklist_invalid') in findings
    assert ('Länge', 'aspect_not_in_category_vocabulary') in findings
    assert row['checks']['aspect_count']['valid_count'] == 0
    assert row['checks']['required_aspects']['status'] == 'action_required'
    assert row['checks']['optional_aspects']['status'] == 'action_required'
    assert row['checks']['optional_aspects']['total_fields'] == 3


def test_no_offer_and_inactive_are_not_read_failures(tmp_path):
    api = Ebay(('unpublished', 'ended'))
    api.offers['unpublished'] = []
    api.offers['ended'][0]['listing']['listingStatus'] = 'ENDED'
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['complete'] and out['fetch_error_count'] == 0
    rows = {r['sku']: r for r in report(tmp_path)['items']}
    assert rows['unpublished']['checks']['offer']['state'] == 'no_offer'
    assert rows['ended']['checks']['offer']['state'] == 'inactive'
    assert rows['ended']['checks']['required_aspects']['status'] == 'not_applicable'


@pytest.mark.parametrize('stage', ['item', 'offer', 'metadata', 'snapshot'])
def test_read_errors_are_partial_safe_and_queued(tmp_path, stage):
    api = Ebay(('bad', 'good'))
    api.fail[(stage, 'bad')] = RuntimeError('SECRET token=do-not-store buyer@example.org')
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['status'] == 'partial' and not out['complete']
    assert out['fetch_error_count'] > 0
    if stage in ('item', 'offer', 'metadata'):
        assert next(r for r in report(tmp_path)['items'] if r['sku'] == 'bad')['checks']['category_consistency']['status'] == 'not_verified'
    assert any(t['code'] == 'read_failed' for t in tasks(tmp_path))
    text = ''.join(p.read_text(encoding='utf-8') for p in tmp_path.rglob('*.json'))
    assert 'SECRET' not in text and 'buyer@example.org' not in text
    assert 'RuntimeError' in text
    assert out['processed_skus'] == out['processed_count']
    assert out['total_skus'] == out['catalog_total']
    assert out['open_reviews'] == out['unresolved_count']


def test_review_queue_survives_batches_failure_and_only_resolves_exact_reread(tmp_path):
    api = Ebay(('one', 'two'))
    api.metadata['123'].append(aspect('Material', required=True))
    api.items['one']['product']['aspects']['Material'] = []
    run = module().run_cycle
    run(api, tmp_path, max_items=1, now=NOW)
    original = next(t for t in tasks(tmp_path) if t['sku'] == 'one' and t['field'] == 'Material')
    run(api, tmp_path, max_items=1, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == original['key'])['status'] == 'unresolved'
    api.items['one']['product']['aspects']['Material'] = ['Holz']
    api.fail[('offer', 'one')] = TimeoutError('secret')
    run(api, tmp_path, max_items=1, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == original['key'])['status'] == 'unresolved'
    api.fail.clear()
    run(api, tmp_path, max_items=2, now=NOW)
    resolved = next(t for t in tasks(tmp_path) if t['key'] == original['key'])
    assert resolved['status'] == 'resolved'
    assert resolved['first_seen'] == original['first_seen']
    assert resolved['resolution_basis'] == 'full_exact_target_read'


def test_atomic_checkpoint_preserves_prior_batch_after_interrupted_replace(tmp_path, monkeypatch):
    api = Ebay(('one', 'two', 'three'))
    mod = module()
    mod.run_cycle(api, tmp_path, max_items=1, now=NOW)
    path = tmp_path / 'data/jobs/listing_standards_state.json'
    before = read(path)
    real_replace = mod.os.replace

    def interrupt(source, destination):
        if destination == path:
            raise OSError('interrupted')
        return real_replace(source, destination)

    with monkeypatch.context() as scoped:
        scoped.setattr(mod.os, 'replace', interrupt)
        with pytest.raises(OSError):
            mod.run_cycle(api, tmp_path, max_items=1, now=NOW)
    assert read(path) == before
    out = mod.run_cycle(api, tmp_path, max_items=1, now=NOW)
    assert out['processed_count'] == 2 and out['cycle_id'] == before['cycle_id']
    assert not list(path.parent.glob('.listing_standards_state.json-*'))


def local_json(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')
    return path


def test_recurring_checklist_uses_exact_readonly_local_mapping_not_sku_parsing(tmp_path):
    api = Ebay(('arbitrary/red/one',))
    sku = next(iter(api.items))
    api.items[sku]['product']['aspects']['Farbe'] = ['Rot']
    api.metadata['123'].append(aspect('Farbe', variations=True))
    config = local_json(tmp_path, 'config/category_overrides.json', {
        '_comment': 'blocked metadata note is NOT a block',
        '1005000000001': {'category_id': '123', 'note': 'historically blocked but reviewed'}})
    labels = local_json(tmp_path, 'config/verified_variant_labels.json', {
        '_blocked_needs_code_change': {'_note': 'all notes must stay notes'},
        '1005000000001': {'_photo_note': 'blocked note is not a SKU', '1200000000001': {'Farbe': 'Rot'}}})
    db_path = tmp_path / 'data/dropshipping.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute('CREATE TABLE products (id INTEGER, aliexpress_product_id TEXT, ebay_item_id TEXT, extra TEXT)')
        db.execute('INSERT INTO products VALUES (7, ?, ?, ?)', ('1005000000001', 'listing-0', 'PRIVATE'))
        db.execute('CREATE TABLE product_variants (product_id INTEGER, sku TEXT, ali_sku_id TEXT)')
        db.execute('INSERT INTO product_variants VALUES (7, ?, ?)', (sku, '1200000000001'))
    ready_path = tmp_path / 'data/listing_ready.sqlite'
    with sqlite3.connect(ready_path) as db:
        db.execute('CREATE TABLE ready_listings (product_id TEXT, status TEXT, expires_at TEXT, blockers TEXT, side_effect_started INTEGER)')
        db.execute('INSERT INTO ready_listings VALUES (?, ?, ?, ?, ?)', ('1005000000001', 'ready', '2026-11-16T12:00:00+00:00', '[]', 0))
    lock = tmp_path / 'data/ready_release.lock'
    lock.write_text('do-not-touch', encoding='utf-8')
    original = {p: p.read_bytes() for p in (config, labels, db_path, ready_path, lock)}
    out = module().run_cycle(api, tmp_path, now=NOW)
    checks = report(tmp_path)['items'][0]['checks']
    assert checks['category_decisions']['status'] == 'verified'
    assert checks['variant_labels']['status'] == 'verified'
    assert checks['competitor_research']['status'] == 'not_verified'
    assert checks['buyer_verification']['status'] == 'not_verified'
    assert checks['dimensions_units']['status'] == 'not_verified'
    assert checks['origin_manufacturer']['status'] == 'not_verified'
    checklist = report(tmp_path)['checklist']
    assert checklist['buffer']['candidate_ready_count'] == 1
    assert checklist['buffer']['status'] == 'not_verified'  # count isn't full gate validation
    assert checklist['safe_maintenance']['status'] == 'verified'
    assert out['complete']
    assert all(p.read_bytes() == data for p, data in original.items())
    assert any(t['sku'] == sku and t['code'] == 'competitor_research_needed' for t in tasks(tmp_path))
    assert not any(t['code'] == 'category_blocked' for t in tasks(tmp_path))
    assert 'PRIVATE' not in json.dumps(report(tmp_path))


@pytest.mark.parametrize('suppliers, expected', [
    ([{'ali_sku_id': '0012000000001'}], '0012000000001'),
    ([{'ali_sku_id': '0012000000001', 'sku_id': '0012000000001'}], '0012000000001'),
    ([{'sku_id': '0012000000001'}], '0012000000001'),
    ([{'ali_sku_id': '0012000000001', 'sku_id': '1200000000002'}], None),
    ([{'ali_sku_id': '0012000000001'}, {'ali_sku_id': '1200000000002'}], None),
    ([{'ali_sku_id': ' 0012000000001'}], None),
    ([{'ali_sku_id': '１２３４５６'}], None),
    ([{'ali_sku_id': 1200000000001}], None),
    ([{'ali_sku_id': '0012000000001', 'sku_id': 'legacy-display'}], None),
])
def test_supplier_mapping_preserves_numeric_strings_and_rejects_ambiguity(suppliers, expected):
    sources = {'products': [{'id': 7, 'aliexpress_product_id': '0010050000001', 'ebay_item_id': 'listing'}],
               'product_variants': [{'product_id': 7, 'sku': 'exact', **v} for v in suppliers]}
    row = {'sku': 'exact', 'offers': [{'listing_id': 'listing'}]}
    assert module()._mapping(row, sources) == ('0010050000001', expected)
    sources['products'].append({'id': 8, 'aliexpress_product_id': '1005000000002', 'ebay_item_id': 'listing'})
    assert module()._mapping(row, sources) == (None, None)
    sources['products'] = [{'id': 7, 'aliexpress_product_id': ' 0010050000001', 'ebay_item_id': 'listing'}]
    assert module()._mapping(row, sources) == (None, None)


def test_unmapped_display_sku_never_becomes_a_supplier_identity(tmp_path):
    api = Ebay(('AE-not-a-supplier-123abc',))
    local_json(tmp_path, 'config/category_overrides.json', {'123': {'blocked': True}})
    module().run_cycle(api, tmp_path, now=NOW)
    row = report(tmp_path)['items'][0]
    assert row['product_id'] is None
    assert row['checks']['category_decisions']['status'] == 'not_verified'
    assert all(t['product_id'] is None for t in tasks(tmp_path) if t['sku'] == row['sku'])
    assert not any(t['code'] in ('malformed_supplier_id', 'category_blocked') for t in tasks(tmp_path))


def test_local_source_read_failure_is_partial_without_disclosing_parser_input(tmp_path):
    path = tmp_path / 'config/category_overrides.json'
    path.parent.mkdir(parents=True)
    path.write_text('{SECRET', encoding='utf-8')
    out = module().run_cycle(Ebay(('one',)), tmp_path, now=NOW)
    assert out['status'] == 'partial' and not out['complete']
    assert any(e['stage'] == 'category_overrides' for e in report(tmp_path)['errors'])
    assert 'SECRET' not in json.dumps(report(tmp_path))


def test_group_category_inconsistency_detected_across_batches_and_resolved_full_cycle(tmp_path):
    api = Ebay(('one', 'two'))
    api.offers['two'][0]['listing']['listingId'] = 'listing-0'
    api.offers['two'][0]['categoryId'] = '456'
    api.metadata['456'] = deepcopy(api.metadata['123'])
    api.names['456'] = 'Anderes'
    run = module().run_cycle
    run(api, tmp_path, max_items=1, now=NOW)
    out = run(api, tmp_path, max_items=1, now=NOW)
    assert out['complete']
    bad = [t for t in tasks(tmp_path) if t['code'] == 'category_inconsistent_across_group']
    assert {t['sku'] for t in bad} == {'one', 'two'}
    api.offers['two'][0]['categoryId'] = '123'
    run(api, tmp_path, max_items=1, now=NOW)
    assert all(t['status'] == 'unresolved' for t in tasks(tmp_path) if t['key'] in {b['key'] for b in bad})
    run(api, tmp_path, max_items=1, now=NOW)
    assert all(t['status'] == 'resolved' for t in tasks(tmp_path) if t['key'] in {b['key'] for b in bad})


def test_model_quantity_collision_never_collapses_real_sibling_skus(tmp_path):
    api = Ebay(('one', 'two'))
    api.offers['two'][0]['listing']['listingId'] = 'listing-0'
    api.metadata['123'] += [aspect('Farbe', variations=True), aspect('Anzahl der Einheiten')]
    for sku, quantity in [('one', '5'), ('two', '10')]:
        api.items[sku]['product']['aspects'].update({'Farbe': ['Transparent'], 'Anzahl der Einheiten': [quantity]})
    original = deepcopy(api.items)
    module().run_cycle(api, tmp_path, now=NOW)
    assert {t['sku'] for t in tasks(tmp_path) if t['code'] == 'variant_axis_model_quantity_collision'} == {'one', 'two'}
    assert api.items == original
    assert len(report(tmp_path)['items']) == 2


def test_fresh_inventory_drift_reconciles_catalog_in_progress(tmp_path):
    api = Ebay(('one', 'two'))
    run = module().run_cycle
    first = run(api, tmp_path, max_items=1, now=NOW)
    api.items['new sku'] = {'sku': 'new sku', 'product': {'aspects': {}}}
    second = run(api, tmp_path, max_items=1, now=NOW)
    assert second['cycle_id'] == first['cycle_id']
    assert second['catalog_total'] == 3
    assert second['fresh_inventory_total'] == 3
    assert report(tmp_path)['checklist']['inventory_drift']['status'] == 'action_required'
    assert any(t['sku'] == 'new sku' and t['code'] == 'inventory_added_during_cycle' for t in tasks(tmp_path))
    third = run(api, tmp_path, max_items=20, now=NOW)
    assert third['complete'] and third['cycle_id'] == first['cycle_id']


def test_removed_before_turn_and_new_skus_never_starve_across_ticks(tmp_path):
    api = Ebay(('first', 'disappears', 'failed'))
    run = module().run_cycle
    first = run(api, tmp_path, max_items=1, now=NOW)
    original = {t['key'] for t in tasks(tmp_path) if t['sku'] == 'first'}
    del api.items['disappears']  # Never fetched individually, not a verified read.
    api.fail[('item', 'failed')] = TimeoutError('private')
    api.items['new-one'] = {'sku': 'new-one', 'product': {'aspects': {}}}
    second = run(api, tmp_path, max_items=1, now=NOW)
    assert second['cycle_id'] == first['cycle_id'] and not second['complete']
    assert second['removed_count'] == 1
    state = read(tmp_path / 'data/jobs/listing_standards_state.json')
    assert state['removals']['disappears']['read_complete'] is False
    assert state['removals']['disappears']['basis'] == 'full_inventory_snapshot'
    assert 'disappears' not in state['catalog']
    api.items['new-two'] = {'sku': 'new-two', 'product': {'aspects': {}}}
    for _ in range(3):
        out = run(api, tmp_path, max_items=1, now=NOW)
        assert out['processed_this_run'] <= 1
        assert out['requests_used'] <= out['request_limit']
    rows = {r['sku']: r for r in report(tmp_path)['items']}
    assert rows['new-one']['read_complete'] and rows['new-two']['read_complete']
    assert not out['complete'] and out['verified_count'] == 3 and out['remaining_count'] == 1
    assert not any(c[1].endswith('/inventory_item/disappears') for c in api.calls)
    assert all(t['status'] == 'unresolved' for t in tasks(tmp_path) if t['key'] in original)
    assert any(t['sku'] == 'disappears' and t['code'] == 'inventory_missing_during_cycle'
               and t['status'] == 'unresolved' for t in tasks(tmp_path))
    api.fail.clear()
    final = run(api, tmp_path, max_items=1, now=NOW)
    assert final['complete'] and final['catalog_total'] == final['verified_count'] == 4
    assert final['removed_count'] == 1


def test_inventory_content_drift_requeues_already_read_exact_target(tmp_path):
    api = Ebay(('one', 'two'))
    run = module().run_cycle
    run(api, tmp_path, max_items=1, now=NOW)
    api.items['one']['product']['aspects']['Produktart'] = ['Bad value']
    out = run(api, tmp_path, max_items=2, now=NOW)
    assert out['processed_this_run'] == 2
    assert any(t['sku'] == 'one' and t['code'] == 'closed_picklist_invalid' for t in tasks(tmp_path))


def test_production_client_never_refreshes_or_logs_response_on_401(tmp_path, capsys):
    from src.api.ebay_client import eBayAPIClient

    class Response:
        status_code = 401

        @property
        def text(self):
            raise AssertionError('Response body must never be read')

    class Session:
        def __init__(self):
            self.calls = []

        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return Response()

    session = Session()
    api = eBayAPIClient(session=session, env_path=tmp_path / 'missing.env', config={'EBAY_ACCESS_TOKEN': 'test-token'})
    out = module().run_cycle(api, tmp_path, now=NOW, max_seconds=1)
    assert out['status'] == 'partial' and not out['complete']
    assert len(session.calls) == 1 and session.calls[0][0] == 'GET'
    assert session.calls[0][2]['allow_redirects'] is False
    assert 0 < session.calls[0][2]['timeout'] <= 1
    assert capsys.readouterr().out == ''
    assert not (tmp_path / '.env').exists()


def test_time_and_request_limits_leave_partial_without_starting_more_reads(tmp_path, monkeypatch):
    mod = module()
    api = Ebay(('one',))
    zero = mod.run_cycle(api, tmp_path, now=NOW, max_seconds=0)
    assert zero['status'] == 'partial' and zero['requests_used'] == 0 and not api.calls
    assert zero['fetch_error_count'] == 0 and zero['budget_exhausted'] is True
    assert report(tmp_path)['errors'] == []
    assert report(tmp_path)['budget_stops']
    large = Ebay(tuple('sku-' + str(i) for i in range(1000)))
    limited = mod.run_cycle(large, tmp_path, now=NOW, max_items=1)
    assert limited['status'] == 'partial' and limited['requests_used'] <= limited['request_limit']
    assert limited['processed_this_run'] == 0
    clock = [0.0]
    original = api._request

    def slow(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if '/inventory_item/' in path:
            clock[0] += 2
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(mod.time, 'monotonic', lambda: clock[0])
        scoped.setattr(api, '_request', slow)
        result = mod.run_cycle(api, tmp_path, now=NOW, max_seconds=1)
    assert not result['complete'] and result['requests_used'] == 2
    assert report(tmp_path)['items'][0]['checks']['required_aspects']['status'] == 'not_verified'


@pytest.mark.parametrize('kind', ['missing-offers', 'unknown-offer-status', 'duplicate-page', 'short-page'])
def test_malformed_reads_never_turn_into_inactive_or_complete(tmp_path, kind):
    api = Ebay(('one', 'two'))
    original = api._request

    def malformed(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.endswith('/offer'):
            if kind == 'missing-offers':
                return {'total': 1}
            if kind == 'unknown-offer-status':
                return {'offers': [{'offerId': 'bad'}], 'total': 1}
        if path.endswith('/inventory_item') and kwargs['params']['offset']:
            if kind == 'duplicate-page':
                return {'inventoryItems': [api.items['one']], 'total': 2}
            if kind == 'short-page':
                return {'inventoryItems': [], 'total': 2}
        return result

    api._request = malformed
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['status'] == 'partial' and not out['complete'] and out['fetch_error_count'] > 0


def test_corrupt_checkpoint_is_fail_closed_and_preserves_queue(tmp_path):
    api = Ebay(('one',))
    mod = module()
    mod.run_cycle(api, tmp_path, now=NOW)
    queue = (tmp_path / 'data/audit/listing_review_queue.json').read_bytes()
    path = tmp_path / 'data/jobs/listing_standards_state.json'
    path.write_text('{SECRET', encoding='utf-8')
    api.calls.clear()
    out = mod.run_cycle(api, tmp_path, now=NOW)
    assert not out['complete'] and out['status'] == 'partial'
    assert out['fetch_error_count'] == 1
    assert (tmp_path / 'data/audit/listing_review_queue.json').read_bytes() == queue
    assert path.read_text(encoding='utf-8') == '{SECRET'
    assert 'SECRET' not in json.dumps(report(tmp_path))


def test_metadata_failure_has_all_check_statuses_and_not_empty_success_cache(tmp_path):
    api = Ebay(('one',))
    api.fail[('metadata', 'one')] = RuntimeError('secret')
    run = module().run_cycle
    run(api, tmp_path, now=NOW)
    row = report(tmp_path)['items'][0]
    assert row['checks']['required_aspects']['status'] == 'not_verified'
    assert row['checks']['optional_aspects']['status'] == 'not_verified'
    state = read(tmp_path / 'data/jobs/listing_standards_state.json')
    assert state['category_cache'] == {}
    api.fail.clear()
    assert run(api, tmp_path, now=NOW)['complete']


def test_optional_absence_is_review_only_and_never_fabricated(tmp_path):
    api = Ebay(('one',))
    api.metadata['123'].append(aspect('Herstellungsland'))
    before = deepcopy(api.items)
    module().run_cycle(api, tmp_path, now=NOW)
    assert api.items == before
    assert any(t['field'] == 'Herstellungsland' and t['code'] == 'missing_optional_aspect' for t in tasks(tmp_path))
    assert report(tmp_path)['checklist']['optional_aspects']['status'] == 'action_required'
    assert any(t['code'] == 'buffer_verification_needed' for t in tasks(tmp_path))


def test_lost_checkpoint_keeps_durable_unresolved_reviews(tmp_path):
    api = Ebay(('one',))
    mod = module()
    mod.run_cycle(api, tmp_path, now=NOW)
    previous = {t['key'] for t in tasks(tmp_path)}
    (tmp_path / 'data/jobs/listing_standards_state.json').unlink()
    api.items.clear()
    mod.run_cycle(api, tmp_path, now=NOW)
    assert previous <= {t['key'] for t in tasks(tmp_path)}


def test_keyboard_interrupt_commits_finished_targets_not_incomplete_target(tmp_path):
    api = Ebay(('one', 'two', 'three'))
    original = api._request

    def interrupted(method, path, **kwargs):
        if path.endswith('/inventory_item/two'):
            raise KeyboardInterrupt()
        return original(method, path, **kwargs)

    api._request = interrupted
    with pytest.raises(KeyboardInterrupt):
        module().run_cycle(api, tmp_path, max_items=2, now=NOW)
    state = read(tmp_path / 'data/jobs/listing_standards_state.json')
    assert set(state['records']) == {'one'}
    api._request = original
    out = module().run_cycle(api, tmp_path, max_items=1, now=NOW)
    assert out['processed_count'] == 2


def test_aspect_review_does_not_resolve_when_display_sku_changes_product(tmp_path):
    api = Ebay(('one',))
    api.metadata['123'].append(aspect('Material', required=True))
    path = tmp_path / 'data/dropshipping.db'
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE products (aliexpress_product_id TEXT, ebay_item_id TEXT)')
        db.execute('INSERT INTO products VALUES (?, ?)', ('1005000000001', 'listing-0'))
    run = module().run_cycle
    run(api, tmp_path, now=NOW)
    old = next(t for t in tasks(tmp_path) if t['field'] == 'Material')
    with sqlite3.connect(path) as db:
        db.execute('UPDATE products SET aliexpress_product_id = ?', ('1005000000002',))
    api.items['one']['product']['aspects']['Material'] = ['Holz']
    run(api, tmp_path, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == old['key'])['status'] == 'unresolved'


@pytest.mark.parametrize('code', ['category_decision_needed', 'category_decision_drift', 'category_blocked',
                                 'variant_label_evidence_needed', 'variant_label_mismatch'])
def test_reviewed_category_and_labels_resolve_only_after_exact_verified_correction(tmp_path, code):
    api = Ebay(('one',))
    pid, supplier = '1005000000001', '1200000000001'
    path = tmp_path / 'data/dropshipping.db'
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE products (id INTEGER, aliexpress_product_id TEXT, ebay_item_id TEXT)')
        db.execute('INSERT INTO products VALUES (7, ?, ?)', (pid, 'listing-0'))
        db.execute('CREATE TABLE product_variants (product_id INTEGER, sku TEXT, sku_id TEXT)')
        db.execute('INSERT INTO product_variants VALUES (7, ?, ?)', ('one', supplier))
    categories = {} if code == 'category_decision_needed' else {
        pid: {'blocked': True} if code == 'category_blocked' else {'category_id': 'wrong'}}
    labels = {} if code == 'variant_label_evidence_needed' else {pid: {supplier: {'Produktart': 'Wrong'}}}
    local_json(tmp_path, 'config/category_overrides.json', categories)
    local_json(tmp_path, 'config/verified_variant_labels.json', labels)
    run = module().run_cycle
    run(api, tmp_path, now=NOW)
    old = next(t for t in tasks(tmp_path) if t['code'] == code)
    local_json(tmp_path, 'config/category_overrides.json', {pid: {'category_id': '123'}})
    local_json(tmp_path, 'config/verified_variant_labels.json', {pid: {supplier: {'Produktart': 'Box'}}})
    api.fail[('offer', 'one')] = TimeoutError('private')
    run(api, tmp_path, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == old['key'])['status'] == 'unresolved'
    api.fail.clear()
    run(api, tmp_path, now=NOW)
    resolved = next(t for t in tasks(tmp_path) if t['key'] == old['key'])
    assert resolved['status'] == 'resolved'
    assert resolved['first_seen'] == old['first_seen']
    assert resolved['resolution_basis'] == 'full_exact_target_read'
    assert all(t['status'] == 'unresolved' for t in tasks(tmp_path)
               if t['code'] in ('variant_axis_evidence_needed', 'origin_manufacturer_evidence_needed',
                                'buyer_verification_needed'))


@pytest.mark.parametrize('different', ['product_id', 'sku'])
def test_verified_checks_do_not_resolve_different_identity_or_unrelated_reviews(different):
    mod = module()
    codes = ['category_decision_needed', 'category_decision_drift', 'category_blocked',
             'variant_label_evidence_needed', 'variant_label_mismatch',
             'variant_axis_evidence_needed', 'origin_manufacturer_evidence_needed', 'buyer_verification_needed']
    old = [dict(mod._task('one', 'review', code, [], product_id='1005000000001'), status='unresolved')
           for code in codes]
    state = {'tasks': {t['key']: t for t in old}}
    row = {'sku': 'one', 'product_id': '1005000000001', 'read_complete': True, 'offers': [{}],
           'tasks': [], 'checks': {k: {'status': 'verified'} for k in ('category_decisions', 'variant_labels')}}
    row[different] = 'different'
    mod._reconcile(state, row, NOW.isoformat())
    assert all(t['status'] == 'unresolved' for t in old)
    row[different] = 'one' if different == 'sku' else '1005000000001'
    mod._reconcile(state, row, NOW.isoformat())
    assert all(t['status'] == 'unresolved' for t in old[-3:])


def test_local_read_error_resolves_only_after_successful_exact_source_reread(tmp_path):
    path = local_json(tmp_path, 'config/category_overrides.json', {})
    path.write_text('{bad', encoding='utf-8')
    run = module().run_cycle
    run(Ebay(('one',)), tmp_path, now=NOW)
    task = next(t for t in tasks(tmp_path) if t['field'] == 'category_overrides' and t['code'] == 'read_failed')
    path.unlink()
    run(Ebay(('one',)), tmp_path, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == task['key'])['status'] == 'unresolved'
    path.write_text('{}', encoding='utf-8')
    run(Ebay(('one',)), tmp_path, now=NOW)
    assert next(t for t in tasks(tmp_path) if t['key'] == task['key'])['status'] == 'resolved'


def test_nonempty_malformed_local_decision_is_partial_and_does_not_abort_batch(tmp_path):
    api = Ebay(('one', 'two'))
    local_json(tmp_path, 'config/category_overrides.json', {'1005000000001': {'category_id': ['not-a-category']}})
    path = tmp_path / 'data/dropshipping.db'
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE products (aliexpress_product_id TEXT, ebay_item_id TEXT)')
        db.execute('INSERT INTO products VALUES (?, ?)', ('1005000000001', 'listing-0'))
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['status'] == 'partial'
    assert out['processed_this_run'] == 2
    assert {r['sku'] for r in report(tmp_path)['items']} == {'one', 'two'}


def test_all_offer_pages_audited_not_first_offer_only(tmp_path):
    api = Ebay(('one',))
    api.offers['one'].append({'offerId': 'offer-second', 'categoryId': '456',
                               'listing': {'listingId': 'listing-0', 'listingStatus': 'ACTIVE'}})
    api.metadata['456'] = [aspect('Material', required=True)]
    api.names['456'] = 'Anderes'
    out = module().run_cycle(api, tmp_path, now=NOW)
    assert out['complete']
    assert any(t['code'] == 'missing_required_aspect' and t['field'] == 'Material' for t in tasks(tmp_path))
    assert any(t['code'] == 'category_inconsistent_across_group' for t in tasks(tmp_path))


def test_catalog_scale_full_optional_fields_can_finish_without_oversized_checkpoint_failure(tmp_path):
    api = Ebay(tuple('SKU-' + str(i) for i in range(211)))
    api.page_size = 100
    api.metadata['123'] += [aspect('Optional ' + str(i)) for i in range(35)]
    run = module().run_cycle
    for _ in range(15):
        out = run(api, tmp_path, max_items=20, now=NOW)
        assert out['processed_this_run'] <= 20
        assert out['requests_used'] <= out['request_limit']
        assert not any(e['stage'] == 'checkpoint' for e in report(tmp_path)['errors'])
        if out['complete']:
            break
    assert out['complete'] and out['processed_skus'] == 211
    assert len(report(tmp_path)['items']) == 211
