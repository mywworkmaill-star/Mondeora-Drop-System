from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.automation.engine import AutamationEngine as E
from src.database.models import Base, Product


def _session():
    eng = create_engine('sqlite://')
    Base.metadata.create_all(eng)
    s = Session(eng)
    s.execute(text('create table product_variants (id integer primary key, product_id integer, sku text unique, '
                   'ali_sku_id text, aspects text, cost real, price real, qty integer, updated_at text)'))
    p = Product(aliexpress_product_id='1005', ebay_item_id='999', sku_id='111', title='t', is_listed=True,
                currency='EUR', category_id='1', fulfillment_verified=True)
    s.add(p); s.commit()
    s.execute(text("insert into product_variants (product_id, sku, ali_sku_id) values (:p,'AE-1005-111','111'),(:p,'AE-1005-222','222')"),
              {'p': p.id})
    s.commit()
    return s, p


def test_variant_sku_resolves_to_product_and_ordered_variant():
    s, p = _session()
    line = {'sku': 'AE-1005-222', 'legacyItemId': '999'}
    prod = E._resolve_product(s, line)
    assert prod is not None and prod.id == p.id
    view = E._variant_view(s, prod, line)
    assert view.sku_id == '222' and view.aliexpress_product_id == '1005'   # ordered variant, not the cheapest
    assert p.sku_id == '111'                                                # ORM row untouched
    try:
        view.sku_id = 'x'
        assert False
    except AttributeError:
        pass


def test_unregistered_variant_sku_is_not_guessed():
    s, _ = _session()
    assert E._resolve_product(s, {'sku': 'AE-1005-333', 'legacyItemId': '999'}) is None   # would buy wrong variant


def test_legacy_sku_and_wrong_listing_unchanged():
    s, p = _session()
    s.add(Product(aliexpress_product_id='2000', ebay_item_id='888', sku_id='5', title='x', is_listed=True))
    s.commit()
    assert E._resolve_product(s, {'sku': 'AE-2000', 'legacyItemId': '888'}).aliexpress_product_id == '2000'
    assert E._resolve_product(s, {'sku': 'AE-1005-111', 'legacyItemId': '000'}) is None


def test_has_variants():
    s, p = _session()
    assert E._has_variants(s, p) is True
