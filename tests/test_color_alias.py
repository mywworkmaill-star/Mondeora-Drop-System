from src.listing_quality.publish import ALIASES


def test_color_aliases_to_farbe_for_ebay_de_categories():
    assert 'Farbe' in ALIASES['Color']
