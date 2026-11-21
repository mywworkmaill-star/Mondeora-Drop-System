"""
Find listings that are on eBay but NOT in database
"""

import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import sqlite3

print('🔍 Finding listings on eBay but not in database...')
print()

# Get all eBay Item IDs from database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('SELECT ebay_item_id FROM products WHERE ebay_item_id IS NOT NULL')
db_item_ids = set(row[0] for row in cursor.fetchall())

print(f'📊 Database has {len(db_item_ids)} eBay Item IDs')
print()

conn.close()

# Try to get all listings from eBay using different approaches
ebay = eBayAPIClient()

print('Method 1: Try to list all inventory items...')
try:
    # This might not work without specific filters
    response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={'limit': 100})
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('inventoryItems', [])
        print(f'   Found {len(items)} inventory items')
    else:
        print(f'   Failed: HTTP {response.status_code}')
        items = []
except Exception as e:
    print(f'   Error: {e}')
    items = []

print()
print('=' * 80)
print('MANUAL STEPS NEEDED:')
print('=' * 80)
print()
print('eBay API does not provide a simple "list all active listings" endpoint.')
print('You need to export CSV from eBay Seller Hub:')
print()
print('1. Go to: https://www.ebay.de/sh/lst/active')
print('2. Click "Export" button (top right)')
print('3. Download CSV file')
print('4. Save as: active_listings.csv')
print()
print('Then I can compare the CSV with database and find missing listings.')
print()
print('=' * 80)
print()
print(f'Database eBay IDs ({len(db_item_ids)}):')
db_ids_list = sorted(list(db_item_ids))
for i, item_id in enumerate(db_ids_list[:20]):
    print(f'  {item_id}')
if len(db_ids_list) > 20:
    print(f'  ... and {len(db_ids_list) - 20} more')
