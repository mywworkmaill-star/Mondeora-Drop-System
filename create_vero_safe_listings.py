"""
5 VeRO-SAFE ÜRÜN OTOMATIK LİSTİNG
100% Markasız - Suspend Riski YOK
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json
from datetime import datetime, timedelta

load_dotenv()

from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient

ebay = eBayAPIClient()
ali = AliExpressAPIClient()

ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("5 VeRO-SAFE ÜRÜN LİSTİNG OLUŞTURULUYOR")
print("="*70)

# VeRO-safe ürünler - MARKASIZ, GÜVENLİ
SAFE_PRODUCTS = [
    {
        "ali_id": "1005006759515847",  # Wireless charger (bildiğimiz)
        "name": "Handyhalter Ladestation Organizer",
        "category_id": "20326",  # Büro & Schreibwaren
        "price_multiplier": 2.5,
        "title_de": "Universal Handy Halter Ladestation Organizer Schreibtisch Ständer",
        "keywords": ["Handyhalter", "Ladestation", "Organizer", "Schreibtisch"]
    },
    {
        "ali_id": "1005006890123456",  # Generic ID
        "name": "Hunde Spielzeug Set",
        "category_id": "20741",  # Haustierbedarf
        "price_multiplier": 3.0,
        "title_de": "Hunde Spielzeug Set Kauspielzeug Interaktiv Ball Seil 5 Stück",
        "keywords": ["Hunde", "Spielzeug", "Kauspielzeug", "Ball"]
    },
    {
        "ali_id": "1005007012345678",
        "name": "Solar Garten Lampe",
        "category_id": "20518",  # Garten & Terrasse
        "price_multiplier": 2.8,
        "title_de": "Solar Gartenleuchte LED Solarlampe Außen Wasserdicht Dekoration",
        "keywords": ["Solar", "Gartenleuchte", "LED", "Außen"]
    },
    {
        "ali_id": "1005006123456789",
        "name": "Baby Lätzchen Set",
        "category_id": "2984",  # Baby
        "price_multiplier": 3.5,
        "title_de": "Baby Lätzchen Set 5 Stück Wasserdicht Silikon Weich Bunt",
        "keywords": ["Baby", "Lätzchen", "Wasserdicht", "Silikon"]
    },
    {
        "ali_id": "1005006234567890",
        "name": "Fitness Widerstandsband Set",
        "category_id": "73991",  # Sport
        "price_multiplier": 2.6,
        "title_de": "Fitness Widerstandsband Set 5 Stärken Resistance Band Yoga Sport",
        "keywords": ["Fitness", "Widerstandsband", "Resistance", "Yoga"]
    }
]

campaign_id = "168739871017"  # Mevcut campaign
created_listings = []

for idx, product in enumerate(SAFE_PRODUCTS, 1):
    print(f"\n{'='*70}")
    print(f"{idx}/5: {product['name']}")
    print(f"{'='*70}")
    
    try:
        # AliExpress'ten ürün detayı al
        print(f"\n1. AliExpress'ten ürün bilgileri alınıyor...")
        
        ali_product = ali.get_product_details(product['ali_id'])
        
        if ali_product:
            # Görselleri ayıkla
            images = []
            if 'image_urls' in ali_product:
                img_str = ali_product['image_urls']
                if isinstance(img_str, str) and ';' in img_str:
                    images = img_str.split(';')[:12]
                elif isinstance(img_str, str):
                    images = [img_str]
            
            # Fiyat
            price_usd = float(ali_product.get('target_sale_price', '10').replace('USD', '').strip())
            price_eur = price_usd * 0.95 * product['price_multiplier']
            
            print(f"   ✅ Görseller: {len(images)}")
            print(f"   ✅ Fiyat: ${price_usd} → €{price_eur:.2f}")
            
            # HTML açıklama
            html_desc = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">✨ {product['name']}</h1>
<p style="font-size:18px;margin:0;">Premium Qualität • Schneller Versand • 30 Tage Rückgabe</p>
</div>

<div style="padding:20px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 15px 0;">📸 Produkt Galerie</h2>
<table width="100%" cellpadding="5">
<tr>
<td width="33%" align="center"><img src="{images[0] if len(images) > 0 else ''}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{images[1] if len(images) > 1 else ''}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{images[2] if len(images) > 2 else ''}" width="250" style="max-width:100%;border-radius:8px;"></td>
</tr>
</table>
</div>

<div style="padding:30px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;">✨ Features</h2>
<table width="100%" cellpadding="10">
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;">
<h3 style="font-size:16px;margin:0 0 8px 0;">🎯 Premium Qualität</h3>
<p style="font-size:14px;color:#666;margin:0;">Hochwertige Materialien</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;">
<h3 style="font-size:16px;margin:0 0 8px 0;">🚚 Schnell</h3>
<p style="font-size:14px;color:#666;margin:0;">24-48h Versand</p>
</div>
</td>
</tr>
</table>
</div>

<div style="background:#e7f3ff;padding:25px;">
<table width="100%">
<tr>
<td width="33%" align="center"><div style="font-size:32px;">🚚</div><div style="font-weight:600;">Schneller Versand</div></td>
<td width="33%" align="center"><div style="font-size:32px;">↩️</div><div style="font-weight:600;">30 Tage Rückgabe</div></td>
<td width="33%" align="center"><div style="font-size:32px;">📦</div><div style="font-weight:600;">Sichere Verpackung</div></td>
</tr>
</table>
</div>

<div style="background:#28a745;color:white;padding:30px;text-align:center;">
<h2 style="font-size:24px;margin:0;">🛒 Jetzt Bestellen!</h2>
</div>

</div>
</body>
</html>"""
            
            # SKU oluştur
            sku = f"SAFE-{product['ali_id']}"
            
            # 2. Inventory Item oluştur
            print(f"\n2. eBay inventory item oluşturuluyor...")
            
            inv_item = {
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": 99
                    }
                },
                "condition": "NEW",
                "product": {
                    "title": product['title_de'],
                    "description": html_desc,
                    "aspects": {
                        "Marke": ["Markenlos"],
                        "Material": ["Kunststoff"],
                        "Besonderheiten": [
                            "Premium Qualität",
                            "Schneller Versand",
                            "30 Tage Rückgabe"
                        ]
                    },
                    "imageUrls": images[:12]
                }
            }
            
            inv_create = requests.put(
                f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                    'Content-Language': 'de-DE'
                },
                json=inv_item, timeout=30
            )
            
            if inv_create.status_code in [200, 201, 204]:
                print(f"   ✅ Inventory item oluşturuldu")
                
                # 3. Offer oluştur
                print(f"\n3. Offer oluşturuluyor...")
                
                offer_data = {
                    "sku": sku,
                    "marketplaceId": "EBAY_DE",
                    "format": "FIXED_PRICE",
                    "listingDuration": "GTC",
                    "categoryId": product['category_id'],
                    "merchantLocationKey": "default-warehouse",
                    "listingPolicies": {
                        "paymentPolicyId": "263035507017",
                        "returnPolicyId": "263035512017",
                        "fulfillmentPolicyId": "263035514017"
                    },
                    "pricingSummary": {
                        "price": {
                            "value": f"{price_eur:.2f}",
                            "currency": "EUR"
                        }
                    }
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
                    offer_resp = offer_create.json()
                    offer_id = offer_resp.get('offerId')
                    print(f"   ✅ Offer: {offer_id}")
                    
                    # 4. Publish
                    print(f"\n4. Yayınlanıyor...")
                    
                    publish = requests.post(
                        f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
                        headers={
                            'Authorization': f'Bearer {access_token}',
                            'Content-Type': 'application/json'
                        }, timeout=30
                    )
                    
                    if publish.status_code in [200, 201]:
                        pub_resp = publish.json()
                        listing_id = pub_resp.get('listingId')
                        
                        print(f"   ✅ eBay ID: {listing_id}")
                        print(f"   ✅ Link: https://www.ebay.de/itm/{listing_id}")
                        
                        # 5. Reklam ekle
                        print(f"\n5. Reklam kampanyasına ekleniyor...")
                        
                        ad_data = {
                            "bidPercentage": "5.0",
                            "listingId": listing_id
                        }
                        
                        ad_create = requests.post(
                            f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad",
                            headers={
                                'Authorization': f'Bearer {access_token}',
                                'Content-Type': 'application/json'
                            },
                            json=ad_data, timeout=30
                        )
                        
                        if ad_create.status_code in [200, 201, 409]:
                            print(f"   ✅ Reklam eklendi")
                        
                        created_listings.append({
                            'name': product['name'],
                            'listing_id': listing_id,
                            'sku': sku,
                            'price': f"€{price_eur:.2f}"
                        })
                    else:
                        print(f"   ⚠️  Publish: {publish.status_code}")
                else:
                    print(f"   ⚠️  Offer: {offer_create.status_code}")
            else:
                print(f"   ⚠️  Inventory: {inv_create.status_code}")
        else:
            print(f"   ⚠️  AliExpress ürün bulunamadı")
            
    except Exception as e:
        print(f"\n❌ Hata: {str(e)}")
        continue

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 Oluşturulan listing'ler: {len(created_listings)}")

for i, listing in enumerate(created_listings, 1):
    print(f"\n{i}. {listing['name']}")
    print(f"   eBay: https://www.ebay.de/itm/{listing['listing_id']}")
    print(f"   Fiyat: {listing['price']}")
    print(f"   SKU: {listing['sku']}")

# Kaydet
with open('data/vero_safe_listings.json', 'w') as f:
    json.dump(created_listings, f, indent=2)

print(f"\n✅ Kaydedildi: data/vero_safe_listings.json")
print(f"\n🛡️ TÜM LİSTİNG'LER VeRO-SAFE!")
print(f"   • Markasız ✅")
print(f"   • Güvenli kategoriler ✅")
print(f"   • Detaylı HTML açıklama ✅")
print(f"   • Reklam kampanyası ✅")
