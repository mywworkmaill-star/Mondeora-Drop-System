"""Hata 26: automatic_sales_boost.py (root-level, bypasses src.jobs hub) - same Hata 8
per-item-isolation gap as engine.py/jobs.py, PLUS no safe dry-run default despite making
real live eBay price/shipping/best-offer/promoted-ad writes. See references/known-bugs.md.
"""
import inspect
import os
import sqlite3

import automatic_sales_boost as asb


def _make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE products (sku_id TEXT, title TEXT, ebay_item_id TEXT, "
        "ebay_price REAL, aliexpress_price REAL, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, datetime('now'))", rows
    )
    conn.commit()
    conn.close()


def test_boost_all_listings_isolates_bad_row(tmp_path, monkeypatch):
    """A NULL ebay_price row (the real shape that used to raise TypeError on
    '€{price:.2f}'.format(None)) must not block the other, healthy rows."""
    monkeypatch.delenv('SALES_BOOST_LIVE_CONFIRMED', raising=False)
    db_path = str(tmp_path / 'test.db')
    _make_db(db_path, [
        ('AUTO-PET-BAD', 'Bad Row', 'EBAYID-1', None, None),   # used to TypeError and kill the batch
        ('AUTO-PET-GOOD-1', 'Good Row 1', 'EBAYID-2', 19.99, 5.0),
        ('AUTO-PET-GOOD-2', 'Good Row 2', 'EBAYID-3', 29.99, 8.0),
    ])

    booster = asb.AutomaticSalesBooster()
    booster.db_path = db_path
    monkeypatch.chdir(tmp_path)

    booster.boost_all_listings()

    with open(tmp_path / 'data' / 'jobs' / 'last_sales_boost.json', encoding='utf-8') as f:
        import json
        status = json.load(f)

    assert status['total'] == 3
    # the NULL-price row must be float(None)-guarded -> price=0.0, NOT skipped/crashed,
    # and the 2 healthy rows processed normally (dry-run, so stats count "would-update").
    assert status['stats']['price_optimized'] >= 2
    assert status['dry_run'] is True


def test_dry_run_default_blocks_live_ebay_calls(monkeypatch, tmp_path):
    """Without SALES_BOOST_LIVE_CONFIRMED=true, optimize_price must never call self.ebay.call
    (the real PUT that moves live eBay prices) - dry-run must short-circuit before the network."""
    monkeypatch.delenv('SALES_BOOST_LIVE_CONFIRMED', raising=False)
    booster = asb.AutomaticSalesBooster()
    assert booster.dry_run is True

    calls = []
    booster.ebay.call = lambda *a, **k: calls.append((a, k))

    result = booster.optimize_price('SOME-SKU', 19.99, 5.0)
    assert result == round(19.99 * 0.85, 2)
    assert calls == []  # no live API call happened


def test_live_confirmed_env_flips_dry_run_off(monkeypatch):
    monkeypatch.setenv('SALES_BOOST_LIVE_CONFIRMED', 'true')
    booster = asb.AutomaticSalesBooster()
    assert booster.dry_run is False


def test_boost_all_listings_source_has_per_item_isolation():
    src = inspect.getsource(asb.AutomaticSalesBooster.boost_all_listings)
    assert 'except Exception as ex' in src
    assert 'skipped.append' in src
    idx = src.index('except Exception as ex')
    assert 'continue' in src[idx:idx + 300]
