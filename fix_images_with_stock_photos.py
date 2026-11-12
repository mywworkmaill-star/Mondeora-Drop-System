"""
STOK GÖRSELLERLE LİSTİNG'LERİ GÜNCELLE
Unsplash'ten ücretsiz, telif hakkı olmayan görseller
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests

load_dotenv()

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("LİSTİNG GÖRSELLERİNİ GÜNCELLEME - STOK GÖRSELLER")
print("="*70)

# Her ürün için uygun stok görseller (Unsplash - telif hakkı serbest)
PRODUCT_IMAGES = {
    "SAFE-PET-001": {  # Hunde Spielzeug
        "name": "Hunde Spielzeug Set",
        "images": [
            "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800",  # Dog toy
            "https://images.unsplash.com/photo-1623387641168-d9803ddd3f35?w=800",  # Dog ball
            "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800",  # Dog playing
            "https://images.unsplash.com/photo-1534361960057-19889db9621e?w=800",  # Dog toys
            "https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=800"   # Pet toys
        ]
    },
    "SAFE-PET-002": {  # Katzen Spielzeug
        "name": "Katzen Spielzeug Set",
        "images": [
            "https://images.unsplash.com/photo-1574158622682-e40e69881006?w=800",  # Cat toy
            "https://images.unsplash.com/photo-1548366086-7f1b76106622?w=800",  # Cat playing
            "https://images.unsplash.com/photo-1529257414772-1960b7bea4eb?w=800",  # Cat with toy
            "https://images.unsplash.com/photo-1608848461950-0fe51dfc41cb?w=800",  # Cat toys
            "https://images.unsplash.com/photo-1573865526739-10c1d3a1f0cc?w=800"   # Playful cat
        ]
    },
    "SAFE-PET-003": {  # Hunde Napf
        "name": "Hunde Napf Set",
        "images": [
            "https://images.unsplash.com/photo-1589924691995-400dc9ecc119?w=800",  # Dog bowl
            "https://images.unsplash.com/photo-1516734212186-a967f81ad0d7?w=800",  # Pet bowls
            "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800",  # Dog eating
            "https://images.unsplash.com/photo-1568393691622-c7ba131d63b4?w=800",  # Pet food
            "https://images.unsplash.com/photo-1444212477490-ca407925329e?w=800"   # Dog dish
        ]
    }
}

updated = 0

for sku, data in PRODUCT_IMAGES.items():
    print(f"\n{'='*70}")
    print(f"{data['name']}")
    print(f"{'='*70}")
    
    try:
        print(f"\n1. Mevcut item alınıyor...")
        
        inv_get = requests.get(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Language': 'de-DE'
            }, timeout=30
        )
        
        if inv_get.status_code == 200:
            inv_data = inv_get.json()
            
            print(f"   ✅ Item bulundu")
            print(f"\n2. Görseller güncelleniyor...")
            print(f"   Yeni görseller: {len(data['images'])}")
            
            for i, img in enumerate(data['images'], 1):
                print(f"      {i}. {img[:50]}...")
            
            # Görselleri değiştir
            inv_data['product']['imageUrls'] = data['images']
            
            # Güncelle
            inv_update = requests.put(
                f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                    'Content-Language': 'de-DE'
                },
                json=inv_data, timeout=30
            )
            
            if inv_update.status_code in [200, 204]:
                print(f"\n   ✅ Görseller başarıyla güncellendi!")
                updated += 1
            else:
                print(f"\n   ⚠️  Güncelleme: {inv_update.status_code}")
                print(f"   {inv_update.text[:200]}")
        else:
            print(f"   ⚠️  Item bulunamadı: {inv_get.status_code}")
            
    except Exception as e:
        print(f"\n❌ Hata: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 Güncellenen: {updated}/3 listing")

if updated > 0:
    print(f"\n🎨 GÖRSELLER DEĞİŞTİRİLDİ!")
    print(f"   ✅ Hunde Spielzeug → Köpek oyuncak görselleri")
    print(f"   ✅ Katzen Spielzeug → Kedi oyuncak görselleri")
    print(f"   ✅ Hunde Napf → Köpek mama kabı görselleri")
    
    print(f"\n📋 eBay'de kontrol et (1-2 dakika sonra):")
    print(f"   • https://www.ebay.de/itm/860125501727")
    print(f"   • https://www.ebay.de/itm/860125507647")
    print(f"   • https://www.ebay.de/itm/860125507728")
    
    print(f"\n⏳ eBay cache güncellenmesi 1-2 dakika sürer")
