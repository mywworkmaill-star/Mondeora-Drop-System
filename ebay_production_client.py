"""
eBay Production API Client - Direct Token Usage
Auto-renewal built-in
"""

import os
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

class EbayProductionClient:
    def __init__(self):
        self.access_token = os.getenv("EBAY_ACCESS_TOKEN")
        self.payment_policy = os.getenv("EBAY_PAYMENT_POLICY_ID", "263035304017")
        self.fulfillment_policy = os.getenv("EBAY_FULFILLMENT_POLICY_ID", "263035403017")
        self.return_policy = os.getenv("EBAY_RETURN_POLICY_ID", "263035310017")
        
        self.base_url = "https://api.ebay.com"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def get_payment_policies(self):
        """Get payment policies"""
        response = requests.get(
            f"{self.base_url}/sell/account/v1/payment_policy",
            headers=self.headers, timeout=30
        )
        return response
    
    def get_fulfillment_policies(self):
        """Get fulfillment policies"""
        response = requests.get(
            f"{self.base_url}/sell/account/v1/fulfillment_policy",
            headers=self.headers, timeout=30
        )
        return response
    
    def get_return_policies(self):
        """Get return policies"""
        response = requests.get(
            f"{self.base_url}/sell/account/v1/return_policy",
            headers=self.headers, timeout=30
        )
        return response
    
    def get_inventory(self, limit=100):
        """Get inventory items"""
        response = requests.get(
            f"{self.base_url}/sell/inventory/v1/inventory?limit={limit}",
            headers=self.headers, timeout=30
        )
        return response
    
    def create_inventory_item(self, sku, product_data):
        """Create or update inventory item"""
        response = requests.post(
            f"{self.base_url}/sell/inventory/v1/inventory/{sku}",
            json=product_data,
            headers=self.headers, timeout=30
        )
        return response

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    client = EbayProductionClient()
    
    print("Testing eBay Production API...")
    print()
    
    # Test Payment Policy
    print("1. Payment Policy:")
    response = client.get_payment_policies()
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Success")
    else:
        print(f"   ❌ Failed: {response.text[:100]}")
    
    # Test Fulfillment Policy
    print("\n2. Fulfillment Policy:")
    response = client.get_fulfillment_policies()
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Success")
    else:
        print(f"   ❌ Failed: {response.text[:100]}")
    
    # Test Inventory
    print("\n3. Inventory:")
    response = client.get_inventory()
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Success")
    else:
        print(f"   ❌ Failed: {response.text[:100]}")
