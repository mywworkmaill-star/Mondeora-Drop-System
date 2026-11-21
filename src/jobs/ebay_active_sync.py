#!/usr/bin/env python3
"""
eBay Active Listings Sync Job
==============================

Sync database with eBay active listings every 10 minutes.

This job:
1. Fetches all PUBLISHED listings from eBay Inventory API
2. Compares with database
3. Updates ebay_item_id for active listings
4. Clears ebay_item_id for removed listings
5. Logs all changes to audit_log

USAGE:
    python -m src.jobs ebay_active_sync
"""

import sys
import sqlite3
import requests
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def confirm_listing_really_ended(ebay, item_id):
    """
    🚨 SAFETY GATE (2026-11-21): this job used to NULL ebay_item_id the
    moment a SKU wasn't found in a single pass of fragile string-matching
    against eBay's inventory_item list — a SKU-format mismatch (this account
    has 4+ different SKU naming schemes across listings) made a genuinely
    LIVE listing look "removed" and destroyed real, working data. Confirmed
    live incident: a manual fix to a real active listing was reverted by
    this exact job mid-session.

    Never clear a real ebay_item_id on the strength of "not found in this
    SKU-matching pass" alone. Independently confirm via the legacy Trading
    API's GetItem (a totally different matching path, keyed on the item_id
    itself, not a SKU string) that the listing's ListingStatus is actually
    Completed before deleting anything. Fail SAFE: any error, timeout, or
    ambiguous response means "do not delete" — a false negative (keeping a
    stale item_id a bit longer) is recoverable; a false positive (deleting a
    live mapping) breaks live automation and has already happened twice.
    """
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
            return False  # fail safe — do not confirm removal on an error
        status = re.search(r'<ListingStatus>([^<]+)</ListingStatus>', r.text)
        if not status:
            return False  # ambiguous response — fail safe
        return status.group(1) == 'Completed'
    except Exception:
        return False  # any exception — fail safe, never delete on uncertainty


