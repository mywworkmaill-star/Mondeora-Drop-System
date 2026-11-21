"""
Batch Upgrade All Listings to Professional Quality
- Generate professional descriptions
- Add real dimensions
- Revise eBay listings
- Update database
"""

import sys
sys.path.insert(0, 'src')

from generate_description import DescriptionGenerator
from api.ebay_client import eBayAPIClient
import sqlite3
import json
import time
from datetime import datetime

def batch_upgrade_all():
    """Upgrade all listings to professional quality"""
    
    print('=' * 80)
    print('BATCH UPGRADE ALL LISTINGS TO PROFESSIONAL')
    print('=' * 80)
    print()
    
    # Connect to database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # Get all listed products except already professional ones
    cursor.execute('''
        SELECT id, title, ebay_item_id, ebay_offer_id, 
               aliexpress_product_id, LENGTH(description) as desc_len
        FROM products
        WHERE is_listed = 1
          AND id NOT IN (44, 155)
        ORDER BY id
    ''')
    
    products = cursor.fetchall()
    
    print(f'Found {len(products)} products to upgrade')
    print()
    
    # Statistics
    stats = {
        'total': len(products),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }
    
    ebay = eBayAPIClient()
    
    for idx, (pid, title, item_id, offer_id, ali_id, desc_len) in enumerate(products, 1):
        
        print(f'[{idx}/{stats["total"]}] Processing ID {pid}...')
        print(f'  Title: {title[:50]}...')
        print(f'  Current desc: {desc_len} chars')
        
        try:
            # Step 1: Load full product
            cursor.execute('SELECT * FROM products WHERE id = ?', (pid,))
            cursor2 = conn.cursor()
            cursor2.execute('PRAGMA table_info(products)')
            columns = [col[1] for col in cursor2.fetchall()]
            
            row = cursor.fetchone()
            product = dict(zip(columns, row))
            
            # Step 2: Generate professional description
            print('  Generating professional description...')
            result = DescriptionGenerator.generate_for_product(product)
            
            new_desc = result['html']
            category = result['category']
            length = result['length']
            
            print(f'  New desc: {length} chars (category: {category})')
            
            # Step 3: Update database
            cursor.execute('''
                UPDATE products
                SET description = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_desc, pid))
            
            conn.commit()
            
            # Step 4: Revise eBay listing if published
            if item_id or offer_id:
                print('  Revising eBay listing...')
                
                sku = f'AE{ali_id}'
                
                # Parse data
                images = [i.strip() for i in product['image_url'].split(',') if i.strip()][:12]
                aspects = json.loads(product['aspects']) if product['aspects'] else {}
                
                # Update inventory item
                inventory_data = {
                    'product': {
                        'title': product['title'],
                        'description': new_desc,
                        'imageUrls': images,
                        'aspects': aspects
                    },
                    'condition': 'NEW',
                    'availability': {
                        'shipToLocationAvailability': {
                            'quantity': 100
                        }
                    }
                }
                
                try:
                    ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_data)
                    print('  ✅ eBay inventory updated')
                except Exception as e:
                    print(f'  ⚠️  eBay update: {str(e)[:60]}')
                
                # If has offer, withdraw and republish
                if offer_id:
                    try:
                        # Withdraw
                        ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/withdraw')
                        
                        # Delete
                        ebay._request('DELETE', f'/sell/inventory/v1/offer/{offer_id}')
                        
                        # Create new offer
                        offer_data = {
                            'sku': sku,
                            'marketplaceId': 'EBAY_DE',
                            'format': 'FIXED_PRICE',
                            'listingPolicies': {
                                'fulfillmentPolicyId': '263035514017',
                                'paymentPolicyId': '263035507017',
                                'returnPolicyId': '263035512017'
                            },
                            'categoryId': '43504',
                            'pricingSummary': {
                                'price': {
                                    'value': str(round(float(product['ebay_price']), 2)),
                                    'currency': 'EUR'
                                }
                            },
                            'quantityLimitPerBuyer': 10,
                            'merchantLocationKey': 'WAREHOUSE_DE_1'
                        }
                        
                        result_offer = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
                        new_offer_id = result_offer['offerId']
                        
                        # Publish
                        result_publish = ebay._request('POST', f'/sell/inventory/v1/offer/{new_offer_id}/publish')
                        new_listing_id = result_publish['listingId']
                        
                        # Update database
                        cursor.execute('''
                            UPDATE products
                            SET ebay_item_id = ?,
                                ebay_offer_id = ?
                            WHERE id = ?
                        ''', (new_listing_id, new_offer_id, pid))
                        
                        conn.commit()
                        
                        print(f'  ✅ eBay listing revised: {new_listing_id}')
                        
                    except Exception as e:
                        print(f'  ⚠️  eBay revise: {str(e)[:60]}')
            
            stats['success'] += 1
            print(f'  ✅ SUCCESS (ID {pid})')
            
        except Exception as e:
            stats['failed'] += 1
            error_msg = f'ID {pid}: {str(e)[:100]}'
            stats['errors'].append(error_msg)
            print(f'  ❌ FAILED: {str(e)[:60]}')
            import traceback
            traceback.print_exc()
        
        print()
        
        # Rate limiting
        time.sleep(2)
    
    conn.close()
    
    # Print summary
    print('=' * 80)
    print('BATCH UPGRADE SUMMARY')
    print('=' * 80)
    print()
    print(f'Total Products:    {stats["total"]}')
    print(f'Successfully Upgraded: {stats["success"]}')
    print(f'Failed:            {stats["failed"]}')
    print(f'Skipped:           {stats["skipped"]}')
    print()
    
    if stats['errors']:
        print('ERRORS:')
        for error in stats['errors'][:10]:
            print(f'  - {error}')
        if len(stats['errors']) > 10:
            print(f'  ... and {len(stats["errors"]) - 10} more')
    
    print()
    print('=' * 80)
    
    success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f'SUCCESS RATE: {success_rate:.1f}%')
    print('=' * 80)
    
    return stats


if __name__ == '__main__':
    start_time = datetime.now()
    
    print()
    print('Starting batch upgrade...')
    print(f'Time: {start_time}')
    print()
    
    stats = batch_upgrade_all()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print(f'Completed in {duration:.1f} seconds ({duration/60:.1f} minutes)')
    print()
