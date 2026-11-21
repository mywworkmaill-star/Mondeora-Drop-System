"""
eBay API Error Parser
Parses eBay HTTP 400 errors and suggests fixes
"""

import re
import json


class eBayErrorParser:
    """Parse and categorize eBay API errors"""
    
    ERROR_PATTERNS = {
        'merchant_location': r'Standortinformationen nicht gefunden|location.*not found',
        'duplicate': r'identische Artikel|identical item|already.*listed',
        'invalid_category': r'category.*invalid|ungültige kategorie',
        'invalid_price': r'price.*invalid|preis.*ungültig',
        'missing_field': r'required field.*missing|pflichtfeld.*fehlt',
        'image_error': r'image.*invalid|imageUrl.*invalid|bild.*ungültig',
        'title_error': r'title.*invalid|titel.*ungültig',
        'description_error': r'description.*invalid|beschreibung.*ungültig',
        'aspect_error': r'aspect.*invalid|eigenschaft.*ungültig',
        'policy_error': r'policy.*invalid|richtlinie.*ungültig',
    }
    
    def parse(self, error_response, status_code):
        """
        Parse eBay error response
        
        Args:
            error_response: Response text or exception message
            status_code: HTTP status code
            
        Returns:
            {
                'error_type': str,
                'message': str,
                'fix': str,
                'auto_fixable': bool,
                'ebay_item_id': str (if duplicate),
                'code': str
            }
        """
        
        if status_code != 400:
            return {
                'error_type': 'non_validation_error',
                'message': f'HTTP {status_code}',
                'auto_fixable': False
            }
        
        # Try to parse JSON error
        message = ''
        error_code = None
        ebay_item_id = None
        
        try:
            if isinstance(error_response, str):
                data = json.loads(error_response)
            else:
                data = error_response
            
            if 'errors' in data and isinstance(data['errors'], list):
                first_error = data['errors'][0]
                message = first_error.get('message', '')
                error_code = first_error.get('errorId')
                
                # Extract duplicate item ID
                if 'parameters' in first_error:
                    for param in first_error['parameters']:
                        if param.get('name') in ('1', '3'):
                            # eBay item ID often in parameter 1 or 3
                            val = param.get('value', '')
                            if val.isdigit() and len(val) == 12:
                                ebay_item_id = val
        except:
            message = str(error_response)
        
        # Detect error type
        error_type = 'unknown'
        for etype, pattern in self.ERROR_PATTERNS.items():
            if re.search(pattern, message, re.IGNORECASE):
                error_type = etype
                break
        
        # Get fix suggestion
        fix_info = self._get_fix(error_type, message, ebay_item_id)
        fix_info['message'] = message
        fix_info['code'] = error_code
        
        return fix_info
    
    def _get_fix(self, error_type, message, ebay_item_id=None):
        """Get fix suggestion for error type"""
        
        fixes = {
            'merchant_location': {
                'error_type': 'merchant_location',
                'fix': "Use valid merchant location key (WAREHOUSE_DE_1)",
                'auto_fixable': True,
                'action': 'update_location',
                'details': "Change merchantLocationKey to 'WAREHOUSE_DE_1' or 'default-warehouse'"
            },
            
            'duplicate': {
                'error_type': 'duplicate',
                'fix': 'Product already listed on eBay',
                'auto_fixable': True,
                'action': 'skip_or_update',
                'ebay_item_id': ebay_item_id,
                'details': f'Existing listing: {ebay_item_id}' if ebay_item_id else 'Already listed'
            },
            
            'invalid_price': {
                'error_type': 'invalid_price',
                'fix': 'Round price to 2 decimals',
                'auto_fixable': True,
                'action': 'fix_price',
                'details': 'Price must have max 2 decimal places'
            },
            
            'image_error': {
                'error_type': 'image_error',
                'fix': 'Fix image URLs (HTTPS required)',
                'auto_fixable': True,
                'action': 'fix_images',
                'details': 'All images must use HTTPS protocol'
            },
            
            'title_error': {
                'error_type': 'title_error',
                'fix': 'Fix title (10-80 chars, no HTML)',
                'auto_fixable': True,
                'action': 'fix_title',
                'details': 'Title must be 10-80 characters, plain text'
            },
            
            'missing_field': {
                'error_type': 'missing_field',
                'fix': 'Add required fields',
                'auto_fixable': False,
                'action': 'manual_review',
                'details': 'Check which field is missing in error message'
            },
            
            'invalid_category': {
                'error_type': 'invalid_category',
                'fix': 'Use valid category ID',
                'auto_fixable': False,
                'action': 'manual_review',
                'details': 'Category 43504 should work for Home Organization'
            },
            
            'aspect_error': {
                'error_type': 'aspect_error',
                'fix': 'Fix product aspects',
                'auto_fixable': False,
                'action': 'manual_review',
                'details': 'Check aspect names and values match category requirements'
            },
            
            'policy_error': {
                'error_type': 'policy_error',
                'fix': 'Check fulfillment/payment/return policies',
                'auto_fixable': True,
                'action': 'update_policies',
                'details': 'Use valid policy IDs for EBAY_DE marketplace'
            },
        }
        
        fix_data = fixes.get(error_type, {
            'error_type': 'unknown',
            'fix': 'Unknown error - manual review required',
            'auto_fixable': False,
            'action': 'manual_review',
            'details': message[:200]
        })
        
        if ebay_item_id:
            fix_data['ebay_item_id'] = ebay_item_id
        
        return fix_data
    
    def format_error_report(self, error_info):
        """Format error info into readable report"""
        
        report = []
        report.append('=' * 80)
        report.append('EBAY API ERROR')
        report.append('=' * 80)
        report.append(f'Type:         {error_info["error_type"]}')
        report.append(f'Auto-fixable: {"Yes" if error_info.get("auto_fixable") else "No"}')
        
        if error_info.get('code'):
            report.append(f'Error Code:   {error_info["code"]}')
        
        if error_info.get('ebay_item_id'):
            report.append(f'eBay Item ID: {error_info["ebay_item_id"]}')
        
        report.append('')
        report.append('Message:')
        report.append(f'  {error_info.get("message", "N/A")[:200]}')
        report.append('')
        report.append('Fix:')
        report.append(f'  {error_info.get("fix", "N/A")}')
        
        if error_info.get('details'):
            report.append('')
            report.append('Details:')
            report.append(f'  {error_info["details"]}')
        
        report.append('=' * 80)
        
        return '\n'.join(report)
