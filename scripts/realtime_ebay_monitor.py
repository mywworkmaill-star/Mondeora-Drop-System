#!/usr/bin/env python3
"""
Real-Time eBay Monitoring System
=================================

Anında tüm eBay listings'leri takip et, database ile senkronize et.

USAGE:
    python scripts/realtime_ebay_monitor.py
    python scripts/realtime_ebay_monitor.py --full-sync
"""

import sys
import json
import sqlite3
import requests
import re
from pathlib import Path
from datetime import datetime
import time

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def confirm_listing_really_ended(ebay, item_id):
    """🚨 SAFETY GATE (2026-11-21) — see src/jobs/ebay_active_sync.py for the
    full incident writeup. This job's old behavior (one offer-GET API call
    per SKU every single minute, silent `except: continue` on ANY transient
    failure, then wiping ebay_item_id+sku_id for anything missing from that
    pass) destroyed live data on ordinary rate-limit/network blips — no
    retry, no independent confirmation. Never clear real DB fields again
    without first confirming via a DIFFERENT, independent check (Trading API
    GetItem keyed on item_id, not a fragile SKU match) that the listing is
    truly Completed. Fail safe on any error/ambiguity: skip, don't delete."""
    if not item_id:
        return False
    try:
        token = ebay._get_headers().get('Authorization', '').replace('Bearer ', '')
        xml = f'''<?xml version="1.0" encoding="utf-8"?>
<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
<ItemID>{item_id}</ItemID>
<DetailLevel>ReturnAll</DetailLevel>
</GetItemRequest>'''
        headers = {
            'X-EBAY-API-SITEID': '77', 'X-EBAY-API-COMPATIBILITY-LEVEL': '1193',
            'X-EBAY-API-CALL-NAME': 'GetItem', 'X-EBAY-API-IAF-TOKEN': token,
            'Content-Type': 'text/xml',
        }
        r = requests.post('https://api.ebay.com/ws/api.dll', headers=headers, data=xml, timeout=20)
        if r.status_code != 200:
            return False
        status = re.search(r'<ListingStatus>([^<]+)</ListingStatus>', r.text)
        if not status:
            return False
        return status.group(1) == 'Completed'
    except Exception:
        return False


