"""
VeRO-SAFE LİSTİNG ŞABLONU
Gerçek ürün ID'leriyle manuel oluşturma
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json

load_dotenv()

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')
campaign_id = "168739871017"

print("="*70)
print("VeRO-SAFE LİSTİNG ŞABLONU - MANUEL ÜRÜN")
print("="*70)

# Generic placeholder görseller (daha sonra değiştirilebilir)
PLACEHOLDER_IMAGES = [
    "https://ae01.alicdn.com/kf/S3fabe80037dd4c208954398406d63d77h.jpg",
    "https://ae01.alicdn.com/kf/Sa7e3b4437e7f4c85ba2859420a522d4bm.jpg",
    "https://ae01.alicdn.com/kf/Sc65f715d9cbb47f99bdaa8a4cc7ddcac2.jpg"
]

# 5 VeRO-safe ürün şablonu
PRODUCTS = [
    {
        "sku": "SAFE-ORGANIZER-001",
        "title": "Schreibtisch Organizer Set Büro Zubehör Stiftehalter Ablage",
        "category_id": "20326",
        "price": "12.99",
        "description_title": "Schreibtisch Organizer Set"
    },
    {
        "sku": "SAFE-PET-TOY-001",
        "title": "Hunde Spielzeug Set Kauspielzeug Ball Seil 5 Stück Haustier",
        "category_id": "20741",
        "price": "14.99",
        "description_title": "Hunde Spielzeug Set"
    },
    {
        "sku": "SAFE-SOLAR-001",
        "title": "Solar Gartenleuchte LED Solarlampe Außen Wasserdicht Deko 4er Set",
        "category_id": "20518",
        "price": "16.99",
        "description_title": "Solar Gartenleuchte LED"
    },
    {
        "sku": "SAFE-BABY-001",
        "title": "Baby Lätzchen Set 5 Stück Wasserdicht Silikon Weich Bunt",
        "category_id": "2984",
        "price": "11.99",
        "description_title": "Baby Lätzchen Set"
    },
    {
        "sku": "SAFE-FITNESS-001",
        "title": "Fitness Widerstandsband Set 5 Stärken Resistance Band Yoga Sport",
        "category_id": "73991",
        "price": "13.99",
        "description_title": "Fitness Widerstandsband Set"
    }
]

created = []

for idx, product in enumerate(PRODUCTS, 1):
    print(f"\n{'='*70}")
    print(f"{idx}/5: {product['description_title']}")
    print(f"{'='*70}")
    
    try:
        # HTML açıklama
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">✨ {product['description_title']}</h1>
<p style="font-size:18px;margin:0;">Premium Qualität • Schneller Versand • 30 Tage Rückgabe</p>
</div>

<div style="padding:20px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 15px 0;">📸 Produktbilder</h2>
<table width="100%" cellpadding="5">
<tr>
<td width="33%" align="center"><img src="{PLACEHOLDER_IMAGES[0]}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{PLACEHOLDER_IMAGES[1]}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{PLACEHOLDER_IMAGES[2]}" width="250" style="max-width:100%;border-radius:8px;"></td>
</tr>
</table>
</div>

<div style="padding:30px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;">✨ Features</h2>
<table width="100%" cellpadding="10">
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;">
<h3>🎯 Premium Qualität</h3>
<p style="color:#666;">Hochwertige Materialien und Verarbeitung</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;">
<h3>🚚 Schnell</h3>
<p style="color:#666;">Lieferung in 24-48 Stunden</p>
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
        
        # 1. Inventory Item
        print(f"1. Inventory item oluşturuluyor...")
        
        inv = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 99
                }
            },
            "condition": "NEW",
            "product": {
                "title": product['title'],
                "description": html,
                "aspects": {
                    "Marke": ["Markenlos"],
                    "Material": ["Kunststoff"],
                    "Besonderheiten": ["Premium Qualität", "Schneller Versand"]
                },
                "imageUrls": PLACEHOLDER_IMAGES
            }
        }
        
        inv_resp = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{product['sku']}",
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
            json=inv, timeout=30
        )
        
        if inv_resp.status_code in [200, 201, 204]:
            print(f"   ✅ Item oluşturuldu")
            
            # 2. Offer
            print(f"2. Offer oluşturuluyor...")
            
            offer = {
                "sku": product['sku'],
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
                        "value": product['price'],
                        "currency": "EUR"
                    }
                }
            }
            
            offer_resp = requests.post(
                "https://api.ebay.com/sell/inventory/v1/offer",
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
                json=offer, timeout=30
            )
            
            if offer_resp.status_code in [200, 201]:
                offer_id = offer_resp.json().get('offerId')
                print(f"   ✅ Offer: {offer_id}")
                
                # 3. Publish
                print(f"3. Publish ediliyor...")
                
                pub_resp = requests.post(
                    f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
                    headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, timeout=30
                )
                
                if pub_resp.status_code in [200, 201]:
                    listing_id = pub_resp.json().get('listingId')
                    print(f"   ✅ Listing: {listing_id}")
                    
                    # 4. Reklam
                    print(f"4. Reklam ekleniyor...")
                    
                    ad_resp = requests.post(
                        f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad",
                        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                        json={"bidPercentage": "5.0", "listingId": listing_id}, timeout=30
                    )
                    
                    if ad_resp.status_code in [200, 201, 409]:
                        print(f"   ✅ Reklam eklendi")
                    
                    created.append({
                        'name': product['description_title'],
                        'listing_id': listing_id,
                        'sku': product['sku'],
                        'price': product['price'],
                        'link': f"https://www.ebay.de/itm/{listing_id}"
                    })
                else:
                    print(f"   ⚠️  Publish: {pub_resp.status_code} - {pub_resp.text[:200]}")
            else:
                print(f"   ⚠️  Offer: {offer_resp.status_code} - {offer_resp.text[:200]}")
        else:
            print(f"   ⚠️  Inventory: {inv_resp.status_code} - {inv_resp.text[:200]}")
            
    except Exception as e:
        print(f"❌ Hata: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 Oluşturulan: {len(created)} listing")

for i, item in enumerate(created, 1):
    print(f"\n{i}. {item['name']}")
    print(f"   {item['link']}")
    print(f"   Fiyat: €{item['price']}")

with open('data/vero_safe_listings.json', 'w') as f:
    json.dump(created, f, indent=2)

print(f"\n✅ Kaydedildi: data/vero_safe_listings.json")
print(f"\n🛡️ VeRO-SAFE:")
print(f"   ✅ Markasız")
print(f"   ✅ Genel başlıklar")
print(f"   ✅ HTML açıklama")
print(f"   ✅ Reklam %5")
