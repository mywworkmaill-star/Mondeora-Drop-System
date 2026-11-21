"""
Delete Ghost Listings from eBay
Removes 8 listings that are not in database
"""

import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import sqlite3

# Ghost listings to delete
GHOST_LISTINGS = [
    {'item_id': '860134884632', 'title': 'Antistressball Squishy Fidget'},
    {'item_id': '860138341251', 'title': 'Küchen-Kabelaufwickler'},
    {'item_id': '860138344632', 'title': 'Werkzeugteile-Aufbewahrungsbox'},
    {'item_id': '860139499815', 'title': 'Fernbedienungs-Organizer'},
    {'item_id': '860139500259', 'title': 'Kabelbinder-Organizer'},
    {'item_id': '860154956940', 'title': 'Aufbewahrungstasche'},
    {'item_id': '860156291620', 'title': 'Toocki Kabel-Organizer'},
    {'item_id': '860157782806', 'title': 'Kabelbinder-Organizer (dup)'},
]

def delete_ghost_listings(dry_run=True):
    """
    Delete ghost listings from eBay
    
    Args:
        dry_run: If True, only simulate (don't actually delete)
    """
    print('=' * 80)
    print('DELETE GHOST LISTINGS')
    print('=' * 80)
    print(f'Mode: {"DRY RUN (simulation)" if dry_run else "LIVE (will delete)"}')
    print()
    
    if not dry_run:
        confirm = input('⚠️  WARNING: This will DELETE listings from eBay! Type "DELETE" to confirm: ')
        if confirm != 'DELETE':
            print('❌ Cancelled')
            return
        print()
    
    ebay = eBayAPIClient()
    
    deleted = 0
    errors = 0
    
    for i, listing in enumerate(GHOST_LISTINGS, 1):
        item_id = listing['item_id']
        title = listing['title']
        
        print(f'[{i}/{len(GHOST_LISTINGS)}] {item_id} | {title[:40]}... ', end='', flush=True)
        
        if dry_run:
            print('✅ Would delete (dry run)')
            deleted += 1
            continue
        
        try:
            # Find the offer ID for this listing
            # We need SKU first
            # Strategy: Search inventory items for this listing
            
            # Get all inventory items and find matching one
            found_sku = None
            for item in ebay._pages('/sell/inventory/v1/inventory_item', 'inventoryItems', params={}, limit=100):
                sku = item.get('sku')
                
                try:
                    offers = ebay._offers(sku)
                    
                    for offer in offers:
                        listing_data = offer.get('listing', {})
                        if listing_data.get('listingId') == item_id:
                            found_sku = sku
                            offer_id = offer.get('offerId')
                            break
                    
                    if found_sku:
                        break
                except:
                    pass
            
            if not found_sku:
                print('❌ SKU not found')
                errors += 1
                continue
            
            # Delete the offer (this ends the listing)
            response = ebay._request('DELETE', f'/sell/inventory/v1/offer/{offer_id}')
            
            if response.status_code == 204:
                print('✅ Deleted')
                deleted += 1
            else:
                print(f'❌ HTTP {response.status_code}')
                errors += 1
                
        except Exception as e:
            print(f'❌ Error: {e}')
            errors += 1
    
    print()
    print('=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'✅ Deleted: {deleted}')
    print(f'❌ Errors:  {errors}')
    print()
    
    if dry_run:
        print('💡 This was a DRY RUN. No listings were actually deleted.')
        print('   Run with dry_run=False to delete for real.')
    else:
        print('✅ Listings have been deleted from eBay.')
        print('   Database is now in sync!')

if __name__ == '__main__':
    # Check for --live flag
    live_mode = '--live' in sys.argv
    
    delete_ghost_listings(dry_run=not live_mode)
