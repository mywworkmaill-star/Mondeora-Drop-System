"""Debug latest attempt"""
import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()

try:
    resp = ebay.session.request('POST', ebay.production_url + '/sell/inventory/v1/offer/publish_by_inventory_item_group',
        headers=ebay._get_headers(), json={'inventoryItemGroupKey': 'VAR-48-1795037032', 'marketplaceId': 'EBAY_DE'}, timeout=30)
    print(f"STATUS: {resp.status_code}\nRESPONSE:\n{resp.text}")
except Exception as e:
    print(f"ERROR: {e}")
