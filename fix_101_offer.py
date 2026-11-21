"""
FIX ID 101 - Update offer directly (bypass inventory item)
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()

print("=" * 80)
print("ID 101 HEIGHT CORRECTION via OFFER UPDATE")
print("=" * 80)
print()

offer_id = '366088237011'

print(f"Getting current offer: {offer_id}")

try:
    # Get current offer
    offer = ebay._request('GET', f'/sell/inventory/v1/offer/{offer_id}')
    
    print(f"✅ Offer found!")
    print(f"   Listing ID: {offer.get('listingId')}")
    print(f"   SKU: {offer.get('sku')}")
    print()
    
    # Update aspects in offer
    print("Updating aspects (Höhe: 13cm → 3cm)...")
    
    # Get current aspects
    aspects = offer.get('listing', {}).get('aspects', {})
    
    print(f"\nCurrent Höhe: {aspects.get('Höhe', ['Not set'])}")
    
    # Update Höhe
    aspects['Höhe'] = ['3 cm']
    
    # Also update Besonderheiten to include "Ultra-Flach 3cm"
    besonderheiten = aspects.get('Besonderheiten', [])
    # Remove any old height mentions
    besonderheiten = [b for b in besonderheiten if '13cm' not in b and 'Flach' not in b]
    besonderheiten.append('Ultra-Flach 3cm')
    aspects['Besonderheiten'] = besonderheiten[:10]  # eBay limit
    
    print(f"New Höhe: {aspects['Höhe']}")
    print()
    
    # Update offer with new aspects
    update_data = {
        'listing': {
            'aspects': aspects
        }
    }
    
    response = ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_data)
    
    print(f"✅ Offer updated!")
    print()
    
    # Republish to apply changes
    print(f"Republishing offer to apply changes...")
    
    response2 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response2.get('listingId')
    
    print(f"✅ Offer republished!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    print("=" * 80)
    print("✅ HEIGHT CORRECTION COMPLETE!")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print()
    print("CORRECTED:")
    print("  ❌ Old: Höhe = 13 cm")
    print("  ✅ New: Höhe = 3 cm")
    print()
    print("Changes now LIVE on eBay.de!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
