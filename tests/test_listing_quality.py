from src.listing_quality import pricing, variants, description, publish, gates

CFG = {'fee_pct': 13.5, 'fixed_fee': 0.35}


def test_price_meets_min_profit_with_real_fee():
    """Minimum profit/margin are tiered by landed cost (cost+ship) - see pricing.TIERS."""
    for cost, ship in [(1.19, 1.99), (6.49, 1.99), (77.69, 1.99), (0.5, 0.0)]:
        min_profit, min_margin = pricing.tier_minimums(cost + ship)
        price, net = pricing.price_for(cost, ship, CFG)
        assert net >= min_profit and net / price >= min_margin
        assert round(price % 1, 2) == 0.99


def test_old_formula_misses_min_profit():
    old = int((1.19 + 1.99 + 25.35) / 0.90) + 0.99
    assert pricing.net_profit(old, 1.19, 1.99, CFG) < 25.0


def _res(skus):
    return {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': skus}}


def _sku(i, color, cost, stock):
    return {'sku_id': str(i), 'offer_sale_price': str(cost), 'currency_code': 'EUR', 'sku_available_stock': stock,
            'ae_sku_property_dtos': {'ae_sku_property_d_t_o': [
                {'sku_property_name': 'Farbe', 'sku_property_value': color, 'sku_property_id': 14, 'sku_image': 'https://x/i.jpg'}]}}


def test_each_variant_gets_its_own_price_and_oos_is_dropped():
    plan = variants.build('1', _res([_sku(1, 'Rot', 2.0, 5), _sku(2, 'Blau', 14.0, 5), _sku(3, 'Grün', 3.0, 0), _sku(4, 'Rot', 2.5, 5)]), 1.99, CFG)
    # Distinct supplier identities with the same colour may be different packs/models.
    # Retain them for review instead of silently selecting one supplier SKU.
    assert plan['is_variation'] and len(plan['variants']) == 3
    assert {d[1] for d in plan['dropped']} == {'out of stock'}
    assert {v['sku_id'] for v in plan['variants']} == {'1', '2', '4'}
    assert all(v['verified'] is False for v in plan['variants'] if v['aspects']['Farbe'] == 'Rot')
    assert 'ambiguous option combination across supplier SKUs: human review' in plan['flags']
    low, high = plan['variants'][0], plan['variants'][-1]
    assert high['price'] > low['price']
    assert all(v['net'] >= pricing.tier_minimums(v['cost'] + 1.99)[0] for v in plan['variants'])
    assert plan['flags']  # 14/2 = 7x spread -> review flag


def test_description_is_built_from_data():
    res = {'ae_item_properties': {'ae_item_property': [{'attr_name': 'Material', 'attr_value': 'Silikon'}]},
           'package_info_dto': {'package_length': 10, 'package_width': 5, 'package_height': 2, 'gross_weight': '0.04'},
           'ae_item_base_info_dto': {'detail': ''}}
    html = description.build('Testprodukt <b>', res, None)
    assert 'Silikon' in html and '10 x 5 x 2 cm' in html and '&lt;b&gt;' in html


def test_title_removes_foreign_language_and_spam():
    """make_title() should clean English/Spanish words and spam markers."""
    raw = "Neu Hot Sale Kabelorganizer 1pc Storage Bag Holder für Kabel NEW"
    title = publish.make_title(raw)
    assert 'Hot Sale' not in title
    assert 'NEW' not in title.upper() or title.count('Neu') <= 1
    assert '1pc' not in title
    assert 'Storage' not in title  # should be translated to Aufbewahrung or removed
    assert len(title) <= 80


def test_title_removes_keyword_stuffing():
    """make_title() should limit word repetition to max 2 occurrences."""
    raw = "Kabel Kabel Kabel Organizer Kabel Manager Kabel Halter"
    title = publish.make_title(raw)
    # "Kabel" should appear max 2 times
    assert title.lower().split().count('kabel') <= 2


def test_title_removes_emoji_and_banned_chars():
    """make_title() should strip emoji and banned characters."""
    raw = "Kabelorganizer 🔥 TOP! für Schreibtisch *NEU* <Angebot>"
    title = publish.make_title(raw)
    assert '🔥' not in title
    assert '!' not in title
    assert '*' not in title
    assert '<' not in title
    assert '>' not in title


def test_title_normalizes_excessive_caps():
    """make_title() should normalize if >40% of words are ALL CAPS."""
    raw = "KABEL ORGANIZER FÜR SCHREIBTISCH Halter Box"
    title = publish.make_title(raw)
    # Should be normalized to title case
    all_caps_count = sum(1 for w in title.split() if len(w) > 3 and w.isupper())
    total_words = len([w for w in title.split() if len(w) > 3 and w.isalpha()])
    if total_words > 0:
        assert all_caps_count / total_words <= 0.4


def test_title_enforces_80_char_limit():
    """make_title() should cut at word boundary before 80 chars."""
    raw = "A" * 100
    title = publish.make_title(raw)
    assert len(title) <= 80


def test_title_removes_stop_word_endings():
    """make_title() should not end with stop words like 'für', 'und', 'mit'."""
    raw = "Kabelorganizer für Schreibtisch für"
    title = publish.make_title(raw)
    assert not title.endswith('für')
    assert not title.endswith('und')
    assert not title.endswith('mit')


def test_title_passes_gates_check():
    """Generated title should pass gates.check_title() validation."""
    raw = "Kabelorganizer Schreibtisch Organizer Kabel Halter Box für Büro Zuhause"
    title = publish.make_title(raw)
    problems = gates.check_title(title)
    # Should have no major issues (no emoji, no excessive stuffing, <=80 chars, no stop ending)
    assert not any('emoji' in p for p in problems)
    assert not any('banned' in p for p in problems)
    assert not any('> 80' in p for p in problems)
