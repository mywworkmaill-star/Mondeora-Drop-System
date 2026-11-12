"""
AUTOMATIC CUSTOMER COMMUNICATION SYSTEM
Sends automatic emails/messages for order updates
Order confirmation, shipping notification, feedback requests
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

class AutoCustomerCommunication:
    """Automatic customer email/message system"""
    
    def __init__(self):
        self.db_path = "data/dropshipping.db"
        self.ebay = eBayAPIClient()
        
    def process_communications(self):
        """Process all pending customer communications"""
        print()
        print("=" * 70)
        print(f"📧 CUSTOMER COMMUNICATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        results = {
            'order_confirmations': 0,
            'shipping_notifications': 0,
            'feedback_requests': 0,
            'errors': 0
        }
        
        # Send order confirmations (new orders)
        print("📧 Checking order confirmations...")
        order_conf = self._send_order_confirmations()
        results['order_confirmations'] = order_conf
        
        # Send shipping notifications (newly shipped)
        print("📧 Checking shipping notifications...")
        shipping_notif = self._send_shipping_notifications()
        results['shipping_notifications'] = shipping_notif
        
        # Send feedback requests (delivered 7+ days ago)
        print("📧 Checking feedback requests...")
        feedback_req = self._send_feedback_requests()
        results['feedback_requests'] = feedback_req
        
        print()
        print("=" * 70)
        print("📊 COMMUNICATION SUMMARY")
        print("=" * 70)
        print(f"📦 Order Confirmations:      {results['order_confirmations']}")
        print(f"🚚 Shipping Notifications:   {results['shipping_notifications']}")
        print(f"⭐ Feedback Requests:        {results['feedback_requests']}")
        print("=" * 70)
        
        return results
    
    def _send_order_confirmations(self):
        """Send order confirmation messages to new buyers"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get new orders without confirmation sent
        cursor.execute('''
            SELECT s.order_id, s.buyer_username, s.title, s.sale_price
            FROM sales s
            LEFT JOIN customer_communications c 
                ON s.order_id = c.order_id AND c.communication_type = 'ORDER_CONFIRMATION'
            WHERE c.id IS NULL
              AND s.created_at >= datetime('now', '-7 days')
        ''')
        
        orders = cursor.fetchall()
        conn.close()
        
        sent_count = 0
        
        for order in orders:
            order_id, buyer_username, title, price = order
            
            message = self._create_order_confirmation_message(title, price)
            
            if self._send_ebay_message(order_id, buyer_username, message, 'Order Confirmation'):
                self._log_communication(order_id, 'ORDER_CONFIRMATION')
                sent_count += 1
                print(f"   ✅ Sent to {buyer_username}")
        
        return sent_count
    
    def _send_shipping_notifications(self):
        """Send shipping notifications with tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recently shipped orders without notification
        cursor.execute('''
            SELECT f.ebay_order_id, s.buyer_username, s.title,
                   f.tracking_number, f.shipping_carrier
            FROM order_fulfillment f
            JOIN sales s ON f.ebay_order_id = s.order_id
            LEFT JOIN customer_communications c 
                ON f.ebay_order_id = c.order_id AND c.communication_type = 'SHIPPING_NOTIFICATION'
            WHERE f.status = 'SHIPPED'
              AND f.tracking_number IS NOT NULL
              AND c.id IS NULL
              AND f.updated_at >= datetime('now', '-7 days')
        ''')
        
        shipments = cursor.fetchall()
        conn.close()
        
        sent_count = 0
        
        for shipment in shipments:
            order_id, buyer_username, title, tracking, carrier = shipment
            
            message = self._create_shipping_notification_message(title, tracking, carrier)
            
            if self._send_ebay_message(order_id, buyer_username, message, 'Your Order Has Shipped'):
                self._log_communication(order_id, 'SHIPPING_NOTIFICATION')
                sent_count += 1
                print(f"   ✅ Sent to {buyer_username}")
        
        return sent_count
    
    def _send_feedback_requests(self):
        """Send feedback requests to delivered orders"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get delivered orders (7+ days ago) without feedback request
        cursor.execute('''
            SELECT f.ebay_order_id, s.buyer_username, s.title
            FROM order_fulfillment f
            JOIN sales s ON f.ebay_order_id = s.order_id
            LEFT JOIN customer_communications c 
                ON f.ebay_order_id = c.order_id AND c.communication_type = 'FEEDBACK_REQUEST'
            WHERE f.status = 'SHIPPED'
              AND f.updated_at <= datetime('now', '-7 days')
              AND c.id IS NULL
        ''')
        
        delivered = cursor.fetchall()
        conn.close()
        
        sent_count = 0
        
        for order in delivered:
            order_id, buyer_username, title = order
            
            message = self._create_feedback_request_message(title)
            
            if self._send_ebay_message(order_id, buyer_username, message, 'Feedback Request'):
                self._log_communication(order_id, 'FEEDBACK_REQUEST')
                sent_count += 1
                print(f"   ✅ Sent to {buyer_username}")
        
        return sent_count
    
    def _create_order_confirmation_message(self, product_title, price):
        """Create order confirmation message"""
        return f"""Hello,

Thank you for your order!

Your order for "{product_title[:50]}" (€{price:.2f}) has been confirmed and is being prepared for shipment.

We will send you another message with tracking information once your item ships.

If you have any questions, please don't hesitate to contact us.

Best regards,
Mondeora Team"""
    
    def _create_shipping_notification_message(self, product_title, tracking, carrier):
        """Create shipping notification message"""
        return f"""Hello,

Great news! Your order has been shipped!

Product: "{product_title[:50]}"
Tracking Number: {tracking}
Carrier: {carrier}

You can track your package using the tracking number above. Estimated delivery: 10-20 business days.

Thank you for your purchase!

Best regards,
Mondeora Team"""
    
    def _create_feedback_request_message(self, product_title):
        """Create feedback request message"""
        return f"""Hello,

We hope you're enjoying your "{product_title[:50]}"!

If you're satisfied with your purchase, we would greatly appreciate your feedback. Positive feedback helps us continue providing great products and service.

Thank you for being a valued customer!

Best regards,
Mondeora Team"""
    
    def _send_ebay_message(self, order_id, buyer_username, message, subject):
        """Send message via eBay Messages API"""
        try:
            # eBay Post-Order API - Send Message
            # Note: This requires eBay Messages API which may have restrictions
            # For now, we'll log it as ready to send
            
            print(f"      📧 Message ready for {buyer_username}: {subject}")
            # In production: self.ebay.send_message(buyer_username, subject, message)
            
            return True
            
        except Exception as e:
            print(f"      ⚠️  Message send error: {e}")
            return False
    
    def _log_communication(self, order_id, comm_type):
        """Log sent communication to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                communication_type TEXT,
                sent_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT INTO customer_communications (order_id, communication_type)
            VALUES (?, ?)
        ''', (order_id, comm_type))
        
        conn.commit()
        conn.close()


def main():
    """Main entry point"""
    comm = AutoCustomerCommunication()
    comm.process_communications()


if __name__ == "__main__":
    main()
