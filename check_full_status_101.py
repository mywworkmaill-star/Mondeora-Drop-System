"""
Check full status of ID 101 on eBay
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import json

ebay = eBayAPIClient()

sku = 'ALI-1005009723070135'
offer_id = '366088237011'

print("=" * 80)
print("ID 101 - FULL STATUS CHECK")
print("=" * 80)
print()

# Check inventory item
print("1. INVENTORY ITEM STATUS:")
print(f"   SKU: {sku}")
print()

try:
    inv = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
    
    print("   ✅ Inventory item EXISTS")
    print(f"   Title: {inv.get('product', {}).get('title', 'N/A')[:60]}...")
    
    aspects = inv.get('product', {}).get('aspects', {})
    print(f"   Höhe: {aspects.get('Höhe', ['Not set'])}")
    print()
    
except Exception as e:
    print(f"   ❌ Inventory item NOT FOUND: {str(e)}")
    print()

# Check offer
print("2. OFFER STATUS:")
print(f"   Offer ID: {offer_id}")
print()

try:
    offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
    
    print("   ✅ Offer EXISTS")
    print(f"   Status: {offer.get('status', 'Unknown')}")
    print(f"   Listing ID: {offer.get('listingId', 'None')}")
    print(f"   SKU: {offer.get('sku', 'N/A')}")
    print()
    
    # Try to get offer details
    listing_aspects = offer.get('listing', {}).get('aspects', {})
    if listing_aspects:
        print(f"   Listing Höhe: {listing_aspects.get('Höhe', ['Not set'])}")
    
    print()
    
except Exception as e:
    print(f"   ❌ Offer NOT FOUND: {str(e)}")
    print()

# Check all offers for this SKU
print("3. ALL OFFERS FOR THIS SKU:")
print()

try:
    all_offers = ebay._request('GET', f'/sell/inventory/v1/offer?sku={sku}')
    
    offers_list = all_offers.get('offers', [])
    
    print(f"   Found {len(offers_list)} offer(s):")
    print()
    
    for i, off in enumerate(offers_list, 1):
        print(f"   Offer {i}:")
        print(f"     ID: {off.get('offerId')}")
        print(f"     Status: {off.get('status')}")
        print(f"     Listing ID: {off.get('listingId', 'None')}")
        print()
    
except Exception as e:
    print(f"   ❌ Error getting offers: {str(e)}")
    print()

print("=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print()

print("Based on the status above:")
print("• If inventory item exists with correct Höhe (3cm) → Good")
print("• If offer is WITHDRAWN → Need to delete old offer + create new")
print("• If offer doesn't exist → Need to create new offer")
print()
print("Next steps will be determined based on this output.")
