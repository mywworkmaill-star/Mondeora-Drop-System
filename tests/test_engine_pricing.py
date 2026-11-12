from src.automation import engine


def test_engine_has_no_old_ten_percent_formula():
    import inspect
    src = inspect.getsource(engine)
    assert '25.35' not in src and '/ 0.90' not in src
    assert 'pricing as _pricing' in src and 'price_for(_ali, _ship)' in src


def test_engine_price_always_calculated_not_kept_from_db():
    import inspect
    src = inspect.getsource(engine)
    assert 'float(product.ebay_price) > (_ali + _ship + 5)' not in src   # no "keep whatever price is there" shortcut
