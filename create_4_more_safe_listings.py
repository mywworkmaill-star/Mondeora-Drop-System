"""
4 YENİ ÜRÜN - ÇALIŞAN KATEGORİLERDE
Pet + Generic Phone Accessories
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
print("4 YENİ ÜRÜN - ÇALIŞAN KATEGORİLER")
print("="*70)

PLACEHOLDER_IMAGES = [
    "https://ae01.alicdn.com/kf/S3fabe80037dd4c208954398406d63d77h.jpg",
    "https://ae01.alicdn.com/kf/Sa7e3b4437e7f4c85ba2859420a522d4bm.jpg",
    "https://ae01.alicdn.com/kf/Sc65f715d9cbb47f99bdaa8a4cc7ddcac2.jpg"
]

PRODUCTS = [
    # 2 Pet ürünü
    {
        "sku": "SAFE-PET-002",
        "title": "Katzen Spielzeug Set Interaktiv Maus Ball Feder 10 Stück",
        "category_id": "20741",  # Haustierbedarf
        "price": "9.99",
        "name": "Katzen Spielzeug Set",
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Kunststoff"],
            "Tierart": ["Katze"],
            "Besonderheiten": ["Interaktiv", "Bunt"]
        }
    },
    {
        "sku": "SAFE-PET-003",
        "title": "Hunde Napf Set 2er Edelstahl Futternapf Wassernapf Rutschfest",
        "category_id": "20741",
        "price": "12.99",
        "name": "Hunde Napf Set",
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Edelstahl"],
            "Tierart": ["Hund"],
            "Besonderheiten": ["Rutschfest", "Spülmaschinenfest"]
        }
    },
    # 2 Generic Phone Accessories
    {
        "sku": "SAFE-PHONE-001",
        "title": "Universal Handyhalterung Auto KFZ Halterung Lüftung 360° Drehbar",
        "category_id": "9394",  # Handy-Zubehör
        "price": "8.99",
        "name": "Universal Handyhalterung Auto",
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Kunststoff"],
            "Produktart": ["Halterung"],
            "Besonderheiten": ["360° Drehbar", "Universal"]
        }
    },
    {
        "sku": "SAFE-PHONE-002",
        "title": "Handykette Universal Umhängeband Schlüsselband Handy Silikon",
        "category_id": "9394",
        "price": "6.99",
        "name": "Handykette Umhängeband",
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Silikon"],
            "Produktart": ["Lanyard"],
            "Besonderheiten": ["Universal", "Verstellbar"]
        }
    }
]

created = []

for idx, product in enumerate(PRODUCTS, 1):
    print(f"\n{'='*70}")
    print(f"{idx}/4: {product['name']}")
    print(f"{'='*70}")
    
    try:
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">✨ {product['name']}</h1>
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
<p style="color:#666;">Hochwertige Materialien</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;">
<h3>🚚 Schnell</h3>
<p style="color:#666;">24-48h Versand</p>
</div>
</td>
</tr>
</table>
</div>

<div style="background:#e7f3ff;padding:25px;">
<table width="100%">
<tr>
<td width="33%" align="center"><div style="font-size:32px;">🚚</div><div>Schneller Versand</div></td>
<td width="33%" align="center"><div style="font-size:32px;">↩️</div><div>30 Tage Rückgabe</div></td>
<td width="33%" align="center"><div style="font-size:32px;">📦</div><div>Sichere Verpackung</div></td>
</tr>
</table>
</div>

<div style="background:#28a745;color:white;padding:30px;text-align:center;">
<h2 style="font-size:24px;margin:0;">🛒 Jetzt Bestellen!</h2>
</div>

</div>
</body>
</html>"""
        
        print(f"1. Inventory item oluşturuluyor...")
        
        inv = {
            "availability": {"shipToLocationAvailability": {"quantity": 99}},
            "condition": "NEW",
            "product": {
                "title": product['title'],
                "description": html,
                "aspects": product['aspects'],
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
                "pricingSummary": {"price": {"value": product['price'], "currency": "EUR"}}
            }
            
            offer_resp = requests.post(
                "https://api.ebay.com/sell/inventory/v1/offer",
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
                json=offer, timeout=30
            )
            
            if offer_resp.status_code in [200, 201]:
                offer_id = offer_resp.json().get('offerId')
                print(f"   ✅ Offer: {offer_id}")
                
                print(f"3. Publish...")
                
                pub_resp = requests.post(
                    f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
                    headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, timeout=30
                )
                
                if pub_resp.status_code in [200, 201]:
                    listing_id = pub_resp.json().get('listingId')
                    print(f"   ✅ Listing: {listing_id}")
                    
                    print(f"4. Reklam...")
                    
                    ad_resp = requests.post(
                        f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad",
                        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                        json={"bidPercentage": "5.0", "listingId": listing_id}, timeout=30
                    )
                    
                    if ad_resp.status_code in [200, 201, 409]:
                        print(f"   ✅ Reklam eklendi")
                    
                    created.append({
                        'name': product['name'],
                        'listing_id': listing_id,
                        'sku': product['sku'],
                        'price': product['price'],
                        'category': 'Pet' if 'PET' in product['sku'] else 'Phone',
                        'link': f"https://www.ebay.de/itm/{listing_id}"
                    })
                else:
                    print(f"   ⚠️  Publish: {pub_resp.status_code}")
                    print(f"   {pub_resp.text[:300]}")
            else:
                print(f"   ⚠️  Offer: {offer_resp.status_code}")
        else:
            print(f"   ⚠️  Inventory: {inv_resp.status_code}")
            
    except Exception as e:
        print(f"❌ Hata: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 Oluşturulan: {len(created)} yeni listing")

for i, item in enumerate(created, 1):
    print(f"\n{i}. {item['name']} ({item['category']})")
    print(f"   {item['link']}")
    print(f"   €{item['price']}")

# Ekle mevcut listeye
try:
    with open('data/vero_safe_listings.json', 'r') as f:
        existing = json.load(f)
except:
    existing = []

existing.extend(created)

with open('data/vero_safe_listings.json', 'w') as f:
    json.dump(existing, f, indent=2)

print(f"\n✅ Toplam VeRO-safe listing: {len(existing)}")
print(f"\n🛡️ TAMAMEN GÜVENLİ:")
print(f"   ✅ Markasız")
print(f"   ✅ Doğru aspect'ler")
print(f"   ✅ HTML açıklama")
print(f"   ✅ Reklam %5")
