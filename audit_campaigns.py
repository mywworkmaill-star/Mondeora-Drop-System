"""
Campaign Audit - Check all eBay listings for active campaigns
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
from tracking.campaign_tracker import CampaignTracker
import sqlite3
import json
import time
from datetime import datetime

def audit_all_campaigns():
    """Audit all listings for eBay campaigns"""
    
    print('=' * 80)
    print('CAMPAIGN AUDIT - ALL LISTINGS')
    print('=' * 80)
    print()
    
    # Connect to database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # Get all listed products
    cursor.execute('''
        SELECT id, title, ebay_item_id, ebay_offer_id,
               aliexpress_product_id, campaign_name, fee_waived
        FROM products
        WHERE is_listed = 1
        ORDER BY id
    ''')
    
    products = cursor.fetchall()
    
    print(f'Found {len(products)} listed products')
    print()
    
    # Statistics
    stats = {
        'total': len(products),
        'already_tracked': 0,
        'new_campaigns': 0,
        'no_campaign': 0,
        'errors': 0,
        'campaigns_found': []
    }
    
    ebay = eBayAPIClient()
    tracker = CampaignTracker()
    
    for idx, (pid, title, item_id, offer_id, ali_id, existing_campaign, fee_waived) in enumerate(products, 1):
        
        print(f'[{idx}/{stats["total"]}] ID {pid}: {title[:40]}...')
        
        if existing_campaign:
            print(f'  ✓ Already tracked: {existing_campaign} (fee_waived={fee_waived})')
            stats['already_tracked'] += 1
            continue
        
        try:
            sku = f'AE{ali_id}'
            
            # Get inventory item (this may have warnings)
            response = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            
            # Parse for campaigns
            campaigns = tracker.parse_ebay_response({'data': response})
            
            if campaigns:
                # Found campaign!
                db_data = tracker.format_for_database()
                
                print(f'  ✅ CAMPAIGN FOUND: {db_data["campaign_name"]}')
                print(f'     Fee Waived: {db_data["fee_waived"]}')
                print(f'     Promotion: {db_data["promotion_id"]}')
                
                # Update database
                cursor.execute('''
                    UPDATE products
                    SET campaign_name = ?,
                        fee_waived = ?,
                        promotion_id = ?
                    WHERE id = ?
                ''', (db_data['campaign_name'], db_data['fee_waived'], db_data['promotion_id'], pid))
                
                conn.commit()
                
                stats['new_campaigns'] += 1
                stats['campaigns_found'].append({
                    'id': pid,
                    'title': title,
                    'campaign': db_data['campaign_name']
                })
                
            else:
                print(f'  - No campaign detected')
                stats['no_campaign'] += 1
            
        except Exception as e:
            print(f'  ⚠️  Error: {str(e)[:60]}')
            stats['errors'] += 1
        
        print()
        time.sleep(1)  # Rate limiting
    
    conn.close()
    
    # Print summary
    print('=' * 80)
    print('CAMPAIGN AUDIT SUMMARY')
    print('=' * 80)
    print()
    print(f'Total Listings:        {stats["total"]}')
    print(f'Already Tracked:       {stats["already_tracked"]}')
    print(f'New Campaigns Found:   {stats["new_campaigns"]}')
    print(f'No Campaign:           {stats["no_campaign"]}')
    print(f'Errors:                {stats["errors"]}')
    print()
    
    if stats['campaigns_found']:
        print('NEW CAMPAIGNS DETECTED:')
        for c in stats['campaigns_found']:
            print(f'  ID {c["id"]}: {c["campaign"]} - {c["title"][:50]}')
        print()
    
    total_tracked = stats['already_tracked'] + stats['new_campaigns']
    print(f'TOTAL CAMPAIGNS TRACKED: {total_tracked}/{stats["total"]} ({total_tracked/stats["total"]*100:.1f}%)')
    
    # Estimated savings
    if total_tracked > 0:
        estimated_savings = total_tracked * 4  # ~€4 per listing
        print(f'ESTIMATED SAVINGS: €{estimated_savings:.2f}')
    
    print('=' * 80)
    
    return stats


if __name__ == '__main__':
    start_time = datetime.now()
    
    print()
    print('Starting campaign audit...')
    print(f'Time: {start_time}')
    print()
    
    stats = audit_all_campaigns()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print(f'Completed in {duration:.1f} seconds ({duration/60:.1f} minutes)')
    print()
