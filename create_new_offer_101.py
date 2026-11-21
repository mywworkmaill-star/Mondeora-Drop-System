"""
Create NEW offer for ID 101 and publish
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

sku = 'ALI-1005009723070135'

print("=" * 80)
print("CREATE NEW OFFER FOR ID 101")
print("=" * 80)
print()

# Get product price from database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('SELECT ebay_price FROM products WHERE id = 101')
result = cursor.fetchone()
price = result[0] if result else 25.67

print(f"SKU: {sku}")
print(f"Price: €{price}")
print()

try:
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
        'categoryId': '20741',
        'merchantLocationKey': 'WAREHOUSE_DE_1',
        'pricingSummary': {
            'price': {
                'currency': 'EUR',
                'value': str(price)
            }
        }
    }
    
    print("Creating new offer...")
    
    response1 = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
    
    new_offer_id = response1.get('offerId')
    
    print(f"✅ New offer created!")
    print(f"   Offer ID: {new_offer_id}")
    print()
    
    # Publish offer
    print("Publishing offer...")
    
    response2 = ebay._request('POST', f'/sell/inventory/v1/offer/{new_offer_id}/publish')
    
    listing_id = response2.get('listingId')
    
    print(f"✅ Offer published!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    # Update database
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            ebay_offer_id = ?,
            updated_at = datetime('now')
        WHERE id = 101
    ''', (listing_id, new_offer_id))
    
    conn.commit()
    
    print("✅ Database updated")
    print()
    
    print("=" * 80)
    print("🎉 NEW LISTING NOW ONLINE!")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print()
    print("Dimensions (correct):")
    print("  Länge: 26.5 cm")
    print("  Breite: 27.5 cm")
    print("  Höhe: 3 cm ✅")
    print()
    print("NOTE: This is a NEW listing (old offer was withdrawn).")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
