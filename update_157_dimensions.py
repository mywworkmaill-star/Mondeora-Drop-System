"""Update ID 157 eBay listing with missing dimension aspects."""
import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import json

print('=' * 80)
print('ID 157 - ADD MISSING DIMENSIONS TO eBay LISTING')
print('=' * 80)
print()

# Initialize eBay client
ebay = eBayAPIClient()

# ID 157 details
ebay_offer_id = '365176523011'
ebay_item_id = '860159069263'

print(f'eBay Item ID:  {ebay_item_id}')
print(f'eBay Offer ID: {ebay_offer_id}')
print()

# Dimensions from image 4/6 analysis (manual extraction)
# Image shows: 17cm / 6.69inch (length) × 8.5cm / 3.35inch (height)
# Width from AliExpress description: ~4.5cm (depth of organizer)

dimensions_to_add = {
    "Länge": ["17 cm"],
    "Höhe": ["8.5 cm"],
    "Breite": ["4.5 cm"]
}

print('DIMENSIONS TO ADD:')
print('-' * 80)
for key, value in dimensions_to_add.items():
    print(f'  {key:15} → {value[0]}')
print()

# Get current aspects from offer
try:
    print('Step 1: Fetching current offer...')
    offer_data = ebay._request('GET', f'/sell/inventory/v1/offer/{ebay_offer_id}')
    
    print('DEBUG: Offer structure')
    print(json.dumps(offer_data, indent=2)[:1000])
    print()
    
    # Try different paths for aspects
    if 'product' in offer_data:
        current_aspects = offer_data['product'].get('aspects', {})
    elif 'listingDescription' in offer_data:
        current_aspects = offer_data.get('aspects', {})
    else:
        # Try root level
        current_aspects = offer_data.get('aspects', {})
    
    print(f'✅ Current aspects: {len(current_aspects)} keys')
    print()
    
    # Merge dimensions with existing aspects
    updated_aspects = current_aspects.copy()
    updated_aspects.update(dimensions_to_add)
    
    print('UPDATED ASPECTS (after merge):')
    print('-' * 80)
    for key, value in updated_aspects.items():
        print(f'  {key:25} → {value}')
    print()
    print(f'Total: {len(updated_aspects)} keys (+{len(dimensions_to_add)} new)')
    print()
    
    # Update offer with new aspects
    print('Step 2: Updating offer with dimensions...')
    
    update_payload = {
        "product": {
            "title": offer_data['product']['title'],
            "description": offer_data['product']['description'],
            "aspects": updated_aspects,
            "imageUrls": offer_data['product']['imageUrls']
        },
        "categoryId": offer_data['categoryId'],
        "format": offer_data['format'],
        "availableQuantity": offer_data['availableQuantity'],
        "pricingSummary": offer_data['pricingSummary'],
        "listingPolicies": offer_data['listingPolicies'],
        "merchantLocationKey": offer_data['merchantLocationKey']
    }
    
    update_response = ebay._request('PUT', f'/sell/inventory/v1/offer/{ebay_offer_id}', json=update_payload)
    
    print('✅ Offer updated successfully!')
    print()
    
    # Publish to apply changes
    print('Step 3: Publishing changes to eBay...')
    
    publish_response = ebay._request('POST', f'/sell/inventory/v1/offer/{ebay_offer_id}/publish')
    
    print('✅✅✅ PUBLISHED SUCCESSFULLY! ✅✅✅')
    print()
    print('=' * 80)
    print('SUCCESS SUMMARY:')
    print('=' * 80)
    print(f'  eBay Item ID: {ebay_item_id}')
    print(f'  URL: https://www.ebay.de/itm/{ebay_item_id}')
    print()
    print('  Added Dimensions:')
    print(f'    • Länge: 17 cm')
    print(f'    • Höhe: 8.5 cm')
    print(f'    • Breite: 4.5 cm')
    print()
    print('  Impact:')
    print('    ✅ Now visible in eBay size filters')
    print('    ✅ Professional specs complete')
    print('    ✅ Competitive with other sellers')
    print()
    print('=' * 80)

except Exception as e:
    print(f'❌ Error: {str(e)}')
    import traceback
    traceback.print_exc()
