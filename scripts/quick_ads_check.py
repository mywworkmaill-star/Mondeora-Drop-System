#!/usr/bin/env python3
"""Quick eBay Ads Check"""

import sys
sys.path.insert(0, '.')

from src.api.ebay_client import eBayAPIClient

def quick_ads_check():
    ebay = eBayAPIClient()
    
    print('━' * 80)
    print('📢 PROMOTED LISTINGS - HIZLI KONTROL')
    print('━' * 80)
    
    try:
        # Get campaigns
        response = ebay._request('GET', '/sell/marketing/v1/ad_campaign')
        campaigns = response.get('campaigns', [])
        
        print(f'\n📊 Toplam kampanya: {len(campaigns)}')
        
        if not campaigns:
            print('\n❌ KRITIK: Hiç Promoted Listings kampanyası yok!')
            print('   → Bu, 0 traffic\'in ana nedeni olabilir.')
            print('   → Çözüm: Tüm ilanlar için kampanya oluştur')
            return False
        
        total_ads = 0
        active_ads = 0
        
        for campaign in campaigns:
            cid = campaign.get('campaignId')
            name = campaign.get('campaignName')
            status = campaign.get('campaignStatus')
            
            print(f'\n📣 {name}')
            print(f'   Durum: {status}')
            
            try:
                ads_resp = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{cid}/ad', 
                                        params={'limit': 500})
                ads = ads_resp.get('ads', [])
                active = [a for a in ads if a.get('adStatus') == 'ACTIVE']
                
                total_ads += len(ads)
                active_ads += len(active)
                
                print(f'   Toplam reklam: {len(ads)}')
                print(f'   Aktif reklam: {len(active)}')
                
                if active:
                    bids = [float(a.get('bidPercentage', 0)) for a in active]
                    avg = sum(bids) / len(bids)
                    min_bid = min(bids)
                    max_bid = max(bids)
                    zero_count = sum(1 for b in bids if b == 0)
                    
                    print(f'   Bid aralığı: %{min_bid:.1f} - %{max_bid:.1f} (ort: %{avg:.1f})')
                    if zero_count > 0:
                        print(f'   ⚠️  {zero_count} reklam 0% bid (görünmez!)')
                
            except Exception as e:
                print(f'   ❌ Reklam listesi alınamadı: {str(e)[:80]}')
        
        print(f'\n📈 TOPLAM:')
        print(f'   Tüm reklamlar: {total_ads}')
        print(f'   Aktif reklamlar: {active_ads}')
        
        # Compare with DB
        import sqlite3
        conn = sqlite3.connect('data/dropshipping.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM products WHERE is_listed=1')
        total_listed = c.fetchone()[0]
        conn.close()
        
        print(f'\n   DB\'de listing: {total_listed}')
        
        if active_ads < total_listed:
            print(f'\n   ⚠️  {total_listed - active_ads} ilan reklamsız!')
            print(f'   → Bu ilanlar organik aramada çok düşük sıralamalıdır')
        
        print('\n' + '━' * 80)
        return True
        
    except Exception as e:
        print(f'\n❌ HATA: {str(e)[:150]}')
        return False

if __name__ == '__main__':
    quick_ads_check()
