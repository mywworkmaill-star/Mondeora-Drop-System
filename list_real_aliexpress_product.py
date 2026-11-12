"""
GERÇEK AliExpress ürününü eBay'e listele
Ürün ID: 1005013457960792
GERÇEK veriler: Browser + API'den
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json

load_dotenv()

# eBay token yenile
from api.ebay_client import eBayAPIClient
ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)

access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("GERÇEK AliExpress ÜRÜNÜ eBay'E LİSTELENİYOR")
print("="*70)

# GERÇEK ÜRÜN BİLGİLERİ (Browser + API'den)
aliexpress_id = "1005013457960792"
aliexpress_url = f"https://www.aliexpress.com/item/{aliexpress_id}.html"

# Browser'dan çekilen GERÇEK bilgiler
title_fr = "Coque imitation originale pour iPhone 18 17 Pro Max 16 15 14 13"
price_eur = "7.09"
sold_count = "68"

# API'den çekilen GERÇEK görsel
main_image = "https://ae01.alicdn.com/kf/S3fabe80037dd4c208954398406d63d77h.jpg"

# Almanca başlık (eBay.de için)
title_de = "Original Design iPhone Hülle 18 17 16 15 14 13 Pro Max Kamera Schutz Matt Case"

# GERÇEK fotoğraflar (API'den alınan ana görsel)
# Not: AliExpress API sadece ana görseli veriyor, daha fazlası için premium API gerek
real_images = [
    main_image,
]

print(f"\nAliExpress Ürün: {aliexpress_id}")
print(f"Gerçek Fiyat: €{price_eur}")
print(f"Satış: {sold_count}")
print(f"Gerçek Görsel: {len(real_images)} adet")

# eBay için SKU
sku = f'ALIEXP-{aliexpress_id}'

# HTML açıklama (kompakt)
html_description = f"""<div style="font-family:Arial;max-width:800px;margin:0 auto;color:#333">
<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px;text-align:center;border-radius:8px;margin-bottom:15px">
<h1 style="margin:0;font-size:22px">📱 Original Design iPhone Hülle</h1>
<p style="margin:8px 0 0">Matt Finish • Kamera Schutz • Stoßfest</p>
</div>
<div style="background:#f8f9fa;padding:18px;border-radius:8px;margin-bottom:15px">
<h2 style="color:#667eea;border-bottom:2px solid #667eea;padding-bottom:8px;margin-top:0">✨ Features</h2>
<ul style="line-height:1.8;margin:10px 0">
<li>🎯 <b>Kamera-Schutz:</b> Erhöhter Rand schützt Linse</li>
<li>💎 <b>Matt Finish:</b> Premium mattes Design</li>
<li>🧲 <b>Leicht & Dünn:</b> Nur 1mm dick</li>
<li>💪 <b>Stoßfest:</b> TPU Silikon Material</li>
<li>🌟 <b>Kratzfest:</b> Langlebiger Schutz</li>
</ul>
</div>
<div style="background:#e7f3ff;padding:18px;border-radius:8px;margin-bottom:15px">
<h2 style="color:#667eea;margin-top:0">📱 Kompatibel</h2>
<p style="margin:5px 0">iPhone 18, 17, 16, 15, 14, 13 - Pro Max, Pro, Plus</p>
</div>
<div style="background:#d4edda;padding:18px;border-radius:8px">
<h2 style="color:#28a745;margin-top:0">🚚 Versand & Garantie</h2>
<p style="margin:5px 0">✅ Versand in 24-48h<br>
✅ 30 Tage Rückgabe<br>
✅ Sichere Verpackung</p>
</div>
</div>"""

print(f"\neBay Başlık: {title_de}")
print(f"SKU: {sku}")

# Fiyat hesaplama (€7.09 alış)
aliexpress_cost = float(price_eur)
ebay_price = round(aliexpress_cost * 2.5, 2)  # 2.5x markup
print(f"eBay Fiyat: €{ebay_price}")

profit = ebay_price - aliexpress_cost - (ebay_price * 0.135)
print(f"Tahmini Kar: €{profit:.2f}")

try:
    # 1. Inventory Item oluştur
    print(f"\n1. Inventory item oluşturuluyor...")
    
    inventory_item = {
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 50
            }
        },
        "condition": "NEW",
        "product": {
            "title": title_de,
            "description": html_description,
            "imageUrls": real_images,  # GERÇEK görsel
            "aspects": {
                "Marke": ["Markenlos"],
                "Produktart": ["Stoßstange"],
                "Material": ["Silikon"],
                "Farbe": ["Schwarz"],
                "Besonderheiten": [
                    "Kameraschutz",
                    "Stoßfest",
                    "Kratzfest",
                    "Mattes Finish"
                ],
                "Kompatibles Modell": [
                    "Für Apple iPhone 18",
                    "Für Apple iPhone 17",
                    "Für Apple iPhone 16",
                    "Für Apple iPhone 15",
                    "Für Apple iPhone 14",
                    "Für Apple iPhone 13"
                ],
                "Design/Ausführung": ["Bumper"]
            }
        }
    }
    
    inv_create = requests.put(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=inventory_item, timeout=30
    )
    
    if inv_create.status_code in [200, 201, 204]:
        print(f"   ✅ Inventory item oluşturuldu")
    else:
        print(f"   ⚠️  {inv_create.status_code}: {inv_create.text[:300]}")
    
    # 2. Offer oluştur
    print(f"\n2. Offer oluşturuluyor...")
    
    offer_data = {
        "sku": sku,
        "marketplaceId": "EBAY_DE",
        "format": "FIXED_PRICE",
        "listingDuration": "GTC",
        "availableQuantity": 50,
        "categoryId": "20349",
        "listingPolicies": {
            "paymentPolicyId": "263035507017",
            "returnPolicyId": "263035512017",
            "fulfillmentPolicyId": "263035514017"
        },
        "pricingSummary": {
            "price": {
                "value": str(ebay_price),
                "currency": "EUR"
            }
        },
        "merchantLocationKey": "default-warehouse"
    }
    
    offer_create = requests.post(
        "https://api.ebay.com/sell/inventory/v1/offer",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=offer_data, timeout=30
    )
    
    if offer_create.status_code in [200, 201]:
        offer_response = offer_create.json()
        offer_id = offer_response.get('offerId')
        print(f"   ✅ Offer oluşturuldu: {offer_id}")
        
        # 3. Yayınla
        print(f"\n3. eBay'e yayınlanıyor...")
        
        publish = requests.post(
            f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            }, timeout=30
        )
        
        if publish.status_code in [200, 201]:
            publish_response = publish.json()
            listing_id = publish_response.get('listingId')
            
            print(f"\n" + "="*70)
            print(f"✅ BAŞARILI! GERÇEK ÜRÜN YAYINDA!")
            print(f"="*70)
            print(f"\neBay ID: {listing_id}")
            print(f"eBay Link: https://www.ebay.de/itm/{listing_id}")
            print(f"\nAliExpress Kaynak: {aliexpress_url}")
            print(f"Gerçek Görsel: {main_image}")
            print(f"\nAlış: €{aliexpress_cost}")
            print(f"Satış: €{ebay_price}")
            print(f"Kar: €{profit:.2f}")
            
            # Kaydet
            result = {
                'ebay_listing_id': listing_id,
                'ebay_url': f'https://www.ebay.de/itm/{listing_id}',
                'aliexpress_id': aliexpress_id,
                'aliexpress_url': aliexpress_url,
                'sku': sku,
                'cost': aliexpress_cost,
                'price': ebay_price,
                'profit': round(profit, 2),
                'image': main_image
            }
            
            with open('data/real_listing_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"\n✅ Sonuç kaydedildi: data/real_listing_result.json")
            
        else:
            print(f"   ❌ Yayınlama hatası: {publish.status_code}")
            print(f"   {publish.text[:500]}")
    else:
        print(f"   ❌ Offer hatası: {offer_create.status_code}")
        print(f"   {offer_create.text[:500]}")

except Exception as e:
    print(f"\n❌ HATA: {str(e)}")
    import traceback
    traceback.print_exc()
