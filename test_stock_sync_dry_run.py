#!/usr/bin/env python3
"""
Test Stock Sync Job - Dry Run
"""

import sys
import os

# Set working directory (Windows path)
os.chdir('C:\\Users\\Administrator\\Desktop\\Mondeora-Drop-System')
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import sqlite3
from datetime import datetime

print("🧪 TESTING STOCK SYNC JOB - DRY RUN")
print("="*70)

# Test 1: Check database schema
print("\n1️⃣ DATABASE SCHEMA CHECK:")
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('PRAGMA table_info(product_variations)')
columns = cursor.fetchall()

needed_cols = ['last_stock_check', 'aliexpress_stock', 'ebay_active']
found_cols = [col[1] for col in columns]

for col in needed_cols:
    if col in found_cols:
        print(f"   ✅ {col}")
    else:
        print(f"   ❌ {col} - MISSING!")

# Test 2: Get products to sync
print("\n2️⃣ PRODUCTS TO SYNC:")

cursor.execute('''
    SELECT p.id, p.aliexpress_product_id, p.title, p.ebay_item_id,
           COUNT(pv.id) as var_count
    FROM products p
    LEFT JOIN product_variations pv ON p.id = pv.product_id
    WHERE p.is_variation_product = 1
    AND p.ebay_item_id IS NOT NULL
    GROUP BY p.id
''')

products = cursor.fetchall()

print(f"   Found: {len(products)} variation products with eBay listings")

for p in products:
    print(f"\n   📦 Product {p[0]}: {p[2][:50]}")
    print(f"      AliExpress: {p[1]}")
    print(f"      eBay: {p[3]}")
    print(f"      Variations: {p[4]}")

# Test 3: Check variations
if products:
    test_product_id = products[0][0]
    
    print(f"\n3️⃣ VARIATION DETAILS (Product {test_product_id}):")
    
    cursor.execute('''
        SELECT sku, color, length, stock, aliexpress_stock, 
               ebay_active, ebay_offer_id, last_stock_check
        FROM product_variations
        WHERE product_id = ?
    ''', (test_product_id,))
    
    variations = cursor.fetchall()
    
    for v in variations:
        print(f"\n   🎯 {v[0]}:")
        print(f"      Color: {v[1]}, Length: {v[2]}")
        print(f"      Stock (DB): {v[3]}")
        print(f"      Stock (AliExpress): {v[4]}")
        print(f"      eBay active: {v[5]}")
        print(f"      eBay offer: {v[6]}")
        print(f"      Last check: {v[7]}")

conn.close()

print("\n" + "="*70)
print("✅ DRY RUN COMPLETE")
print("="*70)
print("\n📋 NEXT STEPS:")
print("   1. Run real sync: python src/jobs/stock_sync_job.py")
print("   2. Check AliExpress API for stock data")
print("   3. Update eBay quantities")
print("   4. Withdraw/reactivate as needed")
