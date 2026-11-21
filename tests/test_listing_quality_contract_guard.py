"""Offline hypothetical contracts; no fixture is supplier or marketplace evidence."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from src.listing_quality import ready_workflow
from src.listing_quality.ready_store import ReadyStore
from test_ready_launch import artifact

PID = '1005000000000'
SID = '2000000000001'


def trial():
    return {'ready_for_supervised_trial': True, 'ready_for_live': False,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'checks': [{'name': 'listing', 'passed': True}]}


def saved(pid=PID):
    result = artifact()
    result['config_fingerprint'] = 'current'
    result['st']['plan']['variants'][0]['sku'] = f'AE-{pid}-{SID}'
    return result


def release(store, **kwargs):
    defaults = dict(readiness=trial(), target=1, fingerprint='current',
                    freshness=lambda *a: None, persist=lambda *a: None)
    defaults.update(kwargs)
    return ready_workflow.release_pool(None, None, store, **defaults)


@pytest.mark.parametrize('reason', ['configuration', 'freshness'])
def test_trial_preflights_before_any_write(tmp_path, reason):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    if reason == 'configuration':
        a['config_fingerprint'] = 'obsolete'
    store.put(PID, a)
    calls = []
    def freshness(*args):
        calls.append('freshness')
        raise ValueError('test-only supplier changed')
    out = release(store, freshness=freshness, sender=lambda *a, **k: calls.append('write'))
    assert 'write' not in calls
    assert out['status'] == 'blocked'
    assert store.get(PID)['status'] == 'stale'


def test_trial_blocks_pending_reconciliation(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    other = '1005000000002'
    store.put(other, saved(other))
    store.mark(other, 'needs_reconciliation')
    calls = []
    out = release(store, sender=lambda *a, **k: calls.append('write'))
    assert calls == []
    assert 'previous_publication_needs_reconciliation' in out['blockers']


def test_trial_claim_order_is_not_a_preflight_bypass(tmp_path, monkeypatch):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    other = '1005000000002'
    store.put(other, saved(other))
    original = store.claim
    def reordered(**kwargs):
        return original(limit=2)[1:]
    monkeypatch.setattr(store, 'claim', reordered)
    calls = []
    out = release(store, sender=lambda *a, **k: calls.append('write'))
    assert calls == []
    assert out['status'] == 'blocked'
    assert store.get(other)['status'] == 'needs_reconciliation'


def test_trial_runs_real_buyer_check_before_verified(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    store.put(PID, a)
    calls = []
    class Buyer:
        def _request(self, method, path, **kwargs):
            calls.append((method, path))
            return {'title': a['st']['title'], 'description': a['st']['desc'],
                    'price': {'currency': 'EUR', 'value': '29.99'}}
    out = ready_workflow.release_pool(None, Buyer(), store, readiness=trial(), target=1,
        fingerprint='current', freshness=lambda *a: None, persist=lambda *a: None,
        sender=lambda *a, **k: {'listing_id': '860000000001'})
    assert calls and calls[0][0] == 'GET'
    assert out['published_count'] == 1
    assert store.get(PID)['detail']['buyer_verified'] is True


def test_trial_ambiguous_write_stops_batch_and_never_retries_or_leaks(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    other = '1005000000002'
    store.put(other, saved(other))
    calls = []
    def sender(*args, **kwargs):
        calls.append(args[1])
        raise TimeoutError('secret-provider-body')
    out = release(store, target=2, sender=sender)
    assert calls == [PID]
    assert out['status'] == 'blocked'
    assert store.get(PID)['status'] == 'needs_reconciliation'
    assert store.get(other)['status'] == 'ready'
    assert 'secret-provider-body' not in str(store.get(PID)) + str(out)
    release(store, sender=sender)
    assert calls == [PID]


def test_trial_buyer_failure_remains_unverified_reconciliation(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    def denied(*args):
        raise ValueError('buyer content mismatch')
    out = release(store, sender=lambda *a, **k: {'listing_id': '860000000001'}, buyer_check=denied)
    assert out['published_count'] == 0
    record = store.get(PID)
    assert record['status'] == 'needs_reconciliation'
    assert not record['detail'].get('buyer_verified')


def test_trial_does_not_forward_unsafe_executor_bypass(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    bypass = []
    def sender(*args, **kwargs):
        bypass.append(kwargs.get('supervised_trial', False))
        return {'listing_id': '860000000001'}
    release(store, sender=sender, buyer_check=lambda *a: None)
    assert bypass == [False]


def test_distinct_supplier_skus_with_same_options_are_not_verified_equivalents():
    from src.listing_quality import variants
    rows = [dict(sku_id=sid, offer_sale_price='4', sku_available_stock=5, currency_code='EUR',
                 ae_sku_property_dtos={'ae_sku_property_d_t_o': [
                     {'sku_property_name': 'Farbe', 'property_value_definition_name': 'Rot'}]})
            for sid in (SID, '2000000000002')]
    result = variants.build(PID, {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': rows}},
                            2, cfg={'fee_pct': 13.5, 'fixed_fee': .35})
    assert {v['sku_id'] for v in result['variants']} == {SID, '2000000000002'}
    assert all(not v['verified'] for v in result['variants'])
    assert any('ambiguous option combination' in flag for flag in result['flags'])


class Competitors:
    """Fake Browse transport: immutable fixture data, no network."""
    def __init__(self, summaries=None, failures=()):
        self.summaries = summaries if summaries is not None else [self.summary(i) for i in range(1, 5)]
        self.failures, self.calls = set(failures), []

    @staticmethod
    def summary(i, seller=None, category='123456'):
        return {'itemId': f'v1|{860000000000 + i}|0', 'title': 'Kabelorganizer Halter',
                'seller': {'username': seller or f'seller-{i}'},
                'categories': [{'categoryId': category}], 'itemWebUrl': f'https://www.ebay.de/itm/{860000000000 + i}'}

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path.endswith('/search'):
            return {'itemSummaries': self.summaries, 'total': len(self.summaries)}
        from urllib.parse import unquote
        iid = unquote(path.rsplit('/', 1)[-1])
        if iid in self.failures:
            raise TimeoutError('secret-transport-body')
        row = next(s for s in self.summaries if s['itemId'] == iid)
        return dict(row, localizedAspects=[{'name': 'Material', 'value': 'Stahl'}])


def test_legacy_competitor_fill_never_mutates_or_imports_facts():
    from src.listing_quality import competitor_aspects
    shared = {'Farbe': ['Rot']}
    meta = [{'name': 'Material', 'mode': 'FREE_TEXT', 'values': []}]
    result = competitor_aspects.fill_from_competitors(Competitors(), meta, 'Kabelorganizer', shared)
    assert shared == result == {'Farbe': ['Rot']}


def test_research_uses_category_leading_type_unique_sellers_and_exclusions():
    from src.listing_quality import competitor_aspects
    rows = [Competitors.summary(1), Competitors.summary(1), Competitors.summary(2, seller='seller-1'),
            Competitors.summary(3), Competitors.summary(4, category='999999'),
            Competitors.summary(5), Competitors.summary(6)]
    ebay = Competitors(rows)
    report = competitor_aspects.research(ebay, 'Kabelorganizer Halter für Hülle universelles Zubehör',
                                        '123456', exclude_listing_ids=('860000000003',))
    params = ebay.calls[0][2]['params']
    assert params['category_ids'] == '123456'
    assert params['q'].startswith('Kabelorganizer')
    assert 'Zubehör' not in params['q']
    assert {row['item_id'] for row in report['candidates']} == {
        f'v1|{860000000000 + i}|0' for i in (1, 5, 6)}
    assert len({row['seller'] for row in report['candidates']}) == 3
    assert all(row['source'] and row['category_ids'] == ['123456'] for row in report['candidates'])
    assert report['suggestions']['Material']['value'] == 'Stahl'
    assert report['suggestions']['Material']['evidence_type'] == 'competitor_suggestion_only'
    assert report['product_facts_verified'] is False


def test_research_requires_three_successful_independent_competitors():
    from src.listing_quality import competitor_aspects
    rows = [Competitors.summary(1), Competitors.summary(2), Competitors.summary(3)]
    report = competitor_aspects.research(Competitors(rows, failures=(rows[2]['itemId'],)),
                                        'Kabelorganizer Halter', '123456')
    assert report['status'] == 'not_verified'
    assert report['suggestions'] == {}
    assert report['completeness']['successful_independent'] == 2
    assert report['errors'] == [{'stage': 'detail', 'item_id': rows[2]['itemId'], 'error_type': 'TimeoutError'}]
    assert 'secret-transport-body' not in str(report)
    assert report['own_listing_exclusion']['complete'] is False


def test_research_never_fetches_more_than_ten_details():
    from src.listing_quality import competitor_aspects
    ebay = Competitors([Competitors.summary(i) for i in range(1, 30)])
    report = competitor_aspects.research(ebay, 'Kabelorganizer', '123456', limit=10)
    assert len(ebay.calls) <= 11
    assert len(report['candidates']) == 10


def aspect(name, *, required=False, values=(), multi=False):
    return {'name': name, 'required': required, 'mode': 'SELECTION_ONLY' if values else 'FREE_TEXT',
            'values': list(values), 'multi': multi, 'variation_ok': False}


def test_supplier_brand_and_manufacturer_are_preserved_without_defaults():
    from src.listing_quality import categories
    meta = [aspect(n, required=True) for n in ('Marke', 'Hersteller', 'Modell', 'EAN')]
    out, missing = categories.fill_aspects(meta, [('Marke', 'REAL BRAND'), ('Hersteller', 'Real GmbH')])
    assert out == {'Marke': ['REAL BRAND'], 'Hersteller': ['Real GmbH']}
    assert missing == ['Modell', 'EAN']
    absent, missing = categories.fill_aspects(meta, [])
    assert absent == {} and missing == ['Marke', 'Hersteller', 'Modell', 'EAN']


def test_unqualified_weight_and_arbitrary_substring_property_are_not_facts():
    from src.listing_quality import categories
    meta = [aspect('Gewicht', required=True), aspect('Material', required=True)]
    out, missing = categories.fill_aspects(meta, [('Gewicht', '.25'), ('Verpackungsmaterial', 'Stahl')])
    assert out == {}
    assert missing == ['Gewicht', 'Material']


def test_explicit_material_aliases_are_bounded_real_properties():
    from src.listing_quality import categories
    out, missing = categories.fill_aspects([aspect('Material', required=True)], [('Hauptmaterial', 'Silikon')])
    assert out == {'Material': ['Silikon']} and missing == []


@pytest.mark.parametrize('title', ['Nicht wasserdicht', 'ohne wasserdicht', 'kein wasserdicht',
                                 'Katzen Hülle für universelles Zubehör'])
def test_title_overlap_and_negation_do_not_fabricate_optional_features(title):
    from src.listing_quality import categories
    meta = [aspect('Besonderheiten', values=('Wasserdicht', 'Katzen Spielzeug'), multi=True)]
    out, missing = categories.fill_aspects(meta, [], subject=title)
    assert out == {} and missing == []


def test_only_full_bounded_picklist_phrases_may_be_title_evidence():
    from src.listing_quality import categories
    meta = [aspect('Produktart', required=True, values=('Katzen Spielzeug',))]
    out, missing = categories.fill_aspects(meta, [], subject='Katzen Spielzeug aus Silikon')
    assert out == {'Produktart': ['Katzen Spielzeug']} and missing == []
    out, missing = categories.fill_aspects(meta, [], subject='Katzen Hülle und Spielzeugkasten')
    assert out == {} and missing == ['Produktart']


@pytest.fixture
def planner(monkeypatch):
    from src.listing_quality import publish, categories, gates, images, source
    raw = {'ae_item_base_info_dto': {'product_id': PID, 'subject': 'Kabelorganizer Halter',
                                   'package_height': 10, 'package_length': 20, 'package_width': 30},
           'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [
               {'sku_id': SID, 'offer_sale_price': '4', 'sku_available_stock': 5, 'currency_code': 'EUR'}]},
           'ae_multimedia_info_dto': {'image_urls': 'https://example.invalid/photo.jpg'}}
    monkeypatch.setattr(source, 'fetch_raw', lambda *a: deepcopy(raw))
    monkeypatch.setattr(categories, 'resolve_for_product', lambda *a: {
        'category_id': '123456', 'needs_review': False, 'confidence': 1})
    monkeypatch.setattr(categories, 'aspects_for', lambda *a: [])
    monkeypatch.setattr(gates, 'evaluate', lambda *a: {'block': [], 'review': []})
    monkeypatch.setattr(gates, 'check_title', lambda *a: [])
    monkeypatch.setattr(gates, 'demand', lambda *a: ({}, []))
    monkeypatch.setattr(images, 'filter_urls', lambda urls: (urls, []))
    return publish, categories, raw


@pytest.mark.parametrize('required,props', [
    ('Höhe', []), ('Tiefe', [('Breite', '30 cm')]), ('Abmessungen', [])])
def test_planner_never_uses_package_or_width_for_product_dimensions(planner, monkeypatch, required, props):
    publish, categories, raw = planner
    raw['ae_item_properties'] = {'ae_item_property': [{'attr_name': n, 'attr_value': v} for n, v in props]}
    monkeypatch.setattr(categories, 'aspects_for', lambda *a: [aspect(required, required=True)])
    with pytest.raises(ValueError, match='required aspects missing'):
        publish.plan_for(None, None, PID, 2)


def test_planner_cannot_reintroduce_one_word_product_type_guess(planner, monkeypatch):
    publish, categories, raw = planner
    monkeypatch.setattr(categories, 'aspects_for', lambda *a: [
        aspect('Produktart', required=True, values=('Kabelorganizer Schutzhülle',))])
    with pytest.raises(ValueError, match='required aspects missing'):
        publish.plan_for(None, None, PID, 2)


def test_every_successful_plan_includes_bounded_research_for_winning_category(planner, monkeypatch):
    from src.listing_quality import competitor_aspects
    publish, categories, raw = planner
    monkeypatch.setattr(categories, 'aspects_for', lambda *a: [aspect('Material')])
    calls = []
    report = {'status': 'suggestions_only', 'suggestions': {'Material': {'value': 'Stahl'}},
              'product_facts_verified': False}
    def research(ebay, subject, category_id, limit=10, exclude_listing_ids=()):
        calls.append((subject, category_id, limit))
        return deepcopy(report)
    monkeypatch.setattr(competitor_aspects, 'research', research, raising=False)
    st = publish.plan_for(None, None, PID, 2)
    assert calls == [('Kabelorganizer Halter', '123456', 10)]
    assert st['competitor_research'] == report
    assert st['shared'] == {}
    assert st['aspect_metadata'] == [aspect('Material')]


def test_planner_records_research_failure_without_fabricating_facts(planner, monkeypatch):
    from src.listing_quality import competitor_aspects
    publish, categories, raw = planner
    def failed(*a, **kw):
        raise TimeoutError('secret-body')
    monkeypatch.setattr(competitor_aspects, 'research', failed, raising=False)
    st = publish.plan_for(None, None, PID, 2)
    assert st['competitor_research']['status'] == 'not_verified'
    assert st['competitor_research']['errors'] == [{'stage': 'research', 'error_type': 'TimeoutError'}]
    assert 'secret-body' not in str(st)


def sourced_plan():
    from test_ready_launch import raw
    st = saved()['st']
    st['res'] = raw()
    st['res']['ae_item_properties'] = {'ae_item_property': [{'attr_name': 'Material', 'attr_value': 'Metall'}]}
    st['aspect_metadata'] = [aspect('Material', required=True), aspect('Tiefe'), aspect('Hersteller')]
    return st


def test_contract_reports_all_category_aspects_without_inventing_optional_facts():
    from src.listing_quality import quality_contract
    st = sourced_plan()
    before = deepcopy(st)
    report = quality_contract.inspect_plan(st)
    assert report['version'] == quality_contract.VERSION
    assert report['blockers'] == []
    assert {a['name'] for a in report['coverage']['aspects']} == {'Material', 'Tiefe', 'Hersteller'}
    assert report['coverage']['unknown_optional'] == ['Tiefe', 'Hersteller']
    assert st == before
    del st['shared']['Material']
    assert 'required_aspect_missing:Material' in quality_contract.inspect_plan(st)['blockers']


@pytest.mark.parametrize('change,blocker', [
    ('sku_suffix', 'retained_sku_identity_invalid'),
    ('supplier_missing', 'retained_supplier_sku_not_exact_match'),
    ('supplier_duplicate', 'supplier_sku_identity_ambiguous'),
    ('combo', 'supplier_option_mapping_ambiguous'),
])
def test_contract_requires_exact_supplier_sku_identity_and_unique_combinations(change, blocker):
    from src.listing_quality import quality_contract
    st = sourced_plan()
    if change == 'sku_suffix':
        st['plan']['variants'][0]['sku'] += '-other'
    elif change == 'supplier_missing':
        st['res']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o'] = []
    elif change == 'supplier_duplicate':
        rows = st['res']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o']
        rows.append(deepcopy(rows[0]))
    else:
        second = deepcopy(st['plan']['variants'][0])
        second.update(sku=f'AE-{PID}-2000000000002', sku_id='2000000000002')
        st['plan']['variants'].append(second)
    assert blocker in quality_contract.inspect_plan(st)['blockers']


@pytest.mark.parametrize('name,value', [('Hersteller', 'Markenlos'), ('Tiefe', '30 cm'), ('Material', 'Stahl')])
def test_contract_blocks_unsupported_derived_shared_facts(name, value):
    from src.listing_quality import quality_contract
    st = sourced_plan()
    st['res']['ae_item_base_info_dto']['package_width'] = 30
    st['shared'][name] = [value]
    assert 'unsafe_derived_fact:' + name in quality_contract.inspect_plan(st)['blockers']


def test_old_plan_without_new_metadata_reports_limits_not_blanket_block():
    from src.listing_quality import quality_contract
    report = quality_contract.inspect_plan(saved()['st'])
    assert report['blockers'] == []
    assert report['coverage']['metadata_available'] is False
    assert 'category_aspect_metadata_unavailable' in report['warnings']


def test_preparation_contract_is_not_filterable_by_supervised_trial(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    a['st'] = sourced_plan()
    a['st']['shared']['Tiefe'] = ['30 cm']
    def builder(*args, **kwargs):
        return {'artifact': deepcopy(a), 'blockers': []}
    out = ready_workflow.prepare_pool(None, None, [{'aliexpress_product_id': PID}], store,
        readiness=trial(), target=1, fingerprint='current', builder=builder)
    assert out['ready_count'] == 0
    record = store.get(PID)
    assert 'contract:unsafe_derived_fact:Tiefe' in record['blockers']
    assert record['artifact']['quality_contract']['coverage']['metadata_available'] is True


def test_release_rechecks_actual_content_not_saved_contract_report(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    a['st'] = sourced_plan()
    a['st']['shared']['Material'] = ['Stahl']
    a['quality_contract'] = {'version': '1', 'blockers': []}
    store.put(PID, a)
    calls = []
    out = release(store, sender=lambda *a, **kw: calls.append('write'))
    assert calls == []
    assert 'contract:unsafe_derived_fact:Material:' + PID in out['blockers']


def test_contract_checked_again_immediately_before_sender(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    a['st'] = sourced_plan()
    store.put(PID, a)
    # Model a local artifact changed after batch preflight but before sending.
    original = store.claim
    def tampered(**kwargs):
        rows = original(**kwargs)
        rows[0]['artifact']['st']['shared']['Tiefe'] = ['30 cm']
        return rows
    store.claim = tampered
    calls = []
    out = release(store, sender=lambda *a, **kw: calls.append('write'))
    assert calls == []
    assert out['status'] == 'blocked'


def test_buyer_check_false_never_marks_verified(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    store.put(PID, saved())
    out = release(store, sender=lambda *a, **k: {'listing_id': '860000000001'}, buyer_check=lambda *a: False)
    assert out['published_count'] == 0
    assert store.get(PID)['status'] == 'needs_reconciliation'


def test_invalid_mapping_keeps_contract_evidence_in_blocked_preparation(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    a['st']['plan']['variants'][0]['sku_id'] = 'legacy-display-sku'
    def builder(*args, **kwargs):
        return {'artifact': a, 'blockers': []}
    ready_workflow.prepare_pool(None, None, [{'aliexpress_product_id': PID}], store,
        readiness=trial(), target=1, fingerprint='current', builder=builder)
    record = store.get(PID)
    assert 'contract:retained_sku_identity_invalid' in record['blockers']
    assert record['artifact']['quality_contract']['blockers'] == ['retained_sku_identity_invalid']


def test_preflight_failure_returns_actual_remaining_ready_count(tmp_path):
    store = ReadyStore(tmp_path / 'ready.sqlite')
    a = saved()
    a['config_fingerprint'] = 'old'
    store.put(PID, a)
    out = release(store, sender=lambda *a, **kw: pytest.fail('no write expected'))
    assert out['ready_count'] == store.summary(1)['ready_count'] == 0


@pytest.mark.parametrize('mutation', ['variant', 'shared', 'metadata', 'raw_properties'])
def test_malformed_contract_input_returns_safe_blocker_not_exception(mutation):
    from src.listing_quality import quality_contract
    st = sourced_plan()
    if mutation == 'variant':
        st['plan']['variants'] = [None]
    elif mutation == 'shared':
        st['shared'] = ['not-an-aspect-map']
    elif mutation == 'metadata':
        st['aspect_metadata'] = [{'name': ['invalid-name']}]
    else:
        st['res']['ae_item_properties'] = ['invalid-properties']
    report = quality_contract.inspect_plan(st)
    assert report['blockers']
    assert 'invalid-properties' not in str(report)
