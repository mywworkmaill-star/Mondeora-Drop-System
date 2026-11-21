"""RED/GREEN contract tests for the bounded real-evidence review-queue resolver.

No live network calls: fake eBay/AliExpress clients only. The resolver must never
self-mark a queue task resolved -- these tests check its own JSON summary/report,
never queue 'status' flips (that stays listing_quality.standards.run_cycle's job).
"""
from datetime import datetime, timezone
from copy import deepcopy
import importlib
import json
import pytest

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def module():
    return importlib.import_module('src.listing_quality.standards_resolve')


def aspect(name, *, required=False, values=None, variations=False, multi=False):
    return {'localizedAspectName': name, 'aspectConstraint': {
        'aspectRequired': required, 'aspectMode': 'SELECTION_ONLY' if values is not None else 'FREE_TEXT',
        'aspectEnabledForVariations': variations,
        'itemToAspectCardinality': 'MULTI' if multi else 'SINGLE'},
        'aspectValues': [{'localizedValue': value} for value in (values or [])]}


def task(key, sku, pid, field, code, **extra):
    return {'key': key, 'sku': sku, 'product_id': pid, 'field': field, 'code': code,
            'status': 'unresolved', 'evidence_needed': [], **extra}


def write_queue(root, tasks):
    path = root / 'data/audit/listing_review_queue.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'generated_at': NOW.isoformat(), 'cycle_id': 'c1',
                                'tasks': tasks}), encoding='utf-8')
    return path


def write_overrides(root, data=None):
    path = root / 'config/category_overrides.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data if data is not None else {'_comment': 'reviewed'}), encoding='utf-8')
    return path


class Ebay:
    """sku -> {'item': inventory_item dict, 'offers': [...]}; records every call."""

    def __init__(self):
        self.items = {}
        self.offers = {}
        self.category_meta = {}
        self.suggestions = []  # list of (category_id, name, path)
        self.calls = []
        self.put_bodies = []
        self.fail_product_get = set()

    def add_sku(self, sku, aspects, category_id, listing_status='ACTIVE'):
        self.items[sku] = {'sku': sku, 'product': {'aspects': dict(aspects)}}
        self.offers[sku] = [{'offerId': 'offer-' + sku, 'categoryId': category_id,
                             'listing': {'listingId': 'listing-' + sku, 'listingStatus': listing_status}}]

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, deepcopy(kwargs)))
        params = kwargs.get('params') or {}
        if method == 'GET':
            if path.endswith('/offer'):
                sku = params['sku']
                offers = self.offers.get(sku, [])
                return {'offers': deepcopy(offers), 'total': len(offers)}
            if '/inventory_item/' in path:
                sku = path.rsplit('/', 1)[-1]
                return deepcopy(self.items[sku])
            if path.endswith('/get_item_aspects_for_category'):
                return {'aspects': deepcopy(self.category_meta[params['category_id']])}
            if path.endswith('/get_category_suggestions'):
                out = []
                for cid, name, catpath in self.suggestions:
                    out.append({'category': {'categoryId': cid, 'categoryName': name},
                               'categoryTreeNodeAncestors': []})
                return {'categorySuggestions': out}
            raise AssertionError('Unexpected GET ' + path)
        if method == 'PUT':
            assert '/inventory_item/' in path, 'resolver must only PUT inventory_item (aspects), never offer'
            sku = path.rsplit('/', 1)[-1]
            body = kwargs['json']
            self.put_bodies.append((sku, deepcopy(body)))
            self.items[sku]['product']['aspects'] = dict(body['product']['aspects'])
            return {}
        raise AssertionError('Unexpected method ' + method)


class Supplier:
    def __init__(self):
        self.products = {}  # pid -> raw result dict

    def add(self, pid, *, subject='A product', props=(), package=None, manufacturer=None):
        properties = [{'attr_name': n, 'attr_value': v} for n, v in props]
        raw = {'ae_item_base_info_dto': {'product_id': pid, 'subject': subject},
               'ae_item_properties': {'ae_item_property': properties}}
        if package is not None:
            raw['package_info_dto'] = package
        if manufacturer is not None:
            raw['manufacturer_info'] = manufacturer
        self.products[pid] = raw

    def _request(self, method, params):
        assert method == 'aliexpress.ds.product.get'
        pid = params['product_id']
        if pid not in self.products:
            raise RuntimeError('unknown test product ' + pid)
        return {'result': deepcopy(self.products[pid])}


def resolution(root):
    return json.loads((root / 'data/audit/listing_review_resolution.json').read_text(encoding='utf-8'))


