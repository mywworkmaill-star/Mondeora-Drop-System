#!/usr/bin/env python3
"""Fix missing images for 4 eBay listings by adding 6+ supplier photos."""
import sys
import json
from pathlib import Path

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import images

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / 'data' / 'audit'

# eBay item ID -> keyword for matching
TARGETS = {
    '860133993419': 'Hundeleine',
    '860139539563': 'Toocki',  # This is an item group (variations)
    '860139559198': 'Tür',  # "Über Die Tür" in cache
    '860139559384': 'Müllbeutelhalter'
}


def find_sku_for_listing(ebay, ebay_item_id, keyword):
    """Find SKU by querying inventory items and matching by title keyword.
    Returns (sku, is_variation_group) tuple."""
    print(f"Looking up SKU for {ebay_item_id} via inventory items...", file=sys.stderr)
    
    # Find by title match in inventory_item
    offset = 0
    
    while offset < 200:  # Max 200 inventory items
        try:
            resp = ebay._request('GET', '/sell/inventory/v1/inventory_item',
                               params={'limit': 25, 'offset': offset})
            items = resp.get('inventoryItems', [])
            
            if not items:
                break
            
            for item in items:
                sku = item['sku']
                title = item.get('product', {}).get('title', '')
                
                # For item groups, return the base SKU without variant suffix
                if keyword.lower() in title.lower():
                    # Check if this is a variant SKU
                    is_variation = '-12000' in sku
                    
                    if is_variation:
                        # Extract base SKU (without variant ID)
                        base_sku = sku.split('-12000')[0]
                        print(f"  ✓ Found base SKU: {base_sku} (from variant {sku[:40]}...)", file=sys.stderr)
                        return base_sku, True
                    else:
                        print(f"  ✓ Found SKU: {sku} - {title[:50]}", file=sys.stderr)
                        return sku, False
            
            offset += 25
                
        except Exception as e:
            print(f"  Error during inventory lookup: {e}", file=sys.stderr)
            break
    
    print(f"  SKU not found", file=sys.stderr)
    return None, False


def find_raw_cache_by_title(keyword):
    """Find raw_*.json cache file by matching title keyword."""
    print(f"Searching cache for '{keyword}'...", file=sys.stderr)
    
    for f in CACHE_DIR.glob('raw_*.json'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            subject = data.get('ae_item_base_info_dto', {}).get('subject', '')
            
            if keyword.lower() in subject.lower():
                product_id = data.get('ae_item_base_info_dto', {}).get('product_id')
                print(f"  Found: {f.name} - {subject[:60]}", file=sys.stderr)
                return data, product_id
        except Exception:
            continue
    
    print(f"  NOT FOUND in cache", file=sys.stderr)
    return None, None


def get_image_urls_from_raw(raw_data):
    """Extract main gallery URLs from raw AliExpress data."""
    image_urls_str = raw_data.get('ae_multimedia_info_dto', {}).get('image_urls', '')
    
    if not image_urls_str:
        return []
    
    # Split by semicolon
    urls = [u.strip() for u in image_urls_str.split(';') if u.strip()]
    
    # Make them canonical (full https URLs)
    canonical = []
    for url in urls:
        if url.startswith('//'):
            url = 'https:' + url
        elif not url.startswith('http'):
            url = 'https://' + url
        canonical.append(url)
    
    return canonical


def update_all_variant_skus(ebay, base_sku, image_urls):
    """Update all variant SKUs for a variation group."""
    print(f"\nFinding all variants for {base_sku}...", file=sys.stderr)
    
    variant_skus = []
    offset = 0
    
    # Find all variant SKUs
    while offset < 200:
        try:
            resp = ebay._request('GET', '/sell/inventory/v1/inventory_item',
                               params={'limit': 25, 'offset': offset})
            items = resp.get('inventoryItems', [])
            
            if not items:
                break
            
            for item in items:
                sku = item['sku']
                if sku.startswith(base_sku + '-'):
                    variant_skus.append(sku)
            
            offset += 25
        except Exception as e:
            print(f"  Error finding variants: {e}", file=sys.stderr)
            break
    
    print(f"  Found {len(variant_skus)} variants", file=sys.stderr)
    
    # Update each variant
    success_count = 0
    for sku in variant_skus:
        try:
            # GET current inventory_item
            current = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            
            # Update imageUrls
            current['product']['imageUrls'] = image_urls
            
            # PUT back
            ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}',
                         json=current)
            success_count += 1
        except Exception as e:
            print(f"  ✗ Failed to update {sku}: {e}", file=sys.stderr)
    
    print(f"  ✓ Updated {success_count}/{len(variant_skus)} variants", file=sys.stderr)
    return success_count > 0


