"""
Debug eBay API Response
Temporary script to see full error response
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import requests

ebay = eBayAPIClient()

# Monkey patch to see response body
original_request = ebay._request

def debug_request(method, path, **kwargs):
    if not path.startswith('/') or '#' in path or '://' in path:
        raise ValueError('Invalid path')
    
    if method != 'GET':
        # Check live mode
        pass
    
    try:
        response = ebay.session.request(
            method,
            ebay.production_url + path,
            headers=ebay._get_headers(),
            timeout=30,
            allow_redirects=False,
            **kwargs
        )
        
        print(f"\n{'='*70}")
        print(f"REQUEST: {method} {path}")
        print(f"STATUS: {response.status_code}")
        print(f"{'='*70}")
        print(f"RESPONSE BODY:")
        print(response.text[:2000])
        print(f"{'='*70}\n")
        
        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}")
        
        return response.json() if response.text else {}
        
    except Exception as e:
        print(f"ERROR: {e}")
        raise

ebay._request = debug_request

# Test
inventory_data = {
    'product': {
        'title': 'Test Kabel-Organizer Schwarz 1m',
        'aspects': {
            'Produktart': ['Kabelorganizer'],
            'Marke': ['Markenlos']
        },
        'description': '<p>Test</p>',
        'imageUrls': []
    },
    'condition': 'NEW',
    'availability': {
        'shipToLocationAvailability': {
            'quantity': 50
        }
    }
}

try:
    ebay._request(
        'PUT',
        '/sell/inventory/v1/inventory_item/TEST-SKU-001',
        json=inventory_data
    )
except:
    pass
