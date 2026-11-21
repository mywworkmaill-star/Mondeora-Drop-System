#!/usr/bin/env python3
"""
Update eBay Offer Prices from Database
=======================================

Sync database prices to eBay via Inventory API.

USAGE:
    python scripts/update_ebay_prices.py
    python scripts/update_ebay_prices.py --dry-run
    python scripts/update_ebay_prices.py --limit 5
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


def get_products_with_price_changes():
    """
    Get products where database price differs from eBay price.
    
    Returns:
        list: Products needing price update
    """
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            aliexpress_product_id,
            title,
            ebay_item_id,
            ebay_price,
            aliexpress_price,
            sku_id
        FROM products
        WHERE ebay_item_id IS NOT NULL
          AND ebay_price IS NOT NULL
          AND sku_id IS NOT NULL
        ORDER BY aliexpress_product_id
    ''')
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products


def update_ebay_offer_price(ebay, sku, new_price, dry_run=False):
    """
    Update eBay offer price via Inventory API.
    
    Args:
        ebay: eBay client
        sku: Product SKU
        new_price: New price (EUR)
        dry_run: If True, don't actually update
    
    Returns:
        bool: Success
    """
    if dry_run:
        return True
    
    try:
        from urllib.parse import quote
        encoded_sku = quote(sku, safe='')
        
        # Get current offer
        response = ebay.session.get(
            f'{ebay.production_url}/sell/inventory/v1/offer?sku={encoded_sku}',
            headers=ebay._get_headers()
        )
        
        if response.status_code == 404:
            print(f"    ⚠️  No offer found for SKU {sku}")
            return False
        
        response.raise_for_status()
        offers = response.json().get('offers', [])
        
        if not offers:
            print(f"    ⚠️  No offers returned")
            return False
        
        offer = offers[0]
        offer_id = offer['offerId']
        
        # Update price
        update_data = {
            "offerId": offer_id,
            "availableQuantity": offer.get('availableQuantity', 1),
            "categoryId": offer.get('categoryId'),
            "listingDescription": offer.get('listingDescription'),
            "listingPolicies": offer.get('listingPolicies'),
            "merchantLocationKey": offer.get('merchantLocationKey'),
            "pricingSummary": {
                "price": {
                    "currency": "EUR",
                    "value": str(new_price)
                }
            },
            "quantityLimitPerBuyer": offer.get('quantityLimitPerBuyer', 1),
            "sku": sku,
            "storeCategoryNames": offer.get('storeCategoryNames', []),
            "marketplaceId": "EBAY_DE",
            "format": "FIXED_PRICE"
        }
        
        # PUT update
        update_response = ebay.session.put(
            f'{ebay.production_url}/sell/inventory/v1/offer/{offer_id}',
            json=update_data,
            headers=ebay._get_headers()
        )
        
        if update_response.status_code == 200 or update_response.status_code == 204:
            print(f"    ✅ eBay offer updated")
            return True
        else:
            print(f"    ❌ eBay update failed: {update_response.status_code}")
            print(f"       {update_response.text[:200]}")
            return False
        
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update eBay prices from database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--limit', type=int, help='Limit number of updates')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get products
    products = get_products_with_price_changes()
    
    print(f"\n{'='*70}")
    print(f"UPDATE EBAY PRICES FROM DATABASE")
    print(f"{'='*70}\n")
    
    print(f"📦 Found {len(products)} products with ebay_item_id\n")
    
    if args.dry_run:
        print(f"🔍 DRY RUN MODE (no changes will be made)\n")
    
    if args.limit:
        products = products[:args.limit]
        print(f"  ⚙️  Limited to {args.limit} products\n")
    
    stats = {'total': 0, 'updated': 0, 'failed': 0, 'skipped': 0}
    
    for i, product in enumerate(products, 1):
        product_id = product['aliexpress_product_id']
        sku = product['sku_id']  # Use real eBay SKU from database
        title = product['title']
        price = product['ebay_price']
        
        print(f"[{i}/{len(products)}] {product_id}")
        print(f"  {title[:50]}...")
        print(f"  Price: €{price:.2f}")
        
        stats['total'] += 1
        
        if args.dry_run:
            print(f"  🔍 DRY RUN - would update eBay offer")
            stats['updated'] += 1
        else:
            success = update_ebay_offer_price(ebay, sku, price, dry_run=False)
            
            if success:
                stats['updated'] += 1
            else:
                stats['failed'] += 1
            
            # Rate limit
            time.sleep(0.5)
        
        print()
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  Total: {stats['total']}")
    print(f"  ✅ Updated: {stats['updated']}")
    print(f"  ❌ Failed: {stats['failed']}")
    print(f"  ⏭️  Skipped: {stats['skipped']}")
    print(f"{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
