"""Tests for automatic quality fix system.

Run with:
    python -m pytest tests/test_auto_fix.py -v
"""
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from src.listing_quality import auto_fix


@pytest.fixture
def mock_ebay():
    """Mock eBay API client."""
    ebay = Mock()
    ebay._request = Mock()
    return ebay


@pytest.fixture
def mock_ali():
    """Mock AliExpress API client."""
    ali = Mock()
    ali._request = Mock()
    return ali


@pytest.fixture
def sample_product_data():
    """Sample AliExpress product data."""
    return {
        'ae_item_base_info_dto': {
            'subject': 'Katzenspielzeug Interaktiv Pop Up Maus mit Quietschgeräusch für Training',
            'detail': '<p>1. Interactive toy for cats<br>2. Pop-up mouse design<br>3. Squeaky sound attracts attention</p>'
        },
        'ae_item_properties': {
            'ae_item_property': [
                {'attr_name': 'Material', 'attr_value': 'Kunststoff'},
                {'attr_name': 'Farbe', 'attr_value': 'Mehrfarbig'},
                {'attr_name': 'Produktart', 'attr_value': 'Spielzeug'},
                {'attr_name': 'Geeignet für', 'attr_value': 'Katzen'},
                {'attr_name': 'Altersgruppe', 'attr_value': 'Alle'},
            ]
        },
        'ae_multimedia_info_dto': {
            'image_urls': 'https://ae01.alicdn.com/kf/S1234567890/img1.jpg;https://ae01.alicdn.com/kf/S1234567891/img2.jpg;https://ae01.alicdn.com/kf/S1234567892/img3.jpg;https://ae01.alicdn.com/kf/S1234567893/img4.jpg;https://ae01.alicdn.com/kf/S1234567894/img5.jpg;https://ae01.alicdn.com/kf/S1234567895/img6.jpg;https://ae01.alicdn.com/kf/S1234567896/img7.jpg;https://ae01.alicdn.com/kf/S1234567897/img8.jpg'
        },
        'package_info_dto': {
            'package_length': 15,
            'package_width': 10,
            'package_height': 5,
            'gross_weight': 0.2
        }
    }


class TestAutoFixTitle:
    """Tests for auto_fix_title()."""
    
    def test_no_issues_returns_success(self, mock_ebay, mock_ali):
        """When title has no issues, should return success without changes."""
        good_title = "Katzenspielzeug Interaktiv Pop Up Maus mit Quietschgeräusch für Training"
        
        result = auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', good_title)
        
        assert result['success'] is True
        assert result['old_title'] == good_title
        assert result['new_title'] == good_title
        assert len(result['problems_found']) == 0
    
    def test_fixes_too_short_title(self, mock_ebay, mock_ali, sample_product_data):
        """Should expand short titles to meet 60-char minimum."""
        short_title = "Katzenspielzeug"  # < 60 chars
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', short_title)
        
        assert result['success'] is True
        assert len(result['new_title']) >= 60
        assert len(result['new_title']) <= 80
    
    def test_fixes_too_long_title(self, mock_ebay, mock_ali, sample_product_data):
        """Should shorten titles exceeding 80 chars."""
        long_title = "Katzenspielzeug Interaktiv Pop Up Maus mit Quietschgeräusch für Training Exercise Game Toy Kitty" * 2  # > 80 chars
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', long_title)
        
        assert result['success'] is True
        assert len(result['new_title']) <= 80
    
    def test_removes_foreign_language(self, mock_ebay, mock_ali, sample_product_data):
        """Should remove non-German words."""
        mixed_title = "Cat Toy Katzenspielzeug Interactive Interaktiv"
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', mixed_title)
        
        assert result['success'] is True
        # Should not contain English words
        assert 'Cat' not in result['new_title']
        assert 'Interactive' not in result['new_title']
    
    def test_api_update_with_sku(self, mock_ebay, mock_ali, sample_product_data):
        """Should update eBay listing when SKU provided."""
        title = "Katzenspielzeug kurz"
        sku = "TEST-SKU-001"
        
        # Mock API responses
        mock_ebay._request.return_value = {
            'product': {'title': title, 'description': 'test'},
            'ebay_item_id': '123456789'
        }
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', title, sku=sku)
        
        # Should have called PUT to update inventory item
        put_calls = [call for call in mock_ebay._request.call_args_list 
                     if call[0][0] == 'PUT']
        assert put_calls == []
        assert result.get('api_updated') is False
        assert result['error'] == 'verified_prepared_revision_required'


