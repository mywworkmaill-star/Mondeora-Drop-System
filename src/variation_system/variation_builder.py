"""
Variation System - Build eBay variation listings
Handles multi-SKU products (color/size variants)
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json
from datetime import datetime

class VariationBuilder:
    """Build eBay variation listings"""
    
    def __init__(self):
        self.ebay = eBayAPIClient()
        self.conn = sqlite3.connect('data/dropshipping.db')
        self.cursor = self.conn.cursor()
    
    def get_variation_products(self):
        """Get all products that need variation listing"""
        self.cursor.execute('''
            SELECT id, title, aliexpress_product_id, 
                   ebay_price, aspects, image_url
            FROM products
            WHERE status = 'needs_variation_listing'
               OR (status = 'ready_to_list' AND id IN (
                   SELECT MIN(id) FROM products
                   WHERE status IN ('needs_variation_listing', 'ready_to_list')
                   GROUP BY aliexpress_product_id
                   HAVING COUNT(*) > 1
               ))
            ORDER BY aliexpress_product_id, id
        ''')
        
        products = self.cursor.fetchall()
        return products
    
    def group_by_parent(self, products):
        """Group variants by parent product (AliExpress ID)"""
        groups = {}
        
        for pid, title, ali_id, price, aspects_json, images in products:
            if ali_id not in groups:
                groups[ali_id] = []
            
            aspects = json.loads(aspects_json) if aspects_json else {}
            images_list = [i.strip() for i in images.split(',') if i and i.strip()] if images else []
            
            groups[ali_id].append({
                'id': pid,
                'title': title,
                'price': float(price) if price else 0,
                'aspects': aspects,
                'images': images_list
            })
        
        return groups
    
    def detect_variation_aspects(self, variants):
        """Detect which aspects vary (Farbe, Größe, etc.)"""
        if len(variants) < 2:
            return []
        
        # Common variation aspects in German
        variation_candidates = ['Farbe', 'Größe', 'Stil', 'Modell', 'Material']
        
        varying_aspects = []
        
        for aspect_name in variation_candidates:
            values = set()
            for v in variants:
                if aspect_name in v['aspects']:
                    values.add(v['aspects'][aspect_name])
            
            if len(values) > 1:  # This aspect varies!
                varying_aspects.append(aspect_name)
        
        return varying_aspects
    
    def build_inventory_item_group(self, ali_id, variants, variation_aspects):
        """Build eBay inventory item group payload"""
        
        # Use first variant as template
        template = variants[0]
        
        # Build variation specifications
        specifications = []
        for aspect in variation_aspects:
            values = []
            for v in variants:
                if aspect in v['aspects']:
                    value = v['aspects'][aspect]
                    if value not in values:
                        values.append(value)
            
            specifications.append({
                'name': aspect,
                'values': values
            })
        
        # Group title (generic, no color/size)
        group_title = template['title']
        for aspect in variation_aspects:
            # Remove color/size from title
            if aspect in template['aspects']:
                group_title = group_title.replace(template['aspects'][aspect], '').strip()
                group_title = group_title.replace('  ', ' ')  # Remove double spaces
        
        payload = {
            'title': group_title[:80],
            'description': 'Verfügbar in verschiedenen Varianten. Bitte wählen Sie Ihre bevorzugte Option.',
            'imageUrls': template['images'][:12],
            'aspects': {k: v for k, v in template['aspects'].items() if k not in variation_aspects},
            'variantSKUs': [],
            'variesBy': {
                'specifications': specifications
            }
        }
        
        # Add variant SKUs
        for v in variants:
            variant_sku = f"AE{ali_id}-{v['id']}"
            payload['variantSKUs'].append(variant_sku)
        
        return payload
    
    def create_variation_listing(self, ali_id, variants):
        """Create eBay variation listing"""
        
        print(f'\nProcessing AliExpress {ali_id} ({len(variants)} variants)...')
        
        # Detect variation aspects
        variation_aspects = self.detect_variation_aspects(variants)
        
        if not variation_aspects:
            print(f'  ⚠️  No variation aspects detected')
            return False
        
        print(f'  Variation aspects: {", ".join(variation_aspects)}')
        
        # Create inventory items for each variant
        for v in variants:
            sku = f"AE{ali_id}-{v['id']}"
            
            inventory_data = {
                'product': {
                    'title': v['title'][:80],
                    'description': v['title'],
                    'imageUrls': v['images'][:12],
                    'aspects': v['aspects']
                },
                'condition': 'NEW',
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': 100
                    }
                }
            }
            
            try:
                self.ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_data)
                print(f'  ✓ Created inventory item: {sku}')
            except Exception as e:
                print(f'  ⚠️  Inventory item {sku}: {str(e)[:40]}')
        
        # Create inventory item group
        group_id = f"GROUP_AE{ali_id}"
        group_data = self.build_inventory_item_group(ali_id, variants, variation_aspects)
        
        try:
            self.ebay._request('PUT', f'/sell/inventory/v1/inventory_item_group/{group_id}', json=group_data)
            print(f'  ✅ Created item group: {group_id}')
        except Exception as e:
            print(f'  ❌ Item group failed: {str(e)[:60]}')
            return False
        
        # Create offer for the group
        offer_data = {
            'format': 'FIXED_PRICE',
            'marketplaceId': 'EBAY_DE',
            'categoryId': '43504',
            'listingPolicies': {
                'fulfillmentPolicyId': '263035514017',
                'paymentPolicyId': '263035507017',
                'returnPolicyId': '263035512017'
            },
            'merchantLocationKey': 'WAREHOUSE_DE_1',
            'inventoryItemGroupKey': group_id,
            'pricingSummary': {
                'price': {
                    'value': str(round(variants[0]['price'], 2)),
                    'currency': 'EUR'
                }
            }
        }
        
        try:
            result_offer = self.ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
            offer_id = result_offer['offerId']
            print(f'  ✓ Created offer: {offer_id}')
            
            # Publish
            result_publish = self.ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
            listing_id = result_publish['listingId']
            
            print(f'  ✅ PUBLISHED: {listing_id}')
            
            # Update database
            for v in variants:
                self.cursor.execute('''
                    UPDATE products
                    SET ebay_item_id = ?,
                        ebay_offer_id = ?,
                        is_listed = 1,
                        status = 'listed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (listing_id, offer_id, v['id']))
            
            self.conn.commit()
            
            return True
            
        except Exception as e:
            print(f'  ❌ Offer/publish failed: {str(e)[:60]}')
            return False
    
    def process_all(self):
        """Process all variation products"""
        
        products = self.get_variation_products()
        print(f'Found {len(products)} products for variation listing')
        
        groups = self.group_by_parent(products)
        print(f'Grouped into {len(groups)} parent products')
        print()
        
        stats = {
            'total_groups': len(groups),
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for ali_id, variants in groups.items():
            if len(variants) < 2:
                print(f'AliExpress {ali_id}: Only 1 variant, skipping')
                stats['skipped'] += 1
                continue
            
            success = self.create_variation_listing(ali_id, variants)
            
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1
        
        return stats
    
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()


if __name__ == '__main__':
    print('=' * 80)
    print('VARIATION SYSTEM - BUILD MULTI-SKU LISTINGS')
    print('=' * 80)
    print()
    
    start_time = datetime.now()
    
    builder = VariationBuilder()
    stats = builder.process_all()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print('=' * 80)
    print('VARIATION BUILD SUMMARY')
    print('=' * 80)
    print()
    print(f'Total Parent Products: {stats["total_groups"]}')
    print(f'Successfully Listed:   {stats["success"]}')
    print(f'Failed:                {stats["failed"]}')
    print(f'Skipped (single):      {stats["skipped"]}')
    print()
    print(f'Completed in {duration:.1f} seconds ({duration/60:.1f} minutes)')
    print('=' * 80)
