"""Hata 29: auto_order_fulfillment.py (job_order_fulfillment, cron: mondeora-order-fulfillment,
hub-routed via src.jobs) has the same per-item isolation gap as listing-pipeline-fixes Hata 8.

_fulfill_order() prints `sale['title'][:50]` BEFORE entering its own try/except block. The
`sales.title` column has no NOT NULL constraint (see sales_tracker.py schema) and a sale row
can be written before product-title sync completes (same root cause already documented for
auto_customer_communication.py's order confirmation/shipping/feedback loops). When title is
NULL, `None[:50]` raises TypeError OUTSIDE the try block, and process_pending_orders()'s loop
has no try/except around the per-item call either -> ONE sale with a NULL title stops pending
AliExpress order-notification creation for ALL OTHER buyers in that run.
"""
import json
import sqlite3

import pytest

from auto_order_fulfillment import AutoOrderFulfillment


class _FakeAli:
    def get_product_details(self, product_id):
        return {'aeop_ae_product_s_k_us': {'aeop_ae_product_sku': [{'sku_available_stock': 99}]}}


class _FakeEbay:
    def get_order_details(self, order_id):
        return {
            'fulfillmentStartInstructions': [{
                'shippingStep': {'shipTo': {
                    'fullName': 'Max Mustermann',
                    'contactAddress': {
                        'addressLine1': 'Teststr. 1', 'addressLine2': '', 'city': 'Berlin',
                        'stateOrProvince': 'BE', 'postalCode': '10115', 'countryCode': 'DE',
                    },
                    'primaryPhone': {'phoneNumber': '+49123456'},
                }},
            }],
        }


def _make_fulfillment(monkeypatch, db_path):
    monkeypatch.setattr(AutoOrderFulfillment, '__init__', lambda self: None)
    f = AutoOrderFulfillment()
    f.db_path = str(db_path)
    f.ali = _FakeAli()
    f.ebay = _FakeEbay()
    f.fulfillment_log = str(db_path.parent / 'fulfillment_log.json')
    # Hata 30: redirect the pending-orders file to tmp_path so a real (non-error) fulfillment
    # path in this test can never append a fake test order into the LIVE data file that a
    # human operator reads to place real manual AliExpress orders.
    f.pending_orders_file = db_path.parent / 'pending_aliexpress_orders.jsonl'
    conn = sqlite3.connect(str(db_path))
    conn.execute('''CREATE TABLE order_fulfillment (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ebay_order_id TEXT UNIQUE NOT NULL,
        aliexpress_order_id TEXT, aliexpress_product_id TEXT, status TEXT,
        buyer_address TEXT, tracking_number TEXT, shipping_carrier TEXT,
        fulfillment_date DATETIME, delivery_date DATETIME, error_message TEXT,
        retry_count INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE products (sku TEXT, ebay_item_id TEXT, aliexpress_product_id TEXT)''')
    conn.execute("INSERT INTO products VALUES ('SKU-1','ITEM-1','ALI-1')")
    conn.execute("INSERT INTO products VALUES (NULL,'ITEM-2','ALI-2')")
    conn.execute("INSERT INTO products VALUES ('SKU-3','ITEM-3','ALI-3')")
    conn.commit()
    conn.close()
    return f


def test_one_null_title_sale_does_not_block_other_orders(monkeypatch, tmp_path):
    db_path = tmp_path / 'test.db'
    f = _make_fulfillment(monkeypatch, db_path)

    sales = [
        {'id': 1, 'order_id': 'ORD-1', 'ebay_item_id': 'ITEM-1', 'sku': 'SKU-1',
         'title': None, 'buyer_username': 'buyer1', 'sale_price': 9.99, 'quantity': 1},
        {'id': 2, 'order_id': 'ORD-2', 'ebay_item_id': 'ITEM-2', 'sku': None,
         'title': 'Normal product 2', 'buyer_username': 'buyer2', 'sale_price': 14.99, 'quantity': 1},
        {'id': 3, 'order_id': 'ORD-3', 'ebay_item_id': 'ITEM-3', 'sku': 'SKU-3',
         'title': 'Normal product 3', 'buyer_username': 'buyer3', 'sale_price': 4.99, 'quantity': 2},
    ]
    monkeypatch.setattr(f, '_get_unfulfilled_sales', lambda: sales)

    results = f.process_pending_orders()

    # BUG (pre-fix): a NULL title on ORD-1 raised TypeError outside _fulfill_order's try block,
    # so process_pending_orders() crashed and ORD-2 / ORD-3 were never attempted (len(results) < 3).
    assert len(results) == 3, f"expected all 3 sales attempted, got {results}"
    by_order = {r['order_id']: r for r in results}
    assert by_order['ORD-1']['success'] is True   # NULL title only affected a print(), order itself is fine
    assert by_order['ORD-2']['success'] is True
    assert by_order['ORD-3']['success'] is True


def test_real_unexpected_error_is_isolated_per_order(monkeypatch, tmp_path):
    """Regression guard: a genuine failure on one order must still be caught and must not
    stop the batch, distinguishing this from the narrower None-title fix above."""
    db_path = tmp_path / 'test.db'
    f = _make_fulfillment(monkeypatch, db_path)

    sales = [
        {'id': 1, 'order_id': 'ORD-BAD', 'ebay_item_id': 'ITEM-1', 'sku': 'SKU-1',
         'title': 'Will blow up', 'buyer_username': 'buyer1', 'sale_price': 9.99, 'quantity': 1},
        {'id': 2, 'order_id': 'ORD-GOOD', 'ebay_item_id': 'ITEM-3', 'sku': 'SKU-3',
         'title': 'Fine product', 'buyer_username': 'buyer2', 'sale_price': 4.99, 'quantity': 1},
    ]
    monkeypatch.setattr(f, '_get_unfulfilled_sales', lambda: sales)

    real_get_address = f._get_buyer_address

    def flaky_get_address(order_id):
        if order_id == 'ORD-BAD':
            raise RuntimeError('eBay API transport exploded')
        return real_get_address(order_id)

    monkeypatch.setattr(f, '_get_buyer_address', flaky_get_address)

    results = f.process_pending_orders()

    assert len(results) == 2
    by_order = {r['order_id']: r for r in results}
    assert by_order['ORD-BAD']['success'] is False
    assert by_order['ORD-GOOD']['success'] is True