class TestAutoDownloadImages:
    """Tests for auto_download_images()."""
    
    def test_sufficient_images_returns_success(self, mock_ali):
        """When enough valid images exist, should return success."""
        good_images = [f'https://example.com/img{i}.jpg' for i in range(8)]
        
        with patch('src.listing_quality.images.filter_urls', return_value=(good_images, [])):
            result = auto_fix.auto_download_images(mock_ali, '12345', good_images)
        
        assert result['success'] is True
        assert result['new_count'] >= 6
    
    def test_filters_low_res_images(self, mock_ali, sample_product_data):
        """Should filter out images < 500px."""
        all_images = [f'https://example.com/img{i}.jpg' for i in range(10)]
        good_images = all_images[:6]  # Only first 6 are valid
        bad_images = [(img, [300, 300]) for img in all_images[6:]]
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.images.filter_urls', side_effect=lambda urls: (
                    [u for u in urls if u in good_images], [b for b in bad_images if b[0] in urls])):
                result = auto_fix.auto_download_images(mock_ali, '12345', current_images=all_images)
        
        assert result['success'] is True
        assert result['new_count'] == 6
        assert len(result['dropped_urls']) == 4
    
    def test_insufficient_images_fails(self, mock_ali, sample_product_data):
        """Should fail when not enough valid images available."""
        all_images = [f'https://example.com/img{i}.jpg' for i in range(3)]
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.images.filter_urls', return_value=(all_images, [])):
                result = auto_fix.auto_download_images(mock_ali, '12345')
        
        assert result['success'] is False
        assert 'insufficient' in result.get('error', '').lower()


class TestAutoGenerateDescription:
    """Tests for auto_generate_description()."""
    
    def test_good_description_returns_success(self, mock_ali):
        """When description meets requirements, should return success."""
        good_desc = '<html><body>' + '<p>' + 'Test description. ' * 100 + '</p></body></html>'
        
        with patch('src.listing_quality.gates.check_description_quality', return_value=([], {})):
            result = auto_fix.auto_generate_description(None, mock_ali, '12345', 'Test Title', good_desc)
        
        assert result['success'] is True
        assert result['new_description'] == good_desc
    
    def test_generates_html_structure(self, mock_ali, sample_product_data):
        """Should generate proper HTML structure with lists and tables."""
        title = "Katzenspielzeug"
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.gates.check_description_quality', return_value=([], {})):
                result = auto_fix.auto_generate_description(None, mock_ali, '12345', title)
        
        assert result['success'] is True
        desc = result['new_description']
        
        # Should contain HTML
        assert '<html>' in desc or '<div' in desc or '<table' in desc
        # Should be long enough
        assert result['new_length'] >= 500
    
    def test_api_update_with_sku(self, mock_ebay, mock_ali, sample_product_data):
        """Should update eBay listing when SKU provided."""
        sku = "TEST-SKU-001"
        title = "Test Title"
        
        mock_ebay._request.return_value = {
            'product': {'title': title, 'description': 'old'}
        }
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            # Explicit injected client; a SKU is not evidence/permission to write.
            with patch('src.listing_quality.gates.check_description_quality', return_value=([], {})):
                result = auto_fix.auto_generate_description(mock_ebay, mock_ali, '12345', title, sku=sku)
        assert not mock_ebay._request.called
        assert result['error'] == 'verified_prepared_revision_required'


class TestAutoFillAspects:
    """Tests for auto_fill_aspects()."""
    
    def test_sufficient_aspects_returns_success(self, mock_ali):
        """When enough aspects exist, should return success."""
        good_aspects = {f'Aspect{i}': [f'Value{i}'] for i in range(12)}
        
        with patch('src.listing_quality.gates.check_item_specifics_count', return_value=([], {})):
            result = auto_fix.auto_fill_aspects(None, mock_ali, '12345', good_aspects)
        
        assert result['success'] is True
        assert result['new_count'] >= 10
    
    def test_does_not_invent_standard_aspects(self, mock_ali, sample_product_data):
        """Missing brand/condition/part-number facts must stay missing."""
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fill_aspects(None, mock_ali, '12345', {})
        
        assert result['success'] is False  # Five source facts cannot satisfy min_count=10.
        aspects = result['new_aspects']
        assert 'Marke' not in aspects
        assert 'Zustand' not in aspects
        assert 'Herstellernummer' not in aspects
    
    def test_converts_properties_to_aspects(self, mock_ali, sample_product_data):
        """Should convert AliExpress properties to eBay aspects."""
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fill_aspects(None, mock_ali, '12345', {})
        
        assert result['success'] is False  # Retain genuine partial facts without padding.
        aspects = result['new_aspects']
        
        # Should contain properties from sample data
        assert 'Material' in aspects or any('Kunststoff' in str(v) for v in aspects.values())


class TestAutoCorrectCategory:
    """Tests for auto_correct_category()."""
    
    def test_good_category_returns_success(self, mock_ebay, mock_ali):
        """When category is confident and doesn't need review, should return success."""
        good_category = {
            'category_id': '20741',
            'path': 'Haustierbedarf > Katzen > Spielzeug',
            'confidence': 0.85,
            'needs_review': False
        }
        
        with patch('src.listing_quality.gates.check_category_confidence', return_value=([], {})):
            result = auto_fix.auto_correct_category(mock_ebay, mock_ali, '12345', 
                                                    'Katzenspielzeug', good_category)
        
        assert result['success'] is True
        assert result['new_category'] == good_category
    
    def test_resolves_low_confidence_category(self, mock_ebay, mock_ali, sample_product_data):
        """Should resolve new category when current has low confidence."""
        bad_category = {
            'category_id': '12345',
            'confidence': 0.3,
            'needs_review': True
        }
        
        better_category = {
            'category_id': '20741',
            'path': 'Haustierbedarf > Katzen > Spielzeug',
            'confidence': 0.75,
            'needs_review': False
        }
        
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.categories.resolve', return_value=better_category):
                result = auto_fix.auto_correct_category(mock_ebay, mock_ali, '12345',
                                                        'Katzenspielzeug', bad_category)
        
        assert result['success'] is True
        assert result['new_category']['confidence'] > 0.6


