#!/usr/bin/env python3
"""
Update Failed Listings
Re-process listings that failed in the previous run.
"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.update_all_with_inventory_api import (
    extract_aspects_for_product,
    update_inventory_item_aspects,
    refresh_offer
)
from src.api.ebay_client import eBayRESTClient
from src.api.aliexpress_client import AliExpressAPIClient
import sqlite3


def main():
    """Update failed listings from last report."""
    
    # Read last report
    report_path = ROOT / 'data' / 'audit' / 'inventory_aspect_update_report.json'
    
    if not report_path.exists():
        print("❌ No report found")
        return
    
    with open(report_path) as f:
        data = json.load(f)
    
    # Get failed listings
    failed = [r for r in data['results'] if r['status'] == 'failed']
    
    print(f"\\n{'='*60}")
    print(f"UPDATE FAILED LISTINGS")
    print(f"{'='*60}\\n")
    
    print(f"📦 Found {len(failed)} failed listings to retry\\n")
    
    # Initialize clients
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    # Get listing details from DB
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    
    success_count = 0
    failed_count = 0
    
    for idx, listing in enumerate(failed, 1):
        product_id = listing['product_id']
        ebay_item_id = listing['ebay_item_id']
        sku = listing['sku']
        
        print(f"\\n[{idx}/{len(failed)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        print(f"  SKU: {sku}")
        
        # Get category
        row = conn.execute('''
            SELECT category_id
            FROM products
            WHERE aliexpress_product_id = ?
        ''', (product_id,)).fetchone()
        
        if not row:
            print(f"  ❌ Product not found in DB")
            failed_count += 1
            continue
        
        category_id = row['category_id']
        
        # Extract aspects
        try:
            print(f"  🔍 Extracting aspects...")
            aspects = extract_aspects_for_product(ali, ebay, product_id, category_id)
            print(f"  📊 Extracted {len(aspects)} aspects")
        except Exception as e:
            print(f"  ❌ Aspect extraction failed: {e}")
            failed_count += 1
            continue
        
        # Update inventory item
        try:
            print(f"  📤 Updating inventory item...")
            if update_inventory_item_aspects(ebay, sku, aspects):
                print(f"  ✅ Inventory item updated")
            else:
                print(f"  ❌ Inventory item update failed")
                failed_count += 1
                continue
        except Exception as e:
            print(f"  ❌ Inventory item update failed: {e}")
            failed_count += 1
            continue
        
        # Refresh offer
        try:
            print(f"  🔄 Refreshing offer...")
            if refresh_offer(ebay, sku):
                print(f"  ✅ Offer refreshed")
                success_count += 1
            else:
                print(f"  ⚠️  Offer refresh failed")
                success_count += 1  # Still count as success if inventory updated
        except Exception as e:
            print(f"  ⚠️  Offer refresh failed: {e}")
            success_count += 1  # Still count as success if inventory updated
    
    conn.close()
    
    print(f"\\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed: {len(failed)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Success rate: {success_count / len(failed) * 100:.1f}%")
    print()


if __name__ == '__main__':
    main()
