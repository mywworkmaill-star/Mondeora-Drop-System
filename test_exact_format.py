#!/usr/bin/env python3
"""
EXACT FORMAT TEST
Başarılı ID 67'nin AYNEN formatını kullan
"""

import sys
import json
import sqlite3
import time

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

# ID 23 - test ürünü
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = 23')
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))
conn.close()

print(f'📦 Test Product: ID 23')
print(f'   Title: {product["title"][:60]}')
print(f'   Price: €{product["ebay_price"]}')

# EXACT FORMAT - ID 67 gibi
listing_data = {
    "sku": f"EXACT-FORMAT-{int(time.time())}",
    "title": product['title'][:80],
    "description": "High quality product from AliExpress",  # Basit!
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",  # ID 67'nin category'si!
    "condition": "NEW",
    "image_urls": [product.get('image_url')]
    # ASPECTSSIZ!
}

print(f'\n📋 Listing Data (ID 67 formatı):')
print(f'   SKU: {listing_data["sku"]}')
print(f'   Category: {listing_data["category_id"]}')
print(f'   Description: {listing_data["description"]}')
print(f'   Aspects: YOK (ID 67 gibi)')

print(f'\n🚀 eBay\'e gönderiliyor...')

ebay = eBayAPIClient()

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f'\n🎉 BAŞARILI!!!')
        print(f'   eBay Item ID: {result.get("ebay_item_id")}')
        print(f'   Offer ID: {result.get("offer_id")}')
        print(f'   Link: https://www.ebay.de/itm/{result.get("ebay_item_id")}')
        
        # Update database
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET ebay_item_id = ?,
                ebay_offer_id = ?,
                is_listed = 1,
                status = 'active'
            WHERE id = 23
        ''', (result.get("ebay_item_id"), result.get("offer_id")))
        conn.commit()
        conn.close()
        
        print(f'   ✅ Database updated!')
        
    else:
        error = result.get('error', 'Unknown') if result else 'No result'
        print(f'\n❌ Failed: {error}')
        
        if hasattr(ebay, 'last_error'):
            print(f'   Last error: {ebay.last_error}')
        
except Exception as e:
    print(f'\n❌ Exception: {e}')
    import traceback
    traceback.print_exc()
