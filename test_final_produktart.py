#!/usr/bin/env python3
"""
FINAL TEST: Minimal Produktart aspect ile
"""

import sys
import json
import sqlite3
import time

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

# ID 23
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = 23')
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))
conn.close()

print(f'📦 Test Product: ID 23')
print(f'   Title: {product["title"][:60]}')
print(f'   Price: €{product["ebay_price"]}')

# MINIMAL: Sadece zorunlu Produktart aspect
listing_data = {
    "sku": f"FINAL-{int(time.time())}",
    "title": product['title'][:80],
    "description": "High quality storage bag. Perfect for home organization. Durable material, foldable design, easy to clean.",
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",
    "condition": "NEW",
    "image_urls": [product.get('image_url')],
    "aspects": {
        "Produktart": ["Aufbewahrungsbox"]  # ARRAY format!
    }
}

print(f'\n📋 Listing Data:')
print(f'   SKU: {listing_data["sku"]}')
print(f'   Category: {listing_data["category_id"]}')
print(f'   Aspects: {listing_data["aspects"]}')

print(f'\n🚀 eBay\'e gönderiliyor...')

ebay = eBayAPIClient()

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f'\n🎉🎉🎉 BAŞARILI!!!')
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
                status = 'active',
                aspects = ?
            WHERE id = 23
        ''', (result.get("ebay_item_id"), result.get("offer_id"), json.dumps(listing_data["aspects"])))
        conn.commit()
        conn.close()
        
        print(f'   ✅ Database updated!')
        print(f'\n🎯 1. ÜRÜN BAŞARIYLA LİSTELENDİ!')
        
    else:
        error = result.get('error', 'Unknown') if result else 'No result'
        print(f'\n❌ Failed: {error}')
        
        if hasattr(ebay, 'last_error'):
            print(f'   Last error: {ebay.last_error}')
        
except Exception as e:
    print(f'\n❌ Exception: {e}')
    import traceback
    traceback.print_exc()
