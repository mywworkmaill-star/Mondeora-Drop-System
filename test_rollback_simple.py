#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from ebay_variation_publisher import VariationListingPublisher
import sqlite3
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("ROLLBACK TEST - Monkey-patching publish to fail")
print("="*80)

# Get product
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute("SELECT id, title FROM products WHERE id = 21")
row = cursor.fetchone()
conn.close()

if not row:
    print("Product 21 not found!")
    sys.exit(1)

product_id, title = row
print(f"Product: {title[:60]}")
print("-"*80)

# Initialize
publisher = VariationListingPublisher()

# Monkey-patch to fail
original = publisher.ebay.publish_offer_by_inventory_item_group

def fail(*args, **kwargs):
    raise Exception("TEST_ERROR: Forced failure at Step 4")

publisher.ebay.publish_offer_by_inventory_item_group = fail

print("Running publish (will fail at Step 4)...")
print("="*80)

# Run
result = publisher.publish_variation_listing(product_id=product_id)

# Restore
publisher.ebay.publish_offer_by_inventory_item_group = original

print()
print("="*80)
print("RESULT")
print("="*80)

if result.get('success'):
    print("UNEXPECTED: Succeeded")
else:
    print("Failed as expected")
    print(f"Error: {result.get('error', 'N/A')[:60]}")
    
    if 'rollback' in result:
        rb = result['rollback']
        print()
        print("Rollback:")
        print(f"  SKUs deleted: {rb.get('skus_deleted', 0)}")
        print(f"  Offers deleted: {rb.get('offers_deleted', 0)}")
        print(f"  Group deleted: {rb.get('group_deleted', False)}")
        
        if rb.get('skus_deleted') >= 2 and rb.get('offers_deleted') >= 2:
            print()
            print("ROLLBACK TEST PASSED!")
        else:
            print()
            print("ROLLBACK INCOMPLETE")
    else:
        print("No rollback data")

print("="*80)
