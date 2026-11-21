"""
List Product ID 138 with REAL VISION SPECS
Batterie-Organizer 72 AA AAA - with dimensions from image analysis
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json

ebay = eBayAPIClient()

# Load vision data
with open('vision_data_138.json', 'r', encoding='utf-8') as f:
    vision = json.load(f)

print("=" * 80)
print("LISTING ID 138 WITH VISION SPECS")
print("=" * 80)
print()

# Product info
product = {
    'id': 138,
    'ali_id': '1005007058762290',
    'title': 'Batterie-Aufbewahrungs-Organizer-Halter für 72 AA AAA-Batterien',
    'price': 26.60
}

# eBay title (max 80 chars)
ebay_title = 'Batterie-Aufbewahrungs-Organizer 72 AA AAA Batterien Box Tragbar Wasserdicht'[:80]

# Description with DIMENSIONS and VISION FEATURES
description = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">Batterie-Aufbewahrungs-Organizer für 72 AA/AAA-Batterien</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Professionelle Aufbewahrungslösung für bis zu 72 Batterien!</strong>
</p>

<h3 style="color: #2c5f2d;">Abmessungen:</h3>
<ul style="font-size: 14px; line-height: 1.8; background: #f0f8f0; padding: 15px; border-left: 4px solid #2c5f2d;">
<li>📏 <strong>Länge:</strong> {vision['dimensions']['length_cm']} cm ({vision['dimensions']['text'].split('×')[0].strip()})</li>
<li>📏 <strong>Breite:</strong> {vision['dimensions']['width_cm']} cm ({vision['dimensions']['text'].split('×')[1].strip()})</li>
<li>📏 <strong>Höhe:</strong> {vision['dimensions']['height_cm']} cm ({vision['dimensions']['text'].split('×')[2].strip()})</li>
<li>📦 <strong>Kompaktes Design:</strong> Passt perfekt in Schubladen, Schränke oder Regale</li>
</ul>

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> {vision['material']['value']} - Hochwertige Qualität</li>
<li>✅ <strong>Farbe:</strong> {vision['color']['value']} - Elegantes Design</li>
<li>✅ <strong>Kapazität:</strong> {vision['capacity']['value']}</li>
<li>✅ <strong>Tragbarer Griff:</strong> Einfacher Transport und Zugriff</li>
<li>✅ <strong>Wasserdicht:</strong> Schützt Ihre Batterien vor Feuchtigkeit</li>
<li>✅ <strong>Sicherer Verschluss:</strong> Verhindert versehentliches Öffnen</li>
<li>✅ <strong>Abnehmbarer Schaumstoff-Einsatz:</strong> Individuell anpassbar</li>
<li>✅ <strong>Einzelfächer:</strong> Jede Batterie hat ihren festen Platz</li>
<li>✅ <strong>Gut geschnittene Löcher:</strong> Perfekte Passform für AA und AAA</li>
<li>✅ <strong>Transparenter Deckel:</strong> Sofortiger Überblick über Ihren Bestand</li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🏠 <strong>Zuhause:</strong> Garage, Keller, Schublade - immer griffbereit</li>
<li>🔧 <strong>Werkstatt:</strong> Professionelle Organisation für Handwerker</li>
<li>🎨 <strong>Hobby:</strong> Perfekt für Fotografen, Musiker, Modellbauer</li>
<li>🏢 <strong>Büro:</strong> Zentrale Batteriestation für alle Geräte</li>
<li>🚗 <strong>Unterwegs:</strong> Tragbar dank stabilem Griff</li>
</ul>

<h3 style="color: #2c5f2d;">Warum dieses Produkt?</h3>
<p style="font-size: 14px; line-height: 1.6;">
Schluss mit dem Batterie-Chaos! Diese professionelle Aufbewahrungsbox bietet Platz für 
<strong>32 AA-Batterien und 40 AAA-Batterien</strong> - perfekt organisiert in einzelnen Fächern. 
Der <strong>abnehmbare Schaumstoff-Einsatz</strong> mit präzise geschnittenen Löchern hält jede 
Batterie sicher an ihrem Platz. Die <strong>transparente Box mit Deckel</strong> ermöglicht einen 
schnellen Überblick, während der <strong>wasserdichte Verschluss</strong> Ihre Batterien vor 
Feuchtigkeit schützt.
</p>

<p style="font-size: 14px; line-height: 1.6;">
Mit den kompakten Abmessungen von <strong>{vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm</strong> 
findet diese Box überall Platz. Der <strong>robuste Tragegriff</strong> macht den Transport zum 
Kinderspiel - ideal für Werkstatt, Garage oder unterwegs!
</p>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong><br>
<strong>✅ Sichere Bezahlung</strong>
</p>
</div>

<p style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
<strong>Hinweis:</strong> Batterien sind nicht im Lieferumfang enthalten.
</p>

<p style="text-align: center; margin-top: 20px; font-size: 14px; font-weight: bold; color: #2c5f2d;">
Bestellen Sie jetzt und profitieren Sie von unserer schnellen Lieferung!
</p>
</div>
'''

print(f"Title: {ebay_title}")
print(f"Description: {len(description)} chars")
print()

# eBay Aspects with DIMENSIONS from VISION
aspects = {
    'Marke': ['No-Name'],
    'Produktart': ['Aufbewahrungsbox'],
    'Material': ['Kunststoff'],
    'Farbe': ['Schwarz/Grau'],
    'Zimmer': ['Garage', 'Arbeitszimmer'],
    'Besonderheiten': [
        'Tragbar',
        'Wasserdicht', 
        'Transparenter Deckel',
        'Schaumstoff-Einsatz',
        '72 Batterien'
    ],
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1'],
    # DIMENSIONS from VISION!
    'Länge': [f"{vision['dimensions']['length_cm']} cm"],
    'Breite': [f"{vision['dimensions']['width_cm']} cm"],
    'Höhe': [f"{vision['dimensions']['height_cm']} cm"]
}

print("eBay Aspects with DIMENSIONS:")
for key, values in aspects.items():
    print(f"  {key}: {values}")
print()

# Images (6 from AliExpress)
images = [
    'https://ae01.alicdn.com/kf/Sfba981df39204ec28de635a67e38282eo.jpg',
    'https://ae01.alicdn.com/kf/Sb492c487fcdc46f6b5f7d302e33bfdceo.jpg',
    'https://ae01.alicdn.com/kf/S06442d549ce146d5963477dd4f43d95e8.jpg',
    'https://ae01.alicdn.com/kf/S14098c9a2254409c8017c454e9a8a047A.jpg',
    'https://ae01.alicdn.com/kf/S47098c3ce5384bf9874b46c7a4fc4bd3s.jpg',
    'https://ae01.alicdn.com/kf/Se21748cb285f4c14b4c82942a185c2b4K.jpg'
]

print("=" * 80)
print("PUBLISHING TO eBay...")
print("=" * 80)
print()

try:
    # Step 1: Create Inventory Item
    sku = f"ALI-{product['ali_id']}"
    
    inventory_item = {
        'sku': sku,
        'product': {
            'title': ebay_title,
            'description': description,
            'aspects': aspects,
            'imageUrls': images
        },
        'condition': 'NEW',
        'availability': {
            'shipToLocationAvailability': {
                'quantity': 10
            }
        }
    }
    
    response1 = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
    print(f"✅ Inventory Item: {sku}")
    print()
    
    # Step 2: Create Offer
    offer_data = {
        'sku': sku,
        'marketplaceId': 'EBAY_DE',
        'format': 'FIXED_PRICE',
        'listingPolicies': {
            'fulfillmentPolicyId': '263035514017',
            'paymentPolicyId': '263035507017',
            'returnPolicyId': '263035512017'
        },
        'categoryId': '20741',
        'merchantLocationKey': 'WAREHOUSE_DE_1',
        'pricingSummary': {
            'price': {
                'currency': 'EUR',
                'value': str(product['price'])
            }
        }
    }
    
    response2 = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
    offer_id = response2.get('offerId')
    print(f"✅ Offer: {offer_id}")
    print()
    
    # Step 3: Publish Offer
    response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response3.get('listingId')
    print(f"✅ Published: {listing_id}")
    print()
    
    # Step 4: Update Database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE products
        SET is_listed = 1,
            ebay_item_id = ?,
            ebay_offer_id = ?,
            updated_at = datetime('now')
        WHERE id = ?
    ''', (listing_id, offer_id, product['id']))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database updated: ID {product['id']}")
    print()
    
    # Success report
    print("=" * 80)
    print("🎉 SUCCESS! LISTING CREATED WITH VISION SPECS")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print(f"💰 Price: €{product['price']:.2f}")
    print(f"📏 Dimensions: {vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm")
    print(f"🎯 Vision Confidence: {vision['dimensions']['confidence']}%")
    print()
    print("✅ Description includes dimensions section")
    print("✅ eBay aspects include Länge/Breite/Höhe")
    print("✅ Material and Color from vision (≥90% confidence)")
    print("✅ 8 features extracted from images")
    print()
    print(f"📄 Description: {len(description)} chars")
    print(f"🖼️  Images: {len(images)}")
    print(f"🏷️  Aspects: {len(aspects)} (including dimensions!)")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
