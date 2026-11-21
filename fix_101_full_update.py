"""
Update inventory item with FULL data, then publish offer
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

sku = 'ALI-1005009723070135'
new_offer_id = '366157002011'

print("=" * 80)
print("STEP 1: UPDATE INVENTORY ITEM WITH FULL DATA")
print("=" * 80)
print()

# Get product from database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT title, image_url, ebay_price
    FROM products
    WHERE id = 101
''')

result = cursor.fetchone()
title, images_str, price = result

images = images_str.split(',')[:8] if images_str else []

print(f"Title: {title[:60]}...")
print(f"Images: {len(images)}")
print(f"Price: €{price}")
print()

# Create proper eBay title (max 80 chars)
ebay_title = ' '.join(title.split()[:12])[:80]

print(f"eBay Title: {ebay_title}")
print()

# Description with correct height
description = '''<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">Küche Hängen Organizer Rack</h2>
<h3 style="color: #2c5f2d;">Abmessungen:</h3>
<ul style="font-size: 14px; line-height: 1.8; background: #f0f8f0; padding: 15px; border-left: 4px solid #2c5f2d;">
<li>📏 <strong>Länge:</strong> 26.5 cm</li>
<li>📏 <strong>Breite:</strong> 27.5 cm (ausziehbar 25-30 cm)</li>
<li>📏 <strong>Höhe:</strong> 3 cm (ultra-flach!)</li>
</ul>
<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> Metall (Schwarz)</li>
<li>✅ <strong>Clip & Go Montage</strong> - Werkzeuglos</li>
<li>✅ <strong>Verstellbar</strong> - 25-30cm Breite</li>
<li>✅ <strong>Ultra-Flach</strong> - Nur 3cm Höhe</li>
<li>✅ <strong>6-8 Haken</strong></li>
</ul>
<h3 style="color: #2c5f2d;">Ideal für Küche, Bad, Garage</h3>
<div style="background: #f0f8f0; padding: 15px; margin-top: 20px;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong>
</p>
</div>
</div>'''

# Aspects
aspects = {
    'Marke': ['No-Name'],
    'Produktart': ['Aufbewahrungsbox'],
    'Material': ['Metall'],
    'Farbe': ['Schwarz'],
    'Zimmer': ['Küche'],
    'Besonderheiten': ['Ausziehbar', 'Clip & Go', 'Verstellbar', 'Werkzeuglos', 'Haken', 'Platzsparend'],
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1'],
    'Länge': ['26.5 cm'],
    'Breite': ['27.5 cm'],
    'Höhe': ['3 cm']
}

# Update inventory item
inventory_data = {
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

print("Updating inventory item with FULL data...")

try:
    ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_data)
    print("✅ Inventory item updated!")
    print()
except Exception as e:
    print(f"❌ Update failed: {str(e)}")
    conn.close()
    exit(1)

# =============================================================================
# STEP 2: PUBLISH OFFER
# =============================================================================

print("=" * 80)
print("STEP 2: PUBLISH OFFER")
print("=" * 80)
print()
print(f"Offer ID: {new_offer_id}")
print()

try:
    response = ebay._request('POST', f'/sell/inventory/v1/offer/{new_offer_id}/publish')
    
    listing_id = response.get('listingId')
    
    print(f"✅ Offer published!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    # Update database
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            ebay_offer_id = ?,
            updated_at = datetime('now')
        WHERE id = 101
    ''', (listing_id, new_offer_id))
    
    conn.commit()
    
    print("✅ Database updated")
    print()
    
    print("=" * 80)
    print("🎉 ID 101 - LISTING NOW LIVE!")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print()
    print("Dimensions: 26.5 × 27.5 × 3 cm ✓")
    
except Exception as e:
    print(f"❌ Publish failed: {str(e)}")
    
finally:
    conn.close()