class TestAutoFixAll:
    """Tests for auto_fix_all() comprehensive fix."""
    
    def test_runs_all_fixes(self, mock_ebay, mock_ali, sample_product_data):
        """Should run all 5 fix operations."""
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.auto_fix.auto_fix_title') as mock_title:
                with patch('src.listing_quality.auto_fix.auto_download_images') as mock_images:
                    with patch('src.listing_quality.auto_fix.auto_generate_description') as mock_desc:
                        with patch('src.listing_quality.auto_fix.auto_fill_aspects') as mock_aspects:
                            with patch('src.listing_quality.auto_fix.auto_correct_category') as mock_cat:
                                # Set all mocks to return success
                                for mock_fn in [mock_title, mock_images, mock_desc, mock_aspects, mock_cat]:
                                    mock_fn.return_value = {'success': True, 'problems_found': [], 'problems_fixed': []}
                                
                                result = auto_fix.auto_fix_all(mock_ebay, mock_ali, '12345')
        
        assert 'fixes' in result
        assert 'title' in result['fixes']
        assert 'images' in result['fixes']
        assert 'description' in result['fixes']
        assert 'aspects' in result['fixes']
        assert 'category' in result['fixes']
    
    def test_dry_run_skips_api_updates(self, mock_ebay, mock_ali, sample_product_data):
        """Dry run should check but not update API."""
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            result = auto_fix.auto_fix_all(mock_ebay, mock_ali, '12345', 
                                          sku='TEST-SKU', dry_run=True)
        
        # Should have summary but no API updates
        assert 'summary' in result
        assert result['summary']['api_updates'] == 0
    
    def test_counts_issues_correctly(self, mock_ebay, mock_ali, sample_product_data):
        """Should correctly count found and fixed issues."""
        with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
            with patch('src.listing_quality.auto_fix.auto_fix_title') as mock_title:
                # Title has 2 problems, both fixed
                mock_title.return_value = {
                    'success': True,
                    'problems_found': ['too short', 'foreign language'],
                    'problems_fixed': ['too short', 'foreign language'],
                    'api_updated': True
                }
                
                with patch('src.listing_quality.auto_fix.auto_download_images') as mock_images:
                    mock_images.return_value = {
                        'success': True,
                        'problems_found': [],
                        'problems_fixed': []
                    }
                    
                    with patch('src.listing_quality.auto_fix.auto_generate_description') as mock_desc:
                        mock_desc.return_value = {
                            'success': True,
                            'problems_found': [],
                            'problems_fixed': [],
                            'api_updated': False
                        }
                        
                        with patch('src.listing_quality.auto_fix.auto_fill_aspects') as mock_aspects:
                            mock_aspects.return_value = {
                                'success': True,
                                'problems_found': [],
                                'problems_fixed': []
                            }
                            
                            with patch('src.listing_quality.auto_fix.auto_correct_category') as mock_cat:
                                mock_cat.return_value = {
                                    'success': True,
                                    'problems_found': [],
                                    'problems_fixed': []
                                }
                                
                                result = auto_fix.auto_fix_all(mock_ebay, mock_ali, '12345', dry_run=True)
        
        assert result['summary']['issues_found'] == 2
        assert result['summary']['issues_fixed'] == 2


class TestLogging:
    """Tests for fix logging functionality."""
    
    def test_creates_log_directory(self, mock_ebay, mock_ali, tmp_path):
        """Should create log directory if it doesn't exist."""
        with patch('src.listing_quality.auto_fix.LOG_DIR', tmp_path / 'logs'):
            with patch('src.listing_quality.source.fetch_raw', return_value={'ae_item_base_info_dto': {'subject': 'test'}}):
                auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', 'Test Title')
            
            assert (tmp_path / 'logs').exists()
    
    def test_logs_fix_actions(self, mock_ebay, mock_ali, tmp_path, sample_product_data):
        """Should log each fix action to JSONL file."""
        with patch('src.listing_quality.auto_fix.LOG_DIR', tmp_path / 'logs'):
            with patch('src.listing_quality.source.fetch_raw', return_value=sample_product_data):
                auto_fix.auto_fix_title(mock_ebay, mock_ali, '12345', 'Kurz')
        
        # Should have created a log file
        log_files = list((tmp_path / 'logs').glob('title_*.jsonl'))
        assert len(log_files) > 0
        
        # Should contain valid JSON lines
        log_content = log_files[0].read_text(encoding='utf-8')
        lines = [line for line in log_content.strip().split('\n') if line]
        assert len(lines) > 0
        
        for line in lines:
            log_entry = json.loads(line)
            assert 'timestamp' in log_entry
            assert 'fix_type' in log_entry
            assert 'product_id' in log_entry


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
