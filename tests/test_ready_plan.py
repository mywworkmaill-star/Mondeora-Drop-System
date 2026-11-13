"""Hypothetical offline fixtures only; no production evidence or live API writes."""
from datetime import datetime, timedelta, timezone
import importlib
import importlib.util
from copy import deepcopy
from decimal import Decimal
import json
import sqlite3

import pytest


NOW = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)


def ready_plan():
    assert importlib.util.find_spec('src.listing_quality.ready_plan') is not None, 'Prepared listing builder must exist'
    return importlib.import_module('src.listing_quality.ready_plan')


def report(**changes):
    value = {'ready_for_live': True, 'generated_at': NOW.isoformat(), 'checks': [
        {'name': 'commercial_account_status', 'passed': True},
        {'name': 'business_and_tax_setup', 'passed': True},
        {'name': 'scoped_finance_evidence', 'passed': True},
        {'name': 'controlled_end_to_end_acceptance', 'passed': False},
        {'name': 'automatic_supplier_payment', 'passed': False},
    ]}
    value.update(changes)
    return value


def test_readiness_rejects_failed_relevant_checks_despite_true_summary():
    module = ready_plan()
    readiness = report()
    for check in readiness['checks'][:3]:
        check['passed'] = False
    assert set(module.readiness_blockers(readiness, now=NOW)) == {
        'readiness_commercial_account_status', 'readiness_business_and_tax_setup',
        'readiness_scoped_finance_evidence',
    }
    assert module.readiness_blockers(report(), now=NOW) == []


@pytest.mark.parametrize('readiness, expected', [
    (None, 'readiness_report_missing'),
    (report(ready_for_live='true'), 'readiness_not_ready_for_live'),
    (report(generated_at=(NOW - timedelta(hours=24, seconds=1)).isoformat()), 'readiness_report_stale'),
    (report(generated_at=(NOW + timedelta(seconds=1)).isoformat()), 'readiness_report_from_future'),
    (report(generated_at='2026-11-13T10:00:00'), 'readiness_report_timestamp_invalid'),
    (report(generated_at=None), 'readiness_report_timestamp_invalid'),
    (report(checks=None), 'readiness_checks_invalid'),
    (report(checks=[]), 'readiness_checks_missing'),
    (report(checks=[{'passed': True}]), 'readiness_checks_invalid'),
    (report(blockers=['commercial_account_status']), 'readiness_commercial_account_status'),
])
def test_readiness_fails_closed_on_stale_or_invalid_evidence(readiness, expected):
    assert expected in ready_plan().readiness_blockers(readiness, now=NOW)
    assert ready_plan().readiness_blockers(report(generated_at=(NOW - timedelta(hours=24)).isoformat()), now=NOW) == []


def test_publication_context_and_fingerprint_exclude_credentials(monkeypatch, tmp_path):
    module = ready_plan()
    from src import runtime
    cfg = {'EBAY_FULFILLMENT_POLICY_ID': 'hypothetical-fulfillment',
           'EBAY_PAYMENT_POLICY_ID': 'hypothetical-payment',
           'EBAY_RETURN_POLICY_ID': 'hypothetical-return',
           'EBAY_MERCHANT_LOCATION_KEY': 'hypothetical-location',
           'EBAY_ACCESS_TOKEN': 'test-only-secret', 'EBAY_FEE_PERCENT': '13.5'}
    monkeypatch.setattr(runtime, 'read_config', lambda: dict(cfg))
    monkeypatch.setattr(runtime, 'PROJECT_ROOT', tmp_path)
    assert hasattr(module, 'publication_context'), 'Safe publication context must exist'
    assert module.publication_context() == {
        'fulfillmentPolicyId': cfg['EBAY_FULFILLMENT_POLICY_ID'],
        'paymentPolicyId': cfg['EBAY_PAYMENT_POLICY_ID'],
        'returnPolicyId': cfg['EBAY_RETURN_POLICY_ID'],
        'merchantLocationKey': cfg['EBAY_MERCHANT_LOCATION_KEY'],
    }
    first = module.config_fingerprint()
    assert len(first) == 64 and int(first, 16) >= 0
    cfg['EBAY_ACCESS_TOKEN'] = 'rotated-test-only-secret'
    assert module.config_fingerprint() == first
    cfg['EBAY_PAYMENT_POLICY_ID'] = 'hypothetical-other-policy'
    second = module.config_fingerprint()
    assert second != first
    config = tmp_path / 'config'
    config.mkdir()
    for name in ('risk_rules.json', 'risk_ack.json', 'category_overrides.json', 'price_pinned_products.json', 'finance_policy.json'):
        (config / name).write_text('{"hypothetical_test_change":true}', encoding='utf-8')
        changed = module.config_fingerprint()
        assert changed != second, name
        second = changed
    cfg['EBAY_FEE_PERCENT'] = '14'
    assert module.config_fingerprint() != second


