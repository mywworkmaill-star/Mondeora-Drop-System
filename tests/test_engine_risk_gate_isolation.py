"""Hata 36: sync_top_products_from_aliexpress()'s publish loop had every risky per-product step
wrapped in try/except (self._details()/validate_source_unit() -> Hata 34; the publish attempt ->
Hata 8) EXCEPT the risk-gate check (gates.check_risk/gates.acknowledged), which reloads
config/risk_rules.json and config/risk_ack.json from disk on every call with no guard at this
call site. A missing/locked/corrupt config file for ONE product's risk check aborted the whole
`for product in products:` loop, so every other already-vetted product in that run was never
even attempted.
"""
import inspect

from src.automation import engine


def test_risk_gate_call_is_isolated_per_product():
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    idx = src.index('_gates.check_risk')
    # the real try: sits ~427 chars before this call (a 4-line explanatory comment sits between
    # them) - use rindex('try:', ...) to find the real preceding try block instead of a fixed-size
    # window, which is brittle against comment-length changes (this test itself regressed on that).
    try_idx = src.rindex('try:', 0, idx)
    window = src[try_idx:idx + 400]
    assert 'try:' in window and 'except (OSError, ValueError)' in window
    assert 'continue' in window[window.index('except (OSError, ValueError)'):]


def test_risk_gate_failure_is_recorded_in_skipped_not_raised():
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    idx = src.index('except (OSError, ValueError) as _gate_ex')
    window = src[idx:idx + 200]
    assert 'skipped.append' in window
    assert 'raise' not in window
