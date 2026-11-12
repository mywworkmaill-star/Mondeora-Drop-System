from src.listing_quality import labels, variants


def test_bare_letter_code_falls_back_to_known_german_color():
    assert labels.label('A', 'WEISS') == ('Weiß', True)
    assert labels.label('B', 'schwarz') == ('Schwarz', True)
    assert labels.label('F', 'Blau') == ('Blau', True)


def test_bare_letter_code_with_unknown_german_value_stays_unverified():
    assert labels.label('X', 'irgendwas') == ('irgendwas', False)


def test_real_definition_name_still_wins_over_german():
    assert labels.label('red', 'Himmelblau') == ('Rot', True)


def test_numeric_size_code_is_not_misread_as_a_bare_letter_code():
    # '30L' (30 Liter) must stay verified=True like before the color-code fallback was added — it is NOT
    # a meaningless single-letter slot code, it embeds a real measurement.
    assert labels.label('30L', 'XL') == ('30L', True)
    assert labels.label('110La', 'S') == ('110La', True)


def test_ships_from_excluded_from_parsed_aspects():
    res = {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [{
        'sku_id': '1', 'offer_sale_price': '3.45', 'currency_code': 'EUR', 'sku_available_stock': 2,
        'ae_sku_property_dtos': {'ae_sku_property_d_t_o': [
            {'sku_property_name': 'Color', 'property_value_definition_name': 'A', 'sku_property_value': 'schwarz'},
            {'sku_property_name': 'Ships From', 'property_value_definition_name': None, 'sku_property_value': 'CN'},
        ]},
    }]}}
    out = variants.parse_skus(res)
    assert out[0]['aspects'] == {'Color': 'Schwarz'}
    assert out[0]['verified'] is True
