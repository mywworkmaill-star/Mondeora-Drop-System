from src.listing_quality import description, source


def test_detail_text_unescapes_html_entities():
    raw = ('<p>Kompakte Gr&ouml;&szlig;e Diese kompakte Gr&ouml;&szlig;e erleichtert die Lagerung und den '
           'Transport, perfekt f&uuml;r kleine Wohnungen und Reisen, spart Platz beim Verstauen.</p>')
    txt = source.detail_text({'ae_item_base_info_dto': {'detail': raw}})
    assert 'ö' in txt and 'ß' in txt and 'ü' in txt
    assert '&ouml;' not in txt and '&szlig;' not in txt and '&uuml;' not in txt


def test_description_build_never_double_escapes_umlauts():
    # Regression: html.escape() applied twice turned '&ouml;' into the literal text '&amp;ouml;' —
    # visible as broken "&ouml;" on the live eBay listing instead of 'ö'.
    raw = ('<p>Kompakte Gr&ouml;&szlig;e Diese kompakte Gr&ouml;&szlig;e erleichtert die Lagerung und den '
           'Transport, perfekt f&uuml;r kleine Wohnungen und Reisen, spart Platz beim Verstauen.</p>')
    res = {'ae_item_base_info_dto': {'detail': raw}, 'ae_item_properties': {}, 'package_info_dto': {}}
    html_out = description.build('Titel', res, {'is_variation': False})
    assert '&amp;ouml;' not in html_out and '&amp;szlig;' not in html_out and '&amp;uuml;' not in html_out
    assert 'Größe' in html_out   # correctly unescaped to real UTF-8 text, renders as "Größe" not "&ouml;"
