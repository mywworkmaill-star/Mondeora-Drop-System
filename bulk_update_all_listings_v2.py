"""
KOLAY TOPLU GÜNCELLEME
Tüm listing'lere otomatik: açıklama + ürün bilgileri + reklam
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
print("TOPLU LİSTİNG GÜNCELLEMESİ - V2")
print("="*70)

# Manuel listing listesi (şimdilik)
# Yeni listing ekledikçe buraya ekle
listings_to_update = [
    {
        "group_key": "GROUP-1005013457960792",
        "listing_id": "860125267161",
        "name": "iPhone Hülle Pro Max"
    }
    # Yeni listing ekledikçe buraya ekle:
    # {
    #     "group_key": "GROUP-XXXXX",
    #     "listing_id": "XXXXXX",
    #     "name": "Ürün Adı"
    # }
]

print(f"\n✅ {len(listings_to_update)} listing güncellenecek")

# Campaign kontrolü
campaign_id = "168739871017"  # Mevcut campaign

updated_count = 0
ad_count = 0

for item in listings_to_update:
    group_key = item['group_key']
    listing_id = item['listing_id']
    name = item['name']
    
    print(f"\n{'='*70}")
    print(f"📦 {name}")
    print(f"{'='*70}")
    
    # Group detayını al
    group_get = requests.get(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Language': 'de-DE'
        }
, timeout=30)
    
    if group_get.status_code == 200:
        group_data = group_get.json()
        image_urls = group_data.get('imageUrls', [])
        
        # Detaylı HTML açıklama
        html_desc = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial;background:#f5f5f5;margin:0;padding:0;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">📱 {name}</h1>
<p style="font-size:18px;margin:0;">Premium Qualität • Schneller Versand • 30 Tage Rückgabe</p>
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
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;border-left:4px solid #667eea;padding-left:15px;">✨ Premium Features</h2>
<table width="100%" cellpadding="10">
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🎯</div>
<h3 style="font-size:16px;margin:8px 0;">Premium Qualität</h3>
<p style="font-size:14px;color:#666;margin:0;">Hochwertige Verarbeitung und Materialien</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🚚</div>
<h3 style="font-size:16px;margin:8px 0;">Schneller Versand</h3>
<p style="font-size:14px;color:#666;margin:0;">Lieferung in 24-48 Stunden</p>
</div>
</td>
</tr>
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">💎</div>
<h3 style="font-size:16px;margin:8px 0;">Top Design</h3>
<p style="font-size:14px;color:#666;margin:0;">Modernes, stilvolles Design</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🛡️</div>
<h3 style="font-size:16px;margin:8px 0;">Garantie</h3>
<p style="font-size:14px;color:#666;margin:0;">30 Tage Rückgaberecht</p>
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
        
        # Açıklamayı güncelle
        print(f"\n1. Açıklama güncelleniyor...")
        
        update_payload = group_data.copy()
        update_payload['description'] = html_desc
        
        group_update = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=update_payload
, timeout=30)
        
        if group_update.status_code in [200, 204]:
            print(f"   ✅ Açıklama güncellendi ({len(image_urls)} görsel)")
            updated_count += 1
        else:
            print(f"   ⚠️  {group_update.status_code}")
        
        # Reklam kampanyasına ekle
        print(f"\n2. Reklam kampanyasına ekleniyor...")
        
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
        
        if ad_create.status_code in [200, 201, 409]:
            status = "zaten var" if ad_create.status_code == 409 else "eklendi"
            print(f"   ✅ Reklam {status}")
            ad_count += 1
        else:
            print(f"   ⚠️  {ad_create.status_code}")

print(f"\n" + "="*70)
print(f"✅ TOPLU GÜNCELLEME TAMAMLANDI!")
print(f"="*70)
print(f"\n📊 Sonuçlar:")
print(f"  • Güncellenen: {updated_count} listing")
print(f"  • Reklam: {ad_count} listing")
print(f"\n✅ Tüm listing'lerde:")
print(f"  ✅ Detaylı HTML açıklama (görselli)")
print(f"  ✅ Premium features")
print(f"  ✅ Reklam kampanyası (%5)")
print(f"\n📝 YENİ ÜRÜN EKLEDİĞİNDE:")
print(f"  1. Scriptin üstüne yeni listing bilgilerini ekle")
print(f"  2. Çalıştır: python bulk_update_all_listings_v2.py")
print(f"  3. Otomatik her şey eklenir!")