def get_all_published_listings(ebay):
    """
    Get ALL published listings from eBay (complete inventory scan).
    
    Returns:
        dict: {
            'listings': [{item_id, sku, title, price, quantity}, ...],
            'total_offers': int,
            'unique_listings': int,
            'single_sku': int,
            'multi_sku': int
        }
    """
    print(f"\n{'='*70}")
    print(f"🔍 SCANNING EBAY FOR ALL ACTIVE LISTINGS")
    print(f"{'='*70}\n")
    
    all_items = []
    offset = 0
    limit = 200
    
    # Step 1: Get all inventory items
    print(f"📦 Fetching inventory items...")
    
    while True:
        try:
            response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={
                'limit': limit,
                'offset': offset
            })
            
            items = response.get('inventoryItems', [])
            
            if not items:
                break
            
            print(f"  Fetched {offset + len(items)} items...")
            
            offset += limit
            total = response.get('total', 0)
            
            if offset >= total:
                break
                
        except Exception as e:
            print(f"❌ Error: {e}")
            break
    
    print(f"✅ Found {total} inventory items\n")
    
    # Step 2: Get offers for each item
    print(f"🔍 Checking offers for each item...")
    
    published_offers = []
    
    offset = 0
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
                
                # Get offer for this SKU
                # 🚨 RELIABILITY FIX (2026-11-21): a single transient failure
                # here used to make a live SKU silently vanish from this
                # run's result set, which downstream fed the destructive
                # "not found = removed" logic. Retry once before giving up.
                offers = []
                for attempt in range(2):
                    try:
                        from urllib.parse import quote
                        encoded_sku = quote(sku, safe='')
                        offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                        offers = offer_response.get('offers', [])
                        break
                    except Exception:
                        if attempt == 0:
                            time.sleep(1.0)
                            continue
                        offers = []  # both attempts failed — treat as unknown, not as "removed"

                for offer in offers:
                    if offer.get('status') == 'PUBLISHED':
                        listing_id = offer.get('listing', {}).get('listingId')
                        if listing_id:
                            published_offers.append({
                                'item_id': listing_id,
                                'sku': sku,
                                'title': product.get('title', ''),
                                'price': float(offer.get('pricingSummary', {}).get('price', {}).get('value', 0)),
                                'quantity': offer.get('availableQuantity', 0)
                            })
            
            print(f"  Checked {offset + len(items)} items... ({len(published_offers)} published)")
            
            offset += limit
            total = response.get('total', 0)
            
            if offset >= total:
                break
                
        except Exception as e:
            print(f"❌ Error: {e}")
            break
    
    print(f"\n✅ Found {len(published_offers)} PUBLISHED offers\n")
    
    # Group by listing ID
    listings_by_id = {}
    for offer in published_offers:
        item_id = offer['item_id']
        if item_id not in listings_by_id:
            listings_by_id[item_id] = []
        listings_by_id[item_id].append(offer)
    
    # Count single vs multi-SKU
    single_sku = sum(1 for skus in listings_by_id.values() if len(skus) == 1)
    multi_sku = sum(1 for skus in listings_by_id.values() if len(skus) > 1)
    
    result = {
        'listings': published_offers,
        'total_offers': len(published_offers),
        'unique_listings': len(listings_by_id),
        'single_sku': single_sku,
        'multi_sku': multi_sku,
        'listings_by_id': listings_by_id
    }
    
    print(f"{'='*70}")
    print(f"📊 EBAY ACTIVE LISTINGS SUMMARY")
    print(f"{'='*70}")
    print(f"  Total PUBLISHED offers:   {result['total_offers']}")
    print(f"  Unique listings:          {result['unique_listings']}")
    print(f"  Single-SKU listings:      {result['single_sku']}")
    print(f"  Multi-SKU (variants):     {result['multi_sku']}")
    print(f"{'='*70}\n")
    
    return result


def get_database_listings():
    """Get all listings from database."""
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            id,
            aliexpress_product_id,
            ebay_item_id,
            sku_id,
            title,
            ebay_price
        FROM products
        WHERE ebay_item_id IS NOT NULL
        ORDER BY ebay_item_id
    ''')
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products


def sync_database_with_ebay(ebay_data, db_products, dry_run=False):
    """
    Sync database with eBay reality.
    
    Args:
        ebay_data: Result from get_all_published_listings()
        db_products: List from get_database_listings()
        dry_run: If True, don't make changes
    
    Returns:
        dict: Sync stats
    """
    print(f"\n{'='*70}")
    print(f"🔄 SYNCING DATABASE WITH EBAY")
    print(f"{'='*70}\n")
    
    # Build lookups
    ebay_by_item_id = ebay_data['listings_by_id']
    db_by_item_id = {p['ebay_item_id']: p for p in db_products}
    
    # Find differences
    ebay_item_ids = set(ebay_by_item_id.keys())
    db_item_ids = set(db_by_item_id.keys())
    
    only_ebay = ebay_item_ids - db_item_ids
    only_db = db_item_ids - ebay_item_ids
    in_both = ebay_item_ids & db_item_ids
    
    print(f"📊 Comparison:")
    print(f"  On eBay only (missing in DB):     {len(only_ebay)}")
    print(f"  In DB only (removed from eBay):   {len(only_db)}")
    print(f"  In both (matched):                {len(in_both)}")
    print()
    
    stats = {
        'ebay_only': len(only_ebay),
        'db_only': len(only_db),
        'matched': len(in_both),
        'added': 0,
        'removed': 0,
        'updated': 0
    }
    
    if dry_run:
        print(f"🔍 DRY RUN - showing changes without applying\n")
    
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    
    # Show missing from DB
    if only_ebay:
        print(f"⚠️  MISSING IN DATABASE ({len(only_ebay)} listings):\n")
        for item_id in list(only_ebay)[:10]:
            offers = ebay_by_item_id[item_id]
            first = offers[0]
            print(f"  {item_id}: {first['title'][:50]}...")
            print(f"    SKUs: {len(offers)}, Price: €{first['price']}")
        
        if len(only_ebay) > 10:
            print(f"  ... and {len(only_ebay) - 10} more\n")
    
    # Remove from DB
    if only_db:
        print(f"\n❌ POTENTIALLY REMOVED FROM EBAY ({len(only_db)} listings) — verifying each before deleting:\n")
        confirmed_removed = 0
        skipped_unconfirmed = 0
        for item_id in list(only_db)[:10]:
            product = db_by_item_id[item_id]
            print(f"  {item_id}: {product['title'][:50]}...")

            if not dry_run:
                # 🚨 SAFETY GATE: "missing from this run's SKU-matched pass"
                # is not proof of removal — it was also the signature of a
                # transient per-SKU API failure (silently swallowed above).
                # Independently confirm via GetItem before deleting anything.
                if confirm_listing_really_ended(ebay, item_id):
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = NULL, sku_id = NULL
                        WHERE ebay_item_id = ?
                    ''', (item_id,))
                    stats['removed'] += 1
                    confirmed_removed += 1
                    print(f"    -> confirmed Completed via GetItem, cleared")
                else:
                    skipped_unconfirmed += 1
                    print(f"    -> GetItem did NOT confirm removal, left untouched (likely a transient SKU-match miss)")

        stats['removal_skipped_unconfirmed'] = skipped_unconfirmed
        if len(only_db) > 10:
            print(f"  ... and {len(only_db) - 10} more\n")
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    return stats


