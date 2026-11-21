"""Hypothetical local records: legacy display SKUs are not supplier identities."""
import pytest
from sqlalchemy import create_engine
from src.database.models import Base, Product, get_session
from src import readiness


@pytest.mark.parametrize('product_id,sku_id,expected', [
    ('1000000000000001', 'AUTO-PHONE-1000000000000001', False),
    ('MANUAL-PHONE-CASE', '1200000000000001', False),
    ('1000000000000001', ' 1200000000000001', False),
    ('1000000000000001', '1200000000000001', True),
])
def test_only_exact_supplier_ids_count_as_vetted(tmp_path, monkeypatch, product_id, sku_id, expected):
    db = create_engine('sqlite:///' + str(tmp_path / 'hypothetical.sqlite'))
    Base.metadata.create_all(db)
    with get_session(db) as session:
        session.add(Product(aliexpress_product_id=product_id, sku_id=sku_id,
                            fulfillment_verified=True, category_id='123456',
                            shipping_cost=0.0, currency='EUR'))
        session.commit()
        assert session.query(Product).count() == 1
    monkeypatch.setattr(readiness, 'read_config', lambda: {})
    monkeypatch.setattr(readiness, 'init_database', lambda: db)
    monkeypatch.setattr(readiness, 'probe_payment_execution', lambda **kw: {'passed': False})
    report = readiness.build_report(live=False)
    check = next(c for c in report['checks'] if c['name'] == 'vetted_products')
    assert check['passed'] is expected
    assert check['detail']['verified_with_required_mapping'] == (1 if expected else 0)
    assert check['detail']['invalid_local_supplier_identity'] == (0 if expected else 1)
