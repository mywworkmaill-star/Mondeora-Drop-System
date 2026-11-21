#!/usr/bin/env python3
"""
Sync Database with eBay - Fix NULL ebay_item_id Problem
Checks eBay account for all listings and updates database
"""

import sys
import sqlite3
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient

def sync_ebay_to_database():
    """Sync all eBay listings to database"""
    
    print("🔄 SYNCING EBAY LISTINGS TO DATABASE")
    print("=" * 70)
    
    # Connect to database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # Get all products
    cursor.execute('SELECT id, title, ebay_item_id FROM products')
    all_products = cursor.fetchall()
    
    print(f"\n📊 Total products in database: {len(all_products)}")
    
    # Count NULL ebay_item_id
    null_count = sum(1 for p in all_products if not p[2])
    print(f"   Products with NULL ebay_item_id: {null_count}")
    
    # Initialize eBay client
    ebay = eBayAPIClient()
    
    print("\n🔍 FETCHING ALL ACTIVE EBAY LISTINGS...")
    
    try:
        # Get all inventory items from eBay
        # This calls: GET /sell/inventory/v1/inventory_item
        response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={'limit': 100})
        
        if not response or 'inventoryItems' not in response:
            print("❌ No inventory items returned from eBay API")
            return
        
        ebay_items = response.get('inventoryItems', [])
        print(f"✅ Found {len(ebay_items)} active listings on eBay")
        
        # Build mapping: SKU -> eBay Item ID
        ebay_mapping = {}
        for item in ebay_items:
            sku = item.get('sku', '')
            # Get offer to find item ID
            # SKU format: "MULTI-{timestamp}" or similar
            ebay_mapping[sku] = item
        
        print(f"\n📝 eBay SKU mapping: {len(ebay_mapping)} items")
        
        # Also get offers to find item IDs
        offers_response = ebay._request('GET', '/sell/inventory/v1/offer', params={'limit': 100})
        
        if offers_response and 'offers' in offers_response:
            offers = offers_response.get('offers', [])
            print(f"✅ Found {len(offers)} offers on eBay")
            
            updates = 0
            
            for offer in offers:
                # Get listing ID (item ID)
                listing = offer.get('listing', {})
                item_id = listing.get('listingId', '')
                sku = offer.get('sku', '')
                title = offer.get('listing', {}).get('title', '')
                
                if not item_id:
                    continue
                
                print(f"\n🔍 eBay Item: {item_id}")
                print(f"   SKU: {sku}")
                print(f"   Title: {title[:60]}")
                
                # Try to match with database by title (fuzzy match)
                cursor.execute('''
                    SELECT id, title, ebay_item_id 
                    FROM products 
                    WHERE ebay_item_id IS NULL
                ''')
                
                null_products = cursor.fetchall()
                
                # Find best match by title similarity
                best_match = None
                best_score = 0
                
                for pid, db_title, db_item_id in null_products:
                    # Simple similarity: count matching words
                    ebay_words = set(title.lower().split())
                    db_words = set(db_title.lower().split())
                    
                    common_words = ebay_words & db_words
                    score = len(common_words) / max(len(ebay_words), len(db_words))
                    
                    if score > best_score and score > 0.5:  # 50% similarity threshold
                        best_score = score
                        best_match = (pid, db_title)
                
                if best_match:
                    pid, db_title = best_match
                    print(f"   ✅ MATCHED with DB ID {pid} (similarity: {best_score:.1%})")
                    print(f"      DB Title: {db_title[:60]}")
                    
                    # Update database
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?,
                            is_listed = 1,
                            status = 'active'
                        WHERE id = ?
                    ''', (item_id, pid))
                    
                    updates += 1
                    print(f"      💾 Database updated!")
                else:
                    print(f"   ⚠️ No match found in database")
            
            conn.commit()
            print(f"\n✅ DATABASE SYNC COMPLETE!")
            print(f"   Updated: {updates} products")
            
        else:
            print("❌ No offers returned from eBay API")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()


if __name__ == '__main__':
    sync_ebay_to_database()
