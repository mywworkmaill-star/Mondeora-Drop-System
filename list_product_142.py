"""List product ID 142 with vision-enhanced aspects (no dimensions found)"""
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
from description_generator.master_generator import generate_description
import sqlite3
import json
from datetime import datetime

ebay = eBayAPIClient()

# ID 142 bilgileri
product_id = 142
ali_product_id = '1005006422575102'

print('=' * 80)
print(f'ID {product_id} - EBAY LİSTELEME')
print('=' * 80)
print()

# Database'den ürün bilgilerini al
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT 
        title,
        aliexpress_price,
        shipping_cost,
        ebay_price,
        image_url
    FROM products
    WHERE id = ?
''', (product_id,))

row = cursor.fetchone()

if not row:
    print(f'❌ ID {product_id} bulunamadı')
    exit(1)

title, ali_price, shipping, ebay_price, image_url = row

print(f'Title: {title}')
print(f'Price: €{ebay_price:.2f}')
print()

# Images
images = image_url.split(',')
print(f'Images: {len(images)} adet')

# Vision results (from manual analysis)
vision_aspects = {
    'Material': ['Bambus-Holz'],
    'Farbe': ['Natur'],
    'Besonderheiten': ['126-Marker Kapasität', 'Stapelbar', 'Schreibtisch', '10+ Reihen', 'Multifunktional']
}

print()
print('Vision Aspects:')
for key, values in vision_aspects.items():
    print(f'  {key}: {", ".join(values)}')
print()

# Generate German description
print('Step 1: Description oluşturuluyor...')

description_data = {
    'product_name': 'Ohuhu Bambus-Marker-Organizer aus Holz',
    'category': 'Schreibtisch-Organizer',
    'material': 'Bambus-Holz',
    'color': 'Natur',
    'features': [
        '126-Marker Kapasität',
        '10+ Reihen für perfekte Organisation',
        'Stapelbar und kombinierbar',
        'Platzsparendes Design',
        'Premium Bambus-Holz',
        'Für Marker, Stifte, Bleistifte',
        'Perfekt für Schreibtisch',
        'Stabil und langlebig'
    ],
    'benefits': [
        'Hält bis zu 126 Marker organisiert',
        'Spart Platz auf dem Schreibtisch',
        'Natürliches Bambus-Material',
        'Einfach zu stapeln und erweitern',
        'Professionell und elegant'
    ]
}

try:
    desc_html = generate_description(description_data, target_length=2500)
    desc_length = len(desc_html)
    
    print(f'✅ Description: {desc_length} chars')
    print()
    
except Exception as e:
    print(f'❌ Description error: {str(e)}')
    # Fallback simple description
    desc_html = f'''
<div style="font-family: Arial; max-width: 800px; margin: 0 auto;">
<h2>{description_data["product_name"]}</h2>
<p><strong>Premium Bambus-Holz Marker-Organizer für perfekte Ordnung!</strong></p>
<ul>
{''.join([f"<li>{feat}</li>" for feat in description_data["features"]])}
</ul>
<p>Material: {description_data["material"]}<br>Farbe: {description_data["color"]}</p>
</div>
'''
    desc_length = len(desc_html)
    print(f'✅ Fallback description: {desc_length} chars')
    print()

# Prepare eBay aspects (German format, arrays)
aspects = {
    'Marke': ['Ohuhu'],
    'Produktart': ['Schreibtisch-Organizer'],
    'Material': vision_aspects['Material'],
    'Farbe': vision_aspects['Farbe'],
    'Zimmer': ['Arbeitszimmer', 'Schlafzimmer', 'Wohnzimmer'],
    'Besonderheiten': vision_aspects['Besonderheiten'][:3],  # Max 3
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1']
}

print('eBay Aspects:')
for key, values in aspects.items():
    print(f'  {key}: {values}')
print()

# eBay title (80 chars max)
ebay_title = 'Ohuhu Bambus Marker-Organizer Holz Schreibtisch 126-Marker Stifthalter'[:80]

print(f'eBay Title: {ebay_title} ({len(ebay_title)} chars)')
print()

# Publish to eBay
print('Step 2: eBay\'e publish ediliyor...')
print()

try:
    # Create inventory item
    sku = f'ALI-{ali_product_id}'
    
    inventory_item = {
        'sku': sku,
        'product': {
            'title': ebay_title,
            'description': desc_html,
            'aspects': aspects,
            'imageUrls': images[:8]  # Max 8
        },
        'condition': 'NEW',
        'availability': {
            'shipToLocationAvailability': {
                'quantity': 10
            }
        }
    }
    
    # Create/update inventory item
    response1 = ebay._request(
        'PUT',
        f'/sell/inventory/v1/inventory_item/{sku}',
        json=inventory_item
    )
    
    print(f'✅ Inventory item created: {sku}')
    
    # Create offer
    offer_data = {
        'sku': sku,
        'marketplaceId': 'EBAY_DE',
        'format': 'FIXED_PRICE',
        'listingPolicies': {
            'fulfillmentPolicyId': '263035514017',
            'paymentPolicyId': '263035507017',
            'returnPolicyId': '263035512017'
        },
        'categoryId': '20741',  # Home Organization
        'merchantLocationKey': 'WAREHOUSE_DE_1',
        'pricingSummary': {
            'price': {
                'currency': 'EUR',
                'value': str(ebay_price)
            }
        }
    }
    
    response2 = ebay._request(
        'POST',
        '/sell/inventory/v1/offer',
        json=offer_data
    )
    
    offer_id = response2.get('offerId')
    
    print(f'✅ Offer created: {offer_id}')
    
    # Publish offer
    response3 = ebay._request(
        'POST',
        f'/sell/inventory/v1/offer/{offer_id}/publish'
    )
    
    listing_id = response3.get('listingId')
    
    print(f'✅ Published! eBay Item ID: {listing_id}')
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
    
    print('=' * 80)
    print('✅ LİSTELEME TAMAMLANDI!')
    print('=' * 80)
    print()
    print(f'🔗 eBay Link: https://www.ebay.de/itm/{listing_id}')
    print(f'💰 Fiyat: €{ebay_price:.2f}')
    print(f'💵 Kar: €{ebay_price - ali_price - shipping - (ebay_price * 0.11):.2f}')
    print()
    
except Exception as e:
    print(f'❌ eBay publish error: {str(e)}')
    import traceback
    traceback.print_exc()

conn.close()
