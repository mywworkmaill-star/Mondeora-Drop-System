"""
Campaign Tracker for eBay Listings
Monitors and records fee waivers, promotions, and campaigns
"""

import re
from datetime import datetime

class CampaignTracker:
    """Track eBay campaigns and fee waivers"""
    
    # Known campaign patterns from API warnings/errors
    CAMPAIGN_PATTERNS = {
        25072: {
            'name': 'Verkaufsprovision erlassen',
            'type': 'FEE_WAIVER',
            'benefit': 'Final value fee waived',
            'fee_waived': True
        },
        25402: {
            'name': 'Payment Hold',
            'type': 'PAYMENT_HOLD',
            'benefit': 'Normal for new sellers',
            'fee_waived': False
        }
    }
    
    def __init__(self):
        self.detected_campaigns = []
    
    def parse_ebay_response(self, response):
        """Parse eBay API response for campaign indicators"""
        
        campaigns = []
        
        # Check for warnings (common place for campaign info)
        if 'warnings' in response:
            for warning in response['warnings']:
                error_id = warning.get('errorId')
                
                if error_id in self.CAMPAIGN_PATTERNS:
                    campaign = self.CAMPAIGN_PATTERNS[error_id].copy()
                    campaign['detected_at'] = datetime.now().isoformat()
                    campaign['raw_message'] = warning.get('message', '')
                    campaigns.append(campaign)
        
        # Check for explicit promotional fields
        if 'promotions' in response:
            for promo in response['promotions']:
                campaigns.append({
                    'name': promo.get('name', 'Unknown'),
                    'type': 'PROMOTION',
                    'promotion_id': promo.get('promotionId'),
                    'fee_waived': True,
                    'detected_at': datetime.now().isoformat()
                })
        
        self.detected_campaigns.extend(campaigns)
        return campaigns
    
    def get_campaign_summary(self):
        """Get summary of detected campaigns"""
        
        if not self.detected_campaigns:
            return {
                'active': False,
                'count': 0,
                'fee_waived': False
            }
        
        fee_waived = any(c.get('fee_waived', False) for c in self.detected_campaigns)
        
        return {
            'active': True,
            'count': len(self.detected_campaigns),
            'fee_waived': fee_waived,
            'campaigns': self.detected_campaigns
        }
    
    def format_for_database(self):
        """Format campaign data for database storage"""
        
        if not self.detected_campaigns:
            return {
                'campaign_name': None,
                'fee_waived': 0,
                'promotion_id': None
            }
        
        # Use first detected campaign
        primary = self.detected_campaigns[0]
        
        return {
            'campaign_name': primary.get('name'),
            'fee_waived': 1 if primary.get('fee_waived', False) else 0,
            'promotion_id': primary.get('promotion_id', f"ERROR_{primary.get('error_id', 'UNKNOWN')}")
        }


# Example usage
if __name__ == '__main__':
    
    tracker = CampaignTracker()
    
    # Simulate eBay API response with Warning 25072
    mock_response = {
        'warnings': [
            {
                'errorId': 25072,
                'domain': 'API_INVENTORY',
                'message': 'Verkaufsprovision erlassen.'
            }
        ]
    }
    
    campaigns = tracker.parse_ebay_response(mock_response)
    
    print('Detected Campaigns:')
    for camp in campaigns:
        print(f"  - {camp['name']}")
        print(f"    Type: {camp['type']}")
        print(f"    Fee Waived: {camp['fee_waived']}")
        print()
    
    summary = tracker.get_campaign_summary()
    print('Summary:')
    print(f"  Active: {summary['active']}")
    print(f"  Count: {summary['count']}")
    print(f"  Fee Waived: {summary['fee_waived']}")
    print()
    
    db_format = tracker.format_for_database()
    print('Database Format:')
    print(f"  campaign_name: {db_format['campaign_name']}")
    print(f"  fee_waived: {db_format['fee_waived']}")
    print(f"  promotion_id: {db_format['promotion_id']}")
