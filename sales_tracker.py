"""
SALES TRACKER - Real-time eBay Sales Monitoring
Monitors eBay orders and sends instant notifications for new sales
"""

import os
import sys
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.ebay_client import eBayRESTClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

class SalesTracker:
    """Real-time sales monitoring and notification system"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ebay = eBayRESTClient()
        self.notification_log = "data/sales_notifications.json"
        self._init_sales_table()
        
    def _init_sales_table(self):
        """Initialize sales tracking table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                ebay_item_id TEXT,
                sku TEXT,
                title TEXT,
                quantity INTEGER,
                sale_price REAL,
                buyer_username TEXT,
                buyer_email TEXT,
                sale_date DATETIME,
                payment_status TEXT,
                fulfillment_status TEXT,
                aliexpress_order_id TEXT,
                profit REAL,
                notification_sent BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Sales table initialized!")
        
    def check_new_sales(self, days_back=1):
        """
        Check for new eBay sales
        
        Args:
            days_back: How many days back to check (default: 1)
            
        Returns:
            List of new sales
        """
        print()
        print("=" * 70)
        print(f"🔍 CHECKING NEW SALES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        try:
            # Get orders from eBay
            start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            print(f"📅 Checking orders since: {start_date}")
            print()
            
            # Call eBay Orders API
            orders = self._get_ebay_orders(start_date)
            
            if not orders:
                print("📭 No orders found")
                return []
            
            print(f"📦 Found {len(orders)} total order(s)")
            print()
            
            # Filter for new sales
            new_sales = []
            
            for order in orders:
                order_id = order.get('orderId')
                
                # Check if already in database
                if self._is_order_tracked(order_id):
                    print(f"⏭️  Order {order_id}: Already tracked")
                    continue
                
                # Process new sale
                sale_data = self._process_order(order)
                
                if sale_data:
                    # Save to database
                    self._save_sale(sale_data)
                    new_sales.append(sale_data)
                    
                    print(f"✅ NEW SALE! Order: {order_id}")
                    print(f"   Product: {sale_data['title'][:50]}...")
                    print(f"   Price: €{sale_data['sale_price']:.2f}")
                    print(f"   Profit: €{sale_data['profit']:.2f}")
                    print()
            
            if new_sales:
                print(f"🎉 {len(new_sales)} NEW SALE(S) DETECTED!")
            else:
                print("📭 No new sales")
            
            print()
            
            return new_sales
            
        except Exception as e:
            print(f"❌ Error checking sales: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_ebay_orders(self, start_date):
        """Get orders from eBay API"""
        try:
            # Calculate days back from start_date
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            days_back = (datetime.now() - start_dt).days + 1
            
            # Use eBayAPIClient's get_orders method
            orders = self.ebay.get_orders(status='NOT_STARTED', days_back=days_back)
            
            return orders if orders else []
            
        except Exception as e:
            print(f"⚠️  eBay API error (may be no orders): {e}")
            return []
    
    def _is_order_tracked(self, order_id):
        """Check if order is already in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM sales WHERE order_id = ?', (order_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists
    
    def _process_order(self, order):
        """Process order data and calculate profit"""
        try:
            order_id = order.get('orderId')
            
            # Get line items
            line_items = order.get('lineItems', [])
            
            if not line_items:
                return None
            
            # Process first item (handle multi-item orders later)
            item = line_items[0]
            
            ebay_item_id = item.get('legacyItemId')
            sku = item.get('sku')
            title = item.get('title')
            quantity = item.get('quantity', 1)
            sale_price = float(item.get('lineItemCost', {}).get('value', 0))
            
            # Get buyer info
            buyer = order.get('buyer', {})
            buyer_username = buyer.get('username', 'Unknown')
            buyer_email = buyer.get('buyerRegistrationAddress', {}).get('email', '')
            
            # Get dates and status
            sale_date = order.get('creationDate')
            payment_status = order.get('orderPaymentStatus', 'UNKNOWN')
            fulfillment_status = order.get('orderFulfillmentStatus', 'NOT_STARTED')
            
            # Calculate profit (get cost from products table)
            profit = self._calculate_profit(sku, ebay_item_id, sale_price, quantity)
            
            return {
                'order_id': order_id,
                'ebay_item_id': ebay_item_id,
                'sku': sku,
                'title': title,
                'quantity': quantity,
                'sale_price': sale_price,
                'buyer_username': buyer_username,
                'buyer_email': buyer_email,
                'sale_date': sale_date,
                'payment_status': payment_status,
                'fulfillment_status': fulfillment_status,
                'profit': profit
            }
            
        except Exception as e:
            print(f"⚠️  Error processing order: {e}")
            return None
    
    def _calculate_profit(self, sku, ebay_item_id, sale_price, quantity):
        """Calculate profit from sale"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find product by SKU or eBay ID
            if sku:
                cursor.execute('''
                    SELECT aliexpress_price, shipping_cost 
                    FROM products 
                    WHERE sku = ?
                ''', (sku,))
            else:
                cursor.execute('''
                    SELECT aliexpress_price, shipping_cost 
                    FROM products 
                    WHERE ebay_item_id = ?
                ''', (ebay_item_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                ali_price, shipping = result
                cost = (ali_price or 0) + (shipping or 0)
                
                # eBay fees (10% + €0.35)
                ebay_fee = (sale_price * 0.10) + 0.35
                
                # Net profit
                profit = (sale_price - cost - ebay_fee) * quantity
                
                return round(profit, 2)
            
            # If product not found, estimate 70% margin
            return round(sale_price * 0.70, 2)
            
        except Exception as e:
            print(f"⚠️  Profit calculation error: {e}")
            return 0
    
    def _save_sale(self, sale_data):
        """Save sale to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sales (
                order_id, ebay_item_id, sku, title, quantity,
                sale_price, buyer_username, buyer_email, sale_date,
                payment_status, fulfillment_status, profit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sale_data['order_id'],
            sale_data['ebay_item_id'],
            sale_data['sku'],
            sale_data['title'],
            sale_data['quantity'],
            sale_data['sale_price'],
            sale_data['buyer_username'],
            sale_data['buyer_email'],
            sale_data['sale_date'],
            sale_data['payment_status'],
            sale_data['fulfillment_status'],
            sale_data['profit']
        ))
        
        conn.commit()
        conn.close()
    
    def send_notification(self, sale):
        """Send notification for new sale"""
        print()
        print("=" * 70)
        print("🎉 NEW SALE NOTIFICATION!")
        print("=" * 70)
        print()
        print(f"📦 Order ID:      {sale['order_id']}")
        print(f"🏷️  Product:       {sale['title'][:60]}...")
        print(f"💰 Sale Price:    €{sale['sale_price']:.2f}")
        print(f"✅ Net Profit:    €{sale['profit']:.2f}")
        print(f"👤 Buyer:         {sale['buyer_username']}")
        print(f"📅 Date:          {sale['sale_date']}")
        print()
        print("=" * 70)
        print()
        
        # Save notification log
        self._log_notification(sale)
        
        # Mark as notified
        self._mark_notified(sale['order_id'])
        
        # Play sound (Windows beep)
        try:
            import winsound
            # Success sound (3 beeps)
            for _ in range(3):
                winsound.Beep(1000, 200)
                time.sleep(0.1)
        except:
            pass
    
    def _log_notification(self, sale):
        """Log notification to file"""
        try:
            notifications = []
            
            if os.path.exists(self.notification_log):
                with open(self.notification_log, 'r', encoding='utf-8') as f:
                    notifications = json.load(f)
            
            notifications.append({
                'order_id': sale['order_id'],
                'title': sale['title'],
                'profit': sale['profit'],
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep last 100 notifications
            notifications = notifications[-100:]
            
            with open(self.notification_log, 'w', encoding='utf-8') as f:
                json.dump(notifications, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️  Error logging notification: {e}")
    
    def _mark_notified(self, order_id):
        """Mark sale as notified in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE sales 
            SET notification_sent = 1 
            WHERE order_id = ?
        ''', (order_id,))
        
        conn.commit()
        conn.close()
    
    def get_sales_summary(self, days=1):
        """Get sales summary for last N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_sales,
                SUM(sale_price) as total_revenue,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit
            FROM sales
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'total_sales': result[0] or 0,
            'total_revenue': result[1] or 0,
            'total_profit': result[2] or 0,
            'avg_profit': result[3] or 0
        }
    
    def run_check_cycle(self):
        """Run a single sales check cycle"""
        print()
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "💰 SALES TRACKER" + " " * 32 + "║")
        print("╚" + "=" * 68 + "╝")
        
        # Check for new sales
        new_sales = self.check_new_sales(days_back=1)
        
        # Send notifications
        for sale in new_sales:
            self.send_notification(sale)
        
        # Print summary
        summary = self.get_sales_summary(days=1)
        
        print()
        print("=" * 70)
        print("📊 24-HOUR SUMMARY")
        print("=" * 70)
        print(f"Total Sales:    {summary['total_sales']}")
        print(f"Total Revenue:  €{summary['total_revenue']:.2f}")
        print(f"Total Profit:   €{summary['total_profit']:.2f}")
        print(f"Avg Profit:     €{summary['avg_profit']:.2f}")
        print("=" * 70)
        print()
        
        return new_sales


def main():
    """Main entry point for testing"""
    tracker = SalesTracker()
    tracker.run_check_cycle()


if __name__ == "__main__":
    main()
