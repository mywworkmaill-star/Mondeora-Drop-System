"""
Quick Product Listing
List one product to eBay
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json

def quick_list(product_id):
    """List a single product to eBay"""
    
    print('🚀 HIZLI LİSTİNG')
    print('=' * 80)
    print(f'Product ID: {product_id}')
    print()
    
    # Get product from database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    cursor2 = conn.cursor()
    cursor2.execute('PRAGMA table_info(products)')
    columns = [col[1] for col in cursor2.fetchall()]
    
    row = cursor.fetchone()
    if not row:
        print(f'❌ Product ID {product_id} not found!')
        return
    
    product = dict(zip(columns, row))
    
    print(f'Title:   {product["title"][:70]}')
    print(f'Price:   €{product["ebay_price"]}')
    print(f'Status:  {product["status"]}')
    print()
    
    # Prepare eBay listing
    ebay = eBayAPIClient()
    
    # Create SKU
    sku = f'AE{product["aliexpress_product_id"]}'
    
    print(f'SKU: {sku}')
    print()
    
    # Parse images
    images = []
    if product['image_url']:
        images = product['image_url'].split(',') if ',' in product['image_url'] else [product['image_url']]
        images = [img.strip() for img in images if img.strip()]
    
    # Parse aspects
    aspects = {}
    if product['aspects']:
        try:
            aspects = json.loads(product['aspects'])
        except:
            pass
    
    # Create inventory item
    print('Step 1: Creating inventory item...')
    
    inventory_item = {
        'product': {
            'title': product['title'],
            'description': product['description'] if product['description'] else 'Produktbeschreibung',
            'imageUrls': images[:12] if images else [],
            'aspects': aspects if aspects else {}
        },
        'condition': 'NEW',
        'availability': {
            'shipToLocationAvailability': {
                'quantity': product['current_stock'] if product['current_stock'] else 100
            }
        }
    }
    
    try:
        result = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
        print('✅ Inventory item created')
    except Exception as e:
        print(f'❌ Error: {e}')
        return
    
    # Create offer
    print('Step 2: Creating offer...')
    
    offer_data = {
        'sku': sku,
        'marketplaceId': 'EBAY_DE',
        'format': 'FIXED_PRICE',
        'listingDescription': product['description'] if product['description'] else 'Produktbeschreibung',
        'listingPolicies': {
            'fulfillmentPolicyId': '263035514017',
            'paymentPolicyId': '263035507017',
            'returnPolicyId': '263035512017'
        },
        'categoryId': product['category_id'] if product['category_id'] else '43504',
        'pricingSummary': {
            'price': {
                'value': str(product['ebay_price']),
                'currency': 'EUR'
            }
        },
        'quantityLimitPerBuyer': 10,
        'merchantLocationKey': 'WAREHOUSE_DE_1'
    }
    
    try:
        result = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
        offer_id = result.get('offerId')
        print(f'✅ Offer created: {offer_id}')
        print()
        
        # Publish offer
        print('Step 3: Publishing to eBay...')
        
        result = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
        listing_id = result.get('listingId')
        
        print('✅ PUBLISHED!')
        print(f'   eBay Item ID: {listing_id}')
        print(f'   URL: https://www.ebay.de/itm/{listing_id}')
        print()
        
        # Update database
        cursor.execute('''
            UPDATE products 
            SET ebay_item_id = ?, 
                ebay_offer_id = ?,
                is_listed = 1,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (listing_id, offer_id, product_id))
        conn.commit()
        
        print('✅ Database updated')
        print()
        print('=' * 80)
        print('SUCCESS!')
        print('=' * 80)
            
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    
    conn.close()

if __name__ == '__main__':
    product_id = int(sys.argv[1]) if len(sys.argv) > 1 else 36
    quick_list(product_id)
