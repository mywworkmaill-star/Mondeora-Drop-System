"""
eBay listing'e varyantları ekle
Multi-variation listing oluştur
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json

load_dotenv()

# Token yenile
from api.ebay_client import eBayAPIClient
ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)

access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

# Varyantları yükle
with open('data/product_variants.json', 'r', encoding='utf-8') as f:
    variant_data = json.load(f)

# Görselleri yükle
with open('data/all_images_combined.json', 'r', encoding='utf-8') as f:
    img_data = json.load(f)

all_images = img_data['all_combined']

print("="*70)
print("eBay MULTI-VARIATION LISTING OLUŞTURULUYOR")
print("="*70)

aliexpress_id = "1005013457960792"
inventory_group_key = f"GROUP-{aliexpress_id}"

print(f"\nInventory Group: {inventory_group_key}")
print(f"Toplam Varyant: {variant_data['total_variants']}")
print(f"Renkler: {len(variant_data['colors'])}")
print(f"Modeller: {len(variant_data['models'])}")

# Sadece popüler modelleri seç (çok fazla varyant eBay'i yavaşlatır)
popular_models = [
    'iPhone 18 Pro Max',
    'iPhone 18 Pro',
    'Iphone 16 pro max',
    'Iphone 16 pro',
    'Iphone 15 pro max',
    'Iphone 15 pro'
]

# HTML açıklama
html_description = """<div style="font-family:Arial;max-width:800px;margin:0 auto;color:#333">
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
<h2 style="color:#667eea;margin-top:0">🎨 Verfügbare Varianten</h2>
<p style="margin:5px 0"><b>Farben:</b> Braun, Himmelblau</p>
<p style="margin:5px 0"><b>Modelle:</b> iPhone 18/16/15 Pro Max & Pro</p>
</div>
<div style="background:#d4edda;padding:18px;border-radius:8px">
<h2 style="color:#28a745;margin-top:0">🚚 Versand</h2>
<p style="margin:5px 0">✅ Versand in 24-48h<br>
✅ 30 Tage Rückgabe<br>
✅ Sichere Verpackung</p>
</div>
</div>"""

try:
    # 1. Inventory Item Group oluştur
    print(f"\n1. Inventory Item Group oluşturuluyor...")
    
    group_data = {
        "inventoryItemGroupKey": inventory_group_key,
        "title": "Original Design iPhone Hülle Pro Max Kamera Schutz Matt Case Viele Modelle",
        "description": html_description,
        "imageUrls": all_images,
        "aspects": {
            "Marke": ["Markenlos"],
            "Produktart": ["Stoßstange"],
            "Material": ["Silikon"],
            "Besonderheiten": [
                "Kameraschutz",
                "Stoßfest",
                "Kratzfest",
                "Mattes Finish"
            ]
        },
        "variantSKUs": [],
        "variesBy": {
            "specifications": [
                {
                    "name": "Farbe",
                    "values": variant_data['colors']
                },
                {
                    "name": "Kompatibles Modell",
                    "values": popular_models
                }
            ]
        }
    }
    
    group_create = requests.put(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{inventory_group_key}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=group_data
, timeout=30)
    
    if group_create.status_code in [200, 201, 204]:
        print(f"   ✅ Inventory Item Group oluşturuldu")
    else:
        print(f"   ⚠️  {group_create.status_code}")
        print(f"   {group_create.text[:500]}")
    
    # 2. Her varyant için inventory item oluştur
    print(f"\n2. Varyant inventory item'ları oluşturuluyor...")
    
    created_variants = []
    
    for sku_data in variant_data['all_skus'][:20]:  # İlk 20 varyant
        props = sku_data['properties']
        color = props.get('Farbe', 'Braun')
        model = props.get('Mobiles Modell', '')
        
        # Sadece popüler modelleri ekle
        if model not in popular_models:
            continue
        
        sku = f"VAR-{aliexpress_id}-{sku_data['sku_id']}"
        price = float(sku_data['price']) * 2.5  # 2.5x markup
        
        variant_item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": sku_data['stock']
                }
            },
            "condition": "NEW",
            "product": {
                "aspects": {
                    "Farbe": [color],
                    "Kompatibles Modell": [model]
                }
            },
            "groupIds": [inventory_group_key]
        }
        
        var_create = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=variant_item
, timeout=30)
        
        if var_create.status_code in [200, 201, 204]:
            created_variants.append(sku)
            print(f"   ✅ {color} - {model}: €{price:.2f}")
        else:
            print(f"   ⚠️  {color} - {model}: {var_create.status_code}")
    
    print(f"\n   Toplam oluşturulan: {len(created_variants)}")
    
    # 3. Group Offer oluştur
    print(f"\n3. Group Offer oluşturuluyor...")
    
    offer_data = {
        "inventoryItemGroupKey": inventory_group_key,
        "marketplaceId": "EBAY_DE",
        "format": "FIXED_PRICE",
        "listingDuration": "GTC",
        "categoryId": "20349",
        "listingPolicies": {
            "paymentPolicyId": "263035507017",
            "returnPolicyId": "263035512017",
            "fulfillmentPolicyId": "263035514017"
        },
        "merchantLocationKey": "default-warehouse",
        "pricingSummary": {
            "price": {
                "value": "17.73",
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
        json=offer_data
, timeout=30)
    
    if offer_create.status_code in [200, 201]:
        offer_response = offer_create.json()
        offer_id = offer_response.get('offerId')
        print(f"   ✅ Offer oluşturuldu: {offer_id}")
        
        # 4. Yayınla
        print(f"\n4. eBay'e yayınlanıyor...")
        
        publish = requests.post(
            f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            }
, timeout=30)
        
        if publish.status_code in [200, 201]:
            publish_response = publish.json()
            listing_id = publish_response.get('listingId')
            
            print(f"\n" + "="*70)
            print(f"✅ BAŞARILI! VARYANTLI LİSTİNG YAYINDA!")
            print(f"="*70)
            print(f"\neBay ID: {listing_id}")
            print(f"eBay Link: https://www.ebay.de/itm/{listing_id}")
            print(f"\nVaryant Sayısı: {len(created_variants)}")
            print(f"Renkler: {', '.join(variant_data['colors'])}")
            print(f"Modeller: {len(popular_models)}")
            
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
