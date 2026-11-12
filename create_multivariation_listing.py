"""
Eski listing'i sil ve GERÇEK multi-variation listing yap
Dropdown menü ile renk/model seçimi
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

# Görselleri yükle
with open('data/all_images_combined.json', 'r', encoding='utf-8') as f:
    img_data = json.load(f)
all_images = img_data['all_combined']

# Varyantları yükle
with open('data/product_variants.json', 'r', encoding='utf-8') as f:
    variant_data = json.load(f)

print("="*70)
print("GERÇEK MULTI-VARIATION LISTING OLUŞTURULUYOR")
print("="*70)

aliexpress_id = "1005013457960792"
old_sku = 'ALIEXP-1005013457960792'
old_offer_id = '349502096011'

try:
    # 1. Eski offer'ı unpublish et
    print(f"\n1. Eski listing unpublish ediliyor...")
    
    unpublish = requests.post(
        f"https://api.ebay.com/sell/inventory/v1/offer/{old_offer_id}/withdraw",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }, timeout=30
    )
    
    if unpublish.status_code in [200, 204]:
        print(f"   ✅ Unpublish edildi")
    else:
        print(f"   ⚠️  {unpublish.status_code}: {unpublish.text[:200]}")
    
    # 2. Eski offer'ı sil
    print(f"\n2. Eski offer siliniyor...")
    
    delete_offer = requests.delete(
        f"https://api.ebay.com/sell/inventory/v1/offer/{old_offer_id}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }, timeout=30
    )
    
    if delete_offer.status_code == 204:
        print(f"   ✅ Offer silindi")
    else:
        print(f"   ⚠️  {delete_offer.status_code}")
    
    # 3. Eski inventory item'ı sil
    print(f"\n3. Eski inventory item siliniyor...")
    
    delete_item = requests.delete(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item/{old_sku}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }, timeout=30
    )
    
    if delete_item.status_code == 204:
        print(f"   ✅ Inventory item silindi")
    else:
        print(f"   ⚠️  {delete_item.status_code}")
    
    print(f"\n" + "="*70)
    print(f"YENİ MULTI-VARIATION LISTING OLUŞTURULUYOR")
    print(f"="*70)
    
    # 4. Popüler varyantları seç (6 varyant - 2 renk x 3 model)
    selected_variants = []
    
    for sku_data in variant_data['all_skus']:
        props = sku_data['properties']
        color = props.get('Farbe', '')
        model = props.get('Mobiles Modell', '')
        
        # Sadece Braun ve Himmelblau, sadece 16/15 Pro Max
        if color in ['Braun', 'HIMMELBLAU'] and model in ['Iphone 16 pro max', 'Iphone 15 pro max', 'iPhone 18 Pro Max']:
            selected_variants.append(sku_data)
            if len(selected_variants) >= 6:
                break
    
    print(f"\nSeçilen varyant: {len(selected_variants)}")
    
    # 5. Her varyant için inventory item oluştur
    print(f"\n4. Varyant inventory item'ları oluşturuluyor...")
    
    group_key = f"GROUP-{aliexpress_id}"
    created_skus = []
    
    for i, sku_data in enumerate(selected_variants, 1):
        props = sku_data['properties']
        color = props.get('Farbe', 'Braun')
        model = props.get('Mobiles Modell', '')
        
        # SKU oluştur
        sku_id = f"VAR-{aliexpress_id}-{i}"
        price = float(sku_data['price'])
        stock = sku_data['stock']
        
        # Renk mapping (Almanca)
        color_de = {
            'Braun': 'Braun',
            'HIMMELBLAU': 'Himmelblau'
        }.get(color, color)
        
        variant_item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": stock
                }
            },
            "condition": "NEW",
            "product": {
                "aspects": {
                    "Farbe": [color_de],
                    "Kompatibles Modell": [f"Für Apple {model}"]
                }
            },
            "groupIds": [group_key]
        }
        
        var_create = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku_id}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=variant_item, timeout=30
        )
        
        if var_create.status_code in [200, 201, 204]:
            created_skus.append(sku_id)
            print(f"   ✅ {i}. {color_de} - {model}")
        else:
            print(f"   ❌ {i}. {color_de} - {model}: {var_create.status_code}")
            print(f"      {var_create.text[:200]}")
    
    print(f"\n   Toplam oluşturulan: {len(created_skus)}")
    
    # 6. Inventory Item Group oluştur
    print(f"\n5. Inventory Item Group oluşturuluyor...")
    
    html_desc = """<div style="font-family:Arial;max-width:800px;margin:0 auto">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:25px;text-align:center;border-radius:10px;margin-bottom:20px">
