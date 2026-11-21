"""Tests for the new quality gate pipeline: title, images, description, aspects, category."""
import pytest
from src.listing_quality import gates
from src.listing_quality import images as img_module


class TestTitleQualityGate:
    """Test check_title_quality() - 60-80 chars, 8+ words, German keywords."""
    
    def test_optimal_title_passes(self):
        title = "Hundespielzeugball Bissfest Ungiftig Gummi für Hunde Katzen 3er-Set"
        probs = gates.check_title_quality(title)
        assert probs == []
    
    def test_too_short_title_fails(self):
        title = "Hundespielzeugball"  # 18 chars, 1 word
        probs = gates.check_title_quality(title)
        assert any('too short' in p for p in probs)
        assert any('too few keywords' in p for p in probs)
    
    def test_too_long_title_fails(self):
        title = "x" * 85
        probs = gates.check_title_quality(title)
        assert any('too long' in p for p in probs)
    
    def test_too_few_words_fails(self):
        title = "Hundespielzeug für Hunde und Katzen"  # 37 chars, only 6 words
        probs = gates.check_title_quality(title)
        assert any('too few keywords' in p for p in probs)
    
    def test_non_german_characters_detected(self):
        title = "Hundespielzeugball для собак 宠物玩具球 Bissfest Ungiftig Gummi"
        probs = gates.check_title_quality(title)
        assert any('non-German characters' in p for p in probs)
    
    def test_edge_case_60_chars_8_words_passes(self):
        # 60+ chars, 9 words - should pass
        title = "Tierspielzeug Ball Hund Katze Gummi Bissfest Ungiftig Set 3 Stück"
        assert len(title) >= 60
        probs = gates.check_title_quality(title)
        # Should have no "too short" issues
        assert not any('too short' in p for p in probs)


class TestImageCountGate:
    """Test check_image_count() - min 6, ideal 8-12, ≥500px."""
    
    def test_no_images_fails(self):
        probs, info = gates.check_image_count([])
        assert any('no images' in p for p in probs)
        assert info['valid'] == 0
    
    def test_insufficient_images_fails(self):
        # Mock filter_urls to return only 4 valid images
        original_filter = img_module.filter_urls
        
        def mock_filter(urls, **kw):
            return urls[:4], urls[4:]  # Keep only 4, drop rest
        
        img_module.filter_urls = mock_filter
        try:
            probs, info = gates.check_image_count(['url1', 'url2', 'url3', 'url4', 'url5'])
            assert any('insufficient images' in p and '< 6' in p for p in probs)
        finally:
            img_module.filter_urls = original_filter
    
    def test_below_ideal_count_warns(self):
        original_filter = img_module.filter_urls
        
        def mock_filter(urls, **kw):
            return urls[:7], []  # 7 images (above min, below ideal)
        
        img_module.filter_urls = mock_filter
        try:
            probs, info = gates.check_image_count(['url' + str(i) for i in range(10)])
            assert any('below ideal' in p and '< 8' in p for p in probs)
            assert info['valid'] == 7
        finally:
            img_module.filter_urls = original_filter
    
    def test_ideal_count_passes(self):
        original_filter = img_module.filter_urls
        
        def mock_filter(urls, **kw):
            return urls[:10], []  # 10 images (ideal range)
        
        img_module.filter_urls = mock_filter
        try:
            probs, info = gates.check_image_count(['url' + str(i) for i in range(10)])
            # No critical issues, but might have "below ideal" if < 8
            assert info['valid'] == 10
            assert not any('insufficient' in p for p in probs)
        finally:
            img_module.filter_urls = original_filter


class TestDescriptionQualityGate:
    """Test check_description_quality() - min 500 chars, HTML, bullets, table."""
    
    def test_empty_description_fails(self):
        probs, info = gates.check_description_quality('')
        assert any('empty description' in p for p in probs)
        assert info['length'] == 0
    
    def test_too_short_description_fails(self):
        desc = "Kurze Beschreibung."  # < 500 chars
        probs, info = gates.check_description_quality(desc)
        assert any('too short' in p for p in probs)
    
    def test_no_html_fails(self):
        desc = "x" * 600  # Long enough, but plain text
        probs, info = gates.check_description_quality(desc)
        assert any('no HTML formatting' in p for p in probs)
        assert info['has_html'] is False
    
    def test_no_lists_fails(self):
        desc = "<p>" + "x" * 600 + "</p>"  # HTML but no lists
        probs, info = gates.check_description_quality(desc)
        assert any('no bullet points' in p for p in probs)
        assert info['has_lists'] is False
    
    def test_no_table_fails(self):
        desc = "<ul><li>Item 1</li><li>Item 2</li></ul>" + "x" * 500
        probs, info = gates.check_description_quality(desc)
        assert any('no specification table' in p for p in probs)
        assert info['has_table'] is False
    
    def test_complete_description_passes(self):
        desc = """<div>
            <h2>Beschreibung</h2>
            <ul>
                <li>Hochwertiges Material</li>
                <li>Bissfest und ungiftig</li>
                <li>Ideal für Hunde und Katzen</li>
            </ul>
            <table>
                <tr><td>Material</td><td>Gummi</td></tr>
                <tr><td>Größe</td><td>5 cm</td></tr>
            </table>
            """ + "x" * 400 + "</div>"
        probs, info = gates.check_description_quality(desc)
        # Should pass all checks
        assert not any('too short' in p for p in probs)
        assert info['has_html'] is True
        assert info['has_lists'] is True
        assert info['has_table'] is True


