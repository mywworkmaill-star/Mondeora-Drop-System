"""Guard + new-listing tests (no network)."""
from src.listing_quality import publish


def test_apply_signature_supports_new_product_without_old_listing():
    import inspect
    sig = inspect.signature(publish.apply)
    assert 'extra_aspects' in sig.parameters and sig.parameters['old_sku'].default is inspect._empty
    src = inspect.getsource(publish.apply)
    assert 'if old_sku else None' in src and 'if old:' in src        # no old listing -> nothing to withdraw


def test_list_new_never_falls_back_to_single_sku():
    import inspect
    src = inspect.getsource(publish.list_new)
    assert "status='manual_review'" in src and 'list_product_fixed_price' not in src


def test_engine_skips_multi_variant_products():
    import inspect
    from src.automation.engine import AutamationEngine
    src = inspect.getsource(AutamationEngine.sync_top_products_from_aliexpress)
    assert 'needs_variation_listing' in src
    assert src.index('needs_variation_listing') < src.index("payload = {'sku'")   # guard runs BEFORE the single-SKU payload


def test_engine_runs_risk_gate_before_single_sku_payload():
    import inspect
    from src.automation.engine import AutamationEngine
    src = inspect.getsource(AutamationEngine.sync_top_products_from_aliexpress)
    assert src.index('check_risk') < src.index("payload = {'sku'") and "'manual_review'" in src


def test_revise_in_place_widens_group_before_items_and_restores():
    import inspect
    from src.listing_quality import publish
    src = inspect.getsource(publish.revise_in_place)
    assert src.index('grp_super') < src.index("api.call('PUT', f'/sell/inventory/v1/inventory_item/{sku}'")   # group first
    assert "previous content restored" in src


def test_group_listings_are_withdrawn_as_one_unit():
    import inspect
    from src.listing_quality import publish
    src = inspect.getsource(publish.recategorize)
    assert 'withdraw_by_inventory_item_group' in src
