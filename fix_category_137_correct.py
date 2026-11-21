"""
FIX CATEGORY FOR ID 137 - CORRECT eBay DE Category
Update from wrong category to 159897 (Storage Boxes)
"""

import os
import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime

print("=" * 80)
print("🔧 FIX CATEGORY - ID 137 → CORRECT eBay DE CATEGORY")
print("=" * 80)
print()

ebay = eBayAPIClient()

# Product info
product_id = 137
ebay_item_id = "860161372096"
offer_id = "366203660011"

# CORRECT eBay DE category for battery organizer storage box
OLD_CATEGORY = "20741"  # Wrong: Pet Supplies > Cat Toys (on eBay DE)
NEW_CATEGORY = "159897"  # Correct: Storage Boxes (Klein- & Hängeaufbewahrung > Boxen)

print(f"Product ID: {product_id}")
print(f"eBay Item: {ebay_item_id}")
print(f"Offer ID: {offer_id}")
print()
print(f"OLD Category: {OLD_CATEGORY} (Haustierbedarf > Katzen > Spielzeug)")
print(f"NEW Category: {NEW_CATEGORY} (Möbel & Wohnen > Boxen)")
print()

try:
    # Step 1: Get current offer
    print("📋 Step 1: Getting current offer...")
    offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
    
    if not offer:
        print(f"❌ Offer not found: {offer_id}")
        sys.exit(1)
    
    sku = offer.get('sku', '')
    
    print(f"✅ Found offer: {offer_id}")
    print(f"   Current category: {offer.get('categoryId', 'Unknown')}")
    print(f"   SKU: {sku}")
    print()
    
    # Step 2: Update offer with correct eBay DE category
    print(f"🔄 Step 2: Updating to category {NEW_CATEGORY}...")
    
    update_payload = {
        'offerId': offer_id,
        'sku': sku,
        'marketplaceId': 'EBAY_DE',
        'format': 'FIXED_PRICE',
        'categoryId': NEW_CATEGORY,  # CORRECT eBay DE category
        'listingDescription': offer.get('listingDescription', ''),
        'listingPolicies': offer.get('listingPolicies', {}),
        'merchantLocationKey': offer.get('merchantLocationKey', 'WAREHOUSE_DE_1'),
        'pricingSummary': offer.get('pricingSummary', {})
    }
    
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
    """, (NEW_CATEGORY, datetime.now().isoformat(), product_id))
    
    conn.commit()
    conn.close()
    
    print("✅ Database updated!")
    print()
    
    print("=" * 80)
    print("✅ CATEGORY FIX COMPLETED!")
    print("=" * 80)
    print()
    print("🔗 Check listing: https://www.ebay.de/itm/860161372096")
    print(f"   New category: {NEW_CATEGORY}")
    print("   Path: Möbel & Wohnen > Klein- & Hängeaufbewahrung > Boxen")
    print()
    print("⏱️  Changes may take 5-15 minutes to reflect on eBay")
    print()
    print("✅ This is the CORRECT category for battery organizer!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
