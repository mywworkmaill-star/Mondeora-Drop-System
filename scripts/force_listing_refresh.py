#!/usr/bin/env python3
"""
Force eBay Listing Refresh
Revise listings to force aspect sync from inventory item to live listing.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def force_refresh_listing(ebay, offer_id, sku):
    """
    Force listing refresh by updating the offer.
    This syncs inventory item aspects to the live listing.
    """
    
    try:
        # Get current offer
        offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        
        # Just update the offer with same data to trigger a refresh
        # eBay will sync aspects from inventory item
        update_payload = {
            'availableQuantity': offer.get('availableQuantity'),
            'categoryId': offer.get('categoryId'),
            'format': offer.get('format'),
            'listingPolicies': offer.get('listingPolicies'),
            'merchantLocationKey': offer.get('merchantLocationKey'),
            'pricingSummary': offer.get('pricingSummary'),
        }
        
        print(f"    🔄 Refreshing offer {offer_id}...")
        ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_payload)
        print(f"    ✅ Offer refreshed")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Failed to refresh: {e}")
        return False


def main():
    """Force refresh failed listings from last republish report."""
    
    ebay = eBayRESTClient()
    
    # Read last republish report
    report_path = ROOT / 'data' / 'audit' / 'aspect_republish_report.json'
    
    if not report_path.exists():
        print("❌ No republish report found")
        return
    
    with open(report_path) as f:
        data = json.load(f)
    
    # Get failed listings
    failed = [r for r in data['results'] if r['status'] == 'failed' and r.get('reason') == 'update_api_error']
    
    print(f"\n{'='*60}")
    print(f"FORCE REFRESH FAILED LISTINGS")
    print(f"{'='*60}\n")
    
    print(f"📦 Found {len(failed)} failed listings to refresh\n")
    
    success_count = 0
    failed_count = 0
    
    for idx, listing in enumerate(failed, 1):
        product_id = listing['product_id']
        ebay_item_id = listing['ebay_item_id']
        
        print(f"\n[{idx}/{len(failed)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        
        # Need to get SKU and offer_id
        # Read from database
        import sqlite3
        db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
        db.row_factory = sqlite3.Row
        
        row = db.execute('''
            SELECT pv.sku
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
            WHERE p.aliexpress_product_id = ?
            LIMIT 1
        ''', (product_id,)).fetchone()
        
        db.close()
        
        if not row:
            print(f"  ❌ SKU not found in database")
            failed_count += 1
            continue
        
        sku = row['sku']
        
        # Get offer_id from SKU
        try:
            offers_response = ebay._request('GET', f'/sell/inventory/v1/offer', params={'sku': sku})
            offers = offers_response.get('offers', [])
            
            if not offers:
                print(f"  ❌ No offers found for SKU {sku}")
                failed_count += 1
                continue
            
            offer_id = offers[0].get('offerId')
            
            # Force refresh
            if force_refresh_listing(ebay, offer_id, sku):
                success_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed_count += 1
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed: {len(failed)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Success rate: {success_count/len(failed)*100:.1f}%")
    print()


if __name__ == '__main__':
    main()
