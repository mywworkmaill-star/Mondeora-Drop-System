"""
Debug new publish attempt
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()

group_key = "VAR-48-1795036915"

print(f"Testing publish for NEW group: {group_key}")
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
    print(response.text)
    
except Exception as e:
    print(f"ERROR: {e}")
