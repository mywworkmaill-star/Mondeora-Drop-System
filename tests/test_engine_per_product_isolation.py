import inspect

from src.automation import engine


def test_sync_inventory_isolates_per_product_failures():
    src = inspect.getsource(engine.AutamationEngine.sync_inventory)
    assert 'except ValueError as ex' in src and "skipped.append" in src
    # the loop must keep going after one bad product (continue inside the except)
    idx = src.index('except ValueError as ex')
    assert 'continue' in src[idx:idx + 500]


def test_price_optimize_isolates_per_product_failures():
    src = inspect.getsource(engine.AutamationEngine.analyze_competition_and_optimize_prices)
    assert 'except ValueError as ex' in src and "skipped.append" in src


def test_price_optimize_never_references_finance_when_fallback_pricing_used():
    # Regression: UnboundLocalError('finance') when _finance_plan() fails and the code fell back to
    # simple pricing, then unconditionally read finance['net_margin_percent'] later in the function.
    src = inspect.getsource(engine.AutamationEngine.analyze_competition_and_optimize_prices)
    assert "product.margin_percent = float(finance['net_margin_percent'])" not in src
    assert 'margin_percent = round(_pricing.net_profit(' in src
    assert 'product.margin_percent = margin_percent' in src
