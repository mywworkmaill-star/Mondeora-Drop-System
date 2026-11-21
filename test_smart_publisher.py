"""
Test Smart Publisher
List product ID 155 with full validation and auto-fix
"""

import sys
sys.path.insert(0, 'src')

from src.listing.smart_publisher import SmarteBayPublisher
from src.api.ebay_client import eBayAPIClient
import sqlite3

def test_smart_publish(product_id=155):
    """Test smart publisher with product ID"""
    
    # Connect to database
    conn = sqlite3.connect('data/dropshipping.db')
    
    # Initialize eBay client
    ebay = eBayAPIClient()
    
    # Initialize Smart Publisher
    publisher = SmarteBayPublisher(ebay, conn)
    
    # Publish product
    result = publisher.publish_product(product_id)
    
    # Print result
    print()
    print('=' * 80)
    print('FINAL RESULT')
    print('=' * 80)
    
    if result['success']:
        print('✅ SUCCESS!')
        print()
        print(f'eBay Item ID:      {result["listing_id"]}')
        print(f'Offer ID:          {result["offer_id"]}')
        print(f'Validation Score:  {result["validation_score"]}/100')
        print(f'Fixes Applied:     {len(result.get("fixes_applied", []))}')
        print()
        print(f'URL: https://www.ebay.de/itm/{result["listing_id"]}')
        
    else:
        print('❌ FAILED')
        print()
        print(f'Stage:  {result.get("stage", "unknown")}')
        
        if 'validation_score' in result:
            print(f'Score:  {result["validation_score"]}/100')
        
        if 'errors' in result:
            print()
            print('Errors:')
            for err in result['errors']:
                print(f'   - {err}')
        
        if 'error' in result:
            print()
            print('Error Info:')
            if isinstance(result['error'], dict):
                for key, value in result['error'].items():
                    print(f'   {key}: {value}')
            else:
                print(f'   {result["error"]}')
    
    conn.close()
    
    return result

if __name__ == '__main__':
    product_id = int(sys.argv[1]) if len(sys.argv) > 1 else 155
    test_smart_publish(product_id)
