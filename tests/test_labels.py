from src.listing_quality import labels, variants


def test_translate_uses_seller_definition_not_machine_german():
    assert labels.translate('Camel white-square') == 'Kamel Weiß eckig'
    assert labels.translate('bule') == 'Blau'
    assert labels.translate('1pc Blue Soap ball') == '1 Stück Blau Seife Ball'
    assert labels.translate('No battery Red') == 'Ohne Batterie Rot'
    assert labels.translate('Dark Blue') == 'Dunkelblau'
    assert labels.translate('1.96 inch') == '5 cm' and labels.translate('2.75 inch') == '7 cm'
    assert labels.translate('lao shu bei') == 'Lao Shu Bei'          # unknown words are kept, never invented


def test_label_without_definition_is_unverified():
    assert labels.label(None, 'Himmelblau') == ('Himmelblau', False)
    assert labels.label('Green-round', 'Rot') == ('Grün rund', True)  # German machine label ignored


def _sku(i, de, en, cost):
    return {'sku_id': str(i), 'offer_sale_price': str(cost), 'currency_code': 'EUR', 'sku_available_stock': 5,
            'ae_sku_property_dtos': {'ae_sku_property_d_t_o': [{'sku_property_name': 'Farbe', 'sku_property_value': de,
                                                                 'property_value_definition_name': en, 'sku_property_id': 14}]}}


def test_variants_use_translated_labels_and_flag_unverified():
    res = {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [_sku(1, 'Grau', 'Camel white-square', 4), _sku(2, 'Blau', 'Green-round', 4)]}}
    plan = variants.build('1', res, 1.99)
    assert plan['is_variation'] and {v['aspects']['Farbe'] for v in plan['variants']} == {'Kamel Weiß eckig', 'Grün rund'} and not plan['flags']
    res = {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [_sku(1, 'Grau', None, 4), _sku(2, 'Blau', 'Green', 4)]}}
    assert any('not verifiable' in f for f in variants.build('1', res, 1.99)['flags'])


def test_single_product_drops_invented_colour():
    res = {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [_sku(1, 'Khaki', '1 PCS', 4)]}}
    plan = variants.build('1', res, 1.99)
    assert not plan['is_variation'] and plan['variants'][0]['aspects'] == {} and plan['specifications'] == []
    res = {'ae_item_sku_info_dtos': {'ae_item_sku_info_d_t_o': [_sku(1, 'Hellgrau', 'Gray', 4)]}}
    assert variants.build('1', res, 1.99)['variants'][0]['aspects'] == {'Farbe': 'Grau'}
