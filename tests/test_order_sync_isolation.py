import inspect

from src.automation import engine


def test_order_sync_isolates_per_order_failures():
    src = inspect.getsource(engine.AutamationEngine.sync_ebay_orders_and_place_aliexpress_orders)
    assert 'except (ValueError, KeyError, TypeError, AttributeError) as ex' in src
    assert "order_errors.append" in src
    # the bad-order handler must continue to the NEXT order, never re-raise and kill the whole batch
    idx = src.index('except (ValueError, KeyError, TypeError, AttributeError) as ex')
    assert 'continue' in src[idx:idx + 1000]
    assert 'order_errors' in src[src.index('return {'):]


def test_order_sync_purchase_ambiguity_breaks_this_order_not_the_whole_batch():
    # Regression: the per-line purchase exception handler used to `raise` after marking manual_review,
    # which propagated out of the per-order try and killed every OTHER paid customer's order that run.
    src = inspect.getsource(engine.AutamationEngine.sync_ebay_orders_and_place_aliexpress_orders)
    handler = src[src.index("except Exception as exc:"):src.index("if header:")]
    assert 'break' in handler
    assert handler.strip().splitlines()[-1].strip().startswith('break')
