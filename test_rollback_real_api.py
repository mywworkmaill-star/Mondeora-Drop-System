#!/usr/bin/env python3
import sys
sys.path.insert(0, "src")

from ebay_variation_publisher import VariationListingPublisher
import sqlite3
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("🧪 ROLLBACK TEST - Monkey-patching publish to fail")
print("="*80)

# Get product data
conn = sqlite3.connect("data/dropshipping.db")
cursor = conn.cursor()
cursor.execute("SELECT p.id, p.title FROM products p JOIN product_variations v ON p.id = v.product_id WHERE p.id = 21 LIMIT 1")
row = cursor.fetchone()
conn.close()

if not row:
    print("❌ Product 21 not found!")
    sys.exit(1)

product_id, title = row
print(f"📦 Product: {title[:60]}")
print("-"*80)
input("Press ENTER to start (or Ctrl+C to cancel)...")

# Initialize publisher
publisher = VariationListingPublisher()

# Monkey-patch the publish method to fail
original_method = publisher.ebay.publish_offer_by_inventory_item_group

def failing_publish(group_key, marketplace_id="EBAY_DE"):
    raise Exception("INTENTIONAL_TEST_ERROR: Forcing failure at Step 4")

publisher.ebay.publish_offer_by_inventory_item_group = failing_publish

print("
🚀 Running publish (will fail at Step 4)...")
print("="*80)

# Run - should fail and trigger rollback
result = publisher.publish_variation_listing(product_id=product_id)

# Restore
publisher.ebay.publish_offer_by_inventory_item_group = original_method

print("
" + "="*80)
print("📊 RESULT")
print("="*80)

if result.get("success"):
    print("❌ UNEXPECTED: Succeeded (should have failed!)")
else:
    print("✅ Failed as expected")
    print(f"Error: {result.get("error", "N/A")[:60]}")
    
    if "rollback" in result:
        rb = result["rollback"]
        print(f"
🔄 Rollback:")
        print(f"   SKUs deleted: {rb.get("skus_deleted", 0)}")
        print(f"   Offers deleted: {rb.get("offers_deleted", 0)}")
        print(f"   Group deleted: {rb.get("group_deleted", False)}")
        
        if rb.get("skus_deleted") >= 2 and rb.get("offers_deleted") >= 2:
            print("
✅✅✅ ROLLBACK TEST PASSED! ✅✅✅")
        else:
            print("
⚠️  ROLLBACK INCOMPLETE")
    else:
        print("❌ No rollback data")

print("="*80)
