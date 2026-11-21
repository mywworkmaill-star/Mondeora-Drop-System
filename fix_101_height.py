"""
FIX ID 101 - Correct height from 13cm to 3cm on eBay
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

print("=" * 80)
print("ID 101 HEIGHT CORRECTION: 13cm → 3cm")
print("=" * 80)
print()

# Get product info
cursor.execute('SELECT aliexpress_product_id, title, ebay_price FROM products WHERE id = 101')
result = cursor.fetchone()
ali_id, title, price = result

sku = f'ALI-{ali_id}'
ebay_title = ' '.join(title.split()[:12])[:80]

print(f"SKU: {sku}")
print(f"Title: {ebay_title}")
print(f"Price: €{price}")
print()

# CORRECTED Description with 3cm height
description = '''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">Küche Hängen Organizer Rack mit Haken</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Praktische Aufbewahrungslösung für Ihre Küche - Ultra-Flaches Design!</strong>
</p>

<h3 style="color: #2c5f2d;">Abmessungen (Produktmaße):</h3>
<ul style="font-size: 14px; line-height: 1.8; background: #f0f8f0; padding: 15px; border-left: 4px solid #2c5f2d;">
<li>📏 <strong>Länge (Tiefe):</strong> 26.5 cm</li>
<li>📏 <strong>Breite:</strong> 27.5 cm (ausziehbar 25-30 cm für flexible Anpassung)</li>
<li>📏 <strong>Höhe:</strong> 3 cm (ultra-flaches, kompaktes Design)</li>
<li>📦 <strong>Kompaktes Design:</strong> Nur 3cm Höhe - perfekt unter Küchenschränken</li>
</ul>

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> Metall (beschichteter Stahl) - Hochwertige Qualität</li>
<li>✅ <strong>Farbe:</strong> Schwarz - Elegantes Design</li>
<li>✅ <strong>Kapazität:</strong> 6-8 Haken für vielseitige Nutzung</li>
<li>✅ <strong>Verstellbare Montage-Clips</strong> - Passt an verschiedene Schrankbreiten</li>
<li>✅ <strong>Ausziehbar 25-30cm</strong> - Flexible Anpassung</li>
<li>✅ <strong>Clip & Go - Werkzeuglose Montage</strong> - Einfach einklemmen, keine Bohrungen!</li>
<li>✅ <strong>Papiertuch-Halter</strong> - Praktischer Abroller integriert</li>
<li>✅ <strong>Schneidebrett-Aufhängung</strong> - Platzsparende Lagerung</li>
<li>✅ <strong>Utensilien-Haken</strong> - Für Kochlöffel, Pfannenwender, etc.</li>
<li>✅ <strong>Mehrfach-Ebenen (2-3 Regale)</strong> - Maximale Raumnutzung</li>
<li>✅ <strong>Ultra-Flach (3cm)</strong> - Stört nicht, passt überall</li>
<li>✅ <strong>Für kleine Küchen</strong> - Optimale Platznutzung</li>
<li>✅ <strong>Platzsparend</strong> - Vertikaler Stauraum</li>
<li>✅ <strong>Langlebig</strong> - Robuste Metall-Konstruktion</li>
<li>✅ <strong>Pflegeleicht</strong> - Einfach abwischbar</li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🍳 <strong>Küche</strong> - Unter Hängeschränken</li>
<li>🛁 <strong>Badezimmer</strong> - Handtuch-Organisation</li>
<li>🧺 <strong>Waschküche</strong> - Reinigungs-Utensilien</li>
<li>🔧 <strong>Garage</strong> - Werkzeug-Aufhängung</li>
<li>🖥️ <strong>Arbeitszimmer</strong> - Schreibtisch-Organisation</li>
</ul>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<h3 style="color: #2c5f2d; margin-top: 0;">Warum dieses Produkt?</h3>
<p style="margin: 0; font-size: 14px;">
✅ <strong>Werkzeuglose Montage</strong> - In Sekunden installiert<br>
✅ <strong>Kompakte Größe (26.5 × 27.5 × 3 cm)</strong> - Ultra-flach<br>
✅ <strong>Verstellbar & Ausziehbar</strong> - Passt zu jedem Schrank<br>
✅ <strong>Vielseitig einsetzbar</strong> - Küche, Bad, Garage<br>
✅ <strong>Platzsparend</strong> - Vertikale Lagerung<br>
✅ <strong>Stabile Konstruktion</strong> - Trägt schwere Gegenstände
</p>
</div>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong><br>
<strong>✅ Sichere Bezahlung</strong>
</p>
</div>

<p style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
Bestellen Sie jetzt und profitieren Sie von unserer schnellen Lieferung!
</p>
</div>
'''

# CORRECTED Aspects with 3cm height
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
        'Papiertuch-Halter',
        'Schneidebrett',
        'Haken',
        'Platzsparend',
        'Ultra-Flach 3cm'
    ],
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1'],
    'Länge': ['26.5 cm'],
    'Breite': ['27.5 cm'],
    'Höhe': ['3 cm']  # ✅ CORRECTED: 13cm → 3cm
}

print("CORRECTED DIMENSIONS:")
print(f"  Länge: {aspects['Länge']}")
print(f"  Breite: {aspects['Breite']}")
print(f"  Höhe: {aspects['Höhe']} ← CORRECTED!")
print()

try:
    # Step 1: Update inventory item
    print("Step 1: Updating inventory item...")
    
    # Check description length
    desc_len = len(description)
    print(f"Description length: {desc_len} chars")
    
    if desc_len > 4000:
        print(f"⚠️  WARNING: Description too long! Trimming to 4000 chars...")
        description = description[:3997] + '...'
    
    inventory_item = {
        'sku': sku,
        'product': {
            'title': ebay_title,
            'description': description,
            'aspects': aspects
        }
    }
    
    response1 = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
    print(f"✅ Inventory updated: {sku}")
    print()
    
except Exception as e:
    print(f"❌ Error during inventory update: {str(e)}")
    
    # Try to get error details
    if hasattr(e, 'response') and hasattr(e.response, 'text'):
        import json as json_lib
        try:
            error_data = json_lib.loads(e.response.text)
            print("\neBay Error Details:")
            print(json_lib.dumps(error_data, indent=2))
        except:
            print(f"\nRaw error: {e.response.text[:500]}")
    
    print("\n⚠️  Trying simplified update (aspects only)...")
    
    try:
        # Try updating just aspects (no description change)
        simple_item = {
            'sku': sku,
            'product': {
                'aspects': aspects
            }
        }
        
        response1 = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=simple_item)
        print(f"✅ Aspects updated (description unchanged)")
        print()
    except Exception as e2:
        print(f"❌ Simplified update also failed: {str(e2)}")
        import traceback
        traceback.print_exc()
        conn.close()
        exit(1)

try:
    
    # Step 2: Republish offer
    offer_id = '366088237011'
    
    print(f"Step 2: Republishing offer {offer_id}...")
    
    response2 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    listing_id = response2.get('listingId')
    
    print(f"✅ Offer republished!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    # Step 3: Update database
    print("Step 3: Updating database...")
    
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            updated_at = datetime('now')
        WHERE id = 101
    ''', (listing_id,))
    
    conn.commit()
    
    print(f"✅ Database updated")
    print()
    
    print("=" * 80)
    print("✅ ID 101 HEIGHT CORRECTION COMPLETE!")
    print("=" * 80)
    print()
    print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
    print()
    print("CORRECTED:")
    print("  ❌ Old: Höhe = 13 cm")
    print("  ✅ New: Höhe = 3 cm")
    print()
    print("Changes now LIVE on eBay.de!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
