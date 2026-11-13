"""Hata 27: auto_database_sync.py (root-level, invoked by src.jobs.job_db_sync -> real cron
`mondeora-db-sync`, nightly 01:00) grouped per-SKU eBay inventory_item/offer rows by listingId
to detect variation-group listings (>1 SKU sharing one listingId), representing the group with
its cheapest variant's price. A code comment claimed sync_ebay_to_database() would then skip
overwriting products.ebay_price for those grouped rows ("ebay_price alanini EZMEZ") - but the
actual price-diff/update branch never checked the is_variation_group flag, so it silently kept
overwriting products.ebay_price with the representative (min-variant) price every night anyway.
Real per-variant pricing is owned by job_variation_sync/product_variants (see engine.py
_has_variants()); this stomps a value other code may read for that product and causes nightly
false-positive "fiyat guncellendi" log noise. See references/known-bugs.md Hata 27.
"""
import sqlite3

import auto_database_sync as ads


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE products (
        id INTEGER PRIMARY KEY, ebay_item_id TEXT, sku_id TEXT, title TEXT, ebay_price REAL,
        status TEXT, aliexpress_product_id TEXT, currency TEXT, ebay_offer_id TEXT,
        category_id TEXT, created_at TEXT, updated_at TEXT)""")
    return conn


def _make_sync(monkeypatch, db_path):
    monkeypatch.setattr(ads.AutoDatabaseSync, '__init__', lambda self: None)
    sync = ads.AutoDatabaseSync()
    sync.db_path = db_path
    return sync


def test_variation_group_price_is_not_overwritten(monkeypatch, tmp_path):
    """A listing with >1 SKU sharing one listingId is a variation group: its representative
    (cheapest-variant) price must NOT clobber the products.ebay_price the DB already has - that
    field is owned by job_variation_sync for variant products, not by the nightly db_sync."""
    db_path = tmp_path / 'test.db'
    conn = _make_db(db_path)
    conn.execute("INSERT INTO products VALUES (1, 'GRP-1', 'AE-1', 'Grouped item', 25.0, "
                 "'AUTO_SYNCED', '1', 'EUR', 'OFFER-1', 'CAT-1', datetime('now'), datetime('now'))")
    conn.commit()
    conn.close()

    sync = _make_sync(monkeypatch, db_path)
    sync.sync_ebay_to_database.__func__  # sanity: method exists (not shadowed)

    monkeypatch.setattr(sync, 'get_ebay_active_listings', lambda: [
        {'ebay_item_id': 'GRP-1', 'sku': 'VAR-1-A', 'title': 'Grouped item',
         'ebay_price': 9.99, 'currency': 'EUR', 'quantity': 5, 'offer_id': 'OFFER-1',
         'category_id': 'CAT-1', 'sold_quantity': 0, 'image_urls': [],
         'is_variation_group': True, 'variant_count': 3},
    ])

    sync.sync_ebay_to_database()

    conn = sqlite3.connect(str(db_path))
    price = conn.execute("SELECT ebay_price FROM products WHERE ebay_item_id='GRP-1'").fetchone()[0]
    conn.close()
    assert price == 25.0  # untouched despite the eBay-side (grouped, cheapest-variant) 9.99


def test_non_variation_listing_price_is_still_updated(monkeypatch, tmp_path):
    """Regression guard for the fix above: a normal single-SKU listing (is_variation_group=False)
    must still get its products.ebay_price updated when eBay's price has genuinely changed."""
    db_path = tmp_path / 'test.db'
    conn = _make_db(db_path)
    conn.execute("INSERT INTO products VALUES (2, 'SINGLE-1', 'AE-2', 'Single item', 10.0, "
                 "'AUTO_SYNCED', '2', 'EUR', 'OFFER-2', 'CAT-2', datetime('now'), datetime('now'))")
    conn.commit()
    conn.close()

    sync = _make_sync(monkeypatch, db_path)
    monkeypatch.setattr(sync, 'get_ebay_active_listings', lambda: [
        {'ebay_item_id': 'SINGLE-1', 'sku': 'AE-2', 'title': 'Single item',
         'ebay_price': 14.5, 'currency': 'EUR', 'quantity': 5, 'offer_id': 'OFFER-2',
         'category_id': 'CAT-2', 'sold_quantity': 0, 'image_urls': [],
         'is_variation_group': False, 'variant_count': 1},
    ])

    sync.sync_ebay_to_database()

    conn = sqlite3.connect(str(db_path))
    price = conn.execute("SELECT ebay_price FROM products WHERE ebay_item_id='SINGLE-1'").fetchone()[0]
    conn.close()
    assert price == 14.5


def test_get_ebay_active_listings_groups_by_listing_id(monkeypatch):
    """Unit check on the grouping logic itself: 3 raw per-SKU offers sharing one listingId
    collapse into a single active_listings row flagged is_variation_group with the min price,
    while an unrelated single-SKU listingId stays its own (non-grouped) row."""
    sync = _make_sync(monkeypatch, 'unused.db')

    raw = [
        {'ebay_item_id': 'GRP-9', 'sku': 'VAR-9-A', 'ebay_price': 12.0},
        {'ebay_item_id': 'GRP-9', 'sku': 'VAR-9-B', 'ebay_price': 9.0},
        {'ebay_item_id': 'GRP-9', 'sku': 'VAR-9-C', 'ebay_price': 15.0},
        {'ebay_item_id': 'SOLO-1', 'sku': 'AE-3', 'ebay_price': 20.0},
    ]

    class _FakeEbay:
        def _request(self, *a, **k):
            raise AssertionError('network should not be hit in this grouping-only test')

    sync.ebay = _FakeEbay()

    # Exercise just the grouping block by re-implementing the call path up to it: patch the
    # per-SKU offer fetch loop by monkeypatching get_ebay_active_listings' inner dependency is
    # not practical (it's one method), so instead assert the grouping helper behavior directly
    # via the documented contract: call the real method with all_items short-circuited.
    def fake_request(method, path, params=None):
        if path == '/sell/inventory/v1/inventory_item':
            if params.get('offset', 0) == 0:
                return {'inventoryItems': [{'sku': e['sku']} for e in raw], 'total': len(raw)}
            return {'inventoryItems': []}
        if path == '/sell/inventory/v1/offer':
            sku = params['sku']
            entry = next(e for e in raw if e['sku'] == sku)
            return {'offers': [{
                'listing': {'listingId': entry['ebay_item_id'], 'listingStatus': 'ACTIVE', 'soldQuantity': 0},
                'pricingSummary': {'price': {'value': str(entry['ebay_price']), 'currency': 'EUR'}},
                'offerId': f"OFFER-{sku}", 'categoryId': 'CAT',
            }]}
        raise AssertionError(f'unexpected path {path}')

    sync.ebay = type('F', (), {'_request': staticmethod(fake_request)})()

    listings = sync.get_ebay_active_listings()
    by_id = {l['ebay_item_id']: l for l in listings}

    assert by_id['GRP-9']['is_variation_group'] is True
    assert by_id['GRP-9']['variant_count'] == 3
    assert by_id['GRP-9']['ebay_price'] == 9.0  # cheapest variant represents the group

    assert by_id['SOLO-1']['is_variation_group'] is False
    assert by_id['SOLO-1']['ebay_price'] == 20.0
