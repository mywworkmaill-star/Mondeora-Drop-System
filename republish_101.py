"""
Republish ID 101 offer (after withdrawal)
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

offer_id = '366088237011'

print("=" * 80)
print("REPUBLISHING OFFER")
print("=" * 80)
print()
print(f"Offer ID: {offer_id}")
print()

try:
    response = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    
    listing_id = response.get('listingId')
    
    print("✅ Offer republished successfully!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    # Update database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            updated_at = datetime('now')
        WHERE id = 101
    ''', (listing_id,))
    
    conn.commit()
    conn.close()
    
    print("✅ Database updated")
    print()
    print("=" * 80)
    print("🎉 LISTING NOW ONLINE!")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print()
    print("Current dimensions:")
    print("  Länge: 26.5 cm")
    print("  Breite: 27.5 cm")  
    print("  Höhe: 3 cm ✅")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
