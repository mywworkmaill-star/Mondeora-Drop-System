"""Hata 13/22: AliExpress TOP client had NO retry/backoff at all (unlike eBay's
GET/PUT retry). All TOP calls are HTTP POST, so idempotency is classified by TOP
method name (_IDEMPOTENT_METHODS allowlist) instead of HTTP verb. Mirrors
tests/test_ebay_retry_backoff.py's GET/PUT vs POST/DELETE split.
"""
from unittest.mock import patch

from src.api.aliexpress_client import AliExpressAPIClient, AliExpressAPIError

_CFG = {
    'ALIEXPRESS_APP_KEY': 'key', 'ALIEXPRESS_APP_SECRET': 'secret',
    'ALIEXPRESS_ACCESS_TOKEN': 'tok', 'ALIEXPRESS_REFRESH_TOKEN': 'r',
    'ALIEXPRESS_SELLER_ID': '1',
}
class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(url)
        return self.responses.pop(0)


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_read_only_method_retries_on_5xx_then_succeeds():
    sess = _FakeSession([_Resp(503), _Resp(200, {'aliexpress_ds_product_get_response': {'ok': True}})])
    c = AliExpressAPIClient(session=sess)
    out = c._request('aliexpress.ds.product.get', {'product_id': '1'})
    assert out == {'ok': True} and len(sess.calls) == 2


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_order_create_does_not_retry_on_500_ambiguous_side_effect():
    sess = _FakeSession([_Resp(500)])
    c = AliExpressAPIClient(session=sess)
    try:
        c._request('aliexpress.ds.order.create', {'order_lines': 'x'})
        assert False, 'should have raised'
    except AliExpressAPIError:
        pass
    # mutating method: 5xx is ambiguous (the order may have already been created
    # server-side), so it must never be blind-retried.
    assert len(sess.calls) == 1


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_order_create_does_retry_on_429_rate_limit_only():
    sess = _FakeSession([_Resp(429), _Resp(200, {'aliexpress_ds_order_create_response': {'ok': True}})])
    c = AliExpressAPIClient(session=sess)
    out = c._request('aliexpress.ds.order.create', {'order_lines': 'x'})
    assert out == {'ok': True} and len(sess.calls) == 2


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_read_only_method_gives_up_after_max_retries():
    sess = _FakeSession([_Resp(503)] * 5)
    c = AliExpressAPIClient(session=sess)
    try:
        c._request('aliexpress.ds.text.search', {'keywords': 'x'})
        assert False, 'should have raised'
    except AliExpressAPIError:
        pass
    assert len(sess.calls) == 4   # 1 try + 3 retries, then give up


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_transport_exception_retries_for_idempotent_method():
    import requests as _requests

    class _ExcSession:
        def __init__(self):
            self.calls = 0

        def post(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise _requests.ConnectionError('boom')
            return _Resp(200, {'aliexpress_ds_product_get_response': {'ok': True}})

    sess = _ExcSession()
    c = AliExpressAPIClient(session=sess)
    out = c._request('aliexpress.ds.product.get', {'product_id': '1'})
    assert out == {'ok': True} and sess.calls == 2


@patch('time.sleep', lambda *_: None)
@patch('src.api.aliexpress_client.dotenv_values', new=lambda *a, **k: dict(_CFG))
def test_transport_exception_does_not_retry_for_mutating_method():
    import requests as _requests

    class _ExcSession:
        def __init__(self):
            self.calls = 0

        def post(self, url, **kwargs):
            self.calls += 1
            raise _requests.ConnectionError('boom')

    sess = _ExcSession()
    c = AliExpressAPIClient(session=sess)
    try:
        c._request('aliexpress.ds.order.create', {'order_lines': 'x'})
        assert False, 'should have raised'
    except AliExpressAPIError:
        pass
    assert sess.calls == 1