@pytest.fixture
def hypothetical_listing(monkeypatch, tmp_path):
    """All values are explicitly hypothetical unit-test data, never readiness proof."""
    from src import runtime
    from src.listing_quality import categories, gates, images, pricing, publish, source
    import requests

    module = ready_plan()
    cfg = {'EBAY_FULFILLMENT_POLICY_ID': 'test-fulfillment', 'EBAY_PAYMENT_POLICY_ID': 'test-payment',
           'EBAY_RETURN_POLICY_ID': 'test-return', 'EBAY_MERCHANT_LOCATION_KEY': 'test-location',
           'EBAY_FEE_PERCENT': '13.5', 'SUPPLIER_AGREEMENT_CONFIRMED': 'true',
           'SUPPLIER_PRODUCT_COMPLIANCE_VERIFIED': 'true', 'DEMAND_VERIFIED': 'true'}
    monkeypatch.setattr(runtime, 'read_config', lambda: dict(cfg))
    monkeypatch.setattr(runtime, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(pricing, '_env', lambda: dict(cfg))
    monkeypatch.setattr(source, 'CACHE', tmp_path / 'supplier-cache')
    monkeypatch.setattr(categories, 'resolve_for_product', lambda *a: {
        'category_id': '12345', 'path': 'Büro > Ablagen', 'needs_review': False})
    monkeypatch.setattr(categories, 'aspects_for', lambda *a: [
        {'name': 'Material', 'required': True, 'mode': 'FREE_TEXT', 'values': [], 'variation_ok': False},
        {'name': 'Farbe', 'required': False, 'values': [], 'variation_ok': True}])
    market_calls = []

    def market(ebay, queries, our_price=None):
        market_calls.append(our_price)
        return {'listings_found': 8, 'median': 70, 'our_price': our_price}, []

    monkeypatch.setattr(gates, 'demand', market)
    monkeypatch.setattr(images, 'filter_urls', lambda urls: (urls, []))

    write_attempts = []
    def forbidden(*args, **kwargs):
        write_attempts.append((args, kwargs))
        raise AssertionError('No database access, remote writes, or unscoped network in builder')

    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(publish, 'Api', forbidden)
    monkeypatch.setattr(publish, 'apply', forbidden)
    monkeypatch.setattr(publish, 'list_new', forbidden)
    monkeypatch.setattr(runtime, 'require_writes', forbidden)

    pid, sku1, sku2 = '1005001234567', '1200001234567', '1200001234568'
    title = 'Dokumenten Organizer Metall Schreibtisch Ablage'
    raw = {'ae_item_base_info_dto': {'product_id': pid, 'subject': title,
            'detail': '<p>Hypothetische Produktbeschreibung nur für Offline-Tests.</p>'},
           'ae_item_properties': {'ae_item_property': [{'attr_name': 'Material', 'attr_value': 'Metall'}]},
           'ae_multimedia_info_dto': {'image_urls': 'https://example.invalid/test-image.jpg'},
           'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [
               {'sku_id': sku, 'currency_code': 'EUR', 'offer_sale_price': cost, 'sku_available_stock': 5,
                'ae_sku_property_dtos': {'ae_sku_property_d_t_o': [{'sku_property_name': 'Farbe',
                    'property_value_definition_name': color, 'sku_property_value': color}]}}
               for sku, cost, color in ((sku1, '12', 'Schwarz'), (sku2, '13', 'Weiß'))]}}
    details = {'product_id': pid, 'product_title': title, 'currency': 'EUR', 'skus': [
        {'sku_id': sku, 'sale_price': Decimal(cost), 'currency': 'EUR', 'warehouse_count': 5}
        for sku, cost in ((sku1, '12'), (sku2, '13'))]}
    quotes = {sku: {'product_id': pid, 'sku_id': sku, 'quantity': 1, 'ship_to_country': 'DE',
                   'currency': 'EUR', 'cost': Decimal(cost), 'quoted_at': NOW.isoformat(),
                   'service_name': 'HYPOTHETICAL-TEST-SERVICE', 'delivery_estimate': {'min_days': 5, 'max_days': 10},
                   'is_estimate': True, 'transaction_ready': False}
              for sku, cost in ((sku1, '1.25'), (sku2, '4.5'))}

    class Supplier:
        def __init__(self):
            self.calls = []

        def get_product_details(self, product_id):
            self.calls.append(('details', product_id))
            assert product_id == pid
            return deepcopy(details)

        def get_shipping_quote(self, product_id, sku_id, *, quantity, ship_to_country):
            self.calls.append(('quote', product_id, sku_id, quantity, ship_to_country))
            assert product_id == pid and quantity == 1 and ship_to_country == 'DE'
            return deepcopy(quotes[sku_id])

        def _request(self, method, params):
            self.calls.append(('read', method, deepcopy(params)))
            assert method == 'aliexpress.ds.product.get'
            assert params == {'product_id': pid, 'ship_to_country': 'DE', 'target_currency': 'EUR', 'target_language': 'de'}
            return {'result': deepcopy(raw)}

    row = {'aliexpress_product_id': pid, 'title': title, 'shipping_cost': 9999,
           'is_listed': 0, 'ebay_item_id': None}
    yield {'module': module, 'supplier': Supplier(), 'ebay': object(), 'pid': pid, 'skus': (sku1, sku2),
           'row': row, 'details': details, 'quotes': quotes, 'raw': raw, 'cfg': cfg,
           'market_calls': market_calls, 'publish': publish, 'pricing': pricing}
    assert write_attempts == [], 'Even caught write attempts are forbidden'


