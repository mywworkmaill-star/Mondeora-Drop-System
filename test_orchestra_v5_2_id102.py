"""
TEST ORCHESTRA v5.2 - Single Product Test (ID 102)
Tests AliExpress verification workflow
"""

import sys
sys.path.insert(0, 'src')

from orchestra_v5_2_aliexpress_verified import OrchestraV52
import sqlite3
from datetime import datetime

PRODUCT_ID = 136  # Battery organizer (similar to ID 137)

print("=" * 80)
print("🧪 ORCHESTRA v5.2 TEST - ALIEXPRESS VERIFICATION")
print("=" * 80)
print(f"Product ID: {PRODUCT_ID}")
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Load product from database
conn = sqlite3.connect('data/dropshipping.db')
c = conn.cursor()

c.execute("""
    SELECT id, title, aliexpress_product_id, aliexpress_price, shipping_cost,
           ebay_price, image_url, status, category_id
    FROM products
    WHERE id = ?
""", (PRODUCT_ID,))

row = c.fetchone()

if not row:
    print(f"❌ Product {PRODUCT_ID} not found!")
    conn.close()
    sys.exit(1)

print("✅ Product loaded:")
print(f"   ID: {row[0]}")
print(f"   Title: {row[1][:60]}...")
print(f"   AliExpress ID: {row[2]}")
print(f"   Price: €{row[5]:.2f}")
print(f"   Status: {row[7]}")
print()

conn.close()

# Run Orchestra v5.2
print("🚀 Starting Orchestra v5.2...")
print()

orchestra = OrchestraV52()

try:
    result = orchestra.run(product_id=PRODUCT_ID)
    
    print()
    print("=" * 80)
    
    if result['success']:
        print("✅ ORCHESTRA v5.2 TEST: SUCCESS!")
        print("=" * 80)
        print()
        print(f"eBay Listing: {result['ebay_item_id']}")
        print(f"Duration: {result.get('duration_seconds', 0):.1f}s")
        print(f"Profit: €{result.get('profit', 0):.2f}")
        print()
        
        if result.get('promoted_listing'):
            print("📢 Promoted Listing:")
            print(f"   Campaign: {result['promoted_listing'].get('campaign_id', 'N/A')}")
            print(f"   Ad ID: {result['promoted_listing'].get('ad_id', 'N/A')}")
            print(f"   Bid: {result['promoted_listing'].get('bid_rate', 0)}%")
            print()
        
        print("🎯 KEY TEST POINTS:")
        print("   1. AliExpress verification completed?")
        print("   2. Color from SKU (not 'Mehrfarbig')?")
        print("   3. Category 159897 used?")
        print("   4. All variant images included?")
        print()
        print(f"🔗 Check listing: https://www.ebay.de/itm/{result['ebay_item_id']}")
        
    else:
        print("❌ ORCHESTRA v5.2 TEST: FAILED")
        print("=" * 80)
        print(f"Error: {result.get('error', 'Unknown')}")
    
except Exception as e:
    print("=" * 80)
    print("❌ EXCEPTION DURING TEST")
    print("=" * 80)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print(f"Test ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
