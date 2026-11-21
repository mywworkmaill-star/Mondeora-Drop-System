#!/usr/bin/env python3
"""Debug eBay API responses by temporarily patching the client"""

import sys
import json
import sqlite3
import time

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

# Monkey-patch _fail to also print response body
original_fail = eBayAPIClient._fail

def debug_fail(self, message, status_code=None):
    print(f"\n🔴 eBay API Error Details:")
    print(f"   Message: {message}")
    if status_code:
        print(f"   Status Code: {status_code}")
    
    # Try to access response object (it might be in session)
    if hasattr(self.session, 'last_response'):
        resp = self.session.last_response
        if hasattr(resp, 'text'):
            print(f"   Response Body: {resp.text[:2000]}")
    
    return original_fail(self, message, status_code)

eBayAPIClient._fail = debug_fail

# Also patch _request to capture responses
original_request = eBayAPIClient._request

def debug_request(self, method, path, **kwargs):
    try:
        result = original_request(self, method, path, **kwargs)
        return result
    except Exception as e:
        # Try to get response from session
        if hasattr(self, 'session') and hasattr(self.session, 'last_response'):
            resp = self.session.last_response
            if hasattr(resp, 'text'):
                print(f"\n🔴 HTTP Response Body:")
                print(resp.text[:2000])
                print()
        raise

eBayAPIClient._request = debug_request

# Now test
product_id = 23

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))
conn.close()

listing_data = {
    "sku": f"DEBUG-{int(time.time())}",
    "title": product['title'][:80],
    "description": "Hochwertige faltbare Aufbewahrungstasche.",
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",
    "condition": "NEW",
    "image_urls": [product.get('image_url')],
    "aspects": {
        "Produktart": ["Aufbewahrungstasche"],
        "Breite": ["40 cm"],
        "Höhe": ["30 cm"],
        "Länge": ["50 cm"],
        "Hauptmaterial": ["Polyester"],
        "Marke": ["Markenlos"]
    }
}

print(f'📦 Testing product ID: {product_id}')
print(f'   SKU: {listing_data["sku"]}')

ebay = eBayAPIClient()

# Monkey-patch requests.Session to capture last response
import requests

original_session_request = requests.Session.request

def capture_response(self, method, url, **kwargs):
    response = original_session_request(self, method, url, **kwargs)
    self.last_response = response
    
    # Print debug info for 400 errors
    if response.status_code == 400:
        print(f"\n🔴 HTTP 400 Details:")
        print(f"   URL: {method} {url}")
        print(f"   Response: {response.text[:2000]}")
        try:
            error_json = response.json()
            print(f"   JSON: {json.dumps(error_json, indent=2)[:2000]}")
        except:
            pass
    
    return response

requests.Session.request = capture_response

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f'\n✅ SUCCESS!')
        print(f'   Item ID: {result.get("ebay_item_id")}')
    else:
        print(f'\n❌ Failed: {result}')
        
except Exception as e:
    print(f'\n❌ Exception: {e}')
    import traceback
    traceback.print_exc()