<h1 style="margin:0;font-size:26px">📱 iPhone Hülle Premium</h1>
<p style="margin:10px 0 0">Kamera Schutz • Matt Finish • Stoßfest</p>
</div>
<div style="background:#f8f9fa;padding:20px;border-radius:10px;margin-bottom:20px">
<h2 style="color:#667eea">✨ Features</h2>
<ul style="line-height:2">
<li>🎯 Kamera-Schutz: Erhöhter Rand</li>
<li>💎 Matt Finish: Premium Design</li>
<li>🧲 MagSafe Kompatibel</li>
<li>💪 Stoßfest: TPU Silikon</li>
</ul>
</div>
</div>"""
    
    group_data = {
        "title": "iPhone Hülle Pro Max Kamera Schutz Matt Case",
        "description": html_desc,
        "imageUrls": all_images[:12],  # Maksimum 12 görsel
        "aspects": {
            "Marke": ["Markenlos"],
            "Produktart": ["Stoßstange"],
            "Material": ["Silikon"],
            "Besonderheiten": ["Kameraschutz", "Stoßfest"]
        },
        "variesBy": {
            "specifications": [
                {
                    "name": "Farbe",
                    "values": ["Braun", "Himmelblau"]
                },
                {
                    "name": "Kompatibles Modell",
                    "values": [
                        "Für Apple Iphone 16 pro max",
                        "Für Apple Iphone 15 pro max",
                        "Für Apple iPhone 18 Pro Max"
                    ]
                }
            ]
        },
        "variantSKUs": created_skus
    }
    
    group_create = requests.put(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=group_data, timeout=30
    )
    
    if group_create.status_code in [200, 201, 204]:
        print(f"   ✅ Group oluşturuldu: {group_key}")
    else:
        print(f"   ❌ Group hatası: {group_create.status_code}")
        print(f"   {group_create.text[:500]}")
        raise Exception("Group oluşturulamadı")
    
    # 7. Group Offer oluştur
    print(f"\n6. Group Offer oluşturuluyor...")
    
    group_offer_data = {
        "inventoryItemGroupKey": group_key,
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
    
    group_offer_create = requests.post(
        "https://api.ebay.com/sell/inventory/v1/offer",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=group_offer_data, timeout=30
    )
    
    if group_offer_create.status_code in [200, 201]:
        offer_resp = group_offer_create.json()
        offer_id = offer_resp.get('offerId')
        print(f"   ✅ Group Offer oluşturuldu: {offer_id}")
        
        # 8. Publish
        print(f"\n7. eBay'e yayınlanıyor...")
        
        publish = requests.post(
            f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            }, timeout=30
        )
        
        if publish.status_code in [200, 201]:
            pub_resp = publish.json()
            listing_id = pub_resp.get('listingId')
            
            print(f"\n" + "="*70)
            print(f"✅ BAŞARILI! MULTI-VARIATION LISTING YAYINDA!")
            print(f"="*70)
            print(f"\nYeni eBay ID: {listing_id}")
            print(f"Yeni Link: https://www.ebay.de/itm/{listing_id}")
            print(f"\nVaryantlar:")
            print(f"  - 2 Renk: Braun, Himmelblau")
            print(f"  - 3 Model: iPhone 18/16/15 Pro Max")
            print(f"  - Toplam: 6 seçilebilir varyant")
            print(f"\n✅ Müşteri dropdown'dan renk ve model seçebilir!")
            
            # Kaydet
            with open('data/multivariation_listing.json', 'w') as f:
                json.dump({
                    'listing_id': listing_id,
                    'offer_id': offer_id,
                    'group_key': group_key,
                    'variant_skus': created_skus,
                    'total_variants': len(created_skus)
                }, f, indent=2)
            
        else:
            print(f"   ❌ Publish hatası: {publish.status_code}")
            print(f"   {publish.text[:500]}")
    else:
        print(f"   ❌ Group Offer hatası: {group_offer_create.status_code}")
        print(f"   {group_offer_create.text[:500]}")

except Exception as e:
    print(f"\n❌ HATA: {str(e)}")
    import traceback
    traceback.print_exc()
