"""
AliExpress Link Validator
Tests if product links are publicly accessible or dropship-only

Status Types:
- 'public': Link works, customer can see
- 'dropship_only': API returns product but link 404 (dropship exclusive)
- 'not_found': Neither API nor link works (product removed)
- 'error': Network/timeout error
"""

import requests
from datetime import datetime
from typing import Dict, Optional
import time


class AliExpressLinkValidator:
    """
    Validates AliExpress product links
    """
    
    TIMEOUT = 10  # seconds
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        })
    
    def test_link(self, product_id: str, test_api: bool = True) -> Dict:
        """
        Test AliExpress product link accessibility
        
        Args:
            product_id: AliExpress product ID (e.g., '1005005528999811')
            test_api: Also test if product exists in API (default: True)
        
        Returns:
            {
                'status': 'public' | 'dropship_only' | 'not_found' | 'error',
                'link': str,
                'http_code': int,
                'tested_at': datetime,
                'message': str
            }
        """
        
        result = {
            'product_id': product_id,
            'status': 'error',
            'link': None,
            'http_code': None,
            'tested_at': datetime.now(),
            'message': ''
        }
        
        # Build test links
        links_to_test = [
            f"https://www.aliexpress.com/item/{product_id}.html",
            f"https://de.aliexpress.com/item/{product_id}.html"
        ]
        
        # Test each link
        link_accessible = False
        final_url = None
        http_code = None
        
        for link in links_to_test:
            try:
                # Use HEAD request (faster, no body download)
                response = self.session.head(
                    link,
                    timeout=self.TIMEOUT,
                    allow_redirects=True
                )
                
                http_code = response.status_code
                final_url = response.url
                
                if http_code == 200:
                    # Link works!
                    link_accessible = True
                    result['link'] = final_url
                    result['http_code'] = http_code
                    break
                
            except requests.Timeout:
                result['message'] = f"Timeout after {self.TIMEOUT}s"
                continue
                
            except requests.RequestException as e:
                result['message'] = f"Request error: {str(e)[:100]}"
                continue
        
        # Determine status
        if link_accessible:
            # Link works - PUBLIC
            result['status'] = 'public'
            result['message'] = 'Link publicly accessible'
            
        elif test_api:
            # Link failed, check if product exists in API
            api_exists = self._test_api_exists(product_id)
            
            if api_exists:
                # API works but link doesn't - DROPSHIP ONLY
                result['status'] = 'dropship_only'
                result['link'] = links_to_test[0]  # Store attempted link
                result['http_code'] = http_code or 404
                result['message'] = 'Product exists in API but link not accessible (dropship-only)'
            else:
                # Neither works - NOT FOUND
                result['status'] = 'not_found'
                result['http_code'] = http_code or 404
                result['message'] = 'Product not found in API or public site'
        else:
            # Link failed and no API test - assume NOT FOUND
            result['status'] = 'not_found'
            result['http_code'] = http_code or 404
            result['message'] = 'Link not accessible'
        
        return result
    
    def _test_api_exists(self, product_id: str) -> bool:
        """
        Test if product exists in AliExpress Dropshipping API
        
        Returns:
            True if product found in API, False otherwise
        """
        try:
            # Import here to avoid circular dependency
            import sys
            sys.path.insert(0, 'src')
            from api.aliexpress_client import AliExpressAPIClient
            
            ali = AliExpressAPIClient()
            product = ali.get_product_details(product_id)
            
            return product is not None
            
        except Exception as e:
            # API error - assume not found
            return False
    
    def validate_and_save(self, product_id: str, db_path: str = 'data/dropshipping.db'):
        """
        Test link and save result to database
        
        Args:
            product_id: Product ID in database
            db_path: Path to SQLite database
        
        Returns:
            Validation result dict
        """
        import sqlite3
        
        # Get AliExpress product ID from database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT aliexpress_product_id FROM products WHERE id = ?',
            (product_id,)
        )
        
        row = cursor.fetchone()
        
        if not row:
            return {
                'success': False,
                'message': f'Product ID {product_id} not found in database'
            }
        
        ali_product_id = row[0]
        
        # Test link
        result = self.test_link(ali_product_id)
        
        # Update database
        cursor.execute('''
            UPDATE products
            SET 
                link_status = ?,
                link_tested_at = ?,
                link_http_code = ?
            WHERE id = ?
        ''', (
            result['status'],
            result['tested_at'].isoformat(),
            result['http_code'],
            product_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'product_id': product_id,
            'ali_product_id': ali_product_id,
            'result': result
        }


# CLI usage
if __name__ == "__main__":
    import sys
    
    print("🔗 ALIExpress LINK VALIDATOR")
    print("=" * 70)
    
    validator = AliExpressLinkValidator()
    
    # Test cases
    test_products = [
        ('1005005528999811', 'ID 143 - Küche Unter-Waschbecken'),
        ('1005007412668346', 'ID 31 - Küchen-Kabelaufwickler'),
        ('1005009905982018', 'ID 41 - Fernbedienungs-Organizer'),
    ]
    
    print("\n🧪 TESTING LINKS:\n")
    
    for ali_id, name in test_products:
        print(f"📦 {name}")
        print(f"   AliExpress: {ali_id}")
        
        result = validator.test_link(ali_id)
        
        # Status emoji
        status_emoji = {
            'public': '✅',
            'dropship_only': '⚠️',
            'not_found': '❌',
            'error': '❌'
        }.get(result['status'], '❓')
        
        print(f"   {status_emoji} Status: {result['status'].upper()}")
        print(f"   HTTP: {result['http_code']}")
        print(f"   Message: {result['message']}")
        
        if result['link']:
            print(f"   Link: {result['link'][:60]}...")
        
        print()
        
        # Rate limit protection
        time.sleep(1)
    
    print("✅ Link validation complete!")
