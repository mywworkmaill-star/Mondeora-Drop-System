from src.listing_quality import pricing, variants, description

CFG = {'fee_pct': 13.5, 'fixed_fee': 0.35, 'min_profit': 25.0, 'min_margin': 0.25}


def test_price_meets_min_profit_with_real_fee():
    for cost, ship in [(1.19, 1.99), (6.49, 1.99), (77.69, 1.99), (0.5, 0.0)]:
        price, net = pricing.price_for(cost, ship, CFG)
        assert net >= 25.0 and net / price >= 0.25
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
    assert plan['is_variation'] and len(plan['variants']) == 2
    assert {d[1] for d in plan['dropped']} == {'out of stock', 'duplicate option combination'}
    low, high = plan['variants']
    assert high['price'] > low['price'] and all(v['net'] >= 25.0 for v in plan['variants'])
    assert plan['flags']  # 14/2 = 7x spread -> review flag


def test_description_is_built_from_data():
    res = {'ae_item_properties': {'ae_item_property': [{'attr_name': 'Material', 'attr_value': 'Silikon'}]},
           'package_info_dto': {'package_length': 10, 'package_width': 5, 'package_height': 2, 'gross_weight': '0.04'},
           'ae_item_base_info_dto': {'detail': ''}}
    html = description.build('Testprodukt <b>', res, None)
    assert 'Silikon' in html and '10 x 5 x 2 cm' in html and '&lt;b&gt;' in html
