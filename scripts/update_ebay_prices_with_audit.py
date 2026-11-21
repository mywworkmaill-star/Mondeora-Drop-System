#!/usr/bin/env python3
"""
Enhanced Update eBay Prices - WITH AUDIT LOGGING
=================================================

Her küçük adımı database'e kaydeder.
"""

import sys
import sqlite3
from pathlib import Path
import time

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.utils.audit_logger import get_logger


def update_ebay_prices_with_audit():
    """Update eBay prices WITH comprehensive audit logging."""
    
    logger = get_logger()
    
    print(f"\n{'='*70}")
    print(f"UPDATE EBAY PRICES (WITH AUDIT LOGGING)")
    print(f"{'='*70}\n")
    
    # Log start
    logger.log(
        action='price_update_batch_start',
        message='Starting eBay price update batch',
        category='price_change',
        level='info'
    )
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get products
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            aliexpress_product_id,
            title,
            ebay_item_id,
            ebay_price,
            sku_id
        FROM products
        WHERE ebay_item_id IS NOT NULL
          AND ebay_price IS NOT NULL
          AND sku_id IS NOT NULL
        ORDER BY aliexpress_product_id
    ''')
    
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"📦 Found {len(products)} products to update\n")
    
    logger.log(
        action='price_update_products_loaded',
        message=f'Loaded {len(products)} products for price update',
        category='price_change',
        level='info',
        data={'product_count': len(products)}
    )
    
    stats = {'total': 0, 'updated': 0, 'failed': 0}
    
    for i, product in enumerate(products, 1):
        product_id = product['aliexpress_product_id']
        sku = product['sku_id']
        item_id = product['ebay_item_id']
        title = product['title']
        new_price = product['ebay_price']
        
        print(f"[{i}/{len(products)}] {product_id}")
        print(f"  {title[:50]}...")
        print(f"  Item ID: {item_id}")
        print(f"  SKU: {sku}")
        print(f"  New Price: €{new_price:.2f}")
        
        stats['total'] += 1
        
        start_time = time.time()
        
        try:
            from urllib.parse import quote
            encoded_sku = quote(sku, safe='')
            
            # Get current offer (LOG API CALL)
            api_start = time.time()
            response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={encoded_sku}')
            api_duration = int((time.time() - api_start) * 1000)
            
            logger.log_api_call(
                endpoint=f'/sell/inventory/v1/offer?sku={sku[:20]}...',
                method='GET',
                success=True,
                duration_ms=api_duration,
                response_code=200
            )
            
            offers = response.get('offers', [])
            
            if not offers:
                print(f"    ⚠️  No offer found")
                
                logger.log_error(
                    action='price_update_no_offer',
                    error_message=f'No offer found for SKU {sku}',
                    product_id=product_id,
                    ebay_item_id=item_id
                )
                
                stats['failed'] += 1
                print()
                continue
            
            offer = offers[0]
            offer_id = offer['offerId']
            current_price = float(offer.get('pricingSummary', {}).get('price', {}).get('value', 0))
            
            # Check if price changed
            if abs(current_price - new_price) < 0.01:
                print(f"    ✅ Already at target price")
                stats['updated'] += 1
                print()
                continue
            
            # Update price (LOG API CALL)
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
            
            api_start = time.time()
            update_response = ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_data)
            api_duration = int((time.time() - api_start) * 1000)
            
            logger.log_api_call(
                endpoint=f'/sell/inventory/v1/offer/{offer_id}',
                method='PUT',
                success=True,
                duration_ms=api_duration,
                response_code=200
            )
            
            # LOG PRICE CHANGE
            logger.log_price_change(
                product_id=product_id,
                ebay_item_id=item_id,
                old_price=current_price,
                new_price=new_price,
                reason='batch_update'
            )
            
            print(f"    ✅ Price updated: €{current_price:.2f} → €{new_price:.2f}")
            stats['updated'] += 1
            
        except Exception as e:
            operation_duration = int((time.time() - start_time) * 1000)
            
            print(f"    ❌ Failed: {e}")
            
            logger.log_error(
                action='price_update_failed',
                error_message=str(e),
                product_id=product_id,
                ebay_item_id=item_id
            )
            
            stats['failed'] += 1
        
        print()
    
    # Log completion
    logger.log(
        action='price_update_batch_complete',
        message=f'Batch complete: {stats["updated"]}/{stats["total"]} updated',
        category='price_change',
        level='success',
        data=stats,
        success=True
    )
    
    print(f"{'='*70}")
    print(f"📊 Summary:")
    print(f"  Total: {stats['total']}")
    print(f"  ✅ Updated: {stats['updated']}")
    print(f"  ❌ Failed: {stats['failed']}")
    print(f"{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(update_ebay_prices_with_audit())
