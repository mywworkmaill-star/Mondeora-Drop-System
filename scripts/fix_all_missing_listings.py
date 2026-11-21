#!/usr/bin/env python3
"""
Fix All Missing eBay Listings
==============================

Update database with ALL eBay listings that are missing.
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.utils.audit_logger import get_logger


def main():
    """Fix all missing listings."""
    
    logger = get_logger()
    ebay = eBayRESTClient()
    
    print(f"\n{'='*70}")
    print(f"FIX ALL MISSING EBAY LISTINGS")
    print(f"{'='*70}\n")
    
    # Load monitoring report
    report_path = ROOT / 'data' / 'audit' / 'ebay_monitor_20261115_013421.json'
    
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    ebay_listings = report['listings']
    
    print(f"📊 Found {len(ebay_listings)} eBay listings in monitoring report\n")
    
    # Get database with WAL mode
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db', timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    
    cursor.execute('SELECT DISTINCT ebay_item_id FROM products WHERE ebay_item_id IS NOT NULL')
    db_items = {row[0] for row in cursor.fetchall()}
    
    print(f"📊 Database has {len(db_items)} eBay Item IDs\n")
    
    # Find missing
    ebay_ids = {listing['item_id'] for listing in ebay_listings}
    missing_ids = ebay_ids - db_items
    
    print(f"⚠️  Missing: {len(missing_ids)} listings\n")
    
    if not missing_ids:
        print(f"✅ No missing listings!\n")
        conn.close()
        return 0
    
    # Get SKUs for missing listings
    print(f"🔍 Fetching SKUs for missing listings...\n")
    
    missing_listings = []
    
    for listing in ebay_listings:
        if listing['item_id'] in missing_ids:
            item_id = listing['item_id']
            
            # Get SKU from eBay
            try:
                response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={
                    'limit': 200
                })
                
                items = response.get('inventoryItems', [])
                
                for item in items:
                    sku = item.get('sku', '')
                    
                    try:
                        from urllib.parse import quote
                        encoded_sku = quote(sku, safe='')
                        offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                        offers = offer_response.get('offers', [])
                        
                        for offer in offers:
                            if offer.get('status') == 'PUBLISHED':
                                listing_id = offer.get('listing', {}).get('listingId')
                                if listing_id == item_id:
                                    missing_listings.append({
                                        'item_id': item_id,
                                        'sku': sku,
                                        'title': listing['title'],
                                        'price': listing['price']
                                    })
                                    break
                    except:
                        continue
                    
                    if missing_listings and missing_listings[-1]['item_id'] == item_id:
                        break
                
            except Exception as e:
                print(f"❌ Error fetching SKU for {item_id}: {e}")
    
    print(f"✅ Found SKUs for {len(missing_listings)} listings\n")
    
    # Add to database
    print(f"{'='*70}")
    print(f"ADDING MISSING LISTINGS")
    print(f"{'='*70}\n")
    
    stats = {'added': 0, 'updated': 0, 'failed': 0}
    
    for i, listing in enumerate(missing_listings, 1):
        item_id = listing['item_id']
        sku = listing['sku']
        title = listing['title']
        price = listing['price']
        
        print(f"[{i}/{len(missing_listings)}] {item_id}")
        print(f"  {title[:60]}...")
        print(f"  SKU: {sku}")
        print(f"  Price: €{price:.2f}")
        
        # Extract AliExpress ID from SKU
        ali_id = None
        if sku.startswith('AE-'):
            parts = sku.split('-')
            if len(parts) >= 2:
                ali_id = parts[1]
        
        try:
            if ali_id:
                # Check if product exists with this AliExpress ID
                cursor.execute('SELECT id, ebay_item_id FROM products WHERE aliexpress_product_id = ?', (ali_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # UPDATE
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?,
                            sku_id = ?,
                            title = ?,
                            ebay_price = ?,
                            status = 'active',
                            updated_at = ?
                        WHERE aliexpress_product_id = ?
                    ''', (item_id, sku, title, price, datetime.now().isoformat(), ali_id))
                    
                    print(f"  ✅ Updated")
                    stats['updated'] += 1
                    
                    try:
                        logger.log(
                            action='missing_listing_updated',
                            message=f'Updated missing listing: {item_id}',
                            category='database_sync',
                            level='info',
                            product_id=ali_id,
                            ebay_item_id=item_id,
                            success=True
                        )
                    except:
                        pass  # Ignore audit log errors
                else:
                    # INSERT
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
                    ''', (ali_id, item_id, sku, title, price, 'active',
                          datetime.now().isoformat(), datetime.now().isoformat()))
                    
                    print(f"  ✅ Added")
                    stats['added'] += 1
                    
                    try:
                        logger.log(
                            action='missing_listing_added',
                            message=f'Added missing listing: {item_id}',
                            category='database_sync',
                            level='info',
                            product_id=ali_id,
                            ebay_item_id=item_id,
                            success=True
                        )
                    except:
                        pass  # Ignore audit log errors
            else:
                # No AliExpress ID - INSERT with NULL
                cursor.execute('''
                    INSERT INTO products (
                        ebay_item_id,
                        sku_id,
                        title,
                        ebay_price,
                        status,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (item_id, sku, title, price, 'active',
                      datetime.now().isoformat(), datetime.now().isoformat()))
                
                print(f"  ✅ Added (no AliExpress ID)")
                stats['added'] += 1
                
                try:
                    logger.log(
                        action='missing_listing_added',
                        message=f'Added missing listing (no AliExpress ID): {item_id}',
                        category='database_sync',
                        level='info',
                        ebay_item_id=item_id,
                        success=True
                    )
                except:
                    pass  # Ignore audit log errors
            
            conn.commit()
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            stats['failed'] += 1
                
            try:
                logger.log_error(
                    action='missing_listing_add_failed',
                    error_message=str(e),
                    ebay_item_id=item_id
                )
            except:
                pass  # Ignore audit log errors
        
        print()
    
    conn.close()
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  ✅ Added:   {stats['added']}")
    print(f"  ✅ Updated: {stats['updated']}")
    print(f"  ❌ Failed:  {stats['failed']}")
    print(f"{'='*70}\n")
    
    try:
        logger.log(
            action='fix_missing_listings_complete',
            message=f'Fixed missing listings: {stats["added"] + stats["updated"]} total',
            category='database_sync',
            level='success',
            data=stats,
            success=True
        )
    except:
        pass  # Ignore audit log errors
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
