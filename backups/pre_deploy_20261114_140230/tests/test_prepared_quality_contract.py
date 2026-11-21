"""Offline contract regression tests; no real product evidence."""
from copy import deepcopy

from test_ready_plan import hypothetical_listing, report, NOW


def test_quality_checks_receive_the_same_fields_as_saved_publication(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    from src.listing_quality import gates
    seen = {}
    monkeypatch.setattr(gates, 'check_title_quality', lambda value: seen.setdefault('title', value) and [])
    monkeypatch.setattr(gates, 'check_description_quality', lambda value: (seen.update(description=value) or [], {}))
    monkeypatch.setattr(gates, 'check_image_count', lambda value: (seen.update(images=value) or [], {}))
    monkeypatch.setattr(gates, 'check_item_specifics_count', lambda value: (seen.setdefault('aspects', []).append(deepcopy(value)) or [], {}))
    monkeypatch.setattr(gates, 'check_category_confidence', lambda value: (seen.update(category=deepcopy(value)) or [], {}))
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    st = result['artifact']['st']
    assert seen['title'] == st['title']
    assert seen['description'] == st['desc']
    assert seen['category'] == st['cat']
    assert seen['images'] == st['imgs']
    expected = [{**st['shared'], **{key: [value] for key, value in variant['aspects'].items()}}
                for variant in st['plan']['variants']]
    assert seen['aspects'] == expected
    assert not any(b.startswith('quality_') for b in result['blockers'])
    assert 'supplier_agreement_missing' in result['blockers']


def healthy_publication(f, monkeypatch):
    """Synthetic publication contract, not supplier or legal evidence."""
    original = f['publish'].plan_for
    def plan(*args, **kwargs):
        st = original(*args, **kwargs)
        st['title'] = 'Dokumenten Organizer aus Metall für Büro Schreibtisch Ablage Ordner Papier'
        st['desc'] = '<ul><li>' + 'Sachliche Offline-Testbeschreibung. ' * 25 + '</li></ul><table><tr><td>Material</td><td>Metall</td></tr></table>'
        st['cat'].update(confidence=0.9, needs_review=False)
        st['imgs'] = ['https://example.invalid/hypothetical-' + str(n) + '.jpg' for n in range(8)]
        st['shared'] = {key: ['Hypothetischer Testwert'] for key in (
            'Material', 'Produktart', 'Breite', 'Höhe', 'Länge', 'Gewicht', 'Form', 'Modell', 'Ausführung')}
        return st
    monkeypatch.setattr(f['publish'], 'plan_for', plan)
    return plan


def test_valid_quality_content_is_not_falsely_reported_empty(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    healthy_publication(f, monkeypatch)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert not any(b.startswith('quality_') for b in result['blockers'])
    assert all(v['aspects']['count'] == 10 for v in result['artifact']['st']['gates']['quality']['variants'])
    assert 'supplier_agreement_missing' in result['blockers']
    assert 'freight_estimate_only' in result['blockers']


import pytest


@pytest.mark.parametrize('change,prefix', [
    ('title', 'quality_title:'), ('description', 'quality_description:'),
    ('category', 'quality_category:'), ('images', 'quality_images:'),
    ('variant_aspects', 'quality_aspects:'),
])
def test_real_missing_saved_fields_still_block(hypothetical_listing, monkeypatch, change, prefix):
    f = hypothetical_listing
    original = healthy_publication(f, monkeypatch)
    def incomplete(*args, **kwargs):
        st = original(*args, **kwargs)
        if change == 'title':
            st['title'] = ''
            st['plan']['title'] = 'This wrong nested field must not hide the real missing title'
        elif change == 'description':
            st['desc'] = ''
        elif change == 'category':
            st['cat']['needs_review'] = True
        elif change == 'images':
            st['imgs'] = []
        else:
            st['plan']['variants'][1]['aspects'] = {}
        return st
    monkeypatch.setattr(f['publish'], 'plan_for', incomplete)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert any(b.startswith(prefix) for b in result['blockers'])


def test_six_valid_images_pass_minimum_while_ideal_count_remains_advisory(hypothetical_listing, monkeypatch):
    f = hypothetical_listing
    original = healthy_publication(f, monkeypatch)
    def six_images(*args, **kwargs):
        st = original(*args, **kwargs)
        st['imgs'] = st['imgs'][:6]
        return st
    monkeypatch.setattr(f['publish'], 'plan_for', six_images)
    result = f['module'].build_prepared(f['supplier'], f['ebay'], f['row'], readiness=report(), now=NOW)
    assert not any(b.startswith('quality_images:') for b in result['blockers'])
    assert result['artifact']['st']['gates']['quality']['warnings']
    assert 'supplier_agreement_missing' in result['blockers']