def test_builder_prepares_full_content_with_every_scoped_quote_but_keeps_evidence_blocked(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    module, pricing = f['module'], f['pricing']
    assert hasattr(module, 'build_prepared'), 'Full read-only prepared builder must exist'
    original = pricing.price_for
    price_calls = []

    def calculate(cost, ship, cfg=None, legacy=False):
        assert type(cost) is float and type(ship) is float
        price_calls.append((cost, ship, legacy))
        return original(cost, ship, cfg, legacy=legacy)

    monkeypatch.setattr(pricing, 'price_for', calculate)
    monkeypatch.setattr(pricing, 'is_pinned', lambda pid: pid == f['pid'])
    original_row = deepcopy(f['row'])
    result = module.build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert result['product_id'] == f['pid']
    artifact = result['artifact']
    assert artifact is not None
    st = artifact['st']
    assert st['title'] == f['row']['title']
    assert st['cat']['category_id'] == '12345'
    assert st['shared']['Material'] == ['Metall']
    assert len(st['desc']) >= 300 and st['imgs'] == ['https://example.invalid/test-image.jpg']
    assert len(st['plan']['variants']) == 2 and st['plan']['is_variation'] is True
    assert artifact['publication_context'] == module.publication_context()
    assert set(artifact['shipping_quotes']) == set(f['skus'])
    for sku, quote in artifact['shipping_quotes'].items():
        assert quote == f['quotes'][sku]
        assert quote['is_estimate'] is True and quote['transaction_ready'] is False
    assert price_calls == [(12.0, 1.25, True), (13.0, 4.5, True)]
    for variant in st['plan']['variants']:
        ship = float(f['quotes'][variant['sku_id']]['cost'])
        assert (variant['price'], variant['net']) == original(variant['cost'], ship, legacy=True)
    assert len(f['market_calls']) == 2  # Original content gate, then changed-price check.
    assert artifact['config_fingerprint'] == module.config_fingerprint()
    assert len(artifact['source_fingerprint']) == 64
    assert artifact['observed_at'] == NOW.isoformat()
    assert set(result['blockers']) >= {
        'supplier_product_compliance_unverified', 'supplier_agreement_missing',
        'manufacturer_eu_responsible_person_missing', 'image_rights_unverified',
        'dispatch_origin_unverified', 'demand_unverified', 'complete_cost_profit_unverified',
        'freight_estimate_only',
    }
    assert f['row'] == original_row
    assert {call[2] for call in f['supplier'].calls if call[0] == 'quote'} == set(f['skus'])
    assert 9999 not in f['market_calls']
    json.dumps(artifact, allow_nan=False)


@pytest.mark.parametrize('changes, blocker', [
    ({'aliexpress_product_id': '1005001234567 '}, 'product_id_invalid'),
    ({'aliexpress_product_id': '123'}, 'product_id_invalid'),
    ({'aliexpress_product_id': '１００５００１２３４５６７'}, 'product_id_invalid'),
    ({'is_listed': 1}, 'already_listed'),
    ({'ebay_item_id': 'hypothetical-existing-listing'}, 'already_listed'),
])
def test_ineligible_rows_are_not_prepared(hypothetical_listing, changes, blocker):
    f = hypothetical_listing
    f['row'].update(changes)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert blocker in result['blockers']
    assert result['artifact'] is None
    assert f['supplier'].calls == []


@pytest.mark.parametrize('mutation, blocker', [
    ('wrong_product', 'supplier_product_identity_mismatch'),
    ('out_of_stock', 'no_current_in_stock_eur_sku'),
    ('invalid_cost', 'no_current_in_stock_eur_sku'),
    ('wrong_currency', 'no_current_in_stock_eur_sku'),
    ('duplicate_sku', 'supplier_sku_identity_ambiguous'),
])
def test_supplier_identity_and_real_cost_stock_are_required(hypothetical_listing, mutation, blocker):
    f = hypothetical_listing
    if mutation == 'wrong_product':
        f['details']['product_id'] = '1005009999999'
    elif mutation == 'duplicate_sku':
        f['details']['skus'].append(deepcopy(f['details']['skus'][0]))
    else:
        key, value = {'out_of_stock': ('warehouse_count', 0), 'invalid_cost': ('sale_price', 'NaN'),
                      'wrong_currency': ('currency', 'USD')}[mutation]
        for sku in f['details']['skus']:
            sku[key] = value
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert blocker in result['blockers']
    assert result['artifact'] is None
    assert not any(call[0] in ('quote', 'read') for call in f['supplier'].calls)


@pytest.mark.parametrize('sku_index', [0, 1])
@pytest.mark.parametrize('change, blocker', [
    ({'product_id': '1005009999999'}, 'freight_scope_mismatch'),
    ({'sku_id': '1200009999999'}, 'freight_scope_mismatch'),
    ({'quantity': True}, 'freight_scope_mismatch'),
    ({'quantity': 2}, 'freight_scope_mismatch'),
    ({'ship_to_country': 'FR'}, 'freight_scope_mismatch'),
    ({'currency': 'USD'}, 'freight_scope_mismatch'),
    ({'cost': '-1'}, 'freight_cost_invalid'),
    ({'cost': 'NaN'}, 'freight_cost_invalid'),
    ({'cost': 'Infinity'}, 'freight_cost_invalid'),
    ({'cost': None}, 'freight_cost_invalid'),
    ({'service_name': ''}, 'freight_service_unverified'),
    ({'quoted_at': None}, 'freight_timestamp_invalid'),
    ({'quoted_at': (NOW - timedelta(hours=25)).isoformat()}, 'freight_quote_stale'),
    ({'quoted_at': (NOW + timedelta(minutes=5)).isoformat()}, 'freight_quote_from_future'),
    ({'is_estimate': False, 'transaction_ready': True}, 'freight_evidence_level_invalid'),
])
def test_all_freight_quotes_must_match_current_sku_scope(hypothetical_listing, sku_index, change, blocker):
    f = hypothetical_listing
    sku = f['skus'][sku_index]
    f['quotes'][sku].update(change)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert blocker in result['blockers']
    if sku_index == 0:
        assert result['artifact'] is None  # No real anchor freight, no content plan call.
        assert not any(call[0] == 'read' for call in f['supplier'].calls)
    else:
        assert result['artifact']['st']['title'] == f['row']['title']
        assert sku not in result['artifact']['shipping_quotes']


def test_zero_freight_is_valid_not_a_fallback(hypothetical_listing):
    f = hypothetical_listing
    for quote in f['quotes'].values():
        quote['cost'] = Decimal('0')
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert len(result['artifact']['shipping_quotes']) == 2
    assert not any(b.startswith(('freight_cost_', 'freight_scope_', 'freight_unverified')) for b in result['blockers'])
    for variant in result['artifact']['st']['plan']['variants']:
        assert variant['price'] == f['pricing'].price_for(float(variant['cost']), 0.0)[0]


@pytest.mark.parametrize('scenario, reason', [
    ('risk_review', 'gate_review'), ('risk_block', 'gate_block'),
    ('category', 'category_unapproved'), ('aspects', 'category_aspects_incomplete'),
    ('images', 'gate_block'), ('identity', 'identity_mismatch'),
])
def test_full_content_gate_failures_are_returned_without_bypass(hypothetical_listing, monkeypatch, scenario, reason):
    f = hypothetical_listing
    from src.listing_quality import categories, gates, images
    if scenario.startswith('risk_'):
        monkeypatch.setattr(gates, 'evaluate', lambda *a, **kw: {
            'block': ['test-only-secret'] if scenario == 'risk_block' else [],
            'review': ['test-only-secret'] if scenario == 'risk_review' else []})
    elif scenario == 'category':
        monkeypatch.setattr(categories, 'resolve_for_product', lambda *a: {'category_id': '12345', 'needs_review': True})
    elif scenario == 'aspects':
        monkeypatch.setattr(categories, 'fill_aspects', lambda *a: ({}, ['test-only-secret']))
    elif scenario == 'images':
        monkeypatch.setattr(images, 'filter_urls', lambda urls: ([], urls))
    else:
        f['row']['title'] = 'Hypothetisches völlig anderes Produkt test-only-secret'
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'content_gate_failed:ValueError:' + reason in result['blockers']
    assert result['artifact'] is None
    assert 'test-only-secret' not in json.dumps(result)


@pytest.mark.parametrize('stage, blocker, has_content', [
    ('details', 'supplier_details_failed:RuntimeError', False),
    ('anchor_quote', 'freight_unavailable:RuntimeError', False),
    ('retained_quote', 'freight_unavailable:RuntimeError', True),
    ('plan', 'content_gate_failed:RuntimeError:content_unavailable', False),
])
def test_provider_failures_are_explicit_no_fallback_and_never_leak_errors(hypothetical_listing, monkeypatch, stage, blocker, has_content):
    f = hypothetical_listing
    def fail(*args, **kwargs):
        raise RuntimeError('hypothetical-secret-token-never-log')
    if stage == 'details':
        monkeypatch.setattr(f['supplier'], 'get_product_details', fail)
    elif stage in ('anchor_quote', 'retained_quote'):
        original = f['supplier'].get_shipping_quote
        def freight(pid, sku, **kwargs):
            if stage == 'anchor_quote' or sku == f['skus'][1]:
                return fail()
            return original(pid, sku, **kwargs)
        monkeypatch.setattr(f['supplier'], 'get_shipping_quote', freight)
    else:
        monkeypatch.setattr(f['publish'], 'plan_for', fail)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert blocker in result['blockers']
    assert (result['artifact'] is not None) == has_content
    assert 'hypothetical-secret-token-never-log' not in json.dumps(result, default=str)


@pytest.mark.parametrize('change, blocker', [
    ('raw_product_identity', 'content_source_product_identity_mismatch'),
    ('placeholder_sku', 'retained_sku_id_invalid'),
    ('missing_current_sku', 'variant_source_unverified'),
    ('changed_cost', 'variant_source_changed'),
    ('changed_stock', 'variant_source_changed'),
])
def test_retained_variants_require_matching_current_source_evidence(hypothetical_listing, change, blocker):
    f = hypothetical_listing
    if change == 'raw_product_identity':
        f['raw']['ae_item_base_info_dto']['product_id'] = '1005009999999'
    elif change == 'placeholder_sku':
        f['raw']['ae_item_sku_info_dtos']['ae_item_sku_info_d_t_o'][1]['sku_id'] = 'AUTO-TEST-PLACEHOLDER'
    elif change == 'missing_current_sku':
        f['details']['skus'].pop()
    elif change == 'changed_cost':
        f['details']['skus'][1]['sale_price'] = Decimal('14')
    else:
        f['details']['skus'][1]['warehouse_count'] = 4
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert blocker in result['blockers']
    assert result['artifact']['st']  # Source problems must not erase completed content.
    assert not any(call[0] == 'quote' and call[2] == 'AUTO-TEST-PLACEHOLDER' for call in f['supplier'].calls)


@pytest.mark.parametrize('outcome', ['review', 'unavailable'])
def test_changed_prices_must_pass_market_recheck_without_new_acknowledgement(hypothetical_listing, monkeypatch, outcome):
    f = hypothetical_listing
    from src.listing_quality import gates
    original = gates.demand
    calls = []
    def market(ebay, queries, our_price=None):
        calls.append(our_price)
        if len(calls) == 1:
            return original(ebay, queries, our_price)
        if outcome == 'unavailable':
            raise RuntimeError('test-only-secret-market')
        return {'listings_found': 0, 'our_price': our_price}, ['test-only-secret-market']
    monkeypatch.setattr(gates, 'demand', market)
    monkeypatch.setattr(gates, 'acknowledged', lambda pid: {})
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    expected = 'repriced_market_review_required' if outcome == 'review' else 'repriced_market_unavailable:RuntimeError'
    assert expected in result['blockers']
    assert result['artifact']['st']
    assert len(calls) == 2
    assert 'test-only-secret-market' not in json.dumps(result['blockers'])


def test_readiness_failures_keep_content_preview_and_cannot_be_overridden_by_flags(hypothetical_listing):
    f = hypothetical_listing
    readiness = report(generated_at=(NOW - timedelta(days=2)).isoformat())
    readiness['checks'][0]['passed'] = False
    f['row'].update(fulfillment_verified=1, supplier_agreement_verified=True,
                    product_compliance_verified=True, image_rights_verified=True)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=readiness, now=NOW)
    assert result['artifact']['st']
    assert {'readiness_report_stale', 'readiness_commercial_account_status',
            'supplier_agreement_missing', 'supplier_product_compliance_unverified',
            'image_rights_unverified'} <= set(result['blockers'])


