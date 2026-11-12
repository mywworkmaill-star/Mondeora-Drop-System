import sqlite3

import pytest

import auto_inventory_sync as inv
import auto_performance_optimization as perf
import autonomous_scheduler_FULL as sched


class FakeEbay:
    def __init__(self, result=True):
        self.calls, self.result = [], result

    def end_listing(self, item_id, reason=None):
        self.calls.append(('end', item_id)); return self.result

    def update_price(self, sku, price):
        self.calls.append(('price', sku, price)); return self.result


class FakeAli:
    def __init__(self, stock=5, price=10.0, skus=1):
        self.stock, self.price, self.n = stock, price, skus

    def get_product_details(self, pid):
        return {'skus': [{'sku_id': str(i), 'warehouse_count': self.stock, 'sale_price': self.price,
                          'currency': 'EUR'} for i in range(self.n)]}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 't.db'
    c = sqlite3.connect(path)
    c.execute('create table products (id integer primary key, ebay_item_id text, sku_id text, aliexpress_product_id text,'
              ' title text, aliexpress_price real, ebay_price real, status text, updated_at text, created_at text)')
    c.execute("insert into products values (1,'111','SKU-1','999','Title',10.0,45.0,'active',null,'2020-01-01')")
    c.commit(); c.close()
    return str(path)


def make(cls, db, ebay, ali=None):
    obj = cls.__new__(cls)
    obj.db_path, obj.ebay = db, ebay
    if ali is not None:
        obj.ali = ali
    return obj


def status(db):
    return sqlite3.connect(db).execute('select status, ebay_price from products').fetchone()


def allow(monkeypatch, value):
    monkeypatch.setattr(inv, '_live_writes_allowed', lambda: value)
    monkeypatch.setattr(perf, '_live_writes_allowed', lambda: value)


def test_inventory_never_writes_when_live_disabled(db, monkeypatch):
    allow(monkeypatch, False)
    ebay = FakeEbay()
    s = make(inv.AutoInventorySync, db, ebay, FakeAli(stock=0))
    s.run_daily_sync()
    assert ebay.calls == [] and status(db)[0] == 'active'


def test_inventory_out_of_stock_ends_listing_and_updates_db(db, monkeypatch):
    allow(monkeypatch, True)
    ebay = FakeEbay()
    make(inv.AutoInventorySync, db, ebay, FakeAli(stock=0)).run_daily_sync()
    assert ebay.calls == [('end', '111')] and status(db)[0] == 'OUT_OF_STOCK'


def test_inventory_db_not_marked_when_ebay_refuses(db, monkeypatch):
    allow(monkeypatch, True)
    ebay = FakeEbay(result=False)
    make(inv.AutoInventorySync, db, ebay, FakeAli(stock=0)).run_daily_sync()
    assert status(db)[0] == 'active'


def test_inventory_price_update_uses_sku_and_keeps_min_profit(db, monkeypatch):
    allow(monkeypatch, True)
    monkeypatch.setattr(inv, '_floor_price', lambda cost: round((cost + 25) / 0.865, 2))
    ebay = FakeEbay()
    make(inv.AutoInventorySync, db, ebay, FakeAli(stock=5, price=12.0)).run_daily_sync()
    kind, sku, price = ebay.calls[0]
    assert (kind, sku) == ('price', 'SKU-1') and price >= round((12 + 25) / 0.865, 2)


def test_inventory_ambiguous_multi_sku_changes_nothing(db, monkeypatch):
    allow(monkeypatch, True)
    ebay = FakeEbay()
    make(inv.AutoInventorySync, db, ebay, FakeAli(stock=0, skus=2)).run_daily_sync()
    assert ebay.calls == []


def test_performance_sql_runs_against_real_schema(db, monkeypatch):
    allow(monkeypatch, True)
    c = sqlite3.connect(db)
    c.execute('create table sales (id integer primary key, ebay_item_id text)'); c.commit(); c.close()
    ebay = FakeEbay()
    o = make(perf.AutoPerformanceOptimization, db, ebay)
    assert o.run_optimization()['low_performers_removed'] == 1
    assert ebay.calls[0] == ('end', '111') and status(db)[0] == 'REMOVED_LOW_PERFORMANCE'


def test_token_check_interval_beats_token_lifetime():
    lifetime = 7200
    assert sched.TOKEN_CHECK_INTERVAL_MINUTES * 60 + sched.TOKEN_REFRESH_THRESHOLD_SECONDS < lifetime


def test_risky_legacy_jobs_are_gated(monkeypatch):
    for name in ('run_auto_product_listing', 'run_order_fulfillment', 'run_tracking_update',
                 'run_customer_communication', 'run_social_media_automation',
                 'run_improvement_cycle', 'run_expansion_cycle'):
        assert name in sched.JOB_GATES
    ran = []
    gated = sched._gated(lambda self: ran.append(1), 'x', lambda: False)
    gated(None)
    assert ran == []
    sched._gated(lambda self: ran.append(1), 'x', lambda: True)(None)
    assert ran == [1]
