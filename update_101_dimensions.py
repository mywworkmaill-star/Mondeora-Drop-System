"""
Update ID 101 eBay Listing with DIMENSIONS
Add Länge/Breite/Höhe to description and aspects
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
import json

ebay = eBayAPIClient()

# Load vision data
with open('vision_data_101.json', 'r', encoding='utf-8') as f:
    vision = json.load(f)

print("=" * 80)
print("UPDATING ID 101 WITH DIMENSIONS")
print("=" * 80)
print()

# Product info
product = {
    'id': 101,
    'ali_id': '1005009723070135',
    'title': 'Küche Hängen Organizer Rack mit Haken Unter Schrank',
    'price': 25.67,
    'ebay_item': '860160910067'
}

print(f"eBay Item: {product['ebay_item']}")
print(f"Dimensions: {vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm")
print()

# Enhanced description with DIMENSIONS
description = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">Küche Hängen Organizer Rack mit Haken</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Praktische Aufhängungslösung für Ihre Küche - platzsparend unter dem Schrank!</strong>
</p>

<h3 style="color: #2c5f2d;">Abmessungen:</h3>
<ul style="font-size: 14px; line-height: 1.8; background: #f0f8f0; padding: 15px; border-left: 4px solid #2c5f2d;">
<li>📏 <strong>Länge (Tiefe):</strong> {vision['dimensions']['length_cm']} cm</li>
<li>📏 <strong>Breite:</strong> {vision['dimensions']['width_cm']} cm (ausziehbar 25-30 cm)</li>
<li>📏 <strong>Höhe:</strong> {vision['dimensions']['height_cm']} cm</li>
<li>📦 <strong>Kompaktes Design:</strong> Perfekt für kleine Küchen und unter Schränken</li>
</ul>

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> {vision['material']['value']} - Hochwertige Qualität</li>
<li>✅ <strong>Farbe:</strong> {vision['color']['value']} - Elegantes Design</li>
<li>✅ <strong>Kapazität:</strong> {vision['capacity']['value']} für Utensilien</li>
<li>✅ <strong>Verstellbare Montage-Clips:</strong> Passt verschiedene Schrankdicken</li>
<li>✅ <strong>Ausziehbar:</strong> 25-30 cm Breite individuell anpassbar</li>
<li>✅ <strong>Clip & Go Montage:</strong> Werkzeuglose Installation in Sekunden</li>
<li>✅ <strong>Papiertuch-Halter:</strong> Integrierter Rollenhalter</li>
<li>✅ <strong>Schneidebrett-Aufhängung:</strong> Praktische Haken für Bretter</li>
<li>✅ <strong>Utensilien-Haken:</strong> Mehrere Haken für Küchenhelfer</li>
<li>✅ <strong>Mehrfach-Ebenen:</strong> 2-3 Regale für optimale Raumnutzung</li>
<li>✅ <strong>Platzsparend:</strong> Ideal für kleine Küchen und begrenzte Arbeitsflächen</li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🍳 <strong>Kleine Küchen:</strong> Maximiert Stauraum unter Schränken</li>
<li>🏠 <strong>Wohnungen:</strong> Platzsparende Lösung ohne Bohren</li>
<li>🔧 <strong>Mietwohnungen:</strong> Keine permanenten Wandbefestigungen nötig</li>
<li>📦 <strong>Organisierte Küche:</strong> Alles griffbereit und übersichtlich</li>
<li>🎓 <strong>Studentenwohnheime:</strong> Einfach montierbar und wieder entfernbar</li>
</ul>

<h3 style="color: #2c5f2d;">Warum dieses Produkt?</h3>
<p style="font-size: 14px; line-height: 1.6;">
Diese intelligente Aufhängungslösung nutzt den ungenutzten Raum unter Ihren Küchenschränken optimal aus. 
Mit der <strong>werkzeuglosen Clip & Go Montage</strong> ist die Installation in Sekunden erledigt - ohne Bohren, 
ohne Schrauben! Die <strong>verstellbaren Montage-Clips</strong> passen sich verschiedenen Schrankdicken an, 
während die <strong>ausziehbare Breite von 25-30 cm</strong> perfekte Flexibilität bietet.
</p>

<p style="font-size: 14px; line-height: 1.6;">
Mit den kompakten Abmessungen von <strong>{vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm</strong> 
passt dieses Rack perfekt unter jeden Standard-Küchenschrank. Die <strong>robuste Metall-Konstruktion</strong> 
in elegantem Schwarz hält Papiertücher, Schneidebretter, Küchenutensilien und mehr - alles griffbereit 
und platzsparend organisiert!
</p>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong><br>
<strong>✅ Sichere Bezahlung</strong>
</p>
</div>

<p style="text-align: center; margin-top: 20px; font-size: 14px; font-weight: bold; color: #2c5f2d;">
Bestellen Sie jetzt und profitieren Sie von unserer schnellen Lieferung!
</p>
</div>
'''

print(f"Description: {len(description)} chars")
print()

# eBay title (keep existing)
ebay_title = 'Küche Hängen Organizer Rack mit Haken Unter Schrank Papier Halter'

# Enhanced aspects with DIMENSIONS
aspects = {
    'Marke': ['No-Name'],
    'Produktart': ['Aufbewahrungsbox'],
    'Material': ['Metall'],
    'Farbe': ['Schwarz'],
    'Zimmer': ['Küche'],
    'Besonderheiten': [
        'Ausziehbar',
        'Clip & Go',
        'Verstellbar',
        'Werkzeuglos',
        'Platzsparend'
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

# Images (existing 6 from database)
images = [
    'https://ae01.alicdn.com/kf/Sca39a48649f1440eb142f8383c49cb812.png',
    'https://ae01.alicdn.com/kf/S2814d0e8a6174ef489ffe47c62c66158f.png',
    'https://ae01.alicdn.com/kf/S8744fb895a524d2ba0d1c1a0e1184e819.png',
    'https://ae01.alicdn.com/kf/S8b2ae964e66549de8fa76a711111c779F.png',
    'https://ae01.alicdn.com/kf/S9926a152561945ff8d3b19156da15ee1g.jpg',
    'https://ae01.alicdn.com/kf/S405a7fe58e0a48ea82641a67ade640e3d.jpg'
]

print("=" * 80)
print("UPDATING eBay LISTING...")
print("=" * 80)
print()

try:
    # Get existing offer ID
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT ebay_offer_id FROM products WHERE id = 101')
    result = cursor.fetchone()
    offer_id = result[0] if result else None
    conn.close()
    
    if not offer_id:
        print("⚠️  Offer ID not found in database, searching via API...")
        # Get offer from inventory item
        sku = f"ALI-{product['ali_id']}"
        
        try:
            # Get offers for this SKU
            response = ebay._request('GET', f'/sell/inventory/v1/offer?sku={sku}')
            offers = response.get('offers', [])
            
            if offers:
                offer_id = offers[0]['offerId']
                print(f"✅ Found Offer ID: {offer_id}")
            else:
                print("❌ No offers found for this SKU")
                offer_id = None
        except Exception as e:
            print(f"❌ Error finding offer: {str(e)}")
            offer_id = None
    
    if not offer_id:
        print()
        print("⚠️  Cannot update without Offer ID")
        print("   Creating NEW listing instead...")
        print()
        
        # Create new inventory item
        sku = f"ALI-{product['ali_id']}-V2"
        
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
        
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
        print(f"✅ Inventory Item: {sku}")
        
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
        new_offer_id = response2.get('offerId')
        print(f"✅ Offer: {new_offer_id}")
        
        response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{new_offer_id}/publish')
        new_listing_id = response3.get('listingId')
        print(f"✅ Published: {new_listing_id}")
        
        print()
        print("=" * 80)
        print("🎉 NEW LISTING CREATED WITH DIMENSIONS!")
        print("=" * 80)
        print()
        print(f"🔗 eBay: https://www.ebay.de/itm/{new_listing_id}")
        print(f"💰 Price: €{product['price']:.2f}")
        print(f"📏 Dimensions: {vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm ✅")
        print()
        print("✅ Description includes Abmessungen section")
        print("✅ eBay aspects include Länge/Breite/Höhe")
        print(f"📄 Description: {len(description)} chars")
        print(f"🏷️  Aspects: {len(aspects)} (including dimensions!)")
        
    else:
        print(f"✅ Found Offer ID: {offer_id}")
        print()
        
        # Update existing inventory item
        sku = f"ALI-{product['ali_id']}"
        
        inventory_item = {
            'product': {
                'title': ebay_title,
                'description': description,
                'aspects': aspects,
                'imageUrls': images
            },
            'availability': {
                'shipToLocationAvailability': {
                    'quantity': 10
                }
            }
        }
        
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
        print(f"✅ Inventory Item Updated: {sku}")
        
        # Republish offer to reflect changes
        ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
        print(f"✅ Offer Republished: {offer_id}")
        
        print()
        print("=" * 80)
        print("🎉 LISTING UPDATED WITH DIMENSIONS!")
        print("=" * 80)
        print()
        print(f"🔗 eBay: https://www.ebay.de/itm/{product['ebay_item']}")
        print(f"💰 Price: €{product['price']:.2f}")
        print(f"📏 Dimensions: {vision['dimensions']['length_cm']} × {vision['dimensions']['width_cm']} × {vision['dimensions']['height_cm']} cm ✅")
        print()
        print("✅ Description updated with Abmessungen section")
        print("✅ eBay aspects updated with Länge/Breite/Höhe")
        print(f"📄 Description: {len(description)} chars")
        print(f"🏷️  Aspects: {len(aspects)} (including dimensions!)")
    
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