def generate_monitoring_report(ebay_data, db_products, stats):
    """Generate monitoring report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'ebay': {
            'total_offers': ebay_data['total_offers'],
            'unique_listings': ebay_data['unique_listings'],
            'single_sku': ebay_data['single_sku'],
            'multi_sku': ebay_data['multi_sku']
        },
        'database': {
            'total_products': len(db_products),
            'unique_item_ids': len(set(p['ebay_item_id'] for p in db_products))
        },
        'sync': stats,
        'listings': [
            {
                'item_id': item_id,
                'title': offers[0]['title'],
                'skus': len(offers),
                'price': offers[0]['price']
            }
            for item_id, offers in ebay_data['listings_by_id'].items()
        ]
    }
    
    # Save report
    report_path = ROOT / 'data' / 'audit' / f'ebay_monitor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Report saved: {report_path.name}\n")
    
    return report


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time eBay monitoring')
    parser.add_argument('--full-sync', action='store_true', help='Sync database with eBay')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without applying')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get eBay data
    ebay_data = get_all_published_listings(ebay)
    
    # Get database data
    db_products = get_database_listings()
    
    print(f"📊 DATABASE STATUS:")
    print(f"  Products with eBay ID: {len(db_products)}")
    print(f"  Unique eBay Item IDs:  {len(set(p['ebay_item_id'] for p in db_products))}")
    print()
    
    # Sync if requested
    if args.full_sync:
        stats = sync_database_with_ebay(ebay_data, db_products, dry_run=args.dry_run)
    else:
        stats = {
            'ebay_only': len(set(ebay_data['listings_by_id'].keys()) - set(p['ebay_item_id'] for p in db_products)),
            'db_only': len(set(p['ebay_item_id'] for p in db_products) - set(ebay_data['listings_by_id'].keys())),
            'matched': len(set(ebay_data['listings_by_id'].keys()) & set(p['ebay_item_id'] for p in db_products)),
            'added': 0,
            'removed': 0,
            'updated': 0
        }
    
    # Generate report
    report = generate_monitoring_report(ebay_data, db_products, stats)
    
    print(f"{'='*70}")
    print(f"✅ MONITORING COMPLETE")
    print(f"{'='*70}\n")
    
    if ebay_data['unique_listings'] != len(set(p['ebay_item_id'] for p in db_products)):
        print(f"⚠️  WARNING: Database mismatch detected!")
        print(f"   eBay: {ebay_data['unique_listings']} listings")
        print(f"   DB:   {len(set(p['ebay_item_id'] for p in db_products))} listings")
        print(f"\n   Run with --full-sync to fix\n")
    else:
        print(f"✅ Database is in sync with eBay\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
