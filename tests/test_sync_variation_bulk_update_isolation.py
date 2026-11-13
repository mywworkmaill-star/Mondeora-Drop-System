"""Hata 36: src/listing_quality/sync.py (variation_sync job) had one unguarded step inside an
otherwise fully-isolated loop - api.call('POST', '.../bulk_update_price_quantity', ...) was never
wrapped in try/except, unlike the fetch_raw/build step above it and the per-SKU offer lookup
below it in the same function. A single chunk's bulk update failing (eBay 4xx/5xx, malformed
response) propagated straight out of `run()`, aborting every OTHER variation-group product still
queued in that day's run - the exact per-item isolation gap catalogued as Hata 8/34.
"""
import sqlite3

from src.listing_quality import sync


def _make_db(path, products):
    db = sqlite3.connect(path)
    db.execute('''create table products (id integer primary key, aliexpress_product_id text,
                  is_listed integer, shipping_cost real)''')
    db.execute('''create table product_variants (id integer primary key, product_id integer,
                  sku text, price real, qty integer, updated_at text)''')
    for p in products:
        db.execute('insert into products (id, aliexpress_product_id, is_listed, shipping_cost) values (?,?,1,1.99)',
                   (p['id'], p['pid']))
        for v in p['variants']:
            db.execute('insert into product_variants (product_id, sku, price, qty) values (?,?,?,?)',
                       (p['id'], v['sku'], v['price'], v['qty']))
    db.commit()
    return db


class _FakeAli:
    """fetch_raw/variants.build both read from this via source.fetch_raw(ali, pid)."""


class _FailingApi:
    """Succeeds for product 1's chunk, raises for product 2's chunk (simulating one bad eBay response)."""
    def __init__(self):
        self.calls = []

    def call(self, method, path, body=None, params=None):
        self.calls.append((method, path))
        if method == 'GET':
            return {'offers': [{'offerId': 'OFFER-' + params['sku']}]}
        # POST bulk_update_price_quantity
        skus_in_request = [r['sku'] for r in body['requests']]
        if 'BAD-SKU' in skus_in_request:
            raise RuntimeError('eBay 500: bulk_update_price_quantity failed')
        return {'responses': [{'sku': s, 'statusCode': 200} for s in skus_in_request]}


def test_one_chunk_bulk_update_failure_does_not_abort_other_products(monkeypatch, tmp_path):
    db_path = str(tmp_path / 'test.db')
    db = _make_db(db_path, [
        {'id': 1, 'pid': 'P1', 'variants': [{'sku': 'BAD-SKU', 'price': 10.0, 'qty': 3}]},
        {'id': 2, 'pid': 'P2', 'variants': [{'sku': 'GOOD-SKU', 'price': 12.0, 'qty': 4}]},
    ])
    db.close()

    monkeypatch.setattr(sync.source, 'fetch_raw', lambda ali, pid: {'ae_item_base_info_dto': {'product_status_type': 'onSelling'}})
    monkeypatch.setattr(sync.variants, 'build', lambda pid, res, ship, legacy=False: {
        'variants': [{'sku': 'BAD-SKU' if pid == 'P1' else 'GOOD-SKU',
                      'price': 99.0, 'qty': 1}]})
    monkeypatch.setattr(sync.pricing, 'is_pinned', lambda pid: False)

    fake_api = _FailingApi()
    monkeypatch.setattr(sync.publish, 'Api', lambda ebay: fake_api)

    summary = sync.run(_FakeAli(), ebay=object(), db_path=db_path)

    # Product 1's chunk failed and must be recorded as an error, not raise out of run().
    assert summary['status'] == 'partial'
    assert any('BAD-SKU' in str(e) for e in summary['errors'])
    # Product 2 (processed AFTER the failing product 1 in id order) must still have been attempted
    # and succeeded - this is the actual isolation being tested.
    assert summary['updated_variants'] == 1
    assert ('POST', '/sell/inventory/v1/bulk_update_price_quantity') in fake_api.calls

    db2 = sqlite3.connect(db_path)
    row = db2.execute("select price, qty from product_variants where sku='GOOD-SKU'").fetchone()
    assert row == (99.0, 1)   # product 2 was actually updated despite product 1's chunk failing
    bad = db2.execute("select price, qty from product_variants where sku='BAD-SKU'").fetchone()
    assert bad == (10.0, 3)   # product 1's row was left untouched (update never confirmed)