def log_to_audit(conn, action, details, status='info'):
    """Log action to audit_log table (matches existing schema)."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO audit_log (category, action, level, message, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', ('ebay_sync', action, status, details, datetime.now().isoformat()))
    conn.commit()


def get_active_listings_from_ebay(ebay):
    """
    Get all PUBLISHED listings from eBay.
    
    Returns:
        dict: {sku: item_id, ...}
    """
    active_listings = {}
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
                
                if not sku:
                    continue
                
                # Get offer to check status
                try:
                    encoded_sku = quote(sku, safe='')
                    offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                    offers = offer_response.get('offers', [])
                    
                    if offers:
                        offer = offers[0]
                        status = offer.get('status', 'UNKNOWN')
                        listing_id = offer.get('listing', {}).get('listingId')
                        
                        # Only PUBLISHED listings
                        if status == 'PUBLISHED' and listing_id:
                            active_listings[sku] = listing_id
                            
                except Exception:
                    # Skip items without offers
                    continue
            
            offset += limit
            
            total = response.get('total', 0)
            if offset >= total:
                break
                
        except Exception as e:
            print(f"Error fetching inventory: {e}")
            break
    
    return active_listings


def sync_active_listings():
    """
    Main sync function.
    
    Returns:
        dict: Sync stats
    """
    print(f"\n{'='*60}")
    print(f"EBAY ACTIVE LISTINGS SYNC")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Initialize
    ebay = eBayRESTClient()
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    
    # Stats
    stats = {
        'timestamp': datetime.now().isoformat(),
        'ebay_active': 0,
        'db_before': 0,
        'still_active': 0,
        'newly_active': 0,
        'removed': 0
    }
    
    try:
        # Get active from eBay
        print(f"📡 Fetching active listings from eBay...")
        ebay_active = get_active_listings_from_ebay(ebay)
        stats['ebay_active'] = len(ebay_active)
        print(f"   ✅ Found {stats['ebay_active']} PUBLISHED listings on eBay\n")
        
        # Get current DB state
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.aliexpress_product_id, p.ebay_item_id, pv.sku
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
            WHERE pv.sku IS NOT NULL
        ''')
        
        db_items = cursor.fetchall()
        db_with_ebay_id = sum(1 for item in db_items if item[2])  # ebay_item_id not null
        stats['db_before'] = db_with_ebay_id
        
        print(f"📊 Database state:")
        print(f"   Total products: {len(db_items)}")
        print(f"   With ebay_item_id: {db_with_ebay_id}\n")
        
        # Process each DB item
        print(f"🔄 Syncing...\n")
        
        for db_id, product_id, ebay_item_id, sku in db_items:
            if not sku:
                continue
            
            # Check if still active on eBay
            if sku in ebay_active:
                new_item_id = ebay_active[sku]
                
                if ebay_item_id != new_item_id:
                    # Update item_id (might have changed)
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?
                        WHERE id = ?
                    ''', (new_item_id, db_id))
                    
                    if ebay_item_id:
                        print(f"   ✏️  Updated: {product_id}")
                        print(f"      {ebay_item_id} → {new_item_id}")
                        log_to_audit(conn, 'ebay_sync_updated_item_id',
                                   f"Product {product_id}: {ebay_item_id} → {new_item_id}")
                    else:
                        print(f"   ➕ Newly active: {product_id}")
                        print(f"      {new_item_id}")
                        stats['newly_active'] += 1
                        log_to_audit(conn, 'ebay_sync_newly_active',
                                   f"Product {product_id}: {new_item_id}")
                
                stats['still_active'] += 1
                
            else:
                # No longer active on eBay (per this run's SKU matching) —
                # 🚨 SAFETY GATE: do NOT trust that alone. Independently
                # confirm via GetItem that it's truly Completed before
                # deleting anything. SKU-string mismatches (not real removal)
                # are the confirmed, repeated root cause of false positives.
                if ebay_item_id:
                    if confirm_listing_really_ended(ebay, ebay_item_id):
                        cursor.execute('''
                            UPDATE products
                            SET ebay_item_id = NULL
                            WHERE id = ?
                        ''', (db_id,))

                        print(f"   ❌ Removed (confirmed via GetItem): {product_id}")
                        print(f"      {ebay_item_id}")
                        stats['removed'] += 1
                        log_to_audit(conn, 'ebay_sync_removed',
                                   f"Product {product_id}: cleared {ebay_item_id} (GetItem-confirmed Completed)")
                    else:
                        print(f"   ⏭️  SKU not matched but GetItem could not confirm removal — SKIPPING (not deleted): {product_id}")
                        print(f"      {ebay_item_id}")
                        log_to_audit(conn, 'ebay_sync_removal_skipped_unconfirmed',
                                   f"Product {product_id}: {ebay_item_id} not SKU-matched this pass but GetItem did not confirm Completed — left untouched")
        
        conn.commit()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"SYNC COMPLETE")
        print(f"{'='*60}\n")
        print(f"  eBay active:     {stats['ebay_active']}")
        print(f"  DB before:       {stats['db_before']}")
        print(f"  Still active:    {stats['still_active']}")
        print(f"  ➕ Newly active: {stats['newly_active']}")
        print(f"  ❌ Removed:      {stats['removed']}")
        print(f"  DB after:        {stats['still_active'] + stats['newly_active']}")
        print(f"\n{'='*60}\n")
        
        # Log summary
        log_to_audit(conn, 'ebay_sync_complete',
                   f"Active: {stats['ebay_active']}, Removed: {stats['removed']}, " +
                   f"Newly active: {stats['newly_active']}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        log_to_audit(conn, 'ebay_sync_failed', str(e), status='error')
        stats['error'] = str(e)
        
    finally:
        conn.close()
    
    return stats


if __name__ == '__main__':
    sync_active_listings()
