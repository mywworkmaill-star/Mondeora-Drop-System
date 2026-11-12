"""
AUTOMATIC INVENTORY SYNC SYSTEM
Daily stock checks, price monitoring, out-of-stock handling
Keeps eBay listings in sync with AliExpress availability
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

def _floor_price(ali_price):
    """Lowest EUR price that still earns MIN_PROFIT_EUR after eBay fees (config-driven)."""
    from decimal import Decimal, ROUND_CEILING
    from src.runtime import read_config
    cfg = read_config()
    fee = Decimal(str(cfg.get('EBAY_FEE_PERCENT') or '0')) / 100
    fixed = Decimal(str(cfg.get('EBAY_FIXED_FEE_EUR') or '0'))
    profit = Decimal(str(cfg.get('MIN_PROFIT_EUR') or '25'))
    if fee >= 1:
        raise ValueError('EBAY_FEE_PERCENT invalid')
    return float(((Decimal(str(ali_price)) + fixed + profit) / (1 - fee)).quantize(Decimal('.01'), rounding=ROUND_CEILING))


def _live_writes_allowed():
    from src.runtime import writes_allowed
    return writes_allowed()


class AutoInventorySync:
    """Automatic inventory synchronization"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ali = AliExpressAPIClient()
        self.ebay = eBayAPIClient()
        self.sync_log = "data/inventory_sync_log.json"
        
    def run_daily_sync(self):
        """Run complete inventory synchronization"""
        print()
        print("=" * 70)
        print(f"📦 INVENTORY SYNC - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        # Get all active products
        products = self._get_active_products()
        
        if not products:
            print("📭 No active products to sync")
            return
        
        print(f"📦 Syncing {len(products)} product(s)...")
        print()
        
        results = {
            'checked': 0,
            'out_of_stock': 0,
            'price_changed': 0,
            'deactivated': 0,
            'updated': 0,
            'errors': 0
        }
        
        for product in products:
            try:
                result = self._sync_product(product)
                
                results['checked'] += 1
                
                if result.get('out_of_stock'):
                    results['out_of_stock'] += 1
                    results['deactivated'] += 1
                
                if result.get('price_changed'):
                    results['price_changed'] += 1
                    results['updated'] += 1
                
            except Exception as e:
                print(f"❌ Error syncing {product['sku']}: {e}")
                results['errors'] += 1
        
        # Print summary
        print()
        print("=" * 70)
        print("📊 SYNC SUMMARY")
        print("=" * 70)
        print(f"✅ Checked:        {results['checked']}")
        print(f"⚠️  Out of Stock:   {results['out_of_stock']}")
        print(f"💰 Price Changes:  {results['price_changed']}")
        print(f"🔄 Updated:        {results['updated']}")
        print(f"❌ Deactivated:    {results['deactivated']}")
        print(f"❌ Errors:         {results['errors']}")
        print("=" * 70)
        
        return results
    
    def _get_active_products(self):
        """Get all active products from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ebay_item_id, sku_id, aliexpress_product_id, title,
                   aliexpress_price, ebay_price, status
            FROM products
            WHERE lower(status) = 'active' AND aliexpress_price IS NOT NULL
              AND ebay_price IS NOT NULL AND aliexpress_product_id IS NOT NULL
              AND ebay_item_id IS NOT NULL AND sku_id IS NOT NULL
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        products = []
        for row in rows:
            products.append({
                'ebay_item_id': row[0],
                'sku': row[1],
                'aliexpress_product_id': row[2],
                'title': row[3],
                'ali_price': row[4],
                'ebay_price': row[5],
                'status': row[6]
            })
        
        return products
    
    def _sync_product(self, product):
        """Sync single product with AliExpress"""
        sku = product['sku']
        ali_id = product['aliexpress_product_id']
        
        print(f"🔍 Checking: {sku}")
        print(f"   Title: {product['title'][:50]}...")
        
        result = {
            'out_of_stock': False,
            'price_changed': False
        }
        
        # Get current AliExpress data
        ali_data = self._get_aliexpress_product_data(ali_id)
        
        if not ali_data:
            print(f"   ⚠️  Cannot fetch AliExpress data (product may be delisted)")
            return result
        
        # Check stock
        if not ali_data.get('available', True):
            print(f"   ❌ OUT OF STOCK - Deactivating eBay listing")
            if self._deactivate_ebay_listing(product['ebay_item_id']):
                self._update_product_status(sku, 'OUT_OF_STOCK')
                result['out_of_stock'] = True
            return result
        
        # Check price changes
        current_ali_price = ali_data.get('price', product['ali_price'])
        
        if abs(current_ali_price - product['ali_price']) > 0.50:
            print(f"   💰 Price changed: €{product['ali_price']:.2f} → €{current_ali_price:.2f}")
            
            # Keep the old margin but never drop below the configured minimum profit
            margin_percent = (product['ebay_price'] - product['ali_price']) / product['ebay_price']
            new_ebay_price = max(current_ali_price / (1 - margin_percent), _floor_price(current_ali_price))
            new_ebay_price = round(new_ebay_price, 2)

            print(f"   🔄 Updating eBay price: €{product['ebay_price']:.2f} → €{new_ebay_price:.2f}")

            if self._update_ebay_price(sku, new_ebay_price):
                self._update_product_price(sku, current_ali_price, new_ebay_price)
                result['price_changed'] = True
        else:
            print(f"   ✅ In stock, price stable")
        
        print()
        return result
    
    def _get_aliexpress_product_data(self, product_id):
        """Current stock/price from the real client schema (skus[].warehouse_count / sale_price).

        Ambiguous (multi-SKU) or incomplete data returns None so nothing is changed.
        """
        try:
            product = self.ali.get_product_details(product_id)
            if not isinstance(product, dict):
                return None
            skus = product.get('skus') or []
            if len(skus) != 1:
                return None
            sku = skus[0]
            stock, price = sku.get('warehouse_count'), sku.get('sale_price')
            if isinstance(stock, bool) or stock is None or price is None or sku.get('currency') != 'EUR':
                return None
            return {'available': int(stock) > 0, 'stock': int(stock), 'price': float(price)}
        except Exception as e:
            print(f"      ⚠️  AliExpress data fetch error: {type(e).__name__}")
            return None

    def _deactivate_ebay_listing(self, ebay_item_id):
        """Withdraw the eBay offer. True only if eBay confirmed it; gated by live-write switches."""
        if not _live_writes_allowed():
            print("      🔒 Live writes disabled - listing NOT ended")
            return False
        try:
            return bool(self.ebay.end_listing(ebay_item_id, reason='OUT_OF_STOCK'))
        except Exception as e:
            print(f"      ⚠️  eBay deactivation error: {type(e).__name__}")
            return False

    def _update_ebay_price(self, sku, new_price):
        """Update the eBay offer price by SKU. True only if eBay confirmed it."""
        if not _live_writes_allowed():
            print("      🔒 Live writes disabled - price NOT changed")
            return False
        try:
            return bool(self.ebay.update_price(sku, round(float(new_price), 2)))
        except Exception as e:
            print(f"      ⚠️  eBay price update error: {type(e).__name__}")
            return False

    def _update_product_status(self, sku, new_status):
        """Update product status in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products
            SET status = ?,
                updated_at = ?
            WHERE sku_id = ?
        ''', (new_status, datetime.now().isoformat(), sku))
        
        conn.commit()
        conn.close()
    
    def _update_product_price(self, sku, new_ali_price, new_ebay_price):
        """Update product prices in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products
            SET aliexpress_price = ?,
                ebay_price = ?,
                updated_at = ?
            WHERE sku_id = ?
        ''', (new_ali_price, new_ebay_price, datetime.now().isoformat(), sku))
        
        conn.commit()
        conn.close()


def main():
    """Main entry point"""
    sync = AutoInventorySync()
    sync.run_daily_sync()


if __name__ == "__main__":
    main()