@pytest.mark.parametrize('key', ['EBAY_FULFILLMENT_POLICY_ID', 'EBAY_PAYMENT_POLICY_ID',
                                'EBAY_RETURN_POLICY_ID', 'EBAY_MERCHANT_LOCATION_KEY'])
def test_missing_publication_context_blocks_without_discarding_content(hypothetical_listing, key):
    f = hypothetical_listing
    f['cfg'].pop(key)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'publication_context_incomplete' in result['blockers']
    assert result['artifact']['st']
    assert 'default-warehouse' not in json.dumps(result, default=str)


def test_artifact_fingerprint_is_canonical_and_excludes_credential_fields(hypothetical_listing):
    f = hypothetical_listing
    first = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    f['raw']['access_token'] = 'hypothetical-secret-for-test'
    f['raw']['ae_item_base_info_dto']['Authorization'] = 'hypothetical-secret-for-test'
    reversed_raw = dict(reversed(list(f['raw'].items())))
    f['raw'].clear()
    f['raw'].update(reversed_raw)
    second = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'hypothetical-secret-for-test' not in json.dumps(second, default=str)
    assert first['artifact']['source_fingerprint'] == second['artifact']['source_fingerprint']
    f['raw']['ae_item_base_info_dto']['detail'] += '<p>Weiterer hypothetischer Quelleninhalt.</p>'
    third = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert third['artifact']['source_fingerprint'] != second['artifact']['source_fingerprint']


