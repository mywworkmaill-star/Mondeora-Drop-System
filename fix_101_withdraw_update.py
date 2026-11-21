"""
FIX ID 101 - Method 2: Withdraw → Update → Republish
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

print("=" * 80)
print("ID 101 HEIGHT CORRECTION - METHOD 2")
print("WITHDRAW → UPDATE → REPUBLISH")
print("=" * 80)
print()

offer_id = '366088237011'
sku = 'ALI-1005009723070135'

# =============================================================================
# STEP 1: WITHDRAW OFFER (Unpublish)
# =============================================================================

print("STEP 1: Withdrawing offer (unpublishing listing)...")
print(f"Offer ID: {offer_id}")
print()

try:
    response1 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/withdraw')
    
    print("✅ Offer withdrawn successfully!")
    print("   Listing is now OFFLINE")
    print()
    
except Exception as e:
    print(f"⚠️  Withdraw error: {str(e)}")
    print("   (May already be withdrawn or not published)")
    print()

# =============================================================================
# STEP 2: UPDATE INVENTORY ITEM with correct height
# =============================================================================

print("STEP 2: Updating inventory item with correct height...")
print(f"SKU: {sku}")
print()

# Get current inventory item
try:
    current = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
    
    print("✅ Current inventory item found")
    print()
    
    # Get current aspects
    aspects = current.get('product', {}).get('aspects', {})
    
    print(f"Current dimensions:")
    print(f"  Länge: {aspects.get('Länge', ['Not set'])}")
    print(f"  Breite: {aspects.get('Breite', ['Not set'])}")
    print(f"  Höhe: {aspects.get('Höhe', ['Not set'])}")
    print()
    
    # Update Höhe to 3cm
    aspects['Höhe'] = ['3 cm']
    
    # Update Besonderheiten
    besonderheiten = aspects.get('Besonderheiten', [])
    # Remove old height mentions
    besonderheiten = [b for b in besonderheiten if '13cm' not in b]
    # Add ultra-flat mention
    if 'Ultra-Flach 3cm' not in besonderheiten:
        besonderheiten.append('Ultra-Flach 3cm')
    aspects['Besonderheiten'] = besonderheiten[:10]
    
    print("CORRECTED dimensions:")
    print(f"  Länge: {aspects['Länge']}")
    print(f"  Breite: {aspects['Breite']}")
    print(f"  Höhe: {aspects['Höhe']} ← CORRECTED!")
    print()
    
    # Update description with correct height
    description = '''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
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
<li>✅ <strong>Papiertuch-Halter</strong></li>
<li>✅ <strong>Schneidebrett-Aufhängung</strong></li>
<li>✅ <strong>6-8 Haken</strong></li>
<li>✅ <strong>Platzsparend</strong></li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🍳 <strong>Küche</strong> - Unter Hängeschränken</li>
<li>🛁 <strong>Badezimmer</strong> - Handtuch-Organisation</li>
<li>🧺 <strong>Waschküche</strong> - Reinigungs-Utensilien</li>
</ul>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong><br>
<strong>✅ Sichere Bezahlung</strong>
</p>
</div>
</div>
'''
    
    # Get images
    images = current.get('product', {}).get('imageUrls', [])
    
    # Update inventory item
    update_data = {
        'sku': sku,
        'product': {
            'title': current.get('product', {}).get('title'),
            'description': description,
            'aspects': aspects,
            'imageUrls': images
        },
        'condition': 'NEW',
        'availability': current.get('availability', {})
    }
    
    print("Updating inventory item...")
    
    response2 = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=update_data)
    
    print("✅ Inventory item updated with correct height!")
    print()
    
except Exception as e:
    print(f"❌ Update error: {str(e)}")
    import traceback
    traceback.print_exc()
    print()
    exit(1)

# =============================================================================
# STEP 3: REPUBLISH OFFER
# =============================================================================

print("STEP 3: Republishing offer...")
print()

try:
    response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
    
    listing_id = response3.get('listingId')
    
    print("✅ Offer republished!")
    print(f"   eBay Item ID: {listing_id}")
    print()
    
    # Update database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE products
        SET ebay_item_id = ?,
            updated_at = datetime('now')
        WHERE id = 101
    ''', (listing_id,))
    
    conn.commit()
    conn.close()
    
    print("✅ Database updated")
    print()
    
except Exception as e:
    print(f"❌ Republish error: {str(e)}")
    import traceback
    traceback.print_exc()
    print()
    exit(1)

# =============================================================================
# FINAL RESULT
# =============================================================================

print("=" * 80)
print("🎉 ID 101 HEIGHT CORRECTION COMPLETE!")
print("=" * 80)
print()
print(f"🔗 eBay Link: https://www.ebay.de/itm/{listing_id}")
print()
print("CORRECTED:")
print("  ❌ Old: Höhe = 13 cm")
print("  ✅ New: Höhe = 3 cm")
print()
print("✅ Changes now LIVE on eBay.de!")
print()
print("NOTE: Listing was temporarily offline during update.")
print("      It is now back ONLINE with correct dimensions.")
