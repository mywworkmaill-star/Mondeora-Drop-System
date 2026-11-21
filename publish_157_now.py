"""
Publish ID 157 - Final Attempt
Using exact method that worked for ID 156
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json
import time

# Load product
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT aliexpress_product_id, sku_id, title, image_url, description,
           ebay_price, aspects
    FROM products
    WHERE id = 157
''')

row = cursor.fetchone()

if not row:
    print('❌ Product not found!')
    exit(1)

ali_id, sku_id, title, images_str, description, price, aspects_json = row

# Parse
images = [i.strip() for i in images_str.split(',') if i.strip()][:12]
aspects = json.loads(aspects_json) if aspects_json else {}

sku = f'AE{ali_id}'

print('=' * 80)
print('PUBLISHING ID 157 - FINAL ATTEMPT')
print('=' * 80)
print()
print(f'SKU:         {sku}')
print(f'Title:       {title[:60]}...')
print(f'Price:       €{price:.2f}')
print(f'Images:      {len(images)}')
print(f'Aspects:     {len(aspects)} keys')
print(f'Description: {len(description)} chars')
print()

ebay = eBayAPIClient()

# Clean slate: Delete ALL existing offers for this SKU
print('Step 0: Cleaning old offers...')
try:
    offers = ebay._request('GET', f'/sell/inventory/v1/offer?sku={sku}')
    if 'offers' in offers:
        for offer in offers['offers']:
            offer_id = offer.get('offerId')
            try:
                ebay._request('DELETE', f'/sell/inventory/v1/offer/{offer_id}')
                print(f'  ✅ Deleted old offer {offer_id}')
            except:
                pass
except:
    pass

time.sleep(2)  # Wait a bit

# Step 1: Create/Update inventory item
print()
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
    error_msg = str(e)
    if 'already exists' in error_msg.lower():
        print('⚠️  Already exists (OK)')
    else:
        print(f'❌ Error: {error_msg[:200]}')
        exit(1)

time.sleep(1)

# Step 2: Create offer (using EXACT same structure as ID 156)
print()
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
    'categoryId': '20741',  # Same as ID 156
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
    print(f'❌ Error creating offer: {str(e)[:300]}')
    
    # Try to get existing
    try:
        offers = ebay._request('GET', f'/sell/inventory/v1/offer?sku={sku}')
        if 'offers' in offers and len(offers['offers']) > 0:
            offer_id = offers['offers'][0]['offerId']
            print(f'⚠️  Using existing offer: {offer_id}')
        else:
            exit(1)
    except:
        exit(1)

time.sleep(1)

# Step 3: Publish
print()
print('Step 3: Publishing...')
print()

try:
    response = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response['listingId']
    
    print('=' * 80)
    print('✅ ✅ ✅  PUBLISHED SUCCESSFULLY!  ✅ ✅ ✅')
    print('=' * 80)
    print()
    print(f'eBay Item ID:  {listing_id}')
    print(f'eBay Offer ID: {offer_id}')
    print(f'URL:           https://www.ebay.de/itm/{listing_id}')
    print()
    print('=' * 80)
    
    # Update database
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            ebay_offer_id = ?,
            is_listed = 1,
            status = 'listed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 157
    ''', (listing_id, offer_id))
    
    conn.commit()
    
    print()
    print('✅ Database updated (ID 157 → listed)')
    print()
    
except Exception as e:
    error_msg = str(e)
    print('=' * 80)
    print('❌ PUBLISH FAILED')
    print('=' * 80)
    print()
    print(f'Error: {error_msg}')
    print()
    
    # Try to get more details
    if hasattr(e, 'response'):
        try:
            error_json = e.response.json()
            print('Detailed error:')
            print(json.dumps(error_json, indent=2))
        except:
            pass
    
    print()
    print('⚠️  Possible causes:')
    print('   - eBay API rate limit (too many requests today)')
    print('   - Account under review (new seller protection)')
    print('   - Temporary eBay API issue')
    print()
    print('💡 Recommendation: Wait 1 hour and try again')
    
    exit(1)

conn.close()

print()
print('✅ ✅ ✅  COMPLETE SUCCESS!  ✅ ✅ ✅')
print()
