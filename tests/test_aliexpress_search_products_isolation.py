"""Hata 36: search_products()'s per-item except only matched 3 narrow substrings
('business error', 'business-error', 'unsupported product schema'), so several outcomes
get_product_details() itself raises for ONE product's data shape alone - mismatched product ID,
unsupported/malformed SKU schema (see aliexpress_client.py:get_product_details) - and
_check_errors()'s generic 'business success=false' business-logic message still aborted the
whole discovery page instead of just skipping that one product. Signature/auth/token failures
(InvalidSignature, IllegalAccessToken, ...) are NOT per-item and must still propagate - this is
checked explicitly so the broadened match doesn't swallow a real systemic outage.
"""
from unittest.mock import patch

import pytest

from src.api.aliexpress_client import AliExpressAPIClient, AliExpressAPIError, AliExpressCapabilityError

_CFG = {
    'ALIEXPRESS_APP_KEY': 'key', 'ALIEXPRESS_APP_SECRET': 'secret',
    'ALIEXPRESS_ACCESS_TOKEN': 'tok', 'ALIEXPRESS_REFRESH_TOKEN': 'r',
    'ALIEXPRESS_SELLER_ID': '1',
}


def _client():
    with patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG)):
        return AliExpressAPIClient(session=object())


@pytest.mark.parametrize('message', [
    'aliexpress.ds.product.get: business success=false',
    'aliexpress.ds.product.get: mismatched product ID',
    'aliexpress.ds.product.get: unsupported SKU schema',
    'aliexpress.ds.product.get: malformed SKU record',
])
def test_per_item_data_shape_errors_are_skipped_not_fatal(monkeypatch, message):
    c = _client()
    monkeypatch.setattr(c, 'search_product_page', lambda *a, **k: {'products': [{'itemId': '1'}, {'itemId': '2'}]})

    calls = []
    def fake_details(pid):
        calls.append(pid)
        if pid == '1':
            raise AliExpressAPIError(message)
        return {'product_id': pid, 'ok': True}
    monkeypatch.setattr(c, 'get_product_details', fake_details)

    out = c.search_products('kw')
    assert calls == ['1', '2']          # product 2 was still attempted after product 1 failed
    assert out == [{'product_id': '2', 'ok': True}]   # only the healthy product is returned
    assert c._skipped_discovery == 1


@pytest.mark.parametrize('message', [
    'aliexpress.ds.product.get: InvalidSignature',
    'aliexpress.ds.product.get: IllegalAccessToken',
    'aliexpress.ds.product.get: InvalidAppKey',
])
def test_signature_and_auth_errors_still_abort_the_whole_page(monkeypatch, message):
    # These are NOT per-item (every remaining item would hit the same failure), so they must
    # keep propagating rather than being silently skipped product-by-product.
    c = _client()
    monkeypatch.setattr(c, 'search_product_page', lambda *a, **k: {'products': [{'itemId': '1'}, {'itemId': '2'}]})
    monkeypatch.setattr(c, 'get_product_details', lambda pid: (_ for _ in ()).throw(AliExpressAPIError(message)))

    with pytest.raises(AliExpressAPIError):
        c.search_products('kw')


def test_capability_error_still_aborts_the_whole_page(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, 'search_product_page', lambda *a, **k: {'products': [{'itemId': '1'}]})
    monkeypatch.setattr(c, 'get_product_details', lambda pid: (_ for _ in ()).throw(AliExpressCapabilityError('nope')))

    with pytest.raises(AliExpressCapabilityError):
        c.search_products('kw')
