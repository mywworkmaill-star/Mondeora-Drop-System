"""List product ID 142 - simplified version"""
import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime

ebay = eBayAPIClient()
product_id = 142
ali_product_id = '1005006422575102'

print('=' * 80)
print(f'ID {product_id} - EBAY LİSTELEME (Simplified)')
print('=' * 80)
print()

# Get product from database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('SELECT title, aliexpress_price, shipping_cost, ebay_price, image_url FROM products WHERE id = ?', (product_id,))
row = cursor.fetchone()

if not row:
    print(f'❌ ID {product_id} not found')
    exit(1)

title, ali_price, shipping, ebay_price, image_url = row
images = image_url.split(',')

print(f'Title: {title}')
print(f'Price: €{ebay_price:.2f}')
print(f'Images: {len(images)}')
print()

# Simple German description
description_html = '''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">Ohuhu Bambus Marker-Organizer aus Holz</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Premium Schreibtisch-Organizer für bis zu 126 Marker!</strong>
</p>

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>126-Marker Kapazität</strong> - Perfekt für große Marker-Sammlungen</li>
<li>✅ <strong>Premium Bambus-Holz</strong> - Natürlich, stabil und langlebig</li>
<li>✅ <strong>Stapelbar & Kombinierbar</strong> - Flexibles Erweiterungssystem</li>
<li>✅ <strong>10+ Reihen</strong> - Übersichtliche Organisation</li>
<li>✅ <strong>Platzsparend</strong> - Optimale Nutzung des Schreibtischs</li>
<li>✅ <strong>Multifunktional</strong> - Für Marker, Stifte, Bleistifte, Kunstpinsel</li>
<li>✅ <strong>Elegantes Design</strong> - Natürliche Bambus-Optik</li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🎨 Künstler und Hobbyzeichner</li>
<li>🏫 Klassenzimmer und Kunstunterricht</li>
<li>🖥️ Büro und Home-Office</li>
<li>🏠 Bastelzimmer</li>
</ul>

<h3 style="color: #2c5f2d;">Material & Qualität:</h3>
<p style="font-size: 14px; line-height: 1.6;">
Hergestellt aus hochwertigem <strong>Bambus-Holz</strong> in natürlicher Farbe. 
Bambus ist besonders stabil, umweltfreundlich und langlebig.
</p>

<h3 style="color: #2c5f2d;">Lieferumfang:</h3>
<p style="font-size: 14px;">1× Bambus Marker-Organizer (Marker nicht im Lieferumfang enthalten)</p>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong>
</p>
</div>
</div>
'''

print(f'Description: {len(description_html)} chars')
print()

# eBay aspects
aspects = {
    'Marke': ['Ohuhu'],
    'Produktart': ['Schreibtisch-Organizer'],
    'Material': ['Bambus-Holz'],
    'Farbe': ['Natur'],
    'Zimmer': ['Arbeitszimmer'],
    'Besonderheiten': ['126-Marker Kapazität', 'Stapelbar', 'Multifunktional'],
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1']
}

# eBay title (80 chars)
ebay_title = 'Ohuhu Bambus Marker-Organizer Holz Schreibtisch 126-Marker Stifthalter'

print(f'Title: {ebay_title} ({len(ebay_title)} chars)')
print()

# Publish
print('Publishing to eBay...')
print()

try:
    sku = f'ALI-{ali_product_id}'
    
    # Inventory item
    inventory_item = {
        'sku': sku,
        'product': {
            'title': ebay_title,
            'description': description_html,
            'aspects': aspects,
            'imageUrls': images[:8]
        },
        'condition': 'NEW',
        'availability': {
            'shipToLocationAvailability': {
                'quantity': 10
            }
        }
    }
    
    ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
    print(f'✅ Inventory item: {sku}')
    
    # Offer
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
                'value': str(ebay_price)
            }
        }
    }
    
    response2 = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
    offer_id = response2.get('offerId')
    print(f'✅ Offer: {offer_id}')
    
    # Publish
    response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response3.get('listingId')
    print(f'✅ Published: {listing_id}')
    print()
    
    # Update database
    cursor.execute('''
        UPDATE products
        SET is_listed = 1,
            ebay_item_id = ?,
            ebay_offer_id = ?,
            listed_at = ?,
            updated_at = ?
        WHERE id = ?
    ''', (listing_id, offer_id, datetime.now().isoformat(), datetime.now().isoformat(), product_id))
    
    conn.commit()
    print('✅ Database updated')
    print()
    
    cost = ali_price + shipping
    profit = ebay_price - cost - (ebay_price * 0.11)
    
    print('=' * 80)
    print('✅ LİSTELEME TAMAMLANDI!')
    print('=' * 80)
    print()
    print(f'🔗 https://www.ebay.de/itm/{listing_id}')
    print(f'💰 €{ebay_price:.2f} (Maliyet: €{cost:.2f}, Kar: €{profit:.2f})')
    print()
    
except Exception as e:
    print(f'❌ Error: {str(e)}')
    import traceback
    traceback.print_exc()

conn.close()