def update_inventory_images(ebay, sku, image_urls, is_variation_group=False):
    """Update inventory_item or all variants with new images via PUT."""
    print(f"\nUpdating {sku} with {len(image_urls)} images...", file=sys.stderr)
    
    try:
        if is_variation_group:
            # Update all variant SKUs individually
            return update_all_variant_skus(ebay, sku, image_urls)
        else:
            # Regular single-SKU item
            endpoint = f'/sell/inventory/v1/inventory_item/{sku}'
            
            # GET current inventory_item
            current = ebay._request('GET', endpoint)
            
            # Update imageUrls only
            current['product']['imageUrls'] = image_urls
            
            # PUT back
            ebay._request('PUT', endpoint, json=current)
        
        print(f"  ✓ Updated successfully", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to update: {e}", file=sys.stderr)
        return False


def verify_with_browse_api(ebay, ebay_item_id):
    """Verify the listing via Browse API (buyer's view)."""
    print(f"\nVerifying {ebay_item_id} via Browse API...", file=sys.stderr)
    
    try:
        # Try single item first
        item = ebay._request('GET', '/buy/browse/v1/item/get_item_by_legacy_id',
                            params={'legacy_item_id': ebay_item_id})
        
        images = []
        if item.get('image', {}).get('imageUrl'):
            images.append(item['image']['imageUrl'])
        if item.get('additionalImages'):
            images.extend([img.get('imageUrl') for img in item['additionalImages']])
        
        print(f"  ✓ Single item: {len(images)} images visible to buyers", file=sys.stderr)
        return len(images)
        
    except Exception as e:
        # Might be an item group
        if 'HTTP 400' in str(e):
            try:
                result = ebay._request('GET', '/buy/browse/v1/item/get_items_by_item_group',
                                      params={'item_group_id': ebay_item_id})
                items = result.get('items', [])
                
                if items:
                    # Check first variant's images
                    item = items[0]
                    images = []
                    if item.get('image', {}).get('imageUrl'):
                        images.append(item['image']['imageUrl'])
                    if item.get('additionalImages'):
                        images.extend([img.get('imageUrl') for img in item['additionalImages']])
                    
                    print(f"  ✓ Item group: {len(items)} variants, {len(images)} images on first variant", file=sys.stderr)
                    return len(images)
            except Exception as e2:
                print(f"  ✗ Browse verification failed: {e2}", file=sys.stderr)
        else:
            print(f"  ✗ Browse verification failed: {e}", file=sys.stderr)
    
    return 0


def main():
    ebay = eBayAPIClient()
    
    # Refresh token first
    try:
        result = ebay.refresh_access_token()
        if not result.get('success'):
            print("❌ Token refresh failed", file=sys.stderr)
            return 1
        print("✓ Token OK\n", file=sys.stderr)
    except Exception as e:
        print(f"❌ Token error: {e}", file=sys.stderr)
        return 1
    
    results = []
    
    for ebay_item_id, keyword in TARGETS.items():
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Processing {ebay_item_id} ({keyword})", file=sys.stderr)
        print('='*60, file=sys.stderr)
        
        # Step 1: Find SKU
        sku, is_variation = find_sku_for_listing(ebay, ebay_item_id, keyword)
        if not sku:
            results.append({
                'ebay_id': ebay_item_id,
                'status': 'error',
                'message': 'SKU not found'
            })
            continue
        
        # Step 2: Find supplier data in cache
        raw_data, product_id = find_raw_cache_by_title(keyword)
        if not raw_data:
            results.append({
                'ebay_id': ebay_item_id,
                'sku': sku,
                'status': 'error',
                'message': 'Supplier data not found in cache'
            })
            continue
        
        # Step 3: Extract image URLs
        image_urls = get_image_urls_from_raw(raw_data)
        print(f"  Found {len(image_urls)} main gallery images", file=sys.stderr)
        
        # Also try detail images from HTML
        try:
            from src.listing_quality import source
            detail_urls = source.detail_images(raw_data, limit=10)
            print(f"  Found {len(detail_urls)} detail images", file=sys.stderr)
            image_urls.extend(detail_urls)
        except Exception as e:
            print(f"  Could not extract detail images: {e}", file=sys.stderr)
        
        print(f"  Total: {len(image_urls)} images to filter", file=sys.stderr)
        
        if len(image_urls) < 1:
            results.append({
                'ebay_id': ebay_item_id,
                'sku': sku,
                'status': 'error',
                'message': f'Only {len(image_urls)} images available from supplier'
            })
            continue
        
        # Step 4: Filter for good quality (>= 500px)
        print(f"  Filtering for quality (>= 500px)...", file=sys.stderr)
        good_urls, dropped = images.filter_urls(image_urls)
        
        print(f"  ✓ {len(good_urls)} good, {len(dropped)} dropped", file=sys.stderr)
        
        if len(good_urls) < 6:
            # Use all good ones we have
            final_urls = good_urls
        else:
            # Use first 6
            final_urls = good_urls[:6]
        
        if len(final_urls) == 0:
            results.append({
                'ebay_id': ebay_item_id,
                'sku': sku,
                'status': 'error',
                'message': 'No high-quality images available'
            })
            continue
        
        # Step 5: Update inventory
        success = update_inventory_images(ebay, sku, final_urls, is_variation_group=is_variation)
        if not success:
            results.append({
                'ebay_id': ebay_item_id,
                'sku': sku,
                'status': 'error',
                'message': 'Failed to update inventory'
            })
            continue
        
        # Step 6: Verify with Browse API
        visible_count = verify_with_browse_api(ebay, ebay_item_id)
        
        results.append({
            'ebay_id': ebay_item_id,
            'sku': sku,
            'product_id': product_id,
            'status': 'success',
            'images_added': len(final_urls),
            'images_visible': visible_count
        })
    
    # Print summary
    print(f"\n{'='*60}", file=sys.stderr)
    print("SUMMARY", file=sys.stderr)
    print('='*60, file=sys.stderr)
    
    for r in results:
        status_icon = '✓' if r['status'] == 'success' else '✗'
        print(f"{status_icon} {r['ebay_id']}: {r.get('message', r.get('images_visible', 'N/A'))} images visible", file=sys.stderr)
    
    # JSON output
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    return 0 if all(r['status'] == 'success' for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
