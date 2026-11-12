"""
Açıklamaya görselleri ekle - eBay-compatible HTML TABLE formatında
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

print("="*70)
print("GÖRSELLER AÇIKLAMAYA EKLENİYOR")
print("="*70)

group_key = "GROUP-1005013457960792"

# eBay-compatible HTML - TABLE based, inline styles
html_template = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f5f5f5;">
<div style="max-width:900px;margin:0 auto;background:white;">

<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:40px 20px;text-align:center;">
<h1 style="font-size:32px;margin:0 0 10px 0;">📱 Premium iPhone Hülle</h1>
<p style="font-size:18px;margin:0;">Kamera Schutz • Matt Finish • Stoßfest • MagSafe</p>
</div>

<div style="background:#fff3cd;padding:25px;margin:20px;border-radius:10px;border:3px solid #ffc107;">
<h2 style="color:#ff6b6b;margin:0 0 20px 0;text-align:center;">🎨 WÄHLEN SIE IHRE VARIANTE</h2>
<p style="text-align:center;margin:20px 0 0 0;padding:15px;background:#ff6b6b;color:white;border-radius:5px;font-weight:bold;">⚠️ Bitte wählen Sie oben Ihr Modell und Ihre Farbe aus!</p>
</div>

<div style="padding:20px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 15px 0;border-left:4px solid #667eea;padding-left:15px;">📸 Produkt Galerie</h2>
<table width="100%" cellpadding="5" cellspacing="0">
<tr>
<td width="33%" align="center"><img src="{img0}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{img1}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{img2}" width="250" style="border-radius:8px;max-width:100%;"></td>
</tr>
<tr>
<td width="33%" align="center"><img src="{img3}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{img4}" width="250" style="border-radius:8px;max-width:100%;"></td>
<td width="33%" align="center"><img src="{img5}" width="250" style="border-radius:8px;max-width:100%;"></td>
</tr>
</table>
</div>

<div style="padding:30px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;border-left:4px solid #667eea;padding-left:15px;">✨ Premium Features</h2>
<table width="100%" cellpadding="10" cellspacing="0">
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🎯</div>
<h3 style="font-size:16px;color:#333;margin:8px 0;">Kamera-Schutz</h3>
<p style="color:#666;font-size:14px;margin:0;">Erhöhter Rand schützt vor Kratzern</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">💎</div>
<h3 style="font-size:16px;color:#333;margin:8px 0;">Matt Finish</h3>
<p style="color:#666;font-size:14px;margin:0;">Premium Design, keine Fingerabdrücke</p>
</div>
</td>
</tr>
<tr>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">🧲</div>
<h3 style="font-size:16px;color:#333;margin:8px 0;">MagSafe Kompatibel</h3>
<p style="color:#666;font-size:14px;margin:0;">Kabelloses Laden problemlos</p>
</div>
</td>
<td width="50%" style="vertical-align:top;">
<div style="background:#f8f9fa;padding:20px;border-radius:8px;border-left:4px solid #667eea;">
<div style="font-size:24px;">💪</div>
<h3 style="font-size:16px;color:#333;margin:8px 0;">Stoßfest</h3>
<p style="color:#666;font-size:14px;margin:0;">TPU-Silikon schützt bei Stürzen</p>
</div>
</td>
</tr>
</table>
</div>

<div style="padding:30px;">
<h2 style="color:#667eea;font-size:24px;margin:0 0 20px 0;border-left:4px solid #667eea;padding-left:15px;">📋 Spezifikationen</h2>
<table width="100%" cellpadding="12" cellspacing="0" style="background:#f8f9fa;border-radius:8px;">
<tr style="border-bottom:1px solid #e0e0e0;">
<td style="font-weight:600;width:40%;">Material</td>
<td>Premium TPU Silikon</td>
</tr>
<tr style="border-bottom:1px solid #e0e0e0;">
<td style="font-weight:600;">Dicke</td>
<td>1,0 mm</td>
</tr>
<tr style="border-bottom:1px solid #e0e0e0;">
<td style="font-weight:600;">Gewicht</td>
<td>ca. 15g</td>
</tr>
<tr style="border-bottom:1px solid #e0e0e0;">
<td style="font-weight:600;">Kameraschutz</td>
<td>Erhöhter Rand 0,5mm</td>
</tr>
<tr style="border-bottom:1px solid #e0e0e0;">
<td style="font-weight:600;">MagSafe</td>
<td>✓ Kompatibel</td>
</tr>
<tr>
<td style="font-weight:600;">Farben</td>
<td>Braun, Himmelblau</td>
</tr>
</table>
</div>

<div style="background:#e7f3ff;padding:25px;">
<table width="100%" cellpadding="10">
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

# Görselleri ekle
html_description = html_template.format(
    img0=all_images[0],
    img1=all_images[1],
    img2=all_images[2],
    img3=all_images[3],
    img4=all_images[4],
    img5=all_images[5]
)

try:
    # Group'u güncelle
    print("\n1. Inventory Item Group güncelleniyor...")
    print(f"\n6 görsel ekleniyor:")
    for i, img in enumerate(all_images[:6], 1):
        print(f"   {i}. {img[:70]}...")
    
    group_update = requests.put(
        f"https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}",
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Content-Language': 'de-DE'
        },
        json={
            "title": "iPhone Hülle Pro Max Kamera Schutz Matt Case Silikon Stoßfest MagSafe",
            "description": html_description,
            "imageUrls": all_images[:12],
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
            "variesBy": {
                "specifications": [
                    {
                        "name": "Farbe",
                        "values": ["Braun", "Himmelblau"]
                    },
                    {
                        "name": "Kompatibles Modell",
                        "values": [
                            "Für Apple iPhone 18 Pro Max",
                            "Für Apple Iphone 16 pro max",
                            "Für Apple Iphone 15 pro max"
                        ]
                    }
                ]
            },
            "variantSKUs": [
                "VAR-1005013457960792-1",
                "VAR-1005013457960792-2",
                "VAR-1005013457960792-3",
                "VAR-1005013457960792-4",
                "VAR-1005013457960792-5",
                "VAR-1005013457960792-6"
            ]
        }, timeout=30
    )
    
    if group_update.status_code in [200, 204]:
        print("\n" + "="*70)
        print("✅ GÖRSELLER AÇIKLAMAYA EKLENDİ!")
        print("="*70)
        print(f"\neBay Link: https://www.ebay.de/itm/860125267161")
        print(f"\n📸 6 görsel galeri eklendi")
        print(f"✨ Premium features eklendi")
        print(f"📋 Spezifikasyon tablosu eklendi")
        print(f"\n⏳ eBay'in işlemesi 1-2 dakika sürebilir")
        print(f"Sonra tarayıcıyı yenile ve kontrol et!")
    else:
        print(f"\n⚠️  Hata: {group_update.status_code}")
        print(f"{group_update.text[:500]}")

except Exception as e:
    print(f"\n❌ HATA: {str(e)}")
    import traceback
    traceback.print_exc()
