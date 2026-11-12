from src.listing_quality import gates


def test_brand_laser_and_fake_words_block():
    b, _ = gates.check_risk('Imitations-Originalhülle für iPhone 18 Pro Max', [])
    groups = {g for g, _ in b}
    assert 'brand_or_fake' in groups and 'brands' in groups
    b, _ = gates.check_risk('Katzenschlüsselanhänger mit Laserpointer', [])
    assert any(g == 'laser' for g, _ in b)


def test_clean_pet_toy_passes_and_electronics_need_review():
    b, r = gates.check_risk('Hundespielzeugball, ungiftiger, bissfester Spielzeugball', [('Material', 'Gummi')])
    assert b == [] and r == []
    b, r = gates.check_risk('Wireless Charging Pad 15W Ladegerät', [])
    assert b == [] and any(g == 'electronics_battery' for g, _ in r)


def test_title_rules():
    assert gates.check_title('Hundespielzeugball für Hunde') == []
    assert any('stop word' in p for p in gates.check_title('Spielzeugball für'))
    assert any('banned' in p for p in gates.check_title('Super Ball!!!'))
    assert any('stuffing' in p for p in gates.check_title('Ball Ball Ball Spielzeug Hund'))
    assert any('>' in p for p in gates.check_title('x' * 81))
    assert any('CAPS' in p for p in gates.check_title('SUPER GUENSTIG SCHNELL VERSAND JETZT KAUFEN'))


def test_review_needs_user_ack(monkeypatch):
    monkeypatch.setattr(gates, 'acknowledged', lambda pid: {'electronics_battery': 'CE geprueft'} if pid == '1' else {})
    r1 = gates.evaluate('1', 'Ladegerät USB', [])
    r2 = gates.evaluate('2', 'Ladegerät USB', [])
    assert r1['review'] == [] and r2['review']


class _E:
    def __init__(self, prices):
        self.prices = prices

    def _request(self, method, path, **kw):
        return {'itemSummaries': [{'itemId': str(i), 'price': {'value': str(p), 'currency': 'EUR'}} for i, p in enumerate(self.prices)]}


def test_demand_flags_overpriced_and_missing_market():
    info, rev = gates.demand(_E([5, 6, 7, 8, 9]), ['x'], our_price=35.0)
    assert info['median'] == 7 and rev and 'median' in rev[0]
    info, rev = gates.demand(_E([30, 33, 35]), ['x'], our_price=35.0)
    assert rev == []
    info, rev = gates.demand(_E([]), ['x'], our_price=35.0)
    assert rev and 'demand unknown' in rev[0]


def test_publish_plan_for_calls_gates_before_category():
    import inspect
    from src.listing_quality import publish
    src = inspect.getsource(publish.plan_for)
    assert src.index('GATE BLOCK') < src.index('resolve_for_product') and 'gates.demand' in src


def test_negative_properties_do_not_trigger_review():
    b, r = gates.check_risk('Hundespielzeugball', [('Ist elektrisch', 'Nein'), ('Batterie', 'Keine')])
    assert b == [] and r == []


def test_evaluate_does_not_title_check_supplier_title():
    res = gates.evaluate('9', 'x ' * 100, [])
    assert not any(b.startswith('title') for b in res['block'])