def test_adds_missing_optional_aspect_and_never_overwrites_disagreeing_existing_value(tmp_path):
    ebay, ali = Ebay(), Supplier()
    ebay.add_sku('sku-a', {'Produktart': ['Box']}, '123')
    ebay.category_meta['123'] = [aspect('Produktart', required=True), aspect('Material', required=False)]
    ali.add(pid='1111110000', props=[('Material', 'Holz'), ('Produktart', 'Andere Box')])
    write_queue(tmp_path, [task('t1', 'sku-a', '1111110000', 'aspects', 'missing_optional_aspect')])
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=False)
    assert out['resolved_candidates'] == 1
    assert out['skipped_no_evidence'] == 0
    assert out['attempted_writes'] == 1
    assert out['written_count'] == 0 and out['dry_run'] is True
    assert not any(c[0] == 'PUT' for c in ebay.calls)
    report = resolution(tmp_path)
    row = report['items'][0]
    assert row['added'] == ['Material']
    assert row['conflicts'] == ['Produktart']
    # The live, disagreeing value must never appear changed anywhere in our evidence.
    assert ebay.items['sku-a']['product']['aspects']['Produktart'] == ['Box']


def test_closed_picklist_only_accepted_when_exact_member_of_real_picklist(tmp_path):
    ebay, ali = Ebay(), Supplier()
    ebay.add_sku('sku-reject', {}, '200')
    ebay.add_sku('sku-accept', {}, '200')
    ebay.category_meta['200'] = [aspect('Farbe', values=['Rot', 'Blau'])]
    ali.add(pid='2222220000', props=[('Farbe', 'Gruen')])   # not an exact picklist member
    ali.add(pid='2222220001', props=[('Farbe', 'Rot')])     # exact member
    write_queue(tmp_path, [
        task('t-reject', 'sku-reject', '2222220000', 'Farbe', 'closed_picklist_invalid'),
        task('t-accept', 'sku-accept', '2222220001', 'Farbe', 'closed_picklist_invalid'),
    ])
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=False)
    assert out['skipped_no_evidence'] == 1
    assert out['resolved_candidates'] == 1
    report = resolution(tmp_path)
    by_sku = {r['sku']: r for r in report['items']}
    assert by_sku['sku-reject']['result'] == 'skipped_no_evidence'
    assert by_sku['sku-accept']['added'] == ['Farbe']


def test_origin_and_dimensions_skip_without_explicit_property_never_use_package_dims(tmp_path):
    ebay = Ebay()
    ali = Supplier()
    ebay.add_sku('sku-pkg', {}, '300')
    ebay.category_meta['300'] = [aspect('Länge', required=False), aspect('Hersteller', required=False)]
    ali.add(pid='3333330000', props=[], package={'package_length': '20', 'package_width': '10',
                                                  'package_height': '5', 'gross_weight': '0.5'})
    write_queue(tmp_path, [
        task('t-origin', 'sku-pkg', '3333330000', 'origin', 'origin_manufacturer_evidence_needed'),
        task('t-dims', 'sku-pkg', '3333330000', 'dimensions', 'dimensions_units_evidence_needed'),
    ])
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=True)
    assert out['skipped_no_evidence'] == 2
    assert out['resolved_candidates'] == 0
    assert out['attempted_writes'] == 0 and out['written_count'] == 0
    assert not any(c[0] == 'PUT' for c in ebay.calls)
    report = resolution(tmp_path)
    text = json.dumps(report)
    assert 'package_length' not in text and 'package_width' not in text and 'gross_weight' not in text
    assert all('added' not in item for item in report['items'])
    assert ebay.items['sku-pkg']['product']['aspects'] == {}


def test_category_confirmed_vs_mismatch_against_category_overrides_file(tmp_path):
    ebay, ali = Ebay(), Supplier()
    ebay.add_sku('sku-match', {}, '555')
    ebay.suggestions = [('555', 'Boxen', 'Moebel > Boxen')]
    ali.add(pid='4444440000', subject='Aufbewahrungsbox aus Holz')
    confirm_root = tmp_path / 'confirm'
    write_overrides(confirm_root)
    write_queue(confirm_root, [task('t-cat', 'sku-match', '4444440000', 'category', 'category_decision_needed')])
    out = module().resolve_cycle(ebay, ali, confirm_root, now=NOW, remote_mutations=False)
    assert out['category_confirmed_count'] == 1
    assert out['category_mismatch_count'] == 0
    assert out['resolved_candidates'] == 1
    overrides = json.loads((confirm_root / 'config/category_overrides.json').read_text(encoding='utf-8'))
    assert overrides['4444440000']['category_id'] == '555'

    ebay2 = Ebay()
    ebay2.add_sku('sku-diff', {}, '999')
    ebay2.suggestions = [('555', 'Boxen', 'Moebel > Boxen')]
    ali2 = Supplier()
    ali2.add(pid='4444440001', subject='Aufbewahrungsbox aus Holz')
    mismatch_root = tmp_path / 'mismatch'
    write_overrides(mismatch_root)
    before = (mismatch_root / 'config/category_overrides.json').read_bytes()
    write_queue(mismatch_root, [task('t-cat2', 'sku-diff', '4444440001', 'category', 'category_decision_needed')])
    out2 = module().resolve_cycle(ebay2, ali2, mismatch_root, now=NOW, remote_mutations=False)
    assert out2['category_mismatch_count'] == 1
    assert out2['category_confirmed_count'] == 0
    assert out2['resolved_candidates'] == 0
    after = (mismatch_root / 'config/category_overrides.json').read_bytes()
    assert after == before
    assert not any(c[0] == 'PUT' for c in ebay2.calls)


