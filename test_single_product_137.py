"""
ORCHESTRA v5.1 - SINGLE PRODUCT TEST
Test ID 137 with full Orchestra v5.1 workflow
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Setup paths
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 80)
print("🎯 ORCHESTRA v5.1 - SINGLE PRODUCT PRODUCTION TEST")
print("=" * 80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Target product
PRODUCT_ID = 137

# Get product from database
conn = sqlite3.connect('data/dropshipping.db')
c = conn.cursor()

c.execute("""
    SELECT id, aliexpress_product_id, sku_id, title, image_url,
           aliexpress_price, shipping_cost, ebay_price,
           description, category_id, currency
    FROM products
    WHERE id = ?
""", (PRODUCT_ID,))

row = c.fetchone()

if not row:
    print(f"❌ Product ID {PRODUCT_ID} not found!")
    sys.exit(1)

# Build product dict
product = {
    'id': row[0],
    'aliexpress_product_id': row[1],
    'sku_id': row[2],
    'title': row[3],
    'image_url': row[4],
    'aliexpress_price': float(row[5]) if row[5] else 0,
    'shipping_cost': float(row[6]) if row[6] else 0,
    'ebay_price': float(row[7]) if row[7] else 0,
    'description': row[8],
    'category_id': row[9] or '20741',  # Default to Home Organization
    'currency': row[10] or 'EUR'
}

conn.close()

print(f"✅ PRODUCT LOADED:")
print(f"   ID: {product['id']}")
print(f"   AliExpress: {product['aliexpress_product_id']}")
print(f"   Title: {product['title'][:70]}")
print(f"   Price: €{product['aliexpress_price']} + €{product['shipping_cost']} → €{product['ebay_price']}")
print()

# Import Orchestra
print("=" * 80)
print("🚀 STARTING ORCHESTRA v5.1...")
print("=" * 80)
print()

try:
    # Import orchestra module
    from orchestra_v5_1_full import OrchestraV51
    
    # Initialize Orchestra
    orchestra = OrchestraV51()
    
    print("✅ Orchestra v5.1 initialized")
    print()
    
    # Run full workflow WITH SPECIFIC PRODUCT ID
    print("🎵 RUNNING FULL 9-STEP WORKFLOW FOR ID 137...")
    print()
    
    result = orchestra.run(product_id=PRODUCT_ID)
    
    # Display result
    print()
    print("=" * 80)
    print("📊 ORCHESTRA RESULT")
    print("=" * 80)
    
    if result:
        print(f"✅ SUCCESS!")
        print(f"   Listing ID: {result.get('listing_id', 'N/A')}")
        print(f"   Product ID: {result.get('product_id', 'N/A')}")
        print(f"   Duration: {result.get('duration', 'N/A'):.1f}s")
        
        if result.get('promoted_listing'):
            ad_info = result['promoted_listing']
            print(f"\n🎯 PROMOTED LISTING:")
            print(f"   Campaign: {ad_info.get('campaign_name', 'N/A')}")
            print(f"   Ad ID: {ad_info.get('ad_id', 'N/A')}")
            print(f"   Bid Rate: {ad_info.get('bid_rate', 'N/A')}%")
        
        if result.get('comprehensive_specs'):
            specs = result['comprehensive_specs']
            print(f"\n📏 SPECS EXTRACTED:")
            if specs.get('dimensions', {}).get('found'):
                dims = specs['dimensions']
                print(f"   Dimensions: {dims.get('length_cm')}×{dims.get('width_cm')}×{dims.get('height_cm')} cm")
            if specs.get('material', {}).get('found'):
                print(f"   Material: {specs['material'].get('value')}")
            if specs.get('color', {}).get('found'):
                print(f"   Color: {specs['color'].get('value')}")
        
        # Save result
        with open(f'orchestra_result_137_{datetime.now():%Y%m%d_%H%M%S}.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\n💾 Result saved to orchestra_result_137_*.json")
    else:
        print("❌ FAILED - No result returned")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 80)
print("✅ TEST COMPLETED")
print("=" * 80)
print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
