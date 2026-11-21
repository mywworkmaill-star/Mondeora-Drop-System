#!/usr/bin/env python3
"""
UPDATE ALL LISTINGS WITH ASPECTS - INVENTORY API
=================================================

Inventory API kullanarak tüm active listings'lere aspect ekle.

NEDEN BU SCRIPT:
- XML Trading API çalışmıyor (Error 21919474: MANAGE_BY_INVENTORY)
- Listing'ler Inventory API ile yaratıldı
- Onları güncellemek için de Inventory API kullanmalıyız

YAKLAŞIM:
1. Her listing için AliExpress'ten aspect çıkar
2. Inventory Item'a aspect ekle (PUT /inventory_item/{sku})
3. Offer'ı refresh et (PUT /offer/{offer_id} ile aynı data)

KULLANIM:
    python scripts/update_all_with_inventory_api.py
    python scripts/update_all_with_inventory_api.py --limit 5
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.ebay_client import eBayAPIClient
from src.api.aliexpress_client import AliExpressAPIClient
from scripts.extract_aspects_from_description import extract_aspects_for_product


def get_published_listings(limit=None):
    """Get all active published listings from DB."""
    conn = sqlite3.connect('data/dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all listings - same query as republish_with_aspects.py
    query = """
        SELECT 
            p.id,
            p.aliexpress_product_id as product_id,
            p.title,
            p.ebay_item_id,
            p.category_id as ebay_category_id,
            pv.sku
        FROM products p
        INNER JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.ebay_item_id IS NOT NULL
          AND p.ebay_item_id != ''
          AND pv.sku IS NOT NULL
        GROUP BY p.id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    listings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return listings


def update_inventory_item_aspects(ebay: eBayAPIClient, sku: str, aspects: dict):
    """
    Update inventory item with aspects.
    
    Args:
        ebay: eBay API client
        sku: Product SKU
        aspects: Dict of {aspect_name: value}
    
    Returns:
        bool: Success
    """
    try:
        # First, get current inventory item
        current = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
        
        if not current:
            print(f"    ⚠️  Inventory item not found for SKU: {sku}")
            return False
        
        # Get existing aspects (preserve them!)
        existing_aspects = {}
        if 'product' in current and 'aspects' in current['product']:
            existing_aspects = current['product']['aspects'].copy()
            print(f"    📋 Existing aspects: {len(existing_aspects)}")
        
        # Build NEW aspects DICT (NOT array!)
        # Format: {"Marke": ["Markenlos"], "Produktart": ["Sonstiges"]}
        new_aspects = {}
        for name, value in aspects.items():
            # Skip dict values (like Dimensions)
            if isinstance(value, dict):
                continue
            
            # Normalize to list
            if isinstance(value, list):
                values = [str(v) for v in value if v]
            else:
                values = [str(value)] if value else []
            
            if values:
                new_aspects[name] = values
        
        # MERGE: Keep existing, add new (don't overwrite existing)
        merged_aspects = existing_aspects.copy()
        added_count = 0
        
        for name, values in new_aspects.items():
            if name not in merged_aspects:
                merged_aspects[name] = values
                added_count += 1
        
        if added_count == 0:
            print(f"    ℹ️  All aspects already present (no update needed)")
            return True
        
        # Update product section with merged aspects
        if 'product' not in current:
            current['product'] = {}
        
        current['product']['aspects'] = merged_aspects
        
        # DEBUG: Print update payload
        print(f"    🔍 Adding {added_count} new aspects (keeping {len(existing_aspects)} existing)")
        print(f"    🔍 Total: {len(merged_aspects)} aspects")
        
        # Send PUT request to update inventory item
        try:
            response = ebay._request(
                'PUT',
                f'/sell/inventory/v1/inventory_item/{sku}',
                json=current
            )
            print(f"    ✅ Inventory item updated with {added_count} new aspects")
            return True
        except Exception as e:
            print(f"    ❌ API Error: {e}")
            # Print eBay API error details
            if hasattr(e, 'response_text') and e.response_text:
                print(f"    🔍 eBay Response: {e.response_text[:800]}")
            raise
        
    except Exception as e:
        print(f"    ❌ Failed to update inventory item: {e}")
        import traceback
        traceback.print_exc()
        return False


