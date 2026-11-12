from src.listing_quality import diagnostics


def test_find_stale_sku_ids_detects_placeholder_patterns(tmp_path):
    import sqlite3
    db_path = str(tmp_path / 't.db')
    db = sqlite3.connect(db_path)
    db.execute('create table products (id integer primary key, title text, aliexpress_product_id text, '
               'sku_id text, is_listed integer)')
    db.executemany('insert into products (title, aliexpress_product_id, sku_id, is_listed) values (?,?,?,1)', [
        ('real one', '1', '12000038678648271'),
        ('legacy auto', '2', 'AUTO-PET-1005007756879885'),
        ('legacy var', '3', 'VAR-1005013457960792-1'),
    ])
    db.commit()
    out = diagnostics.find_stale_sku_ids(db_path)
    assert {r['id'] for r in out} == {2, 3}
    assert all(r['code'] == diagnostics.STALE_SKU_ID for r in out)


def test_diagnose_maps_engine_sku_error_to_stale_sku_code():
    d = diagnostics.diagnose('Verified source SKU is missing or ambiguous')
    assert d['code'] == diagnostics.STALE_SKU_ID and 'AliExpress' in d['advice']
