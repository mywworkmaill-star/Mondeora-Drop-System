#!/usr/bin/env python3
"""
Stock Synchronization Job
Syncs product stock from AliExpress to eBay variation listings

Schedule: Every 30 minutes
Priority: High-velocity products every 5 min, long-tail every 30 min

Flow:
1. Get all variation products with eBay listings
2. For each product, fetch AliExpress stock
3. Compare with current eBay stock
4. Update if changed:
   - Stock > 0: Update quantity, ensure active
   - Stock = 0: Withdraw listing
5. Update database tracking
"""

import sys
sys.path.insert(0, 'src')

import sqlite3
from datetime import datetime, timedelta
from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
import time
from typing import List, Dict


class StockSyncJob:
    """
    Synchronizes stock from AliExpress to eBay variation listings
    """
    
    def __init__(self):
        self.ali = AliExpressAPIClient()
        self.ebay = eBayAPIClient()
        self.db_path = 'data/dropshipping.db'
    
    def get_products_to_sync(self, max_age_minutes: int = 30) -> List[Dict]:
        """
        Get all variation products that need stock sync
        
        Args:
            max_age_minutes: Sync products not checked in last N minutes
        
        Returns:
            List of product dicts with variations
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get products with eBay listings and variations
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        
        cursor.execute('''
            SELECT DISTINCT p.id, p.aliexpress_product_id, p.title, p.ebay_item_id
            FROM products p
            WHERE p.is_variation_product = 1
            AND p.ebay_item_id IS NOT NULL
            AND (
                p.id IN (
                    SELECT DISTINCT product_id 
                    FROM product_variations 
                    WHERE last_stock_check IS NULL 
                    OR last_stock_check < ?
                )
            )
        ''', (cutoff_time,))
        
        products = []
        for row in cursor.fetchall():
            product_id, ali_id, title, ebay_id = row
            
            # Get variations for this product
            cursor.execute('''
                SELECT id, sku, color, length, size, stock, 
                       aliexpress_stock, ebay_active, ebay_offer_id
                FROM product_variations
                WHERE product_id = ?
            ''', (product_id,))
            
            variations = []
            for var_row in cursor.fetchall():
                variations.append({
                    'id': var_row[0],
                    'sku': var_row[1],
                    'color': var_row[2],
                    'length': var_row[3],
                    'size': var_row[4],
                    'stock': var_row[5],
                    'aliexpress_stock': var_row[6],
                    'ebay_active': var_row[7],
                    'ebay_offer_id': var_row[8]
                })
            
            products.append({
                'id': product_id,
                'aliexpress_id': ali_id,
                'title': title,
                'ebay_item_id': ebay_id,
                'variations': variations
            })
        
        conn.close()
        
        return products
    
    def fetch_aliexpress_stock(self, product_id: str) -> Dict:
        """
        Fetch current stock from AliExpress
        
        Args:
            product_id: AliExpress product ID
        
        Returns:
            Dict mapping variant properties to stock count
            Example: {('Black', '1m'): 50, ('White', '2m'): 30}
        """
        
        try:
            # Get product details from AliExpress API
            product_data = self.ali.get_product_details(product_id)
            
            if not product_data:
                print(f"   ⚠️  No data from AliExpress API")
                return {}
            
            # Parse SKU stock info
            # Note: AliExpress API structure may vary
            skus = product_data.get('skus', [])
            
            stock_map = {}
            
            for sku in skus:
                # Extract properties (color, size, length, etc.)
                properties = []
                
                # Try different field names (API varies)
                for field in ['sku_color', 'sku_size', 'sku_length', 'property_value_definition_name']:
                    if field in sku:
                        properties.append(sku[field])
                
                # Get stock
                stock = sku.get('sku_available_stock', 0)
                
                # Map properties tuple to stock
                if properties:
                    key = tuple(properties)
                    stock_map[key] = stock
            
            return stock_map
            
        except Exception as e:
            print(f"   ❌ AliExpress API error: {e}")
            return {}
    
    def match_variation_to_stock(
        self,
        variation: Dict,
        stock_map: Dict
    ) -> int:
        """
        Match a variation to its stock in the AliExpress stock map
        
        Args:
            variation: Variation dict with color, size, length
            stock_map: Dict from fetch_aliexpress_stock()
        
        Returns:
            Stock count (0 if not found)
        """
        
        # Build property tuple from variation
        props = []
        if variation.get('color'):
            props.append(variation['color'])
        if variation.get('size'):
            props.append(variation['size'])
        if variation.get('length'):
            props.append(variation['length'])
        
        # Try exact match
        key = tuple(props)
        if key in stock_map:
            return stock_map[key]
        
        # Try partial matches (order may vary)
        for stock_key, stock in stock_map.items():
            # Check if all our props are in the stock key
            if all(prop in stock_key for prop in props):
                return stock
        
        # No match found
        return 0
    
    def update_ebay_stock(self, sku: str, new_quantity: int) -> bool:
        """
        Update eBay inventory item quantity
        
        Args:
            sku: Inventory item SKU
            new_quantity: New stock quantity
        
        Returns:
            True if successful
        """
        
        try:
            # PUT /inventory_item/{sku}
            # Update availability.shipToLocationAvailability.quantity
            
            inventory_data = {
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': new_quantity
                    }
                }
            }
            
            self.ebay._request(
                'PUT',
                self.ebay.inventory_path + '/inventory_item/' + sku,
                json=inventory_data
            )
            
            return True
            
        except Exception as e:
            print(f"   ❌ eBay update failed for {sku}: {e}")
            return False
    
    def withdraw_listing(self, offer_id: str) -> bool:
        """
        Withdraw eBay offer (out of stock)
        
        Args:
            offer_id: eBay offer ID
        
        Returns:
            True if successful
        """
        
        try:
            # POST /offer/{offer_id}/withdraw
            self.ebay._request(
                'POST',
                self.ebay.inventory_path + '/offer/' + offer_id + '/withdraw'
            )
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  Withdraw failed for {offer_id}: {e}")
            return False
    
    def publish_offer(self, offer_id: str) -> bool:
        """
        Re-publish eBay offer (back in stock)
        
        Args:
            offer_id: eBay offer ID
        
        Returns:
            True if successful
        """
        
        try:
            # POST /offer/{offer_id}/publish
            self.ebay._request(
                'POST',
                self.ebay.inventory_path + '/offer/' + offer_id + '/publish'
            )
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  Publish failed for {offer_id}: {e}")
            return False
    
    def sync_product_stock(self, product: Dict) -> Dict:
        """
        Sync stock for one product
        
        Args:
            product: Product dict with variations
        
        Returns:
            Sync result dict
        """
        
        print(f"\n📦 Product {product['id']}: {product['title'][:50]}")
        print(f"   AliExpress: {product['aliexpress_id']}")
        print(f"   eBay: {product['ebay_item_id']}")
        print(f"   Variations: {len(product['variations'])}")
        
        # Fetch current stock from AliExpress
        stock_map = self.fetch_aliexpress_stock(product['aliexpress_id'])
        
        if not stock_map:
            print(f"   ⚠️  No stock data from AliExpress - skipping")
            return {'success': False, 'reason': 'no_stock_data'}
        
        print(f"   ✅ Fetched stock for {len(stock_map)} variants")
        
        # Sync each variation
        updated = 0
        withdrawn = 0
        reactivated = 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for var in product['variations']:
            # Match to AliExpress stock
            new_stock = self.match_variation_to_stock(var, stock_map)
            
            old_stock = var['aliexpress_stock'] or var['stock']
            
            # Check if stock changed
            if new_stock != old_stock:
                print(f"   🔄 {var['sku']}: {old_stock} → {new_stock}")
                
                # Update eBay quantity
                if self.update_ebay_stock(var['sku'], new_stock):
                    updated += 1
                    
                    # Handle zero stock (withdraw)
                    if new_stock == 0 and var['ebay_active']:
                        if var['ebay_offer_id']:
                            if self.withdraw_listing(var['ebay_offer_id']):
                                withdrawn += 1
                                # Update ebay_active flag
                                cursor.execute('''
                                    UPDATE product_variations
                                    SET ebay_active = 0
                                    WHERE id = ?
                                ''', (var['id'],))
                    
                    # Handle back in stock (reactivate)
                    elif new_stock > 0 and not var['ebay_active']:
                        if var['ebay_offer_id']:
                            if self.publish_offer(var['ebay_offer_id']):
                                reactivated += 1
                                # Update ebay_active flag
                                cursor.execute('''
                                    UPDATE product_variations
                                    SET ebay_active = 1
                                    WHERE id = ?
                                ''', (var['id'],))
                    
                    # Update database
                    cursor.execute('''
                        UPDATE product_variations
                        SET 
                            aliexpress_stock = ?,
                            stock = ?,
                            last_stock_check = ?,
                            updated_at = ?
                        WHERE id = ?
                    ''', (new_stock, new_stock, datetime.now(), datetime.now(), var['id']))
            
            else:
                # No change - just update check time
                cursor.execute('''
                    UPDATE product_variations
                    SET last_stock_check = ?
                    WHERE id = ?
                ''', (datetime.now(), var['id']))
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ Updated: {updated}, Withdrawn: {withdrawn}, Reactivated: {reactivated}")
        
        return {
            'success': True,
            'updated': updated,
            'withdrawn': withdrawn,
            'reactivated': reactivated
        }
    
    def run_sync(self, max_age_minutes: int = 30):
        """
        Run stock sync for all products
        
        Args:
            max_age_minutes: Sync products not checked in last N minutes
        """
        
        print("="*70)
        print(f"📊 STOCK SYNCHRONIZATION JOB")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Get products to sync
        products = self.get_products_to_sync(max_age_minutes)
        
        print(f"\n📦 Found {len(products)} products to sync")
        
        if not products:
            print("   ✅ All products are up to date!")
            return
        
        # Sync each product
        total_updated = 0
        total_withdrawn = 0
        total_reactivated = 0
        failed = 0
        
        for product in products:
            try:
                result = self.sync_product_stock(product)
                
                if result['success']:
                    total_updated += result['updated']
                    total_withdrawn += result['withdrawn']
                    total_reactivated += result['reactivated']
                else:
                    failed += 1
                
                # Rate limit: Wait 1 second between products
                time.sleep(1)
                
            except Exception as e:
                print(f"   ❌ Error syncing product {product['id']}: {e}")
                failed += 1
        
        print("\n" + "="*70)
        print("📊 SYNC COMPLETE")
        print("="*70)
        print(f"   Products synced: {len(products)}")
        print(f"   Variations updated: {total_updated}")
        print(f"   Listings withdrawn: {total_withdrawn}")
        print(f"   Listings reactivated: {total_reactivated}")
        print(f"   Failed: {failed}")
        print("="*70)


# CLI usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Synchronization Job')
    parser.add_argument('--max-age', type=int, default=30,
                        help='Sync products not checked in last N minutes (default: 30)')
    
    args = parser.parse_args()
    
    job = StockSyncJob()
    job.run_sync(max_age_minutes=args.max_age)
