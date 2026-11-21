"""
Manual Publish - ID 156
Direct eBay API calls without validation
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

if not row:
    print('Product not found!')
    exit(1)

ali_id, sku_id, title, images_str, description, price, aspects_json = row

# Parse
images = [i.strip() for i in images_str.split(',') if i.strip()][:12]
aspects = json.loads(aspects_json) if aspects_json else {}

sku = f'AE{ali_id}'

print('=' * 80)
print(f'MANUAL PUBLISH - ID 156')
print('=' * 80)
print()
print(f'SKU:    {sku}')
print(f'Title:  {title[:50]}')
print(f'Price:  €{price:.2f}')
print(f'Images: {len(images)}')
print(f'Aspects: {len(aspects)}')
print()

ebay = eBayAPIClient()

# Step 1: Create inventory item
print('Step 1: Creating inventory item...')

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
    print('✅ Inventory item created')
except Exception as e:
    print(f'❌ Error: {str(e)[:100]}')
    exit(1)

# Step 2: Create offer
print('Step 2: Creating offer...')

offer_data = {
    'sku': sku,
    'marketplaceId': 'EBAY_DE',
    'format': 'FIXED_PRICE',
    'listingPolicies': {
        'fulfillmentPolicyId': '263035514017',
        'paymentPolicyId': '263035507017',
        'returnPolicyId': '263035512017'
    },
    'categoryId': '20741',  # Home & Garden > Household Supplies
    'pricingSummary': {
        'price': {
            'value': str(round(float(price), 2)),
            'currency': 'EUR'
        }
    },
    'quantityLimitPerBuyer': 10,
    'merchantLocationKey': 'WAREHOUSE_DE_1'
}

try:
    response = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
    offer_id = response['offerId']
    print(f'✅ Offer created: {offer_id}')
except Exception as e:
    print(f'❌ Error: {str(e)[:100]}')
    exit(1)

# Step 3: Publish
print('Step 3: Publishing...')

try:
    response = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response['listingId']
    print(f'✅ PUBLISHED: {listing_id}')
    print()
    print(f'URL: https://www.ebay.de/itm/{listing_id}')
    
    # Update database
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            ebay_offer_id = ?,
            is_listed = 1,
            status = 'listed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 156
    ''', (listing_id, offer_id))
    
    conn.commit()
    
    print()
    print('✅ Database updated')
    
except Exception as e:
    print(f'❌ Publish error: {str(e)[:100]}')
    exit(1)

conn.close()

print()
print('=' * 80)
print('✅ SUCCESS!')
print('=' * 80)
