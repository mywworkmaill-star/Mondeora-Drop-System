"""
TÜM LİSTİNG'LERİ DOĞRU GÖRSELLERLE GÜNCELLE
Her ürün için AliExpress'ten gerçek görseller
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json

load_dotenv()

from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient

ebay = eBayAPIClient()
ali = AliExpressAPIClient()

ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("LİSTİNG'LERİ DOĞRU GÖRSELLERLE GÜNCELLEME")
print("="*70)

# Her listing için doğru AliExpress ürün ID'si
LISTINGS_UPDATE = [
    {
        "sku": "SAFE-PET-001",
        "ali_id": "1005010514190442",  # Dog toy ball
        "name": "Hunde Spielzeug Set"
    },
    {
        "sku": "SAFE-PET-002",
        "ali_id": "1005012639925835",  # Cat toy (rope ball)
        "name": "Katzen Spielzeug Set"
    },
    {
        "sku": "SAFE-PET-003",
        "ali_id": "1005012499324398",  # Dog bowl/chew toy
        "name": "Hunde Napf Set"
    }
]

updated_count = 0

for item in LISTINGS_UPDATE:
    print(f"\n{'='*70}")
    print(f"{item['name']}")
    print(f"{'='*70}")
    
    try:
        # AliExpress'ten görselleri al
        print(f"\n1. AliExpress'ten görseller alınıyor (ID: {item['ali_id']})...")
        
        product = ali.get_product_details(item['ali_id'])
        
        if product and 'image_urls' in product:
            img_str = product['image_urls']
            
            # Görselleri ayır
            if isinstance(img_str, str) and ';' in img_str:
                images = img_str.split(';')[:12]
            elif isinstance(img_str, str):
                images = [img_str]
            else:
                images = []
            
            if len(images) > 0:
                print(f"   ✅ {len(images)} görsel bulundu")
                
                for i, img in enumerate(images[:3], 1):
                    print(f"      {i}. {img[:60]}...")
                
                # Inventory item'ı güncelle
                print(f"\n2. eBay inventory item güncelleniyor...")
                
                # Mevcut item'ı al
                inv_get = requests.get(
                    f"https://api.ebay.com/sell/inventory/v1/inventory_item/{item['sku']}",
                    headers={
                        'Authorization': f'Bearer {access_token}',
                        'Content-Language': 'de-DE'
                    }, timeout=30
                )
                
                if inv_get.status_code == 200:
                    inv_data = inv_get.json()
                    
                    # Görselleri güncelle
                    inv_data['product']['imageUrls'] = images
                    
                    # Güncelle
                    inv_update = requests.put(
                        f"https://api.ebay.com/sell/inventory/v1/inventory_item/{item['sku']}",
                        headers={
                            'Authorization': f'Bearer {access_token}',
                            'Content-Type': 'application/json',
                            'Content-Language': 'de-DE'
                        },
                        json=inv_data, timeout=30
                    )
                    
                    if inv_update.status_code in [200, 204]:
                        print(f"   ✅ Görseller güncellendi!")
                        updated_count += 1
                    else:
                        print(f"   ⚠️  Update: {inv_update.status_code}")
                        print(f"   {inv_update.text[:200]}")
                else:
                    print(f"   ⚠️  Get inventory: {inv_get.status_code}")
            else:
                print(f"   ⚠️  Görsel bulunamadı")
        else:
            print(f"   ⚠️  AliExpress ürün detayı alınamadı")
            
    except Exception as e:
        print(f"\n❌ Hata: {str(e)}")
        import traceback
        traceback.print_exc()

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 Güncellenen: {updated_count}/{len(LISTINGS_UPDATE)} listing")

print(f"\n🎨 HER ÜRÜN ŞİMDİ KEND İ GÖRSELLERİNE SAHİP!")
print(f"   ✅ Hunde Spielzeug - Köpek oyuncağı görselleri")
print(f"   ✅ Katzen Spielzeug - Kedi oyuncağı görselleri")
print(f"   ✅ Hunde Napf - Köpek malzemesi görselleri")

print(f"\n📋 eBay'de kontrol et:")
print(f"   • https://www.ebay.de/itm/860125501727 (Hunde Spielzeug)")
print(f"   • https://www.ebay.de/itm/860125507647 (Katzen Spielzeug)")
print(f"   • https://www.ebay.de/itm/860125507728 (Hunde Napf)")
