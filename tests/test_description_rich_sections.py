from src.listing_quality import description, source

_REAL_STYLE_DETAIL = (
    '<div class="detailmodule_html"><div class="detail-desc-decorate-richtext"><div>'
    '<p id="tl_1">Beschreibung <br />'
    '1.Erstklassige Handwerkskunst: Dieses Produkt ist aus hochwertigem Material gefertigt und bietet '
    'eine lange Lebensdauer. <br />'
    '2.Charmante Stücke: Ein einzigartiges Design sorgt für zusätzliche Freude beim Gebrauch. <br />'
    '3.Ansprechendes Training: Fördert logisches Denken und r&auml;umliches Vorstellungsverm&ouml;gen '
    'bei allen Altersgruppen. <br /> <br />'
    'Paketliste <br />'
    'Besonderes Holzspielzeug * 1 <br /></p>'
    '<div>'
    '<img style="max-width:100%;width:800px" width="800px" '
    'src="https://ae01.alicdn.com/kf/Sabc0001.jpg" slate-data-type="image" /> <br />'
    '<img style="max-width:100%;width:800px" width="800px" '
    'src="https://ae01.alicdn.com/kf/Sabc0002.jpg" slate-data-type="image" /> <br />'
    '</div>'
    '<p id="tl_2">Vielen Dank f&uuml;r Ihre Unterst&uuml;tzung! Willkommen bei uns!</p>'
    '</div><br /></div></div>'
)


def _res(detail=_REAL_STYLE_DETAIL, props=None, package=None):
    return {
        'ae_item_properties': {'ae_item_property': props or [{'attr_name': 'Material', 'attr_value': 'Holz'}]},
        'package_info_dto': package or {'package_length': 20, 'package_width': 15, 'package_height': 5, 'gross_weight': '0.3'},
        'ae_item_base_info_dto': {'detail': detail},
    }


def test_detail_sections_splits_suppliers_own_numbered_points_into_bullets():
    bullets, pkg_line = source.detail_sections(_res())
    assert len(bullets) == 3
    assert bullets[0].startswith('Erstklassige Handwerkskunst')
    assert bullets[1].startswith('Charmante Stücke')
    assert bullets[2].startswith('Ansprechendes Training')
    # umlauts must be real unicode chars, not left as literal HTML entities
    assert 'räumliches' in bullets[2] and 'Vorstellungsvermögen' in bullets[2]


def test_detail_sections_package_line_does_not_swallow_the_next_paragraph():
    # Regression: 'Lieferumfang' appearing mid-sentence inside a feature point (e.g. "... ist im
    # Lieferumfang enthalten ...") must NOT be mistaken for the 'Paketliste' section marker, and the
    # package line itself must stop at the next HTML tag boundary, not glue onto the sign-off text.
    detail = (
        '<p>1.Erster Punkt: Eine Referenzzeichnung ist im Lieferumfang enthalten, das hilft beim Start.<br />'
        '2.Zweiter Punkt: Noch mehr echte Details hier beschrieben für den Kunden.<br /><br />'
        'Paketliste <br />Echtes Produkt * 1 <br /></p>'
        '<p>Vielen Dank für Ihre Unterstützung!</p>'
    )
    bullets, pkg_line = source.detail_sections(_res(detail=detail))
    assert len(bullets) == 2
    assert 'Zweiter Punkt' in bullets[1] and 'Noch mehr echte Details' in bullets[1]
    assert pkg_line == 'Echtes Produkt * 1'
    assert 'Vielen Dank' not in pkg_line


def test_detail_sections_falls_back_to_single_paragraph_without_numbered_markers():
    text = ('<p>Nur ein einfacher Beschreibungstext ohne nummerierte Liste, aber lang genug, '
            'um die Mindestlaenge fuer echten Inhalt zu ueberschreiten und nicht als leer zu gelten.</p>')
    bullets, pkg_line = source.detail_sections(_res(detail=text))
    assert len(bullets) == 1
    assert pkg_line is None


def test_detail_images_extracts_real_https_urls_only():
    imgs = source.detail_images(_res())
    assert imgs == ['https://ae01.alicdn.com/kf/Sabc0001.jpg', 'https://ae01.alicdn.com/kf/Sabc0002.jpg']


def test_build_renders_ordered_list_and_all_new_sections_within_ebay_limit():
    plan = {'is_variation': False, 'specifications': []}
    html_out = description.build('Ein echtes Testprodukt', _res(), plan)
    assert len(html_out) <= 4000
    assert '<ol ' in html_out and html_out.count('<li ') == 3
    assert 'Beschreibung' in html_out and 'Spezifikation' in html_out
    assert 'Paket beinhaltet' in html_out and 'Besonderes Holzspielzeug x 1' in html_out
    assert 'Hinweis' in html_out
    assert '<img ' in html_out  # at least one real supplier photo embedded
    assert '&amp;ouml;' not in html_out and '&amp;uuml;' not in html_out


def test_build_compression_keeps_bullet_structure_before_collapsing_to_paragraph():
    # Regression: when the full render overflows 4000 chars, build() must drop photos/properties
    # and then whole bullets one at a time (keeping <ol>/<li> structure) instead of immediately
    # collapsing every bullet into one mangled, mid-sentence-truncated paragraph.
    long_points = ''.join(
        f'{i}.Punkt Nummer {i} mit sehr viel echtem, langem Beschreibungstext fuer den Stresstest. '
        for i in range(1, 6)
    )
    props = [{'attr_name': f'Eigenschaft {i} mit langem Namen', 'attr_value': f'Wert {i} ' * 6} for i in range(20)]
    detail = f'<p>Beschreibung <br />{long_points}<br />Paketliste <br />Produkt * 1 <br /></p>'
    plan = {'is_variation': False, 'specifications': []}
    html_out = description.build('Ein sehr langer Produkttitel für den Stresstest der Kompression', _res(detail=detail, props=props), plan)
    assert len(html_out) <= 4000
    assert '<ol ' in html_out
    assert html_out.count('<li ') >= 1
