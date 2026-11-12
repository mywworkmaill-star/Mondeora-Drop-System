from unittest.mock import patch

from src.api.ebay_client import EBayAPIError, eBayAPIClient


class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.content = b'{}'
        self.headers = {}

    def json(self):
        return self._body


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append(method)
        return self.responses.pop(0)


def _client(session):
    return eBayAPIClient(session=session, config={'EBAY_ACCESS_TOKEN': 'tok'})


@patch('time.sleep', lambda *_: None)
def test_put_retries_on_503_then_succeeds():
    sess = _FakeSession([_Resp(503), _Resp(200, {'ok': True})])
    c = _client(sess)
    out = c._request('PUT', '/sell/inventory/v1/inventory_item/x', json={})
    assert out == {'ok': True} and sess.calls == ['PUT', 'PUT']


@patch('time.sleep', lambda *_: None)
def test_post_does_not_retry_on_500_ambiguous_side_effect():
    sess = _FakeSession([_Resp(500)])
    c = _client(sess)
    try:
        c._request('POST', '/sell/inventory/v1/offer/x/publish', json={})
        assert False, 'should have raised'
    except EBayAPIError:
        pass
    assert sess.calls == ['POST']   # no retry: POST + 5xx is ambiguous, must not be retried blindly


@patch('time.sleep', lambda *_: None)
def test_post_does_retry_on_429_rate_limit_only():
    sess = _FakeSession([_Resp(429), _Resp(200, {'ok': True})])
    c = _client(sess)
    out = c._request('POST', '/sell/inventory/v1/offer/x/publish', json={})
    assert out == {'ok': True} and sess.calls == ['POST', 'POST']


@patch('time.sleep', lambda *_: None)
def test_get_gives_up_after_max_retries():
    sess = _FakeSession([_Resp(503)] * 5)
    c = _client(sess)
    try:
        c._request('GET', '/sell/inventory/v1/inventory_item/x')
        assert False, 'should have raised'
    except EBayAPIError:
        pass
    assert len(sess.calls) == 4   # 1 try + 3 retries, then give up
