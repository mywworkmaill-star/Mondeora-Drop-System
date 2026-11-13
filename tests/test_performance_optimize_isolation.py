"""Hata 25: auto_performance_optimization.py (cron: mondeora-performance-optimize, daily,
bypasses src.jobs hub entirely - not tracked in healing_state.json) had the same per-item
isolation gap as listing-pipeline-fixes Hata 8: _remove_dead_listings()/_optimize_prices()
loop over DB rows and call a raw sqlite3 UPDATE with no try/except AFTER a real eBay live
write already happened. One bad row (db lock, bad value) used to kill the whole run,
leaving: (a) every remaining listing in that batch unprocessed, (b) DB/eBay drift on the
item that blew up (eBay already changed, DB update never landed - see Hata 20).
"""
import sqlite3

import pytest

from auto_performance_optimization import AutoPerformanceOptimization


class _FakeEbayAlwaysSucceeds:
    def end_listing(self, item_id, reason=None):
        return True

    def update_price(self, sku, price):
        return True


def _make_opt(monkeypatch, db_path):
    monkeypatch.setattr(AutoPerformanceOptimization, '__init__', lambda self: None)
    opt = AutoPerformanceOptimization()
    opt.db_path = str(db_path)
    opt.ebay = _FakeEbayAlwaysSucceeds()
    monkeypatch.setattr('auto_performance_optimization._live_writes_allowed', lambda: True)
    return opt


def _seed_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE products (ebay_item_id TEXT, sku_id TEXT PRIMARY KEY,
                     title TEXT, status TEXT, created_at TEXT, ebay_price REAL,
                     aliexpress_price REAL, updated_at TEXT)""")
    conn.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, ebay_item_id TEXT)")
    for r in rows:
        conn.execute("INSERT INTO products VALUES (?,?,?,?,datetime('now','-40 days'),?,?,NULL)",
                      (r['ebay_item_id'], r['sku_id'], r['title'], 'active', r.get('ebay_price', 10.0),
                       r.get('aliexpress_price', 1.0)))
    conn.commit()
    conn.close()


def test_remove_dead_listings_one_bad_db_update_does_not_block_others(monkeypatch, tmp_path):
    db_path = tmp_path / 'test.db'
    _seed_db(db_path, [
        {'ebay_item_id': 'BAD', 'sku_id': 'SKU-BAD', 'title': 'Bad item'},
        {'ebay_item_id': 'GOOD-1', 'sku_id': 'SKU-GOOD-1', 'title': 'Good item 1'},
        {'ebay_item_id': 'GOOD-2', 'sku_id': 'SKU-GOOD-2', 'title': 'Good item 2'},
    ])
    opt = _make_opt(monkeypatch, db_path)

    real_update = opt._update_product_status

    def flaky_update(sku, new_status):
        if sku == 'SKU-BAD':
            raise sqlite3.OperationalError('database is locked')
        return real_update(sku, new_status)

    monkeypatch.setattr(opt, '_update_product_status', flaky_update)

    removed = opt._remove_dead_listings()

    # both good items survived the bad one blowing up
    assert removed == 2
    conn = sqlite3.connect(str(db_path))
    statuses = dict(conn.execute("SELECT sku_id, status FROM products").fetchall())
    conn.close()
    assert statuses['SKU-GOOD-1'] == 'REMOVED_LOW_PERFORMANCE'
    assert statuses['SKU-GOOD-2'] == 'REMOVED_LOW_PERFORMANCE'
    # the bad row's eBay listing was already ended live, but its DB status write failed -
    # this is now a VISIBLE drift (still 'active' in DB) rather than a silently aborted run.
    assert statuses['SKU-BAD'] == 'active'


def test_run_optimization_one_stage_failing_does_not_block_other_stages(monkeypatch, tmp_path):
    db_path = tmp_path / 'test.db'
    _seed_db(db_path, [])
    opt = _make_opt(monkeypatch, db_path)

    def boom():
        raise RuntimeError('remove_dead_listings exploded')

    monkeypatch.setattr(opt, '_remove_dead_listings', boom)
    monkeypatch.setattr(opt, '_optimize_prices', lambda: 3)
    monkeypatch.setattr(opt, '_improve_titles', lambda: 0)

    results = opt.run_optimization()

    assert results['prices_optimized'] == 3   # other stage still ran despite stage 1 raising
    assert results['low_performers_removed'] == 0
    assert len(results['stage_errors']) == 1
    assert 'remove_dead_listings' in results['stage_errors'][0]
