#!/usr/bin/env python3
"""
Add Missing eBay Listings to Database
======================================

Add listings that exist on eBay but missing in database.

USAGE:
    python scripts/add_missing_ebay_listings.py
    python scripts/add_missing_ebay_listings.py --dry-run
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def get_ebay_listings_by_id(ebay):
    """Get all eBay listings indexed by item_id."""
    print(f"\n🔍 Fetching eBay listings...")
    
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
                product = item.get('product', {})
                
                try:
                    from urllib.parse import quote
                    encoded_sku = quote(sku, safe='')
                    offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                    offers = offer_response.get('offers', [])
                    
                    for offer in offers:
                        if offer.get('status') == 'PUBLISHED':
                            listing_id = offer.get('listing', {}).get('listingId')
                            if listing_id:
                                all_items.append({
                                    'item_id': listing_id,
                                    'sku': sku,
                                    'title': product.get('title', ''),
                                    'price': float(offer.get('pricingSummary', {}).get('price', {}).get('value', 0))
                                })
                except:
                    continue
            
            offset += limit
            total = response.get('total', 0)
            
            if offset >= total:
                break
                
        except Exception as e:
            print(f"❌ Error: {e}")
            break
    
    # Group by item_id
    by_id = {}
    for item in all_items:
        item_id = item['item_id']
        if item_id not in by_id:
            by_id[item_id] = []
        by_id[item_id].append(item)
    
    print(f"✅ Found {len(by_id)} unique listings\n")
    
    return by_id


def get_database_item_ids():
    """Get all eBay item IDs from database."""
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT ebay_item_id FROM products WHERE ebay_item_id IS NOT NULL')
    
    item_ids = {row[0] for row in cursor.fetchall()}
    
    conn.close()
    
    return item_ids


def add_missing_listings(ebay_by_id, db_item_ids, dry_run=False):
    """Add missing listings to database."""
    
    ebay_ids = set(ebay_by_id.keys())
    missing_ids = ebay_ids - db_item_ids
    
    print(f"\n{'='*70}")
    print(f"ADDING MISSING LISTINGS TO DATABASE")
    print(f"{'='*70}\n")
    
    print(f"📊 Status:")
    print(f"  eBay listings:       {len(ebay_ids)}")
    print(f"  Database listings:   {len(db_item_ids)}")
    print(f"  Missing:             {len(missing_ids)}\n")
    
    if not missing_ids:
        print(f"✅ No missing listings - database is complete!\n")
        return {'added': 0}
    
    if dry_run:
        print(f"🔍 DRY RUN - would add:\n")
    
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    
    stats = {'added': 0, 'failed': 0}
    
    for i, item_id in enumerate(sorted(missing_ids), 1):
        skus = ebay_by_id[item_id]
        first_sku = skus[0]
        
        title = first_sku['title']
        price = first_sku['price']
        sku = first_sku['sku']
        
        print(f"[{i}/{len(missing_ids)}] {item_id}")
        print(f"  Title: {title[:60]}...")
        print(f"  SKUs:  {len(skus)}")
        print(f"  Price: €{price:.2f}")
        print(f"  SKU:   {sku}")
        
        if dry_run:
            print(f"  🔍 DRY RUN - would add to database")
            stats['added'] += 1
            print()
            continue
        
        try:
            # Extract AliExpress product ID from SKU if possible
            # SKU format: AE-{product_id}-{sku_id} or just {sku_id}
            ali_product_id = None
            
            if sku.startswith('AE-'):
                parts = sku.split('-')
                if len(parts) >= 2:
                    ali_product_id = parts[1]
            
            # Check if this AliExpress product already exists
            if ali_product_id:
                cursor.execute('''
                    SELECT id, ebay_item_id 
                    FROM products 
                    WHERE aliexpress_product_id = ?
                ''', (ali_product_id,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # UPDATE existing record with new eBay item ID
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?,
                            sku_id = ?,
                            title = ?,
                            ebay_price = ?,
                            status = 'active',
                            updated_at = ?
                        WHERE aliexpress_product_id = ?
                    ''', (item_id, sku, title, price, datetime.now().isoformat(), ali_product_id))
                    
                    conn.commit()
                    
                    print(f"  ✅ Updated (was: {existing[1]})")
                    stats['added'] += 1
                    
                else:
                    # INSERT new record
                    cursor.execute('''
                        INSERT INTO products (
                            aliexpress_product_id,
                            ebay_item_id,
                            sku_id,
                            title,
                            ebay_price,
                            status,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ali_product_id,
                        item_id,
                        sku,
                        title,
                        price,
                        'active',
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    
                    conn.commit()
                    
                    print(f"  ✅ Added new")
                    stats['added'] += 1
            else:
                # No AliExpress ID - insert with NULL
                cursor.execute('''
                    INSERT INTO products (
                        aliexpress_product_id,
                        ebay_item_id,
                        sku_id,
                        title,
                        ebay_price,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    None,
                    item_id,
                    sku,
                    title,
                    price,
                    'active',
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                
                print(f"  ✅ Added new (no AliExpress ID)")
                stats['added'] += 1
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            stats['failed'] += 1
        
        print()
    
    conn.close()
    
    return stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add missing eBay listings to database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be added')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get data
    ebay_by_id = get_ebay_listings_by_id(ebay)
    db_item_ids = get_database_item_ids()
    
    # Add missing
    stats = add_missing_listings(ebay_by_id, db_item_ids, dry_run=args.dry_run)
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  ✅ Added:  {stats['added']}")
    print(f"  ❌ Failed: {stats.get('failed', 0)}")
    print(f"{'='*70}\n")
    
    if args.dry_run:
        print(f"⚠️  DRY RUN - No changes made\n")
    else:
        print(f"✅ Database updated!\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