def refresh_offer(ebay: eBayAPIClient, sku: str):
    """
    Refresh offer to sync aspects from inventory item.
    
    Args:
        ebay: eBay API client
        sku: Product SKU
    
    Returns:
        bool: Success
    """
    try:
        from urllib.parse import quote
        
        # Get offers for this SKU (URL encode the SKU)
        encoded_sku = quote(sku, safe='')
        path = f'/sell/inventory/v1/offer?sku={encoded_sku}'
        
        offers_response = ebay._request('GET', path)
        
        if not offers_response or 'offers' not in offers_response:
            print(f"    ⚠️  No offers found for SKU: {sku}")
            return False
        
        offers = offers_response['offers']
        if not offers:
            print(f"    ⚠️  Empty offers array for SKU: {sku}")
            return False
        
        # Get first offer ID
        offer_id = offers[0]['offerId']
        
        # Get current offer
        offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        
        if not offer:
            print(f"    ⚠️  Offer not found: {offer_id}")
            return False
        
        # Update offer with same data to trigger sync
        # Remove read-only fields
        for field in ['offerId', 'status', 'listingId', 'listing']:
            offer.pop(field, None)
        
        # Send PUT request
        response = ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=offer)
        
        print(f"    ✅ Offer {offer_id} refreshed")
        return True
        
    except Exception as e:
        print(f"    ❌ Failed to refresh offer: {e}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update all listings with aspects via Inventory API')
    parser.add_argument('--limit', type=int, help='Limit number of listings to process')
    parser.add_argument('--dry-run', action='store_true', help='Extract aspects but do not update')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("UPDATE ALL ACTIVE LISTINGS WITH ASPECTS")
    print("Using eBay Inventory API")
    print("=" * 60)
    print()
    
    # Initialize clients
    ali = AliExpressAPIClient()
    ebay = eBayAPIClient()
    
    # Get published listings
    listings = get_published_listings(limit=args.limit)
    
    print(f"📦 Found {len(listings)} active published listings")
    print()
    
    if not listings:
        print("⚠️  No active listings found!")
        return
    
    # Process each listing
    results = []
    success_count = 0
    failed_count = 0
    
    for idx, listing in enumerate(listings, 1):
        product_id = listing['product_id']
        ebay_item_id = listing['ebay_item_id']
        category_id = listing['ebay_category_id']
        title = listing['title']
        sku = listing['sku']
        
        print(f"\n[{idx}/{len(listings)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        print(f"  Title: {title[:60]}...")
        print(f"  SKU: {sku}")
        
        # Extract aspects
        try:
            print(f"  🔍 Extracting aspects...")
            aspects = extract_aspects_for_product(ali, ebay, product_id, category_id)
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Aspect extraction failed: {error_msg}")
            
            # If category error (HTTP 400), try with a fallback category
            if 'HTTP 400' in error_msg and category_id == '3024':
                print(f"  🔄 Retrying with fallback category 20741...")
                try:
                    aspects = extract_aspects_for_product(ali, ebay, product_id, '20741')
                except Exception as e2:
                    print(f"  ❌ Fallback also failed: {e2}")
                    failed_count += 1
                    results.append({
                        'product_id': product_id,
                        'ebay_item_id': ebay_item_id,
                        'sku': sku,
                        'status': 'failed',
                        'reason': f'extraction_error: {type(e2).__name__}'
                    })
                    continue
            else:
                failed_count += 1
                results.append({
                    'product_id': product_id,
                    'ebay_item_id': ebay_item_id,
                    'sku': sku,
                    'status': 'failed',
                    'reason': f'extraction_error: {type(e).__name__}'
                })
                continue
        
        if not aspects:
            print(f"  ⚠️  No aspects extracted")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'status': 'failed',
                'reason': 'no_aspects'
            })
            continue
        
        print(f"  📊 Extracted {len(aspects)} aspects")
        
        if args.dry_run:
            print(f"  🔍 DRY RUN - would update with aspects:")
            for name, value in list(aspects.items())[:5]:
                print(f"    - {name}: {value}")
            success_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'status': 'dry_run',
                'aspects_count': len(aspects)
            })
            continue
        
        # Update inventory item
        print(f"  📤 Updating inventory item...")
        update_success = update_inventory_item_aspects(ebay, sku, aspects)
        
        if not update_success:
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'status': 'failed',
                'reason': 'inventory_update_failed'
            })
            continue
        
        # Refresh offer
        print(f"  🔄 Refreshing offer...")
        refresh_success = refresh_offer(ebay, sku)
        
        if refresh_success:
            success_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'status': 'success',
                'aspects_count': len(aspects)
            })
            print(f"  ✅ Update complete")
        else:
            # Inventory updated but offer refresh failed
            # Still count as partial success
            success_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'status': 'partial',
                'reason': 'offer_refresh_failed',
                'aspects_count': len(aspects)
            })
            print(f"  ⚠️  Inventory updated but offer refresh failed")
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total processed: {len(listings)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Success rate: {success_count/len(listings)*100:.1f}%")
    
    # Save report
    report_path = Path('data/audit/inventory_aspect_update_report.json')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total': len(listings),
        'success': success_count,
        'failed': failed_count,
        'success_rate': success_count / len(listings) if listings else 0,
        'dry_run': args.dry_run,
        'results': results
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Report saved: {report_path}")
    
    if not args.dry_run:
        print(f"\n✅ Done! Check eBay.de listings - aspects should be visible now!")


if __name__ == '__main__':
    main()
