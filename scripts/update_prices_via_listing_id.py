#!/usr/bin/env python3
"""
Update eBay Prices via Listing ID
==================================

Direct price update using eBay Item ID (not SKU).

USAGE:
    python scripts/update_prices_via_listing_id.py
    python scripts/update_prices_via_listing_id.py --dry-run
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import time

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def get_products_to_update():
    """Get products with ebay_item_id and price."""
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            aliexpress_product_id,
            title,
            ebay_item_id,
            ebay_price
        FROM products
        WHERE ebay_item_id IS NOT NULL
          AND ebay_price IS NOT NULL
        ORDER BY aliexpress_product_id
    ''')
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products


def update_price_via_inventory_api(ebay, item_id, new_price, dry_run=False):
    """
    Update price by fetching inventory item, finding offer, updating offer.
    
    Args:
        ebay: eBay client
        item_id: eBay listing ID
        new_price: New price (EUR)
        dry_run: If True, don't actually update
    
    Returns:
        bool: Success
    """
    if dry_run:
        return True
    
    try:
        # Get all inventory items
        response = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={
            'limit': 200
        })
        
        items = response.get('inventoryItems', [])
        
        # Find item with matching listing ID
        target_sku = None
        
        for item in items:
            sku = item.get('sku', '')
            
            # Check if this SKU has an offer with our item_id
            try:
                from urllib.parse import quote
                encoded_sku = quote(sku, safe='')
                offer_response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
                offers = offer_response.get('offers', [])
                
                for offer in offers:
                    listing_id = offer.get('listing', {}).get('listingId')
                    if listing_id == item_id:
                        target_sku = sku
                        target_offer_id = offer['offerId']
                        current_offer = offer
                        break
                
                if target_sku:
                    break
                    
            except:
                continue
        
        if not target_sku:
            print(f"    ❌ No SKU found for listing {item_id}")
            return False
        
        print(f"    📦 Found SKU: {target_sku}")
        print(f"    🆔 Offer ID: {target_offer_id}")
        
        # Update offer
        update_data = {
            "offerId": target_offer_id,
            "availableQuantity": current_offer.get('availableQuantity', 1),
            "categoryId": current_offer.get('categoryId'),
            "listingDescription": current_offer.get('listingDescription'),
            "listingPolicies": current_offer.get('listingPolicies'),
            "merchantLocationKey": current_offer.get('merchantLocationKey'),
            "pricingSummary": {
                "price": {
                    "currency": "EUR",
                    "value": str(new_price)
                }
            },
            "quantityLimitPerBuyer": current_offer.get('quantityLimitPerBuyer', 1),
            "sku": target_sku,
            "storeCategoryNames": current_offer.get('storeCategoryNames', []),
            "marketplaceId": "EBAY_DE",
            "format": "FIXED_PRICE"
        }
        
        update_response = ebay._request('PUT', f'/sell/inventory/v1/offer/{target_offer_id}', json=update_data)
        
        print(f"    ✅ Price updated: €{new_price}")
        return True
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update eBay prices via listing ID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--limit', type=int, help='Limit number of updates')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get products
    products = get_products_to_update()
    
    print(f"\n{'='*70}")
    print(f"UPDATE EBAY PRICES VIA LISTING ID")
    print(f"{'='*70}\n")
    
    print(f"📦 Found {len(products)} products\n")
    
    if args.dry_run:
        print(f"🔍 DRY RUN MODE\n")
    
    if args.limit:
        products = products[:args.limit]
        print(f"  ⚙️  Limited to {args.limit} products\n")
    
    stats = {'total': 0, 'updated': 0, 'failed': 0}
    
    for i, product in enumerate(products, 1):
        product_id = product['aliexpress_product_id']
        item_id = product['ebay_item_id']
        title = product['title']
        price = product['ebay_price']
        
        print(f"[{i}/{len(products)}] {product_id}")
        print(f"  {title[:50]}...")
        print(f"  Item ID: {item_id}")
        print(f"  Price: €{price:.2f}")
        
        stats['total'] += 1
        
        if args.dry_run:
            print(f"  🔍 DRY RUN - would update")
            stats['updated'] += 1
        else:
            success = update_price_via_inventory_api(ebay, item_id, price, dry_run=False)
            
            if success:
                stats['updated'] += 1
            else:
                stats['failed'] += 1
            
            time.sleep(1)  # Rate limit
        
        print()
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  Total: {stats['total']}")
    print(f"  ✅ Updated: {stats['updated']}")
    print(f"  ❌ Failed: {stats['failed']}")
    print(f"{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
