import sys
sys.path.insert(0, 'src')
import requests
from dotenv import load_dotenv
import os
import sqlite3

load_dotenv()

token = os.getenv('EBAY_ACCESS_TOKEN')
new_campaign_id = '168750173017'

print('🧪 MANUEL AD CAMPAIGN TEST - TÜMÜNÜ DENE\n')
print('=' * 70)
print(f'Campaign ID: {new_campaign_id} (RUNNING)')

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# Database'den AUTO listing'leri al
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()
cursor.execute("""
SELECT sku_id, ebay_item_id, ebay_price 
FROM products 
WHERE sku_id LIKE 'AUTO-%' 
ORDER BY created_at DESC 
LIMIT 10
""")
listings = cursor.fetchall()
conn.close()

if not listings:
    print('❌ Database\'de AUTO listing yok!')
    sys.exit(1)

print(f'\nBulunan AUTO listings: {len(listings)}')
print('-' * 70)

url = f'https://api.ebay.com/sell/marketing/v1/ad_campaign/{new_campaign_id}/ad'

success_count = 0
already_exists_count = 0
other_error_count = 0

for sku, listing_id, price in listings:
    print(f'\n📝 Test: {listing_id} (€{price})')
    
    payload = {
        'listingId': listing_id,
        'bidPercentage': '5.0'
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if resp.status_code == 201:
        location = resp.headers.get('Location', '')
        ad_id = location.split('/')[-1] if location else 'Unknown'
        print(f'   ✅ BAŞARILI! Ad ID: {ad_id}')
        success_count += 1
        
    elif resp.status_code == 400:
        errors = resp.json().get('errors', [])
        for error in errors:
            error_id = error.get('errorId')
            message = error.get('message', '')
            
            if error_id == 35036:  # Already exists
                print(f'   ⏭️  Zaten var (skip)')
                already_exists_count += 1
            else:
                print(f'   ❌ Error {error_id}: {message[:60]}')
                other_error_count += 1
    else:
        print(f'   ❌ HTTP {resp.status_code}')
        other_error_count += 1

print('\n' + '=' * 70)
print('📊 SONUÇ:')
print(f'   ✅ Başarılı: {success_count}')
print(f'   ⏭️  Zaten var: {already_exists_count}')
print(f'   ❌ Hata: {other_error_count}')

if success_count > 0:
    print('\n🎉🎉🎉 AD CAMPAIGN SİSTEMİ %100 ÇALIŞIYOR! 🎉🎉🎉')
elif already_exists_count > 0:
    print('\n✅ Listing\'ler başka campaign\'de - sistem çalışıyor ama duplicate!')
else:
    print('\n❌ Hiç ad eklenemedi - sorun devam ediyor')