def test_out_of_scope_codes_are_left_completely_untouched_and_uncounted(tmp_path):
    ebay, ali = Ebay(), Supplier()
    out_of_scope = ['variant_label_evidence_needed', 'variant_axis_evidence_needed',
                    'model_quantity_review_needed', 'buyer_verification_needed',
                    'competitor_research_needed', 'buffer_verification_needed']
    tasks = [task(f't-oos-{i}', f'sku-{i}', '5555550000', 'x', code) for i, code in enumerate(out_of_scope)]
    write_queue(tmp_path, tasks)
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=True)
    assert out['candidate_tasks'] == 0
    assert out['processed_count'] == 0
    assert out['resolved_candidates'] == 0
    assert out['skipped_no_evidence'] == 0
    assert ebay.calls == []
    report = resolution(tmp_path)
    assert report['items'] == []


def test_dry_run_zero_puts_live_run_exact_merged_body(tmp_path):
    ebay, ali = Ebay(), Supplier()
    ebay.add_sku('sku-live', {'Produktart': ['Box']}, '123')
    ebay.category_meta['123'] = [aspect('Produktart', required=True), aspect('Material', required=False)]
    ali.add(pid='6666660000', props=[('Material', 'Holz')])
    write_queue(tmp_path, [task('t-dry', 'sku-live', '6666660000', 'aspects', 'missing_optional_aspect')])
    dry = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=False)
    assert dry['attempted_writes'] == 1 and dry['written_count'] == 0
    assert not any(c[0] == 'PUT' for c in ebay.calls)

    ebay2, ali2 = Ebay(), Supplier()
    ebay2.add_sku('sku-live', {'Produktart': ['Box']}, '123')
    ebay2.category_meta['123'] = [aspect('Produktart', required=True), aspect('Material', required=False)]
    ali2.add(pid='6666660000', props=[('Material', 'Holz')])
    write_queue(tmp_path, [task('t-live', 'sku-live', '6666660000', 'aspects', 'missing_optional_aspect')])
    live = module().resolve_cycle(ebay2, ali2, tmp_path, now=NOW, remote_mutations=True)
    assert live['written_count'] == 1 and live['write_error_count'] == 0
    puts = [c for c in ebay2.calls if c[0] == 'PUT']
    assert len(puts) == 1
    body = puts[0][2]['json']
    assert body == {'product': {'aspects': {'Produktart': ['Box'], 'Material': ['Holz']}}}


def test_one_bad_fetch_is_skipped_as_error_rest_of_batch_still_proceeds(tmp_path):
    ebay, ali = Ebay(), Supplier()
    ebay.add_sku('sku-bad', {}, '123')
    ebay.add_sku('sku-good', {}, '123')
    ebay.category_meta['123'] = [aspect('Produktart', required=True), aspect('Material', required=False)]
    ali.add(pid='7777770001', props=[('Material', 'Holz')])
    # '7777770000' deliberately left unregistered -> Supplier._request raises for it.
    write_queue(tmp_path, [
        task('t-bad', 'sku-bad', '7777770000', 'aspects', 'missing_optional_aspect'),
        task('t-good', 'sku-good', '7777770001', 'aspects', 'missing_optional_aspect'),
    ])
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, remote_mutations=False)
    assert out['error_count'] == 1
    assert out['processed_count'] == 2
    assert out['resolved_candidates'] == 1
    report = resolution(tmp_path)
    assert any(e.get('sku') == 'sku-bad' for e in report['errors'])
    assert any(r['sku'] == 'sku-good' and r.get('added') == ['Material'] for r in report['items'])


def test_budget_exhaustion_stops_cleanly_with_accurate_summary(tmp_path):
    ebay, ali = Ebay(), Supplier()
    tasks = [task(f't-{i}', f'sku-{i}', None, 'x', 'missing_optional_aspect') for i in range(5)]
    write_queue(tmp_path, tasks)
    out = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, max_items=2, remote_mutations=False)
    assert out['candidate_tasks'] == 5
    assert out['processed_count'] == 2
    assert out['budget_exhausted'] is True
    assert out['status'] == 'partial'
    json.dumps(out, allow_nan=False)

    # A near-zero wall-clock budget must also stop cleanly (no crash, accurate summary).
    out2 = module().resolve_cycle(ebay, ali, tmp_path, now=NOW, max_items=5, max_seconds=0, remote_mutations=False)
    assert out2['processed_count'] == 0
    assert out2['budget_exhausted'] is True
    assert out2['status'] == 'partial'
