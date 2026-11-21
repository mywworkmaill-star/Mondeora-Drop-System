#!/usr/bin/env python3
"""
Test rollback system with simulated publish failure
"""

import sys
sys.path.insert(0, 'src')

# Mock the eBay client to simulate failure
class MockeBayClient:
    def __init__(self):
        self.inventory_path = '/sell/inventory/v1'
        self.created_items = []
    
    def _request(self, method, path, json=None):
        print(f"   📡 MOCK API: {method} {path[:60]}")
        
        # Track created items
        if method == 'PUT' and '/inventory_item/' in path:
            sku = path.split('/')[-1]
            self.created_items.append(('inventory', sku))
            return {}
        
        elif method == 'POST' and path.endswith('/offer'):
            offer_id = f"OFFER-{len(self.created_items)}"
            self.created_items.append(('offer', offer_id))
            return {'offerId': offer_id}
        
        elif method == 'DELETE':
            return {}
        
        return {}
    
    def create_inventory_item_group(self, group_key, group_data):
        print(f"   📡 MOCK API: PUT /inventory_item_group/{group_key}")
        self.created_items.append(('group', group_key))
        return {}
    
    def publish_offer_by_inventory_item_group(self, group_key):
        # SIMULATE FAILURE HERE
        raise Exception("SIMULATED PUBLISH FAILURE - Testing rollback!")

# Monkey-patch
from ebay_variation_publisher_v2_rollback import VariationListingPublisher
import ebay_variation_publisher_v2_rollback
from api import ebay_client as ebay_client_module

# Replace real client with mock
original_client = ebay_client_module.eBayAPIClient
ebay_client_module.eBayAPIClient = MockeBayClient

print("="*70)
print("🧪 TESTING ROLLBACK SYSTEM WITH SIMULATED FAILURE")
print("="*70)

# Test with product 48 (has variations)
publisher = VariationListingPublisher()
result = publisher.publish_variation_listing(48)

print("\n" + "="*70)
print("📊 TEST RESULT:")
print("="*70)
print(f"Success: {result.get('success')}")
print(f"Error: {result.get('error')}")

if 'rollback' in result:
    rollback = result['rollback']
    print(f"\n🔄 ROLLBACK PERFORMED:")
    print(f"   SKUs deleted: {rollback['skus_deleted']}")
    print(f"   Offers deleted: {rollback['offers_deleted']}")
    print(f"   Group deleted: {rollback['group_deleted']}")
    print(f"   Errors: {len(rollback['errors'])}")
    
    if rollback['errors']:
        print(f"\n⚠️  Rollback errors:")
        for err in rollback['errors']:
            print(f"   - {err}")
    
    print(f"\n✅ ROLLBACK SYSTEM WORKS!" if rollback['skus_deleted'] > 0 else "❌ ROLLBACK FAILED")
else:
    print("\n❌ NO ROLLBACK DATA - System did not trigger rollback")

# Restore original client
ebay_client_module.eBayAPIClient = original_client
