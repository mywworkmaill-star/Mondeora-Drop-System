from src.listing_quality import description


def test_description_respects_ebay_4000_char_limit_even_with_many_properties():
    # Regression: a product with 20 long AliExpress properties pushed the styled HTML over eBay's
    # inventory_item.product.description 4000-char cap -> PUT failed with errorId 25718.
    props = [{'attr_name': f'Eigenschaft Nummer {i} mit langem Namen', 'attr_value': f'Wert {i} ' * 6}
             for i in range(25)]
    res = {
        'ae_item_properties': {'ae_item_property': props},
        'package_info_dto': {'package_length': 30, 'package_width': 20, 'package_height': 10, 'gross_weight': '1.2'},
        'ae_item_base_info_dto': {'detail': '<p>' + 'Lange Produktbeschreibung mit vielen Details. ' * 20 + '</p>'},
    }
    plan = {'is_variation': True, 'specifications': [{'name': 'Farbe', 'values': [f'Farbe{i}' for i in range(10)]}]}
    html_out = description.build('Ein sehr langer Produkttitel für den Stresstest', res, plan)
    assert len(html_out) <= 4000
    assert 'Seite 1' in html_out and 'Seite 2' in html_out
