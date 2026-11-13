"""Hata 28: auto_database_sync.py:get_database_products() keyed its dict by ebay_item_id.
Multiple products rows can legitimately have ebay_item_id IS NULL at once (discovered/
needs_variation_listing/manual_review products not yet published). Keying a plain dict by that
column collapsed ALL of them into a single `products[None]` entry (last-write-wins), which:

  1. Hid every other NULL-ebay_item_id row from sync_ebay_to_database() entirely.
  2. Made a genuinely-live eBay listing for one of those hidden products look "new" (no DB
     match by ebay_item_id), so the code tried to INSERT a second row for the same
     aliexpress_product_id and hit the UNIQUE constraint instead of backfilling the existing
     row's missing ebay_item_id.
  3. Caused the one surviving `products[None]` row to be wrongly marked DELISTED every run
     (`db_id not in ebay_item_ids` is trivially true for an unpublished product), via an
     `UPDATE ... WHERE ebay_item_id = ?` bound to Python None -> SQL `= NULL`, which never
     matches any row (SQL NULL semantics) - so the corruption was silently masked, but the
     logic was still wrong and the reported delisted_count was fabricated.

Fix: get_database_products() only indexes products[] by REAL (non-null) ebay_item_id and
additionally returns a self._db_products_by_ali_id reverse lookup (aliexpress_product_id ->
[row, ...]) used by sync_ebay_to_database() to backfill an existing NULL-ebay_item_id row
instead of inserting a duplicate or silently losing it. See references/known-bugs.md Hata 28.
"""
import sqlite3

import auto_database_sync as ads


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE products (
        id INTEGER PRIMARY KEY, ebay_item_id TEXT, sku_id TEXT, title TEXT, ebay_price REAL,
        status TEXT, aliexpress_product_id TEXT UNIQUE, currency TEXT, ebay_offer_id TEXT,
        category_id TEXT, created_at TEXT, updated_at TEXT)""")
    return conn


def _make_sync(monkeypatch, db_path):
    monkeypatch.setattr(ads.AutoDatabaseSync, '__init__', lambda self: None)
    sync = ads.AutoDatabaseSync()
    sync.db_path = db_path
    return sync


def test_get_database_products_does_not_collapse_multiple_null_ebay_ids(monkeypatch, tmp_path):
    db_path = tmp_path / 'test.db'
    conn = _make_db(db_path)
    conn.execute("INSERT INTO products (ebay_item_id, title, status, aliexpress_product_id) "
                 "VALUES (NULL, 'Product A', 'manual_review', '1111111111')")
    conn.execute("INSERT INTO products (ebay_item_id, title, status, aliexpress_product_id) "
                 "VALUES (NULL, 'Product B', 'active', '2222222222')")
    conn.execute("INSERT INTO products (ebay_item_id, title, status, aliexpress_product_id) "
                 "VALUES ('REAL-1', 'Product C', 'AUTO_SYNCED', '3333333333')")
    conn.commit()
    conn.close()

    sync = _make_sync(monkeypatch, db_path)
    products = sync.get_database_products()

    # Only the real (non-null) ebay_item_id is a dict key.
    assert list(products.keys()) == ['REAL-1']
    # But BOTH null-keyed rows are still reachable via the ali_id reverse lookup.
    assert sync._db_products_by_ali_id['1111111111'][0]['title'] == 'Product A'
    assert sync._db_products_by_ali_id['2222222222'][0]['title'] == 'Product B'
    assert sync._db_total_rows == 3


def test_new_live_listing_backfills_existing_null_row_instead_of_inserting_duplicate(monkeypatch, tmp_path):
    """The exact live scenario hit on 2026-11-13: a product already exists with
    ebay_item_id=NULL and a real aliexpress_product_id; eBay now reports an ACTIVE listing for
    that same AliExpress product under a real listingId. The sync must UPDATE (backfill) the
    existing row, not attempt a second INSERT (which would violate the UNIQUE constraint)."""
    db_path = tmp_path / 'test.db'
    conn = _make_db(db_path)
    conn.execute("INSERT INTO products (ebay_item_id, sku_id, title, ebay_price, status, "
                 "aliexpress_product_id) VALUES (NULL, '12000038378199786', 'Hundeleine', NULL, "
                 "'active', '1005006807226688')")
    conn.commit()
    conn.close()

    sync = _make_sync(monkeypatch, db_path)
    monkeypatch.setattr(sync, 'get_ebay_active_listings', lambda: [
        {'ebay_item_id': '860133993419', 'sku': 'VAR-1005006807226688-1', 'title': 'Hundeleine',
         'ebay_price': 12.99, 'currency': 'EUR', 'quantity': 5, 'offer_id': 'OFFER-X',
         'category_id': 'CAT-1', 'sold_quantity': 0, 'image_urls': [], 'is_variation_group': False},
    ])

    result = sync.sync_ebay_to_database()

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT ebay_item_id, ebay_price, status FROM products "
                         "WHERE aliexpress_product_id='1005006807226688'").fetchall()
    conn.close()

    # Exactly one row for this product - no duplicate was inserted.
    assert len(rows) == 1
    assert rows[0][0] == '860133993419'  # backfilled, not left NULL
    assert rows[0][1] == 12.99
    assert rows[0][2] == 'AUTO_SYNCED'
    assert result['added'] == 0
    assert result['updated'] == 1
    assert result['delisted'] == 0


def test_unpublished_products_are_never_marked_delisted(monkeypatch, tmp_path):
    """A product with ebay_item_id IS NULL was never published, so "not found on eBay" is
    meaningless for it - it must never be flipped to DELISTED by this sync, regardless of what
    eBay's active-listing list contains."""
    db_path = tmp_path / 'test.db'
    conn = _make_db(db_path)
    conn.execute("INSERT INTO products (ebay_item_id, title, status, aliexpress_product_id) "
                 "VALUES (NULL, 'Not yet listed', 'needs_variation_listing', '4444444444')")
    conn.commit()
    conn.close()

    sync = _make_sync(monkeypatch, db_path)
    monkeypatch.setattr(sync, 'get_ebay_active_listings', lambda: [
        {'ebay_item_id': 'UNRELATED-1', 'sku': 'AE-9999999999', 'title': 'Other item',
         'ebay_price': 5.0, 'currency': 'EUR', 'quantity': 1, 'offer_id': 'OFFER-Y',
         'category_id': 'CAT-2', 'sold_quantity': 0, 'image_urls': [], 'is_variation_group': False},
    ])

    result = sync.sync_ebay_to_database()

    conn = sqlite3.connect(str(db_path))
    status = conn.execute("SELECT status FROM products "
                           "WHERE aliexpress_product_id='4444444444'").fetchone()[0]
    conn.close()

    assert status == 'needs_variation_listing'  # untouched
    assert result['delisted'] == 0
