"""
AUTOMATIC PERFORMANCE OPTIMIZATION SYSTEM
Removes dead listings, optimizes prices, tests variations
Maximizes sales and profitability automatically
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

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


class AutoPerformanceOptimization:
    """Automatic listing performance optimization"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ebay = eBayAPIClient()
        
    def run_optimization(self):
        """Run complete performance optimization"""
        print()
        print("=" * 70)
        print(f"⚡ PERFORMANCE OPTIMIZATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        results = {
            'analyzed': 0,
            'low_performers_removed': 0,
            'prices_optimized': 0,
            'titles_improved': 0
        }
        
        # Remove dead listings (0 views in 30 days)
        print("🗑️  Checking dead listings...")
        removed = self._remove_dead_listings()
        results['low_performers_removed'] = removed
        
        # Optimize prices for low-conversion listings
        print("💰 Optimizing prices...")
        optimized = self._optimize_prices()
        results['prices_optimized'] = optimized
        
        # Improve titles for low-view listings
        print("📝 Improving titles...")
        improved = self._improve_titles()
        results['titles_improved'] = improved
        
        print()
        print("=" * 70)
        print("📊 OPTIMIZATION SUMMARY")
        print("=" * 70)
        print(f"🗑️  Dead Listings Removed:   {results['low_performers_removed']}")
        print(f"💰 Prices Optimized:        {results['prices_optimized']}")
        print(f"📝 Titles Improved:         {results['titles_improved']}")
        print("=" * 70)
        
        return results
    
    def _remove_dead_listings(self):
        """Remove listings with 0 sales in 30+ days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get old listings with no sales
        cursor.execute('''
            SELECT p.ebay_item_id, p.sku_id, p.title
            FROM products p
            LEFT JOIN sales s ON p.ebay_item_id = s.ebay_item_id
            WHERE lower(p.status) = 'active'
              AND p.created_at <= datetime('now', '-30 days')
              AND s.id IS NULL
        ''')
        
        dead_listings = cursor.fetchall()
        conn.close()
        
        removed_count = 0
        
        for listing in dead_listings:
            ebay_item_id, sku, title = listing
            
            print(f"   🗑️  Removing: {title[:50]}...")
            
            # End eBay listing
            if self._end_ebay_listing(ebay_item_id):
                self._update_product_status(sku, 'REMOVED_LOW_PERFORMANCE')
                removed_count += 1
                print(f"      ✅ Removed")
        
        return removed_count
    
    def _optimize_prices(self):
        """Optimize prices for better conversion"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get listings with views but no sales (14-30 days old)
        # In production, this would fetch eBay analytics
        # For now, we'll use a simple heuristic
        
        cursor.execute('''
            SELECT p.ebay_item_id, p.sku_id, p.title, p.ebay_price, p.aliexpress_price
            FROM products p
            LEFT JOIN sales s ON p.ebay_item_id = s.ebay_item_id
            WHERE lower(p.status) = 'active'
              AND p.created_at >= datetime('now', '-30 days')
              AND p.created_at <= datetime('now', '-14 days')
              AND s.id IS NULL
              AND p.ebay_price > p.aliexpress_price * 3
              AND p.ebay_item_id IS NOT NULL AND p.sku_id IS NOT NULL
        ''')
        
        overpriced = cursor.fetchall()
        conn.close()
        
        optimized_count = 0
        
        for listing in overpriced:
            ebay_item_id, sku, title, ebay_price, ali_price = listing
            
            # Reduce price by 15%
            new_price = ebay_price * 0.85
            
            # Never go below the configured minimum profit after fees
            if new_price >= _floor_price(ali_price):
                print(f"   💰 Optimizing: {title[:50]}...")
                print(f"      €{ebay_price:.2f} → €{new_price:.2f}")
                
                if self._update_ebay_price(sku, new_price):
                    self._update_product_ebay_price(sku, new_price)
                    optimized_count += 1
                    print(f"      ✅ Price updated")
        
        return optimized_count
    
    def _improve_titles(self):
        """Improve titles for better visibility"""
        # In production, this would use AI to generate better titles
        # based on successful competitors and keywords
        
        # For now, we'll just log potential improvements
        print(f"   📝 Title optimization available via AI analysis")
        print(f"      (Requires competitor analysis and keyword research)")
        
        return 0
    
    def _end_ebay_listing(self, ebay_item_id):
        """End eBay listing. True only if eBay confirmed; gated by live-write switches."""
        if not _live_writes_allowed():
            print("         🔒 Live writes disabled - listing NOT ended")
            return False
        try:
            return bool(self.ebay.end_listing(ebay_item_id, reason='NOT_AVAILABLE'))
        except Exception as e:
            print(f"         ⚠️  End listing error: {type(e).__name__}")
            return False

    def _update_ebay_price(self, sku, new_price):
        """Update eBay offer price by SKU. True only if eBay confirmed."""
        if not _live_writes_allowed():
            print("         🔒 Live writes disabled - price NOT changed")
            return False
        try:
            return bool(self.ebay.update_price(sku, round(float(new_price), 2)))
        except Exception as e:
            print(f"         ⚠️  Price update error: {type(e).__name__}")
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
    
    def _update_product_ebay_price(self, sku, new_price):
        """Update product eBay price in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products
            SET ebay_price = ?,
                updated_at = ?
            WHERE sku_id = ?
        ''', (new_price, datetime.now().isoformat(), sku))
        
        conn.commit()
        conn.close()


def main():
    """Main entry point"""
    optimizer = AutoPerformanceOptimization()
    optimizer.run_optimization()


if __name__ == "__main__":
    main()
