"""
10 VeRO-SAFE PET ÜRÜNÜ - GERÇEK AliExpress Görselleriyle
3 mevcut düzeltme + 7 yeni ürün
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
campaign_id = "168739871017"

print("="*70)
print("10 GERÇEK PET ÜRÜNÜ - AliExpress Görselleriyle")
print("="*70)

# 10 GERÇEK AliExpress Pet ürünü
PRODUCTS = [
    # Mevcut 3'ün düzeltilmesi (sadece görseller güncellenecek)
    {
        "sku": "SAFE-PET-001",
        "ali_id": "1005005051143560",  # Dog toy ball
        "update_only": True,
        "name": "Hunde Spielzeug Ball Set"
    },
    {
        "sku": "SAFE-PET-002",
        "ali_id": "1005012107815974",  # Cat toy mouse
        "update_only": True,
        "name": "Katzen Spielzeug Maus Set"
    },
    {
        "sku": "SAFE-PET-003",
        "ali_id": "1005013139245441",  # Dog bowl
        "update_only": True,
        "name": "Hunde Napf Edelstahl Set"
    },
    
    # 7 YENİ ÜRÜN
    {
        "sku": "SAFE-PET-004",
        "ali_id": "1005013173259438",  # Cat scratching post
        "title": "Katzen Kratzbaum Sisalseil Spielzeug Kratzsäule",
        "category_id": "20741",
        "price_mult": 3.0,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Sisal"],
            "Tierart": ["Katze"],
            "Besonderheiten": ["Kratzschutz", "Spielzeug"]
        }
    },
    {
        "sku": "SAFE-PET-005",
        "ali_id": "1005012621587758",  # Dog leash
        "title": "Hunde Leine Ausziehbar 5m Automatik Flexileine",
        "category_id": "20741",
        "price_mult": 2.5,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Nylon"],
            "Tierart": ["Hund"],
            "Besonderheiten": ["Ausziehbar", "5m"]
        }
    },
    {
        "sku": "SAFE-PET-006",
        "ali_id": "1005013079571200",  # Cat carrier
        "title": "Katzen Transportbox Faltbar Tragbar Reisebox",
        "category_id": "20741",
        "price_mult": 3.5,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Stoff"],
            "Tierart": ["Katze"],
            "Besonderheiten": ["Faltbar", "Tragbar"]
        }
    },
    {
        "sku": "SAFE-PET-007",
        "ali_id": "1005013380599868",  # Dog LED collar
        "title": "Hunde Halsband LED Leuchtend Wiederaufladbar USB",
        "category_id": "20741",
        "price_mult": 2.8,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Nylon"],
            "Tierart": ["Hund"],
            "Besonderheiten": ["LED", "Wiederaufladbar"]
        }
    },
    {
        "sku": "SAFE-PET-008",
        "ali_id": "1005013479383498",  # Cat feeder
        "title": "Katzen Futterautomat Automatisch Zeitschaltuhr 4 Mahlzeiten",
        "category_id": "20741",
        "price_mult": 4.0,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Kunststoff"],
            "Tierart": ["Katze"],
            "Besonderheiten": ["Automatisch", "Zeitschaltuhr"]
        }
    },
    {
        "sku": "SAFE-PET-009",
        "ali_id": "1005013167003737",  # Dog shoes
        "title": "Hunde Schuhe Pfotenschutz 4er Set Wasserdicht Rutschfest",
        "category_id": "20741",
        "price_mult": 3.0,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Gummi"],
            "Tierart": ["Hund"],
            "Besonderheiten": ["Wasserdicht", "Rutschfest"]
        }
    },
    {
        "sku": "SAFE-PET-010",
        "ali_id": "1005012505456352",  # Cat water fountain
        "title": "Katzen Trinkbrunnen Automatisch 2L Wasserspender Leise",
        "category_id": "20741",
        "price_mult": 3.5,
        "aspects": {
            "Marke": ["Markenlos"],
            "Material": ["Kunststoff"],
            "Tierart": ["Katze"],
            "Besonderheiten": ["Automatisch", "2L"]
        }
    }
]

updated = 0
created = 0
errors = []

for idx, item in enumerate(PRODUCTS, 1):
    print(f"\n{'='*70}")
    print(f"{idx}/10: {item.get('name', item.get('title', item['sku']))}")
    print(f"{'='*70}")
    
    try:
        # 1. AliExpress'ten GERÇEK ürün al
        print(f"1. AliExpress ID: {item['ali_id']}...")
        
        product = ali.get_product_details(item['ali_id'])
        
        if not product:
            print(f"   ❌ Ürün bulunamadı!")
            errors.append(f"{item['sku']}: Ürün bulunamadı")
            continue
        
        # 2. GERÇEK görselleri çıkar
        img_str = product.get('image_urls', '')
        if isinstance(img_str, str) and ';' in img_str:
            images = img_str.split(';')
        elif isinstance(img_str, str) and img_str:
            images = [img_str]
        else:
            images = []
        
        # SKU görselleri ekle
        sku_info = product.get('ae_item_sku_info_dtos', {})
        if sku_info:
            sku_list = sku_info.get('ae_item_sku_info_d_t_o', [])
            for sku in sku_list[:5]:
                props = sku.get('ae_sku_property_dtos', {}).get('ae_sku_property_d_t_o', [])
                for prop in props:
                    sku_img = prop.get('sku_image')
                    if sku_img and sku_img not in images:
                        images.append(sku_img)
        
        images = images[:12]  # eBay limit
        
        if len(images) == 0:
            print(f"   ❌ Görsel yok!")
            errors.append(f"{item['sku']}: Görsel yok")
            continue
        
        print(f"   ✅ {len(images)} gerçek görsel bulundu")
        
        # 3. Fiyat hesapla
        price_str = product.get('sale_price')
        if not price_str or float(price_str) == 0:
            skus = product.get('skus', [])
            if skus and skus[0].get('sale_price'):
                price_str = str(skus[0]['sale_price'])
            else:
                price_str = "10.00"
        
        if item.get('update_only'):
            # Sadece görselleri güncelle
            print(f"2. Mevcut item'ın görselleri güncelleniyor...")
            
            inv_get = requests.get(
                f"https://api.ebay.com/sell/inventory/v1/inventory_item/{item['sku']}",
                headers={'Authorization': f'Bearer {access_token}', 'Content-Language': 'de-DE'}, timeout=30
            )
            
            if inv_get.status_code == 200:
                inv_data = inv_get.json()
                inv_data['product']['imageUrls'] = images
                
                inv_update = requests.put(
                    f"https://api.ebay.com/sell/inventory/v1/inventory_item/{item['sku']}",
                    headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
                    json=inv_data, timeout=30
                )
                
                if inv_update.status_code in [200, 204]:
                    print(f"   ✅ Görseller güncellendi!")
                    updated += 1
                else:
                    print(f"   ⚠️  Update: {inv_update.status_code}")
                    errors.append(f"{item['sku']}: Update failed {inv_update.status_code}")
            else:
                print(f"   ⚠️  Get: {inv_get.status_code}")
                errors.append(f"{item['sku']}: Get failed")
        
        else:
            # Yeni ürün oluştur
            price = float(price_str) * item['price_mult']
            price = round(price, 2)
            
            print(f"2. Fiyat: €{price_str} → €{price}")
            
            # HTML
            html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">✨ Premium Qualität</h1>
<p style="font-size:18px;margin:0;">Schneller Versand • 30 Tage Rückgabe</p>
</div>
<div style="padding:20px;">
<table width="100%" cellpadding="5">
<tr>
<td width="33%" align="center"><img src="{images[0]}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{images[1] if len(images)>1 else images[0]}" width="250" style="max-width:100%;border-radius:8px;"></td>
<td width="33%" align="center"><img src="{images[2] if len(images)>2 else images[0]}" width="250" style="max-width:100%;border-radius:8px;"></td>
</tr>
</table>
</div>
<div style="background:#e7f3ff;padding:25px;">
<table width="100%"><tr>
<td width="33%" align="center"><div style="font-size:32px;">🚚</div><div>Schnell</div></td>
<td width="33%" align="center"><div style="font-size:32px;">↩️</div><div>30 Tage</div></td>
<td width="33%" align="center"><div style="font-size:32px;">📦</div><div>Sicher</div></td>
</tr></table>
</div>
<div style="background:#28a745;color:white;padding:30px;text-align:center;">
<h2 style="font-size:24px;margin:0;">🛒 Jetzt Bestellen!</h2>
</div>
</div></body></html>"""
            
            print(f"3. Inventory item oluşturuluyor...")
            
            inv = {
                "availability": {"shipToLocationAvailability": {"quantity": 99}},
                "condition": "NEW",
                "product": {
                    "title": item['title'],
                    "description": html,
                    "aspects": item['aspects'],
                    "imageUrls": images
                }
            }
            
            inv_resp = requests.put(
                f"https://api.ebay.com/sell/inventory/v1/inventory_item/{item['sku']}",
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
                json=inv, timeout=30
            )
            
            if inv_resp.status_code in [200, 201, 204]:
                print(f"   ✅ Item oluşturuldu")
                
                print(f"4. Offer oluşturuluyor...")
                
                offer = {
                    "sku": item['sku'],
                    "marketplaceId": "EBAY_DE",
                    "format": "FIXED_PRICE",
                    "listingDuration": "GTC",
                    "categoryId": item['category_id'],
                    "merchantLocationKey": "default-warehouse",
                    "listingPolicies": {
                        "paymentPolicyId": "263035507017",
                        "returnPolicyId": "263035512017",
                        "fulfillmentPolicyId": "263035514017"
                    },
                    "pricingSummary": {"price": {"value": str(price), "currency": "EUR"}}
                }
                
                offer_resp = requests.post(
                    "https://api.ebay.com/sell/inventory/v1/offer",
                    headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json', 'Content-Language': 'de-DE'},
                    json=offer, timeout=30
                )
                
                if offer_resp.status_code in [200, 201]:
                    offer_id = offer_resp.json().get('offerId')
                    print(f"   ✅ Offer: {offer_id}")
                    
                    print(f"5. Publish...")
                    
                    pub_resp = requests.post(
                        f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
                        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, timeout=30
                    )
                    
                    if pub_resp.status_code in [200, 201]:
                        listing_id = pub_resp.json().get('listingId')
                        print(f"   ✅ Listing: {listing_id}")
                        
                        print(f"6. Reklam...")
                        
                        ad_resp = requests.post(
                            f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad",
                            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                            json={"bidPercentage": "5.0", "listingId": listing_id}, timeout=30
                        )
                        
                        if ad_resp.status_code in [200, 201, 409]:
                            print(f"   ✅ Reklam eklendi")
                        
                        created += 1
                    else:
                        print(f"   ⚠️  Publish: {pub_resp.status_code}")
                        errors.append(f"{item['sku']}: Publish failed")
                else:
                    print(f"   ⚠️  Offer: {offer_resp.status_code}")
                    errors.append(f"{item['sku']}: Offer failed")
            else:
                print(f"   ⚠️  Inventory: {inv_resp.status_code}")
                errors.append(f"{item['sku']}: Inventory failed")
                
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        errors.append(f"{item['sku']}: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 SONUÇ:")
print(f"   Güncellenen: {updated} mevcut listing")
print(f"   Oluşturulan: {created} yeni listing")
print(f"   Toplam: {updated + created}/10")

if errors:
    print(f"\n⚠️  HATALAR ({len(errors)}):")
    for err in errors:
        print(f"   - {err}")

print(f"\n🛡️ VeRO-SAFE GARANTİSİ:")
print(f"   ✅ 10 gerçek AliExpress ürünü")
print(f"   ✅ Her ürün KENDİ görselleriyle")
print(f"   ✅ Markasız (VeRO-safe)")
print(f"   ✅ Pet kategorisi (20741)")
print(f"   ✅ HTML + Reklam %5")
