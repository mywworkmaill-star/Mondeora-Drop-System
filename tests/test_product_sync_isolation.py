import inspect

from src.automation import engine


def test_sync_top_products_isolates_per_product_discovery_failures():
    # Hata 34: unlike its siblings (sync_inventory, analyze_competition_and_optimize_prices,
    # sync_ebay_orders_and_place_aliexpress_orders), the publish loop in
    # sync_top_products_from_aliexpress used to call self._details()/validate_source_unit()
    # with NO per-product try/except, so one stale/placeholder SKU or one bad supplier price
    # aborted the whole batch and silently starved every other, correctly-mapped product.
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    assert 'except ValueError as ex' in src and 'skipped.append' in src
    idx = src.index('except ValueError as ex')
    assert 'continue' in src[idx:idx + 700]


def test_sync_top_products_publish_failure_does_not_abort_batch():
    # Regression: the publish-attempt exception handler used to `raise` after marking the
    # product manual_review, which propagated out of the `for product in products:` loop and
    # killed every OTHER healthy product's publish attempt for the rest of that run.
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    handler = src[src.index("except Exception as ex:"):src.index("return {'status': 'success'")]
    assert 'raise' not in handler
    assert handler.strip().splitlines()[-1].strip() == 'continue'


def test_sync_top_products_reports_skipped_products():
    # The caller (job_product_sync / job_listing_pipeline) needs visibility into which
    # products were skipped and why, same shape as sync_inventory's 'skipped' list.
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    assert "'skipped': skipped" in src[src.index("return {'status': 'success'"):]


def test_sync_top_products_missing_content_does_not_raise():
    # A single product missing title/description/image_url must be skipped, not raise
    # ValueError and abort every other product queued for publish in this run.
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    idx = src.index("Listing content requires verification")
    window = src[max(0, idx - 200):idx + 200]
    assert "raise ValueError('Listing content requires verification')" not in window
    assert 'skipped.append' in window


def test_sync_top_products_live_writes_disabled_still_aborts_whole_run():
    # This one IS a global-state condition (live writes disabled for the whole job), not a
    # per-product data problem, so it must still propagate and stop the batch immediately —
    # confirms the fix did not accidentally swallow this too.
    src = inspect.getsource(engine.AutamationEngine.sync_top_products_from_aliexpress)
    assert "raise RuntimeError('Live writes disabled during job')" in src
