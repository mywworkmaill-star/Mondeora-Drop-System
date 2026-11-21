#!/usr/bin/env python3
"""
List product using aspect template
"""

import sys
import json
import sqlite3
import time

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
from scripts.aspect_collector import AspectCollector

# ID 44 - Kabelorganizer
product_id = 44

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))
conn.close()

print(f'📦 Product ID {product_id}')
print(f'   Title: {product["title"][:60]}')
print(f'   Price: €{product["ebay_price"]}')

# Template'den aspects al
collector = AspectCollector()

custom_values = {
    'Produktart': 'Kabelorganizer',
    'Breite': '8 cm',
    'Höhe': '8 cm',
    'Länge': '8 cm',
    'Hauptmaterial': 'Kunststoff',
    'Material': 'Kunststoff',
    'Farbe': 'Mehrfarbig',
    'Marke': 'Markenlos',
    'Herstellungsland und -region': 'China',
    'Zustand': 'Neu'
}

aspects = collector.apply_template_to_product(product_id, '43504', custom_values)

print(f'\n📋 Generated Aspects ({len(aspects)} items):')
for i, (name, values) in enumerate(list(aspects.items())[:10], 1):
    print(f'   {i}. {name}: {values[0]}')

# List to eBay
listing_data = {
    "sku": f"TEMPLATE-{int(time.time())}",
    "title": product['title'][:80],
    "description": "Praktischer Kabelorganizer für Schreibtisch. Hält Ladekabel ordentlich. Fluoreszierendes Design, leicht zu finden. Kompakte Größe. Ideal für Zuhause und Büro.",
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",
    "condition": "NEW",
    "image_urls": [product.get('image_url')],
    "aspects": aspects
}

print(f'\n🚀 Listing to eBay...')

ebay = eBayAPIClient()

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f'\n🎉🎉🎉 BAŞARILI!')
        print(f'   eBay Item ID: {result.get("ebay_item_id")}')
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
                aspects = ?,
                category_id = 43504
            WHERE id = ?
        ''', (result.get("ebay_item_id"), result.get("offer_id"), json.dumps(aspects), product_id))
        conn.commit()
        conn.close()
        
        print(f'   ✅ Database updated!')
        print(f'\n🎯 2. ÜRÜN TEMPLATE İLE LİSTELENDİ!')
        
    else:
        error = result.get('error', 'Unknown') if result else 'No result'
        print(f'\n❌ Failed: {error}')
        
        if hasattr(ebay, 'last_error'):
            print(f'   Last error: {ebay.last_error}')
        
except Exception as e:
    print(f'\n❌ Exception: {e}')
    import traceback
    traceback.print_exc()
