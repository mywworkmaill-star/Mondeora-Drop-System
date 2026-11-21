#!/usr/bin/env python3
"""
Get Active eBay Listings
=========================

Fetch REAL active listings from eBay Inventory API and sync with database.

USAGE:
    python scripts/get_active_listings.py
    python scripts/get_active_listings.py --sync  # Update database
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def get_active_inventory_items(ebay):
    """
    Get all active inventory items from eBay.
    
    Returns:
        list: [
            {
                'sku': str,
                'item_id': str,
                'title': str,
                'price': float,
                'quantity': int,
                'status': str
            },
            ...
        ]
    """
    print(f"\n🔍 Fetching active inventory items from eBay...")
    
    all_items = []
    offset = 0
    limit = 100
    
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
                availability = item.get('availability', {})
                
                # Get offer to find item_id
                try:
                    from urllib.parse import quote
                    encoded_sku = quote(sku, safe='')
                    offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                    offers = offer_response.get('offers', [])
                    
                    if offers:
                        offer = offers[0]
                        listing_id = offer.get('listing', {}).get('listingId')
                        status = offer.get('status', 'UNKNOWN')
                        
                        # Only include PUBLISHED listings
                        if status == 'PUBLISHED' and listing_id:
                            all_items.append({
                                'sku': sku,
                                'item_id': listing_id,
                                'title': product.get('title', ''),
                                'price': float(offer.get('pricingSummary', {}).get('price', {}).get('value', 0)),
                                'quantity': availability.get('shipToLocationAvailability', {}).get('quantity', 0),
                                'status': status
                            })
                except Exception as e:
                    # Skip items without offers
                    continue
            
            print(f"  📦 Fetched {len(all_items)} active items so far...")
            
            offset += limit
            
            # Check if there are more
            total = response.get('total', 0)
            if offset >= total:
                break
                
        except Exception as e:
            print(f"  ❌ Error fetching inventory: {e}")
            break
    
    return all_items


def sync_database_with_ebay(ebay, dry_run=False):
    """
    Sync database with eBay active listings.
    
    Args:
        ebay: eBay client
        dry_run: If True, don't update database
    """
    print(f"\n{'='*70}")
    print(f"SYNC DATABASE WITH EBAY ACTIVE LISTINGS")
    print(f"{'='*70}\n")
    
    if dry_run:
        print(f"  🔍 DRY RUN MODE (no database changes)\n")
    
    # Get active items from eBay
    active_items = get_active_inventory_items(ebay)
    
    print(f"\n  ✅ Found {len(active_items)} PUBLISHED listings on eBay\n")
    
    if not active_items:
        print(f"  ⚠️  No active listings found!")
        return
    
    # Get all items from database
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.aliexpress_product_id, p.title, p.ebay_item_id, pv.sku
        FROM products p
        LEFT JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.ebay_item_id IS NOT NULL
    ''')
    
    db_items = cursor.fetchall()
    
    print(f"  📊 Database has {len(db_items)} items with ebay_item_id\n")
    
    # Create lookup dicts
    ebay_by_sku = {item['sku']: item for item in active_items}
    ebay_by_item_id = {item['item_id']: item for item in active_items}
    
    # Track changes
    stats = {
        'total_db': len(db_items),
        'total_ebay': len(active_items),
        'still_active': 0,
        'removed': 0,
        'missing_in_db': 0
    }
    
    removed_items = []
    
    # Check each DB item
    print(f"  🔍 Checking each database item...\n")
    
    for db_item in db_items:
        db_id, product_id, title, ebay_item_id, sku = db_item
        
        # Check if still active on eBay
        is_active = False
        
        if sku and sku in ebay_by_sku:
            is_active = True
            stats['still_active'] += 1
        elif ebay_item_id and ebay_item_id in ebay_by_item_id:
            is_active = True
            stats['still_active'] += 1
        
        if not is_active:
            stats['removed'] += 1
            removed_items.append({
                'product_id': product_id,
                'title': title,
                'ebay_item_id': ebay_item_id,
                'sku': sku
            })
            
            print(f"  ❌ REMOVED: {title[:50]}...")
            print(f"     eBay Item: {ebay_item_id}")
            print(f"     SKU: {sku}")
            
            if not dry_run:
                # Clear ebay_item_id from database
                cursor.execute('''
                    UPDATE products
                    SET ebay_item_id = NULL
                    WHERE id = ?
                ''', (db_id,))
                print(f"     ✅ Cleared from database\n")
            else:
                print(f"     🔍 Would clear from database\n")
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    # Check for items on eBay but not in DB
    db_item_ids = {item[3] for item in db_items if item[3]}  # ebay_item_id
    
    for ebay_item in active_items:
        if ebay_item['item_id'] not in db_item_ids:
            stats['missing_in_db'] += 1
            print(f"  ⚠️  ON EBAY BUT NOT IN DB: {ebay_item['title'][:50]}...")
            print(f"     Item: {ebay_item['item_id']}")
            print(f"     SKU: {ebay_item['sku']}\n")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SYNC SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"  📊 Statistics:")
    print(f"  ──────────────────────────────────────────")
    print(f"  Database items:     {stats['total_db']}")
    print(f"  eBay active items:  {stats['total_ebay']}")
    print(f"  Still active:       {stats['still_active']}")
    print(f"  ❌ Removed:         {stats['removed']}")
    print(f"  ⚠️  Missing in DB:  {stats['missing_in_db']}")
    print(f"  ──────────────────────────────────────────\n")
    
    if removed_items:
        print(f"  🗑️  Removed items ({len(removed_items)}):\n")
        for item in removed_items[:10]:
            print(f"    • {item['title'][:50]}...")
            print(f"      {item['ebay_item_id']}\n")
    
    # Save report
    report = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'active_items': active_items,
        'removed_items': removed_items,
        'dry_run': dry_run
    }
    
    report_file = ROOT / 'data' / 'audit' / f'ebay_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"  💾 Report saved to: {report_file.name}\n")
    print(f"  {'='*70}\n")
    
    return stats, active_items


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Get active eBay listings and sync database')
    parser.add_argument('--sync', action='store_true', help='Sync database (remove inactive items)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    if args.sync or args.dry_run:
        sync_database_with_ebay(ebay, dry_run=args.dry_run)
    else:
        # Just list active items
        active_items = get_active_inventory_items(ebay)
        
        print(f"\n✅ Found {len(active_items)} active listings\n")
        
        for i, item in enumerate(active_items, 1):
            print(f"{i}. {item['title'][:60]}...")
            print(f"   Item: {item['item_id']}")
            print(f"   Price: €{item['price']:.2f}")
            print(f"   Qty: {item['quantity']}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
