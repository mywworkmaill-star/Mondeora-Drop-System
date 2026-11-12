import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests

load_dotenv()

access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("EBAY LISTING GUNCELLENIYOR - PROFESYONEL FOTOGRAFLAR")
print("="*70)

# PROFESYONEL İPHONE KILIF FOTOGRAFLARI
# Unsplash (ücretsiz, yüksek kalite, ticari kullanım izinli)
professional_images = [
    # iPhone kılıf fotoğrafları - gerçek, profesyonel
    'https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1574944985070-8f3ebc6b79d2?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1556656793-08538906a9f8?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1603891219772-c39afc4c4cc9?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1592286927505-38b37258b7e0?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1585060544812-6b45742d762f?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1580910051074-3eb694886505?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1616348436168-de43ad0db179?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1551816230-ef5deaed4a26?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1585239915416-c17c4e5eef53?w=1600&h=1600&fit=crop&q=90',
    'https://images.unsplash.com/photo-1605236453806-6ff36851218e?w=1600&h=1600&fit=crop&q=90'
]

sku = 'PREMIUM-IPHONE-CAMERA-CASE-001'

try:
    print(f"\nSKU: {sku}")
    print(f"Fotograf sayisi: {len(professional_images)}")
    
    # 1. Mevcut item'ı al
    print(f"\n1. Mevcut listing aliniyor...")
    
    inv_get = requests.get(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }, timeout=30
    )
    
    if inv_get.status_code == 200:
        current_item = inv_get.json()
        print(f"   OK - Listing bulundu")
        
        # 2. Fotoğrafları güncelle
        print(f"\n2. Fotograflar guncelleniyor...")
        current_item['product']['imageUrls'] = professional_images
        
        inv_update = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=current_item, timeout=30
        )
        
        if inv_update.status_code in [200, 204]:
            print(f"   OK - {len(professional_images)} fotograf yuklendi!")
            
            print(f"\n" + "="*70)
            print(f"BASARILI! FOTOGRAFLAR GUNCELLENDI")
            print(f"="*70)
            
            print(f"\neBay Listing: https://www.ebay.de/itm/860123929318")
            print(f"\nYeni fotograflar:")
            for i, img in enumerate(professional_images[:5], 1):
                print(f"  {i}. {img[:60]}...")
            print(f"  ... ve {len(professional_images)-5} tane daha")
            
            print(f"\n✅ Toplam {len(professional_images)} profesyonel fotograf eklendi!")
            print(f"✅ Tum fotograflar yuksek cozunurluk (1600x1600)")
            print(f"✅ Unsplash kaynaklı - ticari kullanım izinli")
            
        else:
            print(f"   HATA: {inv_update.status_code}")
            print(f"   {inv_update.text[:500]}")
    else:
        print(f"   HATA: Listing bulunamadi - {inv_get.status_code}")
        print(f"   {inv_get.text[:300]}")

except Exception as e:
    print(f"\nHATA: {str(e)}")
    import traceback
    traceback.print_exc()
