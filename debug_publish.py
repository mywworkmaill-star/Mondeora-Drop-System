"""
Debug publish_by_inventory_item_group call
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import requests

ebay = eBayAPIClient()

# Test publish
group_key = "VAR-48-1795036775"

print(f"Testing publish for group: {group_key}")
print()

try:
    response = ebay.session.request(
        'POST',
        ebay.production_url + '/sell/inventory/v1/offer/publish_by_inventory_item_group',
        headers=ebay._get_headers(),
        json={
            'inventoryItemGroupKey': group_key,
            'marketplaceId': 'EBAY_DE'
        },
        timeout=30
    )
    
    print(f"STATUS: {response.status_code}")
    print(f"RESPONSE:")
    print(response.text[:1500])
    
except Exception as e:
    print(f"ERROR: {e}")
