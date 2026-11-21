"""Offline hypothetical fixtures, never marketplace evidence."""
import copy
import pytest


def raw(cost='4.00', stock=5):
    return {'ae_item_base_info_dto': {'product_id': '1005000000000', 'subject': 'Geprüfter Halter', 'detail': '<p>Fakten</p>'},
            'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [
                {'sku_id': '2000000000001', 'offer_sale_price': cost, 'currency_code': 'EUR', 'sku_available_stock': stock}]}}


class Supplier:
    def __init__(self, current=None, freight=2):
        self.current, self.freight = current or raw(), freight

    def _request(self, name, params):
        assert name == 'aliexpress.ds.product.get'
        return {'result': self.current}

    def get_shipping_quote(self, pid, sku, **kwargs):
        return {'product_id': pid, 'sku_id': sku, 'currency': 'EUR', 'ship_to_country': 'DE',
                'quantity': 1, 'cost': self.freight, 'service_name': 'TRACKED'}


def test_freshness_rejects_cost_change_before_any_publication(monkeypatch):
    from src.listing_quality import ready_launch, listing_evidence
    # This transport/source test assumes a separately authenticated document review.
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    saved = artifact()
    saved['st']['res'] = raw()
    saved['shipping_quotes'] = {'2000000000001': Supplier().get_shipping_quote('1005000000000', '2000000000001')}
    assert ready_launch.validate_fresh(Supplier(), '1005000000000', saved) is None
    with pytest.raises(ValueError, match='changed'):
        ready_launch.validate_fresh(Supplier(raw(cost='8.00')), '1005000000000', saved)
    with pytest.raises(ValueError, match='stock'):
        ready_launch.validate_fresh(Supplier(raw(stock=0)), '1005000000000', saved)
    with pytest.raises(ValueError, match='freight'):
        ready_launch.validate_fresh(Supplier(freight=3), '1005000000000', saved)


def artifact():
    return {'st': {'title': 'Geprüfter Halter', 'desc': '<p>Gespeicherte Beschreibung</p>',
        'cat': {'category_id': '123456'}, 'shared': {'Material': ['Metall']},
        'imgs': ['https://example.invalid/photo.jpg'],
        'plan': {'is_variation': False, 'specifications': [], 'variants': [
            {'sku': 'AE-1005000000000-2000000000001', 'sku_id': '2000000000001',
             'aspects': {}, 'image': None, 'price': 29.99, 'cost': 4.00, 'qty': 2, 'net': 17.0}]}},
        'publication_context': {'fulfillmentPolicyId': '111111', 'paymentPolicyId': '222222',
                                'returnPolicyId': '333333', 'merchantLocationKey': 'tested-location'}}


def test_compile_uses_saved_content_and_exact_policy_ids():
    from src.listing_quality import ready_launch
    payloads = ready_launch.compile_payloads('1005000000000', artifact())
    inventory = payloads['items'][0]['body']
    assert inventory['product']['title'] == 'Geprüfter Halter'
    assert inventory['product']['description'] == '<p>Gespeicherte Beschreibung</p>'
    assert inventory['availability']['shipToLocationAvailability']['quantity'] == 2
    offer = payloads['offers'][0]['body']
    assert offer['merchantLocationKey'] == 'tested-location'
    assert offer['listingPolicies']['paymentPolicyId'] == '222222'
    assert offer['pricingSummary']['price'] == {'value': '29.99', 'currency': 'EUR'}
    assert payloads['group'] is None


class FakeApi:
    """Test transport only; no HTTP."""
    def __init__(self, fail_publish=False, existing=False):
        self.calls, self.items, self.offers = [], {}, {}
        self.fail_publish, self.existing = fail_publish, existing

    def call(self, method, path, body=None, params=None):
        self.calls.append((method, path))
        if path.endswith('/offer') and method == 'GET':
            return {'offers': ([{'offerId': 'existing'}] if self.existing else [])}
        if '/inventory_item/' in path:
            if method == 'PUT': self.items[path] = body; return {}
            return self.items[path]
        if path.endswith('/offer') and method == 'POST':
            self.offers['123'] = dict(body, offerId='123', status='UNPUBLISHED')
            return {'offerId': '123'}
        if path.endswith('/offer/123'):
            return self.offers['123']
        if path.endswith('/offer/123/publish'):
            if self.fail_publish: raise TimeoutError('Ambiguous test timeout')
            self.offers['123'].update(status='PUBLISHED', listing={'listingId': '860000000001'})
            return {'listingId': '860000000001'}
        raise AssertionError((method, path))


def test_publish_saved_payloads_reads_back_exact_target(monkeypatch):
    from src.listing_quality import ready_launch, listing_evidence
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    saved = artifact()
    saved['payloads'] = ready_launch.compile_payloads('1005000000000', saved)
    api = FakeApi()
    result = ready_launch.execute(None, '1005000000000', saved, api=api)
    assert result['listing_id'] == '860000000001'
    assert result['sell_readback_verified'] is True
    assert sum(method == 'POST' and path.endswith('/publish') for method, path in api.calls) == 1


def test_publish_ambiguous_failure_does_not_retry_or_delete(monkeypatch):
    from src.listing_quality import ready_launch, listing_evidence
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    saved = artifact()
    saved['payloads'] = ready_launch.compile_payloads('1005000000000', saved)
    api = FakeApi(fail_publish=True)
    with pytest.raises(TimeoutError):
        ready_launch.execute(None, '1005000000000', saved, api=api)
    assert not any(method == 'DELETE' for method, _ in api.calls)
    assert sum(method == 'POST' and path.endswith('/publish') for method, path in api.calls) == 1


def test_existing_offer_stops_before_any_new_write(monkeypatch):
    from src.listing_quality import ready_launch, listing_evidence
    monkeypatch.setattr(listing_evidence, 'validate_saved', lambda *a, **kw: {})
    saved = artifact()
    saved['payloads'] = ready_launch.compile_payloads('1005000000000', saved)
    api = FakeApi(existing=True)
    with pytest.raises(ValueError, match='reconciliation'):
        ready_launch.execute(None, '1005000000000', saved, api=api)
    assert all(method == 'GET' for method, _ in api.calls)
