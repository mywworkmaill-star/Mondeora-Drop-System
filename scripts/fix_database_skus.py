#!/usr/bin/env python3
"""
Fix Database SKUs from eBay
============================

Update database SKUs to match real eBay SKU format.

USAGE:
    python scripts/fix_database_skus.py
    python scripts/fix_database_skus.py --dry-run
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix database SKUs from eBay')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    print(f"\n{'='*70}")
    print(f"FIX DATABASE SKUs FROM EBAY")
    print(f"{'='*70}\n")
    
    if args.dry_run:
        print(f"🔍 DRY RUN MODE\n")
    
    # Get database products
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            id,
            aliexpress_product_id,
            ebay_item_id,
            sku_id,
            title
        FROM products
        WHERE ebay_item_id IS NOT NULL
        ORDER BY aliexpress_product_id
    ''')
    
    db_products = [dict(row) for row in cursor.fetchall()]
    
    print(f"📦 Found {len(db_products)} products in database\n")
    
    # Get eBay inventory
    print(f"🔍 Fetching eBay inventory...\n")
    
    all_items = []
    offset = 0
    limit = 200
    
    while True:
        try:
            response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={
                'limit': limit,
                'offset': offset
            })
            
            items = response.get('inventoryItems', [])
            
            if not items:
                break
            
            for item in items:
                sku = item.get('sku', '')
                
                # Get offer
                try:
                    from urllib.parse import quote
                    encoded_sku = quote(sku, safe='')
                    offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                    offers = offer_response.get('offers', [])
                    
                    if offers:
                        offer = offers[0]
                        listing_id = offer.get('listing', {}).get('listingId')
                        status = offer.get('status', 'UNKNOWN')
                        
                        if status == 'PUBLISHED' and listing_id:
                            all_items.append({
                                'sku': sku,
                                'item_id': listing_id
                            })
                except:
                    continue
            
            offset += limit
            total = response.get('total', 0)
            
            if offset >= total:
                break
                
        except Exception as e:
            print(f"❌ Error fetching inventory: {e}")
            break
    
    print(f"📦 Found {len(all_items)} eBay items\n")
    
    # Build lookup by item_id
    ebay_by_item_id = {}
    for item in all_items:
        item_id = item['item_id']
        if item_id not in ebay_by_item_id:
            ebay_by_item_id[item_id] = []
        ebay_by_item_id[item_id].append(item)
    
    # Update database
    stats = {'total': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    
    print(f"{'='*70}")
    print(f"UPDATING DATABASE SKUs")
    print(f"{'='*70}\n")
    
    for product in db_products:
        product_id = product['aliexpress_product_id']
        item_id = product['ebay_item_id']
        old_sku = product['sku_id']
        title = product['title']
        
        stats['total'] += 1
        
        # Find eBay items
        ebay_items = ebay_by_item_id.get(item_id, [])
        
        if not ebay_items:
            print(f"[{stats['total']}] ⚠️  No eBay items for {item_id}")
            print(f"  {title[:50]}...")
            stats['skipped'] += 1
            print()
            continue
        
        # Use first SKU (parent or only variant)
        new_sku = ebay_items[0]['sku']
        
        print(f"[{stats['total']}] {product_id}")
        print(f"  {title[:50]}...")
        print(f"  Item ID: {item_id}")
        print(f"  Old SKU: {old_sku}")
        print(f"  New SKU: {new_sku}")
        
        if old_sku == new_sku:
            print(f"  ✅ Already correct")
            stats['skipped'] += 1
            print()
            continue
        
        if args.dry_run:
            print(f"  🔍 DRY RUN - would update")
            stats['updated'] += 1
        else:
            try:
                cursor.execute('''
                    UPDATE products
                    SET sku_id = ?
                    WHERE id = ?
                ''', (new_sku, product['id']))
                
                conn.commit()
                
                print(f"  ✅ Updated")
                stats['updated'] += 1
                
            except Exception as e:
                print(f"  ❌ Failed: {e}")
                stats['failed'] += 1
        
        print()
    
    conn.close()
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  Total: {stats['total']}")
    print(f"  ✅ Updated: {stats['updated']}")
    print(f"  ⏭️  Skipped: {stats['skipped']}")
    print(f"  ❌ Failed: {stats['failed']}")
    print(f"{'='*70}\n")
    
    if args.dry_run:
        print(f"⚠️  DRY RUN - No changes made\n")
    else:
        print(f"✅ Database SKUs updated!\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
