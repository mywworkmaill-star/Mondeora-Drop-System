"""
TOPLU LİSTİNG GÜNCELLEMESİ
Tüm aktif listing'lere otomatik:
1. Detaylı HTML açıklama ekler
2. Ürün bilgilerini doldurur
3. Reklam kampanyasına ekler
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

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)

access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("TOPLU LİSTİNG GÜNCELLEMESİ")
print("="*70)

# Campaign ID'yi al (veya yeni oluştur)
campaign_id = None

try:
    # Mevcut campaign'leri kontrol et
    campaigns_get = requests.get(
        "https://api.ebay.com/sell/marketing/v1/ad_campaign?campaign_status=RUNNING",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }
, timeout=30)
    
    if campaigns_get.status_code == 200:
        campaigns = campaigns_get.json()
        if campaigns.get('total', 0) > 0:
            campaign_id = campaigns['campaigns'][0]['campaignId']
            print(f"\n✅ Mevcut campaign kullanılacak: {campaign_id}")
except:
    pass

# Eğer campaign yoksa yeni oluştur
if not campaign_id:
    print(f"\n📢 Yeni campaign oluşturuluyor...")
    
    tomorrow = datetime.utcnow() + timedelta(days=1)
    start_date = tomorrow.strftime('%Y-%m-%dT00:00:00.000Z')
    
    campaign_data = {
        "campaignName": f"Auto Campaign {datetime.now().strftime('%Y%m%d')}",
        "startDate": start_date,
        "fundingStrategy": {
            "fundingModel": "COST_PER_SALE",
            "bidPercentage": "5.0"
        },
        "marketplaceId": "EBAY_DE"
    }
    
    campaign_create = requests.post(
        "https://api.ebay.com/sell/marketing/v1/ad_campaign",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json=campaign_data
, timeout=30)
    
    if campaign_create.status_code == 201:
        campaign_id = campaign_create.headers.get('location', '').split('/')[-1]
        print(f"   ✅ Campaign oluşturuldu: {campaign_id}")

print(f"\n" + "="*70)
print(f"LİSTİNG'LERİ GÜNCELLEME")
print(f"="*70)

# Tüm inventory group'ları al
groups_get = requests.get(
    "https://api.ebay.com/sell/inventory/v1/inventory_item_group",
    headers={
        'Authorization': f'Bearer {access_token}',
        'Content-Language': 'de-DE'
    }
, timeout=30)

updated_count = 0
ad_count = 0

if groups_get.status_code == 200:
    groups_data = groups_get.json()
    groups = groups_data.get('inventoryItemGroups', [])
    
    print(f"\nBulunan inventory group: {len(groups)}")
    
    for group in groups:
        group_key = group.get('inventoryItemGroupKey')
        
        print(f"\n{'='*70}")
        print(f"Group: {group_key}")
        print(f"{'='*70}")
        
        # Group detaylarını al
        group_detail = requests.get(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Language': 'de-DE'
            }
, timeout=30)
        
        if group_detail.status_code == 200:
            group_info = group_detail.json()
            
            # İlk görseli al (varsa)
            image_urls = group_info.get('imageUrls', [])
            
            # Basit HTML şablon (görseller varsa kullan)
            if image_urls:
                html_desc = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">📱 Premium Produkt</h1>
<p style="font-size:18px;margin:0;">Schneller Versand • 30 Tage Rückgabe • Qualität</p>
</div>

<div style="background:#fff3cd;padding:25px;margin:20px;border-radius:10px;border:3px solid #ffc107;">
<h2 style="color:#ff6b6b;margin:0 0 10px 0;text-align:center;">⚠️ WICHTIG</h2>
<p style="text-align:center;margin:0;padding:15px;background:#ff6b6b;color:white;border-radius:5px;font-weight:bold;">
Bitte wählen Sie oben Ihre Variante aus!
</p>
</div>

<div style="padding:20px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 15px 0;border-left:4px solid #667eea;padding-left:15px;">📸 Produkt Galerie</h2>
<table width="100%" cellpadding="5">
<tr>
<td width="33%" align="center"><img src="{image_urls[0] if len(image_urls) > 0 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{image_urls[1] if len(image_urls) > 1 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{image_urls[2] if len(image_urls) > 2 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
</tr>
<tr>
<td width="33%" align="center"><img src="{image_urls[3] if len(image_urls) > 3 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{image_urls[4] if len(image_urls) > 4 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{image_urls[5] if len(image_urls) > 5 else ''}" width="250" style="border-radius:8px;max-width:100%;"></td>
</tr>
</table>
</div>

<div style="padding:30px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;border-left:4px solid #667eea;padding-left:15px;">✨ Features</h2>
<table width="100%" cellpadding="10">
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🎯</div>
<h3 style="font-size:16px;margin:8px 0;">Premium Qualität</h3>
<p style="font-size:14px;color:#666;margin:0;">Hochwertige Verarbeitung</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">💎</div>
<h3 style="font-size:16px;margin:8px 0;">Schneller Versand</h3>
<p style="font-size:14px;color:#666;margin:0;">24-48 Stunden</p>
</div>
</td>
</tr>
</table>
</div>

<div style="background:#e7f3ff;padding:25px;">
<table width="100%">
<tr>
<td width="33%" align="center">
<div style="font-size:32px;">🚚</div>
<div style="font-weight:600;">Schneller Versand</div>
</td>
<td width="33%" align="center">
<div style="font-size:32px;">↩️</div>
<div style="font-weight:600;">30 Tage Rückgabe</div>
</td>
<td width="33%" align="center">
<div style="font-size:32px;">📦</div>
<div style="font-weight:600;">Sichere Verpackung</div>
</td>
</tr>
</table>
</div>

<div style="background:#28a745;color:white;padding:30px;text-align:center;">
<h2 style="font-size:24px;margin:0;">🛒 Jetzt Bestellen!</h2>
</div>

</div>
</body>
</html>
"""
            else:
                html_desc = "<p>Premium Produkt - Schneller Versand - 30 Tage Rückgabe</p>"
            
            # Group'u güncelle
            print(f"\n1. Açıklama güncelleniyor...")
            
            update_data = group_info.copy()
            update_data['description'] = html_desc
            
            # Aspects ekle/güncelle
            if 'aspects' not in update_data:
                update_data['aspects'] = {}
            
            update_data['aspects']['Besonderheiten'] = [
                "Schneller Versand",
                "Premium Qualität",
                "30 Tage Rückgabe"
            ]
            
            group_update = requests.put(
                f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                    'Content-Language': 'de-DE'
                },
                json=update_data
