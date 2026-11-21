#!/usr/bin/env python3
"""
Add Aspects to Description
===========================

Adds item specifics (aspects) as HTML table to description.

WORKFLOW:
1. Get inventory item (has aspects)
2. Extract aspects
3. Build HTML table
4. Append to description
5. Update inventory item
6. Refresh offer

USAGE:
    python scripts/add_aspects_to_description.py              # All listings
    python scripts/add_aspects_to_description.py --limit 3    # Test 3
"""

import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
import sqlite3


def build_aspects_html(aspects: dict) -> str:
    """
    Build COMPACT HTML list from aspects (not table - saves space).
    
    Args:
        aspects: Dict of {aspect_name: [values]}
    
    Returns:
        str: Compact HTML list
    """
    if not aspects:
        return ""
    
    # Build compact list
    items = []
    for name, values in aspects.items():
        # Get value (list or string)
        if isinstance(values, list):
            value = ', '.join(str(v) for v in values)
        else:
            value = str(values)
        
        items.append(f"<b>{name}:</b> {value}")
    
    # Join with separator
    items_html = " • ".join(items)
    
    html = f"""
<div style="margin-top:16px;padding:12px;background:#f8f9fa;border-left:3px solid #1a5276;font-size:12px;">
  <b style="color:#1a5276;">Artikelmerkmale:</b> {items_html}
</div>
"""
    
    return html


def add_aspects_to_description(ebay: eBayRESTClient, sku: str) -> bool:
    """
    Add aspects table to inventory item description.
    
    Args:
        ebay: eBay API client
        sku: Product SKU
    
    Returns:
        bool: Success (or None if skipped due to length)
    """
    try:
        # Get inventory item
        item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
        
        if not item or 'product' not in item:
            print(f"    ⚠️  No product data for SKU: {sku}")
            return False
        
        product = item['product']
        aspects = product.get('aspects', {})
        description = product.get('description', '')
        
        if not aspects:
            print(f"    ⚠️  No aspects to add")
            return False
        
        print(f"    📊 {len(aspects)} aspects found")
        
        # Check if aspects already in description
        if 'Artikelmerkmale' in description:
            print(f"    ℹ️  Aspects already in description (skipping)")
            return None  # Skip, not failure
        
        # Build aspects HTML
        aspects_html = build_aspects_html(aspects)
        
        # Check length BEFORE adding
        new_description = description + aspects_html
        
        if len(new_description) > 4000:
            print(f"    ⚠️  Description too long ({len(description)} + {len(aspects_html)} = {len(new_description)} > 4000)")
            print(f"    ℹ️  Skipping (not enough space)")
            return None  # Skip, not failure
        
        # Update product
        product['description'] = new_description
        
        # Send PUT request
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=item)
        
        print(f"    ✅ Aspects added to description ({len(aspects)} items, {len(new_description)} chars)")
        return True
        
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def refresh_offer(ebay: eBayRESTClient, sku: str) -> bool:
    """Refresh offer to sync changes."""
    try:
        from urllib.parse import quote
        
        encoded_sku = quote(sku, safe='')
        path = f'/sell/inventory/v1/offer?sku={encoded_sku}'
        
        response = ebay._request('GET', path)
        offers = response.get('offers', [])
        
        if not offers:
            return False
        
        offer_id = offers[0]['offerId']
        offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        
        # Remove read-only fields
        for field in ['offerId', 'status', 'listingId', 'listing']:
            offer.pop(field, None)
        
        ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=offer)
        print(f"    ✅ Offer refreshed")
        return True
        
    except Exception as e:
        print(f"    ⚠️  Offer refresh failed: {e}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Add aspects to listing descriptions')
    parser.add_argument('--limit', type=int, help='Limit number of listings')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"ADD ASPECTS TO DESCRIPTIONS")
    print(f"{'='*60}\n")
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get listings from DB
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    
    query = """
        SELECT p.id, p.aliexpress_product_id, p.title, p.ebay_item_id, pv.sku
        FROM products p
        INNER JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.ebay_item_id IS NOT NULL
          AND pv.sku IS NOT NULL
        GROUP BY p.id
    """
    
    if args.limit:
        query += f" LIMIT {args.limit}"
    
    cursor = conn.cursor()
    cursor.execute(query)
    listings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"📦 Found {len(listings)} active published listings\n")
    
    # Process each
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for idx, listing in enumerate(listings, 1):
        product_id = listing['aliexpress_product_id']
        ebay_item_id = listing['ebay_item_id']
        title = listing['title']
        sku = listing['sku']
        
        print(f"\n[{idx}/{len(listings)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        print(f"  Title: {title[:60]}...")
        print(f"  SKU: {sku}")
        
        # Add aspects to description
        result = add_aspects_to_description(ebay, sku)
        
        if result is True:
            # Refresh offer
            refresh_offer(ebay, sku)
            success_count += 1
        elif result is False:
            failed_count += 1
        else:  # None = skipped
            skipped_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed: {len(listings)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  ℹ️  Skipped: {skipped_count}")
    print(f"  Success rate: {success_count / len(listings) * 100:.1f}%")
    print()


if __name__ == '__main__':
    main()
