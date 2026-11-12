"""
AUTOMATIC TRACKING MANAGEMENT SYSTEM
Retrieves tracking numbers from AliExpress and uploads to eBay
Marks orders as shipped automatically
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

from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

class AutoTrackingManagement:
    """Automatic tracking number management"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ali = AliExpressAPIClient()
        self.ebay = eBayAPIClient()
        
    def process_pending_tracking(self):
        """Process all orders waiting for tracking numbers"""
        print()
        print("=" * 70)
        print(f"🚚 TRACKING MANAGEMENT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        # Get orders with AliExpress order ID but no tracking yet
        pending = self._get_pending_tracking_orders()
        
        if not pending:
            print("📭 No orders waiting for tracking")
            return []
        
        print(f"🚚 Found {len(pending)} order(s) waiting for tracking")
        print()
        
        results = []
        
        for order in pending:
            result = self._process_tracking(order)
            results.append(result)
            time.sleep(2)
        
        return results
    
    def _get_pending_tracking_orders(self):
        """Get orders that need tracking numbers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Orders with AliExpress ID but no tracking
        cursor.execute('''
            SELECT ebay_order_id, aliexpress_order_id, aliexpress_product_id
            FROM order_fulfillment
            WHERE aliexpress_order_id IS NOT NULL
              AND aliexpress_order_id NOT LIKE 'PENDING%'
              AND tracking_number IS NULL
              AND status != 'FAILED'
              AND created_at >= datetime('now', '-30 days')
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        orders = []
        for row in rows:
            orders.append({
                'ebay_order_id': row[0],
                'aliexpress_order_id': row[1],
                'aliexpress_product_id': row[2]
            })
        
        return orders
    
    def _process_tracking(self, order):
        """Process tracking for single order"""
        ebay_order_id = order['ebay_order_id']
        ali_order_id = order['aliexpress_order_id']
        
        print(f"🚚 Processing: {ebay_order_id}")
        print(f"   AliExpress Order: {ali_order_id}")
        
        try:
            # Step 1: Get tracking from AliExpress
            print("   🔍 Step 1: Getting tracking from AliExpress...")
            tracking_info = self._get_aliexpress_tracking(ali_order_id)
            
            if not tracking_info:
                print("   ⏳ Tracking not available yet (order may not be shipped)")
                return {'success': False, 'reason': 'tracking_not_ready'}
            
            tracking_number = tracking_info['tracking_number']
            carrier = tracking_info['carrier']
            
            print(f"   ✅ Tracking: {tracking_number}")
            print(f"   ✅ Carrier: {carrier}")
            
            # Step 2: Upload tracking to eBay
            print("   🔍 Step 2: Uploading tracking to eBay...")
            upload_success = self._upload_tracking_to_ebay(
                ebay_order_id,
                tracking_number,
                carrier
            )
            
            if not upload_success:
                raise Exception("Failed to upload tracking to eBay")
            
            print("   ✅ Tracking uploaded to eBay")
            
            # Step 3: Mark as shipped
            print("   🔍 Step 3: Marking order as shipped...")
            self._mark_order_shipped(ebay_order_id, tracking_number, carrier)
            
            print("   ✅ Order marked as shipped")
            print(f"✅ Tracking management completed!")
            print()
            
            return {
                'success': True,
                'ebay_order_id': ebay_order_id,
                'tracking_number': tracking_number,
                'carrier': carrier
            }
            
        except Exception as e:
            print(f"❌ Tracking management failed: {e}")
            print()
            
            return {
                'success': False,
                'ebay_order_id': ebay_order_id,
                'error': str(e)
            }
    
    def _get_aliexpress_tracking(self, ali_order_id):
        """Get tracking number from AliExpress"""
        try:
            # AliExpress Logistics API
            response = self.ali.get_order_tracking(ali_order_id)
            
            if not response or 'logistics_info' not in response:
                return None
            
            logistics = response['logistics_info']
            
            if not logistics.get('tracking_number'):
                return None
            
            return {
                'tracking_number': logistics['tracking_number'],
                'carrier': logistics.get('service_name', 'Standard Shipping'),
                'status': logistics.get('status', 'SHIPPED')
            }
            
        except Exception as e:
            print(f"      ⚠️  AliExpress tracking error: {e}")
            return None
    
    def _upload_tracking_to_ebay(self, ebay_order_id, tracking_number, carrier):
        """Upload tracking number to eBay"""
        try:
            # Map AliExpress carrier to eBay carrier
            ebay_carrier = self._map_carrier_name(carrier)
            
            # eBay Fulfillment API - Add Tracking
            result = self.ebay.add_tracking_number(
                order_id=ebay_order_id,
                tracking_number=tracking_number,
                carrier_code=ebay_carrier
            )
            
            return result is not None
            
        except Exception as e:
            print(f"      ⚠️  eBay tracking upload error: {e}")
            return False
    
    def _map_carrier_name(self, aliexpress_carrier):
        """Map AliExpress carrier to eBay carrier code"""
        carrier_map = {
            'ePacket': 'OTHER',
            'China Post': 'OTHER',
            'AliExpress Standard Shipping': 'OTHER',
            'DHL': 'DHL',
            'FedEx': 'FEDEX',
            'UPS': 'UPS',
            'USPS': 'USPS'
        }
        
        for key, value in carrier_map.items():
            if key.lower() in aliexpress_carrier.lower():
                return value
        
        return 'OTHER'
    
    def _mark_order_shipped(self, ebay_order_id, tracking_number, carrier):
        """Mark order as shipped in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE order_fulfillment
            SET tracking_number = ?,
                shipping_carrier = ?,
                status = 'SHIPPED',
                updated_at = ?
            WHERE ebay_order_id = ?
        ''', (tracking_number, carrier, datetime.now().isoformat(), ebay_order_id))
        
        conn.commit()
        conn.close()


def main():
    """Main entry point"""
    tracking = AutoTrackingManagement()
    results = tracking.process_pending_tracking()
    
    print()
    print("=" * 70)
    print("📊 TRACKING SUMMARY")
    print("=" * 70)
    
    success = sum(1 for r in results if r.get('success'))
    failed = len(results) - success
    
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print("=" * 70)


if __name__ == "__main__":
    main()