@pytest.mark.parametrize('stage, expected', [
    ('price', 'variant_pricing_failed:ValueError'),
    ('config', 'preparation_config_unavailable:PermissionError'),
])
def test_post_content_failures_retain_offline_artifacts(hypothetical_listing, monkeypatch, stage, expected):
    f = hypothetical_listing
    if stage == 'price':
        def fail(*args, **kwargs):
            raise ValueError('test-only-secret-price')
        monkeypatch.setattr(f['pricing'], 'price_for', fail)
    else:
        def fail(*args, **kwargs):
            raise PermissionError('test-only-secret-config')
        monkeypatch.setattr(f['module'], 'config_fingerprint', fail)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert expected in result['blockers']
    assert result['artifact']['st']
    assert set(result['artifact']['shipping_quotes']) == set(f['skus'])
    assert 'test-only-secret' not in json.dumps(result, default=str)


def test_config_drift_during_preparation_invalidates_saved_content(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    original = f['publish'].plan_for
    def plan(*args, **kwargs):
        value = original(*args, **kwargs)
        f['cfg']['EBAY_PAYMENT_POLICY_ID'] = 'hypothetical-changed-during-plan'
        return value
    monkeypatch.setattr(f['publish'], 'plan_for', plan)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'preparation_config_changed' in result['blockers']
    assert result['artifact']['st']


@pytest.mark.parametrize('result_pair', [(float('nan'), 1), (1, float('inf')), (0, 0), (20, -1)])
def test_invalid_pricing_output_is_blocked_without_losing_content(hypothetical_listing, monkeypatch, result_pair):
    f = hypothetical_listing
    monkeypatch.setattr(f['pricing'], 'price_for', lambda *a, **kw: result_pair)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'variant_pricing_invalid' in result['blockers']
    assert result['artifact']['st']
    json.dumps(result, default=str, allow_nan=False)


def test_unreadable_publication_context_keeps_gated_draft(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    def fail():
        raise PermissionError('test-only-secret-context')
    monkeypatch.setattr(f['module'], 'publication_context', fail)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert 'publication_context_unavailable:PermissionError' in result['blockers']
    assert result['artifact']['st']
    assert 'test-only-secret-context' not in json.dumps(result, default=str)
