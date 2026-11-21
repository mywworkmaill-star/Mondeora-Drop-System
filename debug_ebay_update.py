"""Debug eBay inventory update with full error details"""

import sys
sys.path.insert(0, 'src')
import json
import requests
import sqlite3
from pathlib import Path
from dotenv import dotenv_values

# Load credentials
env_path = Path('.env')
settings = {**dotenv_values(env_path)}
access_token = settings.get('EBAY_ACCESS_TOKEN')

if not access_token:
    print('❌ No access token found')
    sys.exit(1)

# Get product data
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = 44')
cursor2 = conn.cursor()
cursor2.execute('PRAGMA table_info(products)')
columns = [col[1] for col in cursor2.fetchall()]

row = cursor.fetchone()
product = dict(zip(columns, row))

images = [i.strip() for i in product['image_url'].split(',') if i.strip()][:12]
aspects = json.loads(product['aspects'])
desc = product['description']
sku = f'AE{product["aliexpress_product_id"]}'

print('🔍 EBAY INVENTORY UPDATE DEBUG')
print('=' * 80)
print()
print(f'SKU: {sku}')
print(f'Images: {len(images)}')
print(f'Description: {len(desc)} chars')
print(f'Aspects: {len(aspects)} items')
print()

# Key dimensions
print('DIMENSIONS TO UPDATE:')
for dim in ['Länge', 'Breite', 'Höhe']:
    print(f'  {dim:10s}: {aspects.get(dim)}')
print()

# Prepare payload
payload = {
    'product': {
        'title': product['title'],
        'description': desc,
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

# Make request
url = f'https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}'

headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE',
    'Accept-Language': 'de-DE',
    'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE'
}

print('Sending PUT request to eBay...')
print()

try:
    response = requests.put(url, headers=headers, json=payload, timeout=30)
    
    print(f'HTTP Status: {response.status_code}')
    print()
    
    if response.status_code == 204:
        print('✅ SUCCESS - Inventory item updated!')
        print()
        
        # Verify
        verify_response = requests.get(url, headers=headers, timeout=30)
        if verify_response.status_code == 200:
            data = verify_response.json()
            if 'product' in data and 'aspects' in data['product']:
                print('VERIFICATION - Current eBay Aspects:')
                updated_aspects = data['product']['aspects']
                for dim in ['Länge', 'Breite', 'Höhe']:
                    value = updated_aspects.get(dim, ['NOT FOUND'])[0]
                    status = '✅' if value != 'Siehe Beschreibung' else '❌'
                    print(f'{status} {dim}: {value}')
    
    else:
        print('❌ UPDATE FAILED')
        print()
        print('FULL ERROR RESPONSE:')
        print('=' * 80)
        try:
            error_json = response.json()
            print(json.dumps(error_json, indent=2, ensure_ascii=False))
        except:
            print(response.text)
        print('=' * 80)
        
except Exception as e:
    print(f'❌ Request failed: {e}')
    import traceback
    traceback.print_exc()

conn.close()
