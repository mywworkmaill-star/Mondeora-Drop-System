"""
ORCHESTRA v5.1 - COMPREHENSIVE SPEC EXTRACTION + PROMOTED LISTINGS

NEW FEATURE: Step 9 - Automatic eBay Promoted Listings (Ads)
After publishing, automatically creates ad campaign and promotes listing

Changes:
- Added Step 9: Promoted Listings
- Marketing API integration
- Campaign auto-creation if not exists
- Suggested bid rate usage
- Ad verification

🚨 CRITICAL RULE - SPEC ACCURACY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ USE ONLY 100% CERTAIN SPECS (Confidence ≥95%)
❌ IF NOT 100% SURE → DO NOT USE (FORBIDDEN!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BETTER TO OMIT THAN TO BE WRONG!
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
import sqlite3
import json
import time
import os
from datetime import datetime

ali = AliExpressAPIClient()
ebay = eBayAPIClient()

class OrchestraV51Ads:
    """Orchestra v5.1 - Comprehensive Spec Extraction + Promoted Listings"""
    
    def __init__(self):
        self.conn = sqlite3.connect('data/dropshipping.db')
        self.cursor = self.conn.cursor()
        self.log = []
        self.comprehensive_specs = None
        self.campaign_id = None  # Will be set in step 9
        
    def close(self):
        self.conn.close()
    
    def log_step(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        self.log.append(log_line)
        print(log_line)
    
    # ... (keeping all existing methods from v5.0) ...
    # step_1_select_product()
    # step_2_update_images()
    # step_4_comprehensive_spec_extraction()
    # _filter_verified_specs()
    # _log_found_specs()
    # step_5_competitor_pricing()
    # step_6_create_comprehensive_description()
    # step_7_publish_with_comprehensive_aspects()
    # step_8_update_database()
    
    def step_9_create_promoted_listing(self, product, listing_id):
        """
        Step 9: Create eBay Promoted Listing (Ad Campaign)
        
        NEW IN v5.1: Automatically promotes listing after publish
        """
        self.log_step('=' * 80)
        self.log_step('STEP 9: PROMOTED LISTINGS (REKLAM KAMPANYASI)')
        self.log_step('=' * 80)
        
        self.log_step(f'Listing ID: {listing_id}')
        self.log_step('')
        
        try:
            # Step 9.1: Get or create campaign
            campaign = self._get_or_create_campaign()
            
            if not campaign:
                self.log_step('⚠️  Kampanya oluşturulamadı, reklam atlanıyor')
                self.log_step('')
                return None
            
            self.campaign_id = campaign['campaign_id']
            self.log_step(f"✅ Kampanya: {campaign['campaign_name']}")
            self.log_step(f"   Campaign ID: {self.campaign_id}")
            self.log_step(f"   Status: {campaign['status']}")
            self.log_step('')
            
            # Step 9.2: Get suggested bid rate
            suggested_bid = self._get_suggested_bid_rate(listing_id)
            
            if suggested_bid:
                bid_rate = suggested_bid
                self.log_step(f"✅ Suggested bid rate: {bid_rate}%")
            else:
                bid_rate = 8.0  # Default safe rate
                self.log_step(f"⚠️  Suggested bid unavailable, using default: {bid_rate}%")
            
            self.log_step('')
            
            # Step 9.3: Add listing to campaign
            ad_created = self._add_listing_to_campaign(listing_id, bid_rate)
            
            if ad_created:
                self.log_step(f"✅ Reklam oluşturuldu!")
                self.log_step(f"   Listing: {listing_id}")
                self.log_step(f"   Bid Rate: {bid_rate}%")
                self.log_step(f"   Campaign: {campaign['campaign_name']}")
                self.log_step('')
                
                # Update database with ad info
                self.cursor.execute('''
                    UPDATE products
                    SET ad_campaign_id = ?,
                        ad_bid_rate = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                ''', (self.campaign_id, bid_rate, product['id']))
                
                self.conn.commit()
                
                return {
                    'campaign_id': self.campaign_id,
                    'campaign_name': campaign['campaign_name'],
                    'ad_id': ad_created.get('ad_id'),
                    'bid_rate': bid_rate
                }
            else:
                self.log_step('❌ Reklam oluşturulamadı')
                self.log_step('')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Promoted listing error: {str(e)}')
            self.log_step('')
            return None
    
    def _get_or_create_campaign(self):
        """Get existing campaign or create new one"""
        
        self.log_step('Checking existing campaigns...')
        
        try:
            # Get campaigns
            response = ebay._request('GET', '/sell/marketing/v1/ad_campaign?campaign_status=RUNNING')
            
            campaigns = response.get('campaigns', [])
            
            self.log_step(f'Found {len(campaigns)} RUNNING campaign(s)')
            
            # Look for Mondeora campaign
            for campaign in campaigns:
                name = campaign.get('campaignName', '')
                if 'Mondeora' in name or 'Auto' in name:
                    return {
                        'campaign_id': campaign.get('campaignId'),
                        'campaign_name': name,
                        'status': campaign.get('campaignStatus')
                    }
            
            # No existing campaign, create one
            self.log_step('No Mondeora campaign found, creating new...')
            
            return self._create_new_campaign()
            
        except Exception as e:
            self.log_step(f'Error getting campaigns: {str(e)}')
            
            # Try to create new campaign
            return self._create_new_campaign()
    
    def _create_new_campaign(self):
        """Create new Promoted Listings campaign"""
        
        self.log_step('Creating new campaign: "Mondeora Auto Campaign"')
        
        campaign_data = {
            'campaignName': f'Mondeora Auto Campaign {datetime.now().strftime("%Y-%m")}',
            'marketplaceId': 'EBAY_DE',
            'fundingStrategy': {
                'fundingModel': 'COST_PER_SALE',
                'bidPercentage': '8.0'  # Default 8% for campaign
            },
            'startDate': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        try:
            response = ebay._request('POST', '/sell/marketing/v1/ad_campaign', json=campaign_data)
            
            campaign_id = response.get('campaignId')
            
            if campaign_id:
                self.log_step(f'✅ Campaign created: {campaign_id}')
                
                return {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign_data['campaignName'],
                    'status': 'RUNNING'
                }
            else:
                self.log_step('❌ Campaign creation failed (no ID returned)')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Campaign creation error: {str(e)}')
            return None
    
    def _get_suggested_bid_rate(self, listing_id):
        """Get eBay suggested bid rate for listing"""
        
        self.log_step(f'Getting suggested bid rate for {listing_id}...')
        
        try:
            # Try suggested bid API
            response = ebay._request(
                'GET',
                f'/sell/marketing/v1/ad_campaign_suggested_bid?marketplace_id=EBAY_DE&listing_ids={listing_id}'
            )
            
            suggestions = response.get('suggestions', [])
            
            if suggestions and len(suggestions) > 0:
                suggested = suggestions[0].get('suggestedBidPercentage')
                
                if suggested:
                    # Parse suggested rate
                    rate = float(suggested)
                    
                    # Cap between 2.0 and 20.0 for safety
                    if rate < 2.0:
                        rate = 2.0
                    elif rate > 20.0:
                        rate = 20.0
                    
                    return round(rate, 1)
            
            return None
            
        except Exception as e:
            self.log_step(f'⚠️  Suggested bid unavailable: {str(e)}')
            return None
    
    def _add_listing_to_campaign(self, listing_id, bid_rate):
        """Add listing to campaign as promoted ad"""
        
        self.log_step(f'Adding listing {listing_id} to campaign...')
        
        # Format bid rate as string with 1 decimal
        bid_str = f"{bid_rate:.1f}"
        
        request_data = {
            'requests': [
                {
                    'listingId': listing_id,
                    'bidPercentage': bid_str  # MUST be string with 1 decimal
                }
            ]
        }
        
        try:
            response = ebay._request(
                'POST',
                f'/sell/marketing/v1/ad_campaign/{self.campaign_id}/bulk_create_ads_by_listing_id',
                json=request_data
            )
            
            # Check responses
            responses = response.get('responses', [])
            
            if responses and len(responses) > 0:
                first = responses[0]
                status_code = first.get('statusCode')
                
                if status_code == 201:
                    # Success!
                    return {
                        'ad_id': first.get('adId'),
                        'listing_id': first.get('listingId'),
                        'status': 'ACTIVE'
                    }
                else:
                    self.log_step(f'❌ Ad creation failed: HTTP {status_code}')
                    errors = first.get('errors', [])
                    for err in errors:
                        self.log_step(f'   Error: {err.get("message", "Unknown")}')
                    return None
            else:
                self.log_step('❌ No response from bulk create')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Add listing error: {str(e)}')
            return None
    
    def run(self):
        """Full v5.1 workflow with Promoted Listings"""
        self.log_step('╔══════════════════════════════════════════════════════════════════════╗')
        self.log_step('║      ORCHESTRA v5.1 - COMPREHENSIVE SPECS + PROMOTED LISTINGS      ║')
        self.log_step('╚══════════════════════════════════════════════════════════════════════╝')
        self.log_step('')
        
        start_time = time.time()
        
        # Steps 1-8 same as v5.0
        # (Product selection, images, specs, pricing, description, publish, DB update)
        
        # For now, simplified version - will integrate full v5.0 later
        self.log_step('⚠️  v5.1 FRAMEWORK - Full integration pending')
        self.log_step('   Step 9 (Promoted Listings) can be tested standalone')
        self.log_step('')
        
        return None

# Main
if __name__ == '__main__':
    orchestra = OrchestraV51Ads()
    
    try:
        result = orchestra.run()
        
        if result:
            print()
            print('✅ SUCCESS - WITH PROMOTED LISTINGS!')
        else:
            print('⚠️  Framework created - full integration pending')
            
    finally:
        orchestra.close()