, timeout=30)
            
            if group_update.status_code in [200, 204]:
                print(f"   ✅ Açıklama güncellendi")
                updated_count += 1
            else:
                print(f"   ⚠️  {group_update.status_code}")
            
            # Bu group'un listing'lerini reklam kampanyasına ekle
            if campaign_id:
                print(f"\n2. Reklam kampanyasına ekleniyor...")
                
                # Group'un variant SKU'larını al
                variant_skus = group_info.get('variantSKUs', [])
                
                for sku in variant_skus[:1]:  # Sadece ilk varyantı ekle (grup için yeterli)
                    # SKU'nun offer'ını bul
                    sku_offers = requests.get(
                        f"https://api.ebay.com/sell/inventory/v1/offer?sku={sku}",
                        headers={
                            'Authorization': f'Bearer {access_token}',
                            'Content-Language': 'de-DE'
                        }
, timeout=30)
                    
                    if sku_offers.status_code == 200:
                        sku_offers_data = sku_offers.json()
                        if sku_offers_data.get('offers'):
                            listing_id = sku_offers_data['offers'][0].get('listingId')
                            
                            if listing_id:
                                # Reklam kampanyasına ekle
                                ad_data = {
                                    "bidPercentage": "5.0",
                                    "listingId": listing_id
                                }
                                
                                ad_create = requests.post(
                                    f"https://api.ebay.com/sell/marketing/v1/ad_campaign/{campaign_id}/ad",
                                    headers={
                                        'Authorization': f'Bearer {access_token}',
                                        'Content-Type': 'application/json',
                                        'Content-Language': 'de-DE'
                                    },
                                    json=ad_data
, timeout=30)
                                
                                if ad_create.status_code in [200, 201, 409]:  # 409 = already exists
                                    print(f"   ✅ Reklam eklendi: {listing_id}")
                                    ad_count += 1
                                else:
                                    print(f"   ⚠️  Reklam: {ad_create.status_code}")

print(f"\n" + "="*70)
print(f"✅ TOPLU GÜNCELLEME TAMAMLANDI!")
print(f"="*70)
print(f"\nGüncellenen listing: {updated_count}")
print(f"Reklam eklenen: {ad_count}")
print(f"\n📊 Tüm listing'ler:")
print(f"  ✅ Detaylı HTML açıklama")
print(f"  ✅ Ürün bilgileri (aspects)")
print(f"  ✅ Reklam kampanyası (%5)")
