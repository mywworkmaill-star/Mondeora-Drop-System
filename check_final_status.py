"""
Final Status Check After Ghost Deletion
"""

import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import sqlite3
import time

print('📊 FINAL STATUS CHECK')
print('=' * 80)
print()

ebay = eBayAPIClient()

# Get unique eBay listing IDs
print('Step 1: Counting eBay listings...')
unique_listings = set()
processed_items = 0

try:
    for item in ebay._pages('/sell/inventory/v1/inventory_item', 'inventoryItems', params={}, limit=100):
        processed_items += 1
        
        if processed_items % 50 == 0:
            print(f'   Processed {processed_items} items, found {len(unique_listings)} unique listings...', flush=True)
        
        try:
            sku = item.get('sku')
            offers = ebay._offers(sku)
            
            for offer in offers:
                if offer.get('status') == 'PUBLISHED' and offer.get('marketplaceId') == 'EBAY_DE':
                    listing = offer.get('listing', {})
                    listing_id = listing.get('listingId')
                    
                    if listing_id:
                        unique_listings.add(listing_id)
        except:
            pass
        
        time.sleep(0.05)  # Rate limiting
        
except KeyboardInterrupt:
    print('\n⚠️  Scan interrupted by user')
except Exception as e:
    print(f'\n⚠️  Scan error: {e}')

print()
print(f'✅ Found {len(unique_listings)} unique eBay listings')
print(f'   (Processed {processed_items} inventory items)')
print()

# Get database count
print('Step 2: Checking database...')
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('SELECT ebay_item_id FROM products WHERE ebay_item_id IS NOT NULL AND is_listed = 1')
db_ids = set(row[0] for row in cursor.fetchall())

conn.close()

print(f'✅ Database has {len(db_ids)} active listings')
print()

# Compare
ghosts = unique_listings - db_ids
missing = db_ids - unique_listings
matching = unique_listings & db_ids

print('=' * 80)
print('FINAL RESULTS:')
print('=' * 80)
print(f'eBay listings:           {len(unique_listings)}')
print(f'Database listings:       {len(db_ids)}')
print(f'✅ Matching:             {len(matching)} ({100*len(matching)//max(len(db_ids),1)}%)')
print()
print(f'👻 Ghost (eBay only):    {len(ghosts)}')
print(f'⚠️  Missing (DB only):   {len(missing)}')
print()

if ghosts:
    print('Ghost listings (need deletion):')
    for i, gid in enumerate(sorted(list(ghosts)), 1):
        print(f'   {i}. {gid}')
        if i >= 20:
            print(f'   ... and {len(ghosts) - 20} more')
            break
    print()

if missing:
    print('Missing from eBay (ended/sold?):')
    for i, mid in enumerate(sorted(list(missing)), 1):
        print(f'   {i}. {mid}')
        if i >= 10:
            print(f'   ... and {len(missing) - 10} more')
            break
    print()

# Summary
print('=' * 80)
print('SUMMARY:')
print('=' * 80)

if len(ghosts) == 0:
    print('✅ PERFECT! No ghost listings found.')
    print('   All eBay listings are tracked in database.')
elif len(ghosts) <= 5:
    print(f'⚠️  {len(ghosts)} ghost listings remain.')
    print('   Run deletion script again to remove them.')
else:
    print(f'⚠️  {len(ghosts)} ghost listings found.')
    print('   This is unusual - review the list above.')

print()
print(f'Sync rate: {100*len(matching)//max(len(unique_listings),1)}%')
