"""
Manual Publish - ID 156 (DEBUG VERSION)
Get full error details
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json

# Load product
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT aliexpress_product_id, sku_id, title, image_url, description,
           ebay_price, aspects
    FROM products
    WHERE id = 156
''')

row = cursor.fetchone()
ali_id, sku_id, title, images_str, description, price, aspects_json = row

# Parse
images = [i.strip() for i in images_str.split(',') if i.strip()][:12]
aspects = json.loads(aspects_json) if aspects_json else {}

sku = f'AE{ali_id}'

print('INVENTORY DATA:')
print(json.dumps({
    'sku': sku,
    'title': title[:80],
    'images_count': len(images),
    'aspects_count': len(aspects),
    'price': price
}, indent=2))
print()

ebay = eBayAPIClient()

inventory_data = {
    'product': {
        'title': title[:80],
        'description': description,
        'imageUrls': images,
        'aspects': aspects
    },
    'condition': 'NEW',
    'availability': {
        'shipToLocationAvailability': {
            'quantity': 100
        }
    }
}

try:
    response = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_data)
    print('✅ Success')
except Exception as e:
    print(f'❌ Full error:')
    print(str(e))
    
    # Try to get response body
    if hasattr(e, 'response'):
        print()
        print('Response body:')
        try:
            print(json.dumps(json.loads(e.response.text), indent=2))
        except:
            print(e.response.text if hasattr(e.response, 'text') else 'No response text')

conn.close()
