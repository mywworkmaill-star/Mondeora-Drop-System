"""
Test: Add ID 101 (860161122076) to Promoted Listings
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
from datetime import datetime

ebay = eBayAPIClient()

listing_id = '860161122076'  # ID 101 - just published

print("=" * 80)
print("TEST: ADD LISTING TO PROMOTED LISTINGS")
print("=" * 80)
print()
print(f"Listing ID: {listing_id}")
print()

# =============================================================================
# STEP 1: Get or create campaign
# =============================================================================

print("STEP 1: Checking existing campaigns...")
print()

try:
    response1 = ebay._request('GET', '/sell/marketing/v1/ad_campaign?campaign_status=RUNNING')
    
    campaigns = response1.get('campaigns', [])
    
    print(f"Found {len(campaigns)} RUNNING campaign(s)")
    print()
    
    campaign_id = None
    campaign_name = None
    
    # Look for Mondeora campaign
    for campaign in campaigns:
        name = campaign.get('campaignName', '')
        if 'Mondeora' in name or 'Auto' in name:
            campaign_id = campaign.get('campaignId')
            campaign_name = name
            print(f"✅ Found existing campaign:")
            print(f"   Name: {name}")
            print(f"   ID: {campaign_id}")
            print()
            break
    
    # Create if not exists
    if not campaign_id:
        print("No Mondeora campaign found, creating new...")
        print()
        
        campaign_data = {
            'campaignName': f'Mondeora Auto Campaign {datetime.now().strftime("%Y-%m")}',
            'marketplaceId': 'EBAY_DE',
            'fundingStrategy': {
                'fundingModel': 'COST_PER_SALE',
                'bidPercentage': '8.0'
            },
            'startDate': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        response_create = ebay._request('POST', '/sell/marketing/v1/ad_campaign', json=campaign_data)
        
        campaign_id = response_create.get('campaignId')
        campaign_name = campaign_data['campaignName']
        
        if campaign_id:
            print(f"✅ Campaign created!")
            print(f"   Name: {campaign_name}")
            print(f"   ID: {campaign_id}")
            print()
        else:
            print("❌ Campaign creation failed")
            exit(1)

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

# =============================================================================
# STEP 2: Get suggested bid rate
# =============================================================================

print("STEP 2: Getting suggested bid rate...")
print()

suggested_bid = None

try:
    response2 = ebay._request(
        'GET',
        f'/sell/marketing/v1/ad_campaign_suggested_bid?marketplace_id=EBAY_DE&listing_ids={listing_id}'
    )
    
    suggestions = response2.get('suggestions', [])
    
    if suggestions and len(suggestions) > 0:
        suggested = suggestions[0].get('suggestedBidPercentage')
        
        if suggested:
            suggested_bid = float(suggested)
            
            # Cap between 2.0 and 20.0
            if suggested_bid < 2.0:
                suggested_bid = 2.0
            elif suggested_bid > 20.0:
                suggested_bid = 20.0
            
            suggested_bid = round(suggested_bid, 1)
            
            print(f"✅ Suggested bid rate: {suggested_bid}%")
            print()

except Exception as e:
    print(f"⚠️  Suggested bid unavailable: {str(e)}")
    print()

# Use default if no suggestion
if not suggested_bid:
    suggested_bid = 8.0
    print(f"Using default bid rate: {suggested_bid}%")
    print()

# =============================================================================
# STEP 3: Add listing to campaign
# =============================================================================

print("STEP 3: Adding listing to campaign...")
print()

bid_str = f"{suggested_bid:.1f}"

request_data = {
    'requests': [
        {
            'listingId': listing_id,
            'bidPercentage': bid_str
        }
    ]
}

print(f"Request: listingId={listing_id}, bidPercentage={bid_str}")
print()

try:
    response3 = ebay._request(
        'POST',
        f'/sell/marketing/v1/ad_campaign/{campaign_id}/bulk_create_ads_by_listing_id',
        json=request_data
    )
    
    responses = response3.get('responses', [])
    
    if responses and len(responses) > 0:
        first = responses[0]
        status_code = first.get('statusCode')
        
        if status_code == 201:
            ad_id = first.get('adId')
            
            print("✅ AD CREATED SUCCESSFULLY!")
            print()
            print(f"   Ad ID: {ad_id}")
            print(f"   Listing ID: {first.get('listingId')}")
            print(f"   Campaign: {campaign_name}")
            print(f"   Bid Rate: {bid_str}%")
            print()
            
            print("=" * 80)
            print("🎉 PROMOTED LISTING ACTIVE!")
            print("=" * 80)
            print()
            print(f"🔗 eBay Listing: https://www.ebay.de/itm/{listing_id}")
            print(f"💰 Ad Cost: {bid_str}% of sale price")
            print(f"📈 Campaign: {campaign_name}")
            
        else:
            print(f"❌ Ad creation failed: HTTP {status_code}")
            
            errors = first.get('errors', [])
            for err in errors:
                print(f"   Error: {err.get('message', 'Unknown')}")
                print(f"   Code: {err.get('errorId', 'N/A')}")
    else:
        print("❌ No response from bulk create")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