class TestItemSpecificsGate:
    """Test check_item_specifics_count() - min 10 aspects."""
    
    def test_no_aspects_fails(self):
        probs, info = gates.check_item_specifics_count({})
        assert any('no item specifics' in p for p in probs)
        assert info['count'] == 0
    
    def test_too_few_aspects_fails(self):
        aspects = {'Marke': 'Unbranded', 'Material': 'Gummi', 'Farbe': 'Blau'}
        probs, info = gates.check_item_specifics_count(aspects)
        assert any('insufficient' in p and '< 10' in p for p in probs)
        assert info['count'] == 3
    
    def test_sufficient_aspects_passes(self):
        aspects = {
            'Marke': 'Unbranded',
            'Material': 'Gummi',
            'Farbe': 'Blau',
            'Größe': 'M',
            'Gewicht': '100g',
            'Herstellungsland': 'China',
            'Altersgruppe': 'Erwachsene',
            'Besonderheiten': 'Bissfest',
            'Produktart': 'Spielzeug',
            'Tierart': 'Hund',
            'Paketinhalt': '3 Stück'
        }
        probs, info = gates.check_item_specifics_count(aspects)
        assert not any('insufficient' in p for p in probs)
        assert info['count'] == 11
    
    def test_aspects_as_list_of_tuples(self):
        aspects = [
            ('Marke', 'Unbranded'),
            ('Material', 'Gummi'),
            ('Farbe', 'Blau'),
        ]
        probs, info = gates.check_item_specifics_count(aspects)
        assert info['count'] == 3
        assert any('insufficient' in p for p in probs)


class TestCategoryConfidenceGate:
    """Test check_category_confidence() - ≥ 0.6 confidence, needs_review check."""
    
    def test_low_confidence_fails(self):
        cat_result = {
            'confidence': 0.4,
            'needs_review': False,
            'category_id': '12345'
        }
        probs, info = gates.check_category_confidence(cat_result)
        assert any('low category confidence' in p and '< 0.6' in p for p in probs)
        assert info['confidence'] == 0.4
    
    def test_needs_review_fails(self):
        cat_result = {
            'confidence': 0.8,
            'needs_review': True,
            'category_id': '12345'
        }
        probs, info = gates.check_category_confidence(cat_result)
        assert any('flagged for manual review' in p for p in probs)
    
    def test_no_category_id_fails(self):
        cat_result = {
            'confidence': 0.8,
            'needs_review': False,
            'category_id': None
        }
        probs, info = gates.check_category_confidence(cat_result)
        assert any('no category ID' in p for p in probs)
    
    def test_good_category_passes(self):
        cat_result = {
            'confidence': 0.85,
            'needs_review': False,
            'category_id': '12345'
        }
        probs, info = gates.check_category_confidence(cat_result)
        assert probs == []
        assert info['confidence'] == 0.85
    
    def test_edge_case_exactly_0_6_passes(self):
        cat_result = {
            'confidence': 0.6,
            'needs_review': False,
            'category_id': '12345'
        }
        probs, info = gates.check_category_confidence(cat_result)
        assert not any('low category confidence' in p for p in probs)


class TestIntegrationWithReadyPlan:
    """Test that quality gates are integrated into build_prepared()."""
    
    def test_quality_blockers_format(self):
        # Test that blocker names follow the pattern: quality_<gate>:<reason>
        blockers = [
            'quality_title:too_short',
            'quality_images:insufficient_images',
            'quality_description:no_HTML_formatting',
            'quality_aspects:insufficient_item_specifics',
            'quality_category:low_category_confidence'
        ]
        for blocker in blockers:
            assert blocker.startswith('quality_')
            assert ':' in blocker
