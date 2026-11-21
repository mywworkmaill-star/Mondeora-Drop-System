#!/usr/bin/env python3
"""eBay Promoted Listings & Ranking Check"""

import sys
sys.path.insert(0, '.')

from src.api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime

def check_promoted_ads():
    """Check Promoted Listings campaign status"""
    ebay = eBayAPIClient()
    
    print('━' * 80)
    print('📢 PROMOTED LISTINGS STATUS')
    print('━' * 80)
    
    try:
        # Get all campaigns
        response = ebay._request('GET', '/sell/marketing/v1/ad_campaign')
        campaigns = response.get('campaigns', [])
        
        if not campaigns:
            print('\n⚠️  HATA: Hiç Promoted Listings kampanyası yok!')
            print('   Tüm ilanların 0 görüntüleme almasının ana nedeni bu olabilir.')
            return
        
        for campaign in campaigns:
            campaign_id = campaign.get('campaignId')
            name = campaign.get('campaignName')
            status = campaign.get('campaignStatus')
            funding = campaign.get('fundingStrategy', {}).get('fundingModel')
            
            print(f'\n📣 Kampanya: {name}')
            print(f'   ID: {campaign_id}')
            print(f'   Durum: {status}')
            print(f'   Funding: {funding}')
            
            # Get ads in campaign
            try:
                ads_response = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad')
                ads = ads_response.get('ads', [])
                
                active_ads = [a for a in ads if a.get('adStatus') == 'ACTIVE']
                
                print(f'   Toplam reklam: {len(ads)}')
                print(f'   Aktif reklam: {len(active_ads)}')
                
                if active_ads:
                    bids = [float(a.get('bidPercentage', 0)) for a in active_ads]
                    avg_bid = sum(bids) / len(bids) if bids else 0
                    print(f'   Ortalama bid: %{avg_bid:.1f}')
                    
                    # Check if any have 0 bid
                    zero_bid = [a for a in active_ads if float(a.get('bidPercentage', 0)) == 0]
                    if zero_bid:
                        print(f'   ⚠️  {len(zero_bid)} ilan 0% bid ile (görünmez!)')
                
            except Exception as e:
                print(f'   ⚠️  Reklam detayları alınamadı: {str(e)[:100]}')
        
        # Check which products are in ads
        conn = sqlite3.connect('data/dropshipping.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM products WHERE is_listed=1')
        total_listed = c.fetchone()[0]
        
        # Get all inventory items
        try:
            all_items = []
            offset = 0
            while True:
                inv_response = ebay._request('GET', '/sell/inventory/v1/inventory_item', 
                                            params={'limit': 100, 'offset': offset})
                items = inv_response.get('inventoryItems', [])
                if not items:
                    break
                all_items.extend(items)
                offset += 100
            
            # Check which have ads
            items_with_ads = 0
            for item in all_items:
                sku = item.get('sku')
                # Try to find ad for this SKU
                for campaign in campaigns:
                    try:
                        campaign_id = campaign.get('campaignId')
                        ad_check = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad',
                                                params={'inventory_reference_id': sku, 'inventory_reference_type': 'INVENTORY_ITEM'})
                        if ad_check.get('ads'):
                            items_with_ads += 1
                            break
                    except:
                        pass
            
            print(f'\n📊 Reklam Kapsama:')
            print(f'   Toplam listing: {total_listed}')
            print(f'   Reklamı olan: {items_with_ads}')
            print(f'   Reklamı olmayan: {total_listed - items_with_ads}')
            
            if items_with_ads < total_listed:
                print(f'\n   ⚠️  {total_listed - items_with_ads} ilan reklam almıyor!')
        
        except Exception as e:
            print(f'\n⚠️  Reklam kapsama analizi başarısız: {str(e)[:100]}')
        
        conn.close()
        
    except Exception as e:
        print(f'\n❌ HATA: Promoted Listings API erişilemedi')
        print(f'   Detay: {str(e)[:200]}')
        print(f'\n   Bu, ilanların 0 traffic almasının ana nedeni olabilir!')
    
    print('\n' + '━' * 80)

if __name__ == '__main__':
    check_promoted_ads()
