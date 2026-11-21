"""
FIX CATEGORY FOR ID 137 - eBay Item 860161372096
Correct category from Pet Supplies to Home Organization
"""

import os
import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime

print("=" * 80)
print("🔧 FIX CATEGORY - ID 137")
print("=" * 80)
print()

ebay = eBayAPIClient()

# Product info
product_id = 137
ebay_item_id = "860161372096"
offer_id = "366203660011"  # From database

# Correct category
CORRECT_CATEGORY = "20741"  # Home Organization & Storage

print(f"Product ID: {product_id}")
print(f"eBay Item: {ebay_item_id}")
print(f"Offer ID: {offer_id}")
print(f"Target Category: {CORRECT_CATEGORY} (Home Organization)")
print()

try:
    # Step 1: Get current offer
    print("📋 Step 1: Getting current offer...")
    offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
    
    if not offer:
        print(f"❌ Offer not found: {offer_id}")
        sys.exit(1)
    
    print(f"✅ Found offer: {offer_id}")
    print(f"   Current category: {offer.get('categoryId', 'Unknown')}")
    print(f"   SKU: {offer.get('sku', 'Unknown')}")
    print()
    
    # Step 2: Update offer with correct category
    print("🔄 Step 2: Updating offer category...")
    
    # Get SKU from offer
    sku = offer.get('sku', '')
    
    update_payload = {
        'offerId': offer_id,
        'sku': sku,
        'marketplaceId': 'EBAY_DE',
        'format': 'FIXED_PRICE',
        'categoryId': CORRECT_CATEGORY,  # HOME ORGANIZATION
        'listingDescription': offer.get('listingDescription', ''),
        'listingPolicies': offer.get('listingPolicies', {}),
        'merchantLocationKey': offer.get('merchantLocationKey', 'WAREHOUSE_DE_1'),
        'pricingSummary': offer.get('pricingSummary', {})
    }
    
    # Add aspects with correct room
    if 'listingPolicies' in offer:
        update_payload['listingPolicies'] = offer['listingPolicies']
    
    result = ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_payload)
    
    print("✅ Offer updated successfully!")
    print()
    
    # Step 3: Update database
    print("💾 Step 3: Updating database...")
    conn = sqlite3.connect('data/dropshipping.db')
    c = conn.cursor()
    
    c.execute("""
        UPDATE products
        SET category_id = ?,
            updated_at = ?
        WHERE id = ?
    """, (CORRECT_CATEGORY, datetime.now().isoformat(), product_id))
    
    conn.commit()
    conn.close()
    
    print("✅ Database updated!")
    print()
    
    print("=" * 80)
    print("✅ CATEGORY FIX COMPLETED!")
    print("=" * 80)
    print()
    print("🔗 Check listing: https://www.ebay.de/itm/860161372096")
    print("   Category should now be: Home Organization & Storage")
    print()
    print("⏱️  Changes may take 5-10 minutes to reflect on eBay")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
