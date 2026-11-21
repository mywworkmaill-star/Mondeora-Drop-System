#!/usr/bin/env python3
"""
Re-publish Existing eBay Listings with Enriched Aspects
Updates published listings via eBay Inventory API.
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayRESTClient
from src.runtime import read_config
from scripts.extract_aspects_from_description import extract_aspects_for_product


def get_published_listings(db_path):
    """Get all published listings from database with real eBay SKUs."""
    
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    
    # Get products with their variants' SKUs
    # Note: eBay uses product_variants.sku, not a generated SKU
    query = '''
        SELECT 
            p.id,
            p.aliexpress_product_id as product_id,
            p.title,
            p.ebay_item_id,
            p.ebay_price,
            p.category_id as ebay_category_id,
            pv.sku
        FROM products p
        LEFT JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.ebay_item_id IS NOT NULL
        AND p.ebay_item_id != ''
        AND p.status != 'DELISTED'
        AND pv.sku IS NOT NULL
        ORDER BY p.id DESC
    '''
    
    rows = db.execute(query).fetchall()
    db.close()
    
    # Group by product, keeping first SKU
    seen = set()
    results = []
    for row in rows:
        r = dict(row)
        if r['ebay_item_id'] not in seen:
            seen.add(r['ebay_item_id'])
            results.append(r)
    
    return results


def get_offer_id_from_item(ebay, item_id, sku=None):
    """Get offer ID from eBay item ID using SKU.
    
    Args:
        ebay: eBay REST client
        item_id: eBay item ID (may not be used, kept for reference)
        sku: Product SKU (required - read from DB)
    
    Returns:
        Offer ID string or None
    """
    
    if not sku:
        print(f"    ⚠️  No SKU provided for item {item_id}")
        return None
    
    try:
        # Get offers for this SKU from Inventory API
        offers_response = ebay._request('GET', f'/sell/inventory/v1/offer',
                                       params={'sku': sku})
        
        offers = offers_response.get('offers', [])
        if not offers:
            print(f"    ⚠️  No offers found for SKU {sku}")
            return None
        
        # Get the first published offer
        for offer in offers:
            if offer.get('status') == 'PUBLISHED':
                offer_id = offer.get('offerId')
                print(f"    ✅ Found offer ID: {offer_id} (SKU: {sku})")
                return offer_id
        
        # If no published offer, return first offer
        offer_id = offers[0].get('offerId')
        status = offers[0].get('status', 'unknown')
        print(f"    ⚠️  Using first offer ID: {offer_id} (status: {status})")
        return offer_id
        
    except Exception as e:
        print(f"    ❌ Failed to get offer ID for SKU {sku}: {e}")
        return None


def get_current_offer(ebay, offer_id):
    """Get current offer details from eBay Inventory API."""
    
    try:
        # eBay Inventory API: GET /sell/inventory/v1/offer/{offerId}
        response = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        return response
    except Exception as e:
        print(f"    ❌ Failed to get offer {offer_id}: {e}")
        return None


def update_offer_aspects(ebay, offer_id, sku, new_aspects):
    """Update inventory item aspects and republish offer."""
    
    # Step 1: Update INVENTORY ITEM (not offer)
    # eBay aspects are stored in inventory_item, not in offer
    try:
        print(f"    📦 Updating inventory item (SKU: {sku})...")
        
        # Get current inventory item
        inv_item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
        
        if 'product' not in inv_item:
            inv_item['product'] = {}
        
        # Convert aspects to eBay format: {name: [values]}
        aspects_dict = {}
        for name, value in new_aspects.items():
            aspects_dict[name] = [value] if isinstance(value, str) else value
        
        inv_item['product']['aspects'] = aspects_dict
        
        # DEBUG
        print(f"    🔍 Sending {len(aspects_dict)} aspects to inventory item:")
        for name, values in list(aspects_dict.items())[:5]:
            print(f"       {name}: {values}")
        
        # PUT /sell/inventory/v1/inventory_item/{sku}
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inv_item)
        print(f"    ✅ Inventory item updated")
        
    except Exception as e:
        print(f"    ❌ Failed to update inventory item: {e}")
        return False
    
    # Step 2: Republish the offer to reflect changes
    # eBay requires offer to be withdrawn and republished for aspect changes
    try:
        print(f"    🔄 Republishing offer {offer_id}...")
        
        # Get current offer
        offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
        
        # Withdraw (unpublish) the offer
        ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/withdraw')
        print(f"    ⏸️  Offer withdrawn")
        
        # Publish again
        ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
        print(f"    ✅ Offer republished with new aspects")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Failed to republish offer: {e}")
        # Try to publish back even if we fail
        try:
            ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
        except:
            pass
        return False


def verify_aspects_on_ebay(ebay, item_id):
    """Verify aspects using eBay Buy API."""
    
    try:
        # eBay Browse API: GET /buy/browse/v1/item/{item_id}
        response = ebay._request('GET', f'/buy/browse/v1/item/v1|{item_id}|0',
                                base_url='https://api.ebay.com')
        
        aspects = {}
        for aspect in response.get('localizedAspects', []):
            aspects[aspect['name']] = aspect['value']
        
        return aspects
    except Exception as e:
        print(f"    ⚠️  Verification failed: {e}")
        return {}


def republish_with_aspects(ali, ebay, limit=None):
    """
    Main function: Re-publish all listings with enriched aspects.
    
    Args:
        ali: AliExpress client
        ebay: eBay client
        limit: Max listings to process (None = all)
    
    Returns:
        dict: {success_count, failed_count, results}
    """
    
    print(f"\n{'='*60}")
    print("RE-PUBLISH LISTINGS WITH ENRICHED ASPECTS")
    print(f"{'='*60}\n")
    
    # Get published listings
    db_path = ROOT / 'data' / 'dropshipping.db'
    listings = get_published_listings(db_path)
    
    print(f"📦 Found {len(listings)} published listings")
    
    if limit:
        listings = listings[:limit]
        print(f"🔒 Limited to {limit} listings\n")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for idx, listing in enumerate(listings, 1):
        product_id = listing['product_id']
        sku = listing['sku']
        ebay_item_id = listing['ebay_item_id']
        category_id = listing['ebay_category_id']
        
        print(f"\n[{idx}/{len(listings)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        print(f"  Title: {listing['title'][:50]}...")
        
        if not category_id:
            print(f"  ⚠️  No category ID - skipping")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'skipped',
                'reason': 'no_category_id'
            })
            continue
        
        # Extract aspects
        try:
            aspects = extract_aspects_for_product(ali, ebay, product_id, category_id)
        except Exception as e:
            print(f"  ❌ Aspect extraction failed: {e}")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
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
                'status': 'failed',
                'reason': 'no_aspects_extracted'
            })
            continue
        
        # Update eBay offer
        # First, get the correct offer_id from SKU
        print(f"\n  🔍 Getting offer ID for SKU {sku}...")
        offer_id = get_offer_id_from_item(ebay, ebay_item_id, sku=sku)
        
        if not offer_id:
            print(f"  ❌ Could not find offer ID for item {ebay_item_id}")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'failed',
                'reason': 'offer_id_not_found'
            })
            continue
        
        print(f"  📤 Updating eBay offer {offer_id}...")
        success = update_offer_aspects(ebay, offer_id, sku, aspects)
        
        if success:
            print(f"  ✅ Updated successfully!")
            success_count += 1
            
            # Verify
            print(f"  🔍 Verifying aspects on eBay...")
            verified = verify_aspects_on_ebay(ebay, ebay_item_id)
            
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'success',
                'aspects_added': len(aspects),
                'verified_count': len(verified),
                'aspects': aspects
            })
            
            print(f"  ✅ Verified: {len(verified)} aspects on eBay")
        else:
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'failed',
                'reason': 'update_api_error'
            })
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed: {len(listings)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Success rate: {success_count / len(listings) * 100:.1f}%")
    
    # Save report
    report_path = ROOT / 'data' / 'audit' / 'aspect_republish_report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'total': len(listings),
        'success': success_count,
        'failed': failed_count,
        'results': results
    }
    
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n📄 Report saved: {report_path}")
    
    return report


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Re-publish eBay listings with enriched aspects')
    parser.add_argument('--limit', type=int, help='Max listings to process (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Extract aspects but do not update eBay')
    args = parser.parse_args()
    
    # Initialize clients - they auto-load credentials from .env
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No eBay updates will be made\n")
    
    report = republish_with_aspects(ali, ebay, limit=args.limit)
    
    print(f"\n✅ Done! Check report for details.")
