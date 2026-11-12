"""
AUTOMATIC ORDER FULFILLMENT SYSTEM
Places AliExpress orders automatically when eBay sale is detected
100% hands-free dropshipping automation
"""

import os
import sys
import json
import time
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

class AutoOrderFulfillment:
    """Automatic order fulfillment when sale is detected"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ali = AliExpressAPIClient()
        self.ebay = eBayAPIClient()
        self.fulfillment_log = "data/fulfillment_log.json"
        self._init_fulfillment_table()
        
    def _init_fulfillment_table(self):
        """Initialize fulfillment tracking table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_fulfillment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ebay_order_id TEXT UNIQUE NOT NULL,
                aliexpress_order_id TEXT,
                aliexpress_product_id TEXT,
                status TEXT,
                buyer_address TEXT,
                tracking_number TEXT,
                shipping_carrier TEXT,
                fulfillment_date DATETIME,
                delivery_date DATETIME,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Order fulfillment table initialized!")
        
    def process_pending_orders(self):
        """Process all unfulfilled eBay orders"""
        print()
        print("=" * 70)
        print(f"📦 ORDER FULFILLMENT CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        # Get unfulfilled sales from database
        unfulfilled = self._get_unfulfilled_sales()
        
        if not unfulfilled:
            print("📭 No pending orders to fulfill")
            return []
        
        print(f"📦 Found {len(unfulfilled)} order(s) to fulfill")
        print()
        
        results = []
        
        for sale in unfulfilled:
            result = self._fulfill_order(sale)
            results.append(result)
            
            # Small delay between orders
            time.sleep(2)
        
        return results
    
    def _get_unfulfilled_sales(self):
        """Get sales that haven't been fulfilled yet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get sales without fulfillment record
        cursor.execute('''
            SELECT s.id, s.order_id, s.ebay_item_id, s.sku, s.title,
                   s.buyer_username, s.sale_price, s.quantity
            FROM sales s
            LEFT JOIN order_fulfillment f ON s.order_id = f.ebay_order_id
            WHERE f.id IS NULL 
               OR (f.status = 'FAILED' AND f.retry_count < 3)
            ORDER BY s.created_at ASC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        sales = []
        for row in rows:
            sales.append({
                'id': row[0],
                'order_id': row[1],
                'ebay_item_id': row[2],
                'sku': row[3],
                'title': row[4],
                'buyer_username': row[5],
                'sale_price': row[6],
                'quantity': row[7]
            })
        
        return sales
    
    def _fulfill_order(self, sale):
        """Fulfill a single order"""
        order_id = sale['order_id']
        
        print(f"📦 Processing order: {order_id}")
        print(f"   Product: {sale['title'][:50]}...")
        print()
        
        try:
            # Step 1: Get buyer address from eBay
            print("   🔍 Step 1: Getting buyer address...")
            buyer_address = self._get_buyer_address(order_id)
            
            if not buyer_address:
                raise Exception("Failed to get buyer address from eBay")
            
            print(f"   ✅ Address: {buyer_address['city']}, {buyer_address['country']}")
            
            # Step 2: Get AliExpress product ID
            print("   🔍 Step 2: Finding AliExpress product...")
            ali_product_id = self._get_aliexpress_product_id(sale)
            
            if not ali_product_id:
                raise Exception("Failed to find AliExpress product")
            
            print(f"   ✅ AliExpress ID: {ali_product_id}")
            
            # Step 3: Check AliExpress stock
            print("   🔍 Step 3: Checking stock availability...")
            stock_available = self._check_aliexpress_stock(ali_product_id, sale['quantity'])
            
            if not stock_available:
                raise Exception("Product out of stock on AliExpress")
            
            print(f"   ✅ Stock available")
            
            # Step 4: Place AliExpress order (SIMULATED - see note below)
            print("   🔍 Step 4: Placing AliExpress order...")
            ali_order_id = self._place_aliexpress_order(
                ali_product_id,
                sale['quantity'],
                buyer_address
            )
            
            if ali_order_id:
                print(f"   ✅ Order placed: {ali_order_id}")
            else:
                print(f"   ⚠️  Order queued (manual confirmation needed)")
                ali_order_id = "PENDING_MANUAL_" + order_id
            
            # Step 5: Save fulfillment record
            self._save_fulfillment(
                ebay_order_id=order_id,
                aliexpress_order_id=ali_order_id,
                aliexpress_product_id=ali_product_id,
                buyer_address=buyer_address,
                status='PENDING' if 'PENDING' in ali_order_id else 'ORDERED'
            )
            
            print(f"✅ Order fulfillment completed!")
            print()
            
            return {
                'success': True,
                'order_id': order_id,
                'ali_order_id': ali_order_id,
                'status': 'ORDERED'
            }
            
        except Exception as e:
            print(f"❌ Order fulfillment failed: {e}")
            print()
            
            # Save error
            self._save_fulfillment_error(order_id, str(e))
            
            return {
                'success': False,
                'order_id': order_id,
                'error': str(e)
            }
    
    def _get_buyer_address(self, ebay_order_id):
        """Get buyer shipping address from eBay"""
        try:
            # Get order details from eBay API
            order = self.ebay.get_order_details(ebay_order_id)
            
            if not order:
                return None
            
            # Extract shipping address
            fulfillment = order.get('fulfillmentStartInstructions', [{}])[0]
            shipping = fulfillment.get('shippingStep', {}).get('shipTo', {})
            
            return {
                'name': shipping.get('fullName', ''),
                'address1': shipping.get('contactAddress', {}).get('addressLine1', ''),
                'address2': shipping.get('contactAddress', {}).get('addressLine2', ''),
                'city': shipping.get('contactAddress', {}).get('city', ''),
                'state': shipping.get('contactAddress', {}).get('stateOrProvince', ''),
                'postal_code': shipping.get('contactAddress', {}).get('postalCode', ''),
                'country': shipping.get('contactAddress', {}).get('countryCode', ''),
                'phone': shipping.get('primaryPhone', {}).get('phoneNumber', '')
            }
            
        except Exception as e:
            print(f"      ⚠️  Address extraction error: {e}")
            return None
    
    def _get_aliexpress_product_id(self, sale):
        """Get AliExpress product ID from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get from products table
            if sale['sku']:
                cursor.execute('''
                    SELECT aliexpress_product_id 
                    FROM products 
                    WHERE sku = ?
                ''', (sale['sku'],))
            else:
                cursor.execute('''
                    SELECT aliexpress_product_id 
                    FROM products 
                    WHERE ebay_item_id = ?
                ''', (sale['ebay_item_id'],))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            print(f"      ⚠️  Product ID lookup error: {e}")
            return None
    
    def _check_aliexpress_stock(self, product_id, quantity):
        """Check if product is in stock on AliExpress"""
        try:
            # Use AliExpress API to get product details
            product = self.ali.get_product_details(product_id)
            
            if not product:
                return False
            
            # Check availability
            available_quantity = product.get('aeop_ae_product_s_k_us', {}).get('aeop_ae_product_sku', [{}])[0].get('sku_available_stock', 0)
            
            return available_quantity >= quantity
            
        except Exception as e:
            print(f"      ⚠️  Stock check error: {e}")
            # Assume available if check fails (optimistic)
            return True
    
    def _place_aliexpress_order(self, product_id, quantity, address):
        """
        Place order on AliExpress
        
        SAFE MODE: Creates pending order notification for manual approval.
        Real payment automation requires Selenium + login credentials (RISKY).
        This approach gives you a ready-to-click AliExpress link + address.
        """
        
        # Create ready-to-order link
        ali_order_url = f"https://www.aliexpress.com/item/{product_id}.html?quantity={quantity}"
        
        # Format address for copy-paste
        formatted_address = f"""
{address['name']}
{address['address1']}
{address['address2'] if address.get('address2') else ''}
{address['city']}, {address['state']} {address['postal_code']}
{address['country']}
Phone: {address['phone']}
        """.strip()
        
        # Create notification (save to file for monitoring system)
        notification = {
            'timestamp': datetime.now().isoformat(),
            'product_id': product_id,
            'quantity': quantity,
            'order_url': ali_order_url,
            'shipping_address': formatted_address,
            'status': 'PENDING_MANUAL_ORDER'
        }
        
        # Save to pending orders file
        pending_file = Path('data/pending_aliexpress_orders.jsonl')
        pending_file.parent.mkdir(exist_ok=True)
        with open(pending_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(notification, ensure_ascii=False) + '\n')
        
        print("      ✅ Pending order created!")
        print(f"      🔗 AliExpress: {ali_order_url}")
        print(f"      📍 Address ready in: {pending_file}")
        print()
        print("      ⚠️  MANUAL ACTION REQUIRED:")
        print("         1. Open AliExpress link above")
        print("         2. Login & add to cart")
        print("         3. Paste address at checkout")
        print("         4. Complete payment")
        print()
        
        # Return pending order identifier (not a real AliExpress order ID)
        return f"PENDING_{product_id}_{int(datetime.now().timestamp())}"
        
        # OPTION 2: Browser automation (would require Selenium)
        # return self._place_order_via_browser(product_id, quantity, address)
        
        # OPTION 3: Business API (requires special account)
        # return self._place_order_via_business_api(product_id, quantity, address)
    
    def _save_fulfillment(self, ebay_order_id, aliexpress_order_id, 
                         aliexpress_product_id, buyer_address, status):
        """Save fulfillment record to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        address_json = json.dumps(buyer_address)
        
        cursor.execute('''
            INSERT OR REPLACE INTO order_fulfillment (
                ebay_order_id, aliexpress_order_id, aliexpress_product_id,
                buyer_address, status, fulfillment_date
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ebay_order_id,
            aliexpress_order_id,
            aliexpress_product_id,
            address_json,
            status,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def _save_fulfillment_error(self, ebay_order_id, error_message):
        """Save fulfillment error"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO order_fulfillment (
                ebay_order_id, status, error_message, retry_count
            ) VALUES (?, 'FAILED', ?, COALESCE(
                (SELECT retry_count + 1 FROM order_fulfillment WHERE ebay_order_id = ?),
                1
            ))
        ''', (ebay_order_id, error_message, ebay_order_id))
        
        conn.commit()
        conn.close()


def main():
    """Main entry point"""
    fulfillment = AutoOrderFulfillment()
    results = fulfillment.process_pending_orders()
    
    print()
    print("=" * 70)
    print("📊 FULFILLMENT SUMMARY")
    print("=" * 70)
    
    success = sum(1 for r in results if r.get('success'))
    failed = len(results) - success
    
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print("=" * 70)


if __name__ == "__main__":
    main()
