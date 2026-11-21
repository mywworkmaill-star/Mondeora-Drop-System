#!/usr/bin/env python3
"""Simple test: List 1 product with minimal data (like existing successful listing)"""

import sys
import json
import sqlite3
import time

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

# Test product: ID 23
product_id = 23

# Get from database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))
conn.close()

print(f'📦 Testing product ID: {product_id}')
print(f'   Title: {product["title"][:60]}...')
print(f'   Price: €{product["ebay_price"]}')
print(f'   Image: {product.get("image_url", "NO IMAGE")[:60]}...')

# Minimal listing data (like existing successful listings)
listing_data = {
    "sku": f"TEST-MINIMAL-{int(time.time())}",
    "title": product['title'][:80],
    "description": "High quality product. Fast shipping. Great value!",  # Simple text, no HTML
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "20514",  # Home organizers
    "condition": "NEW",
    "image_urls": [product.get('image_url')],
    "aspects": {
        "Marke": "Unbranded",
        "Herstellernummer": "nicht zutreffend",
        "Material": "Polyester",
        "Farbe": "Mehrfarbig",
        "Produktart": "Aufbewahrungsbox"
    }
    # Policy IDs will come from .env
}

print(f'\n📋 Listing data:')
for key in ['sku', 'title', 'price', 'category_id', 'condition']:
    print(f'   {key}: {listing_data[key]}')

print(f'\n🚀 Attempting listing...')

ebay = eBayAPIClient()

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f'\n✅ SUCCESS!')
        print(f'   eBay Item ID: {result.get("ebay_item_id")}')
        print(f'   Offer ID: {result.get("offer_id")}')
        print(f'   Link: https://www.ebay.de/itm/{result.get("ebay_item_id")}')
    else:
        error = result.get('error', 'Unknown') if result else 'No result'
        print(f'\n❌ FAILED: {error}')
        
        # Try to get more details
        if hasattr(ebay, 'last_error') and ebay.last_error:
            print(f'   Last error: {ebay.last_error}')
            
        if hasattr(ebay, 'last_response') and ebay.last_response:
            print(f'   Last response status: {ebay.last_response.status_code if hasattr(ebay.last_response, "status_code") else "unknown"}')
            if hasattr(ebay.last_response, 'text'):
                print(f'   Response body: {ebay.last_response.text[:500]}...')
        
except Exception as e:
    print(f'\n❌ Exception: {e}')
    import traceback
    traceback.print_exc()
