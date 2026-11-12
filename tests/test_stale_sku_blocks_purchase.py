from src.automation.engine import AutamationEngine
from src.database.models import Product


def test_unverified_fulfillment_blocks_auto_purchase():
    # Products with a confirmed stale/placeholder sku_id must never be auto-purchased from the supplier —
    # fulfillment_verified=0 is the real gate _vetted() checks.
    e = AutamationEngine.__new__(AutamationEngine)
    p = Product(fulfillment_verified=0, aliexpress_product_id='1', sku_id='AUTO-X', category_id='1', currency='EUR')
    assert e._vetted(p) is False
