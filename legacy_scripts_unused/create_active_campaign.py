import sys
sys.path.insert(0, 'src')
import requests
import json
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

print('🚀 YENİ RUNNING CAMPAIGN OLUŞTURMA:\n')
print('=' * 70)

token = os.getenv('EBAY_ACCESS_TOKEN')

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

# Şimdi (UTC)
now = datetime.utcnow()
start_date = now.strftime('%Y-%m-%dT%H:%M:%S.000Z')
timestamp = now.strftime('%Y%m%d_%H%M%S')

# BASİT campaign
campaign_data = {
    'campaignName': f'Auto Pet Listings {timestamp}',
    'startDate': start_date,
    'fundingStrategy': {
        'fundingModel': 'COST_PER_SALE',
        'bidPercentage': '5.0'
    },
    'marketplaceId': 'EBAY_DE'
}

print(f'Campaign Name: {campaign_data["campaignName"]}')
print(f'Start Date: {start_date}')
print(f'Funding: COST_PER_SALE @ 5%')
print(f'Marketplace: EBAY_DE\n')

url = 'https://api.ebay.com/sell/marketing/v1/ad_campaign'
resp = requests.post(url, headers=headers, json=campaign_data, timeout=30)

print(f'Response Status: {resp.status_code}')
print(f'Response Headers: {dict(resp.headers)}')
print(f'Response Body: {resp.text[:500]}')

if resp.status_code == 201:
    # Campaign ID genellikle Location header'da olur
    location = resp.headers.get('Location', '')
    if location:
        # Location: .../ad_campaign/123456789012
        campaign_id = location.split('/')[-1]
        print(f'\nCampaign ID from Location header: {campaign_id}')
    elif resp.text:
        result = resp.json()
        campaign_id = result.get('campaignId')
    else:
        print('\n❌ Campaign ID bulunamadı!')
        campaign_id = None
    
    if not campaign_id:
        print('Response boş, campaign ID çıkarılamadı')
        sys.exit(1)
    
    print(f'\n✅ CAMPAIGN BAŞARIY LA OLUŞTURULDU!\n')
    print(f'Campaign ID: {campaign_id}')
    
    # .env'e kaydet
    with open('.env', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    found = False
    for i, line in enumerate(lines):
        if line.startswith('ACTIVE_CAMPAIGN_ID='):
            lines[i] = f'ACTIVE_CAMPAIGN_ID={campaign_id}\n'
            found = True
            break
    
    if not found:
        lines.append(f'\nACTIVE_CAMPAIGN_ID={campaign_id}\n')
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f'✅ .env güncellendi')
    
    # Test: Ad ekle
    print(f'\n{"="*70}')
    print(f'\n🧪 TEST: Ad Ekleme\n')
    
    test_listing = '860125869925'
    ad_url = f'https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad'
    ad_payload = {
        'listingId': test_listing,
        'bidPercentage': '5.0'
    }
    
    print(f'Listing ID: {test_listing}')
    ad_resp = requests.post(ad_url, headers=headers, json=ad_payload, timeout=30)
    print(f'Status: {ad_resp.status_code}')
    
    if ad_resp.status_code == 201:
        ad_data = ad_resp.json()
        ad_id = ad_data.get('adId')
        print(f'\n✅ AD BAŞARIY LA EKLENDİ!')
        print(f'Ad ID: {ad_id}')
        print(f'\n🎉 SİSTEM %100 ÇALIŞIYOR!')
    else:
        ad_errors = ad_resp.json().get('errors', [])
        for error in ad_errors:
            print(f'❌ Error {error.get("errorId")}: {error.get("message")}')
else:
    print(f'\n❌ Campaign oluşturulamadı!')
    errors = resp.json().get('errors', [])
    for error in errors:
        error_id = error.get('errorId')
        message = error.get('message')
        long_message = error.get('longMessage', '')
        print(f'\nError {error_id}: {message}')
        if long_message:
            print(f'Details: {long_message}')
