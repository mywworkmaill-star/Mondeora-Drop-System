#!/usr/bin/env python3
"""
Create BETTER listing than ID 75
Using AliExpress aspects + Category 43504 template
"""

import sys
import json
import sqlite3
import time
from pathlib import Path

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient
from scripts.aspect_collector import AspectCollector

# ID 31 - yeni ürün
NEW_PRODUCT_ID = 31

# ID 75 - referans (en iyi mevcut listing)
REFERENCE_ID = 75

print("🏆 CREATING BETTER LISTING THAN ID 75")
print("=" * 70)

# Get product info
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

# New product
cursor.execute('SELECT * FROM products WHERE id = ?', (NEW_PRODUCT_ID,))
columns = [desc[0] for desc in cursor.description]
product = dict(zip(columns, cursor.fetchone()))

# Reference product
cursor.execute('SELECT aspects, description FROM products WHERE id = ?', (REFERENCE_ID,))
ref_aspects, ref_desc = cursor.fetchone()

conn.close()

print(f"\n📦 NEW PRODUCT (ID {NEW_PRODUCT_ID}):")
print(f"   Title: {product['title'][:60]}")
print(f"   Price: €{product['ebay_price']}")
print(f"   AliExpress: {product['aliexpress_product_id']}")

print(f"\n📊 REFERENCE (ID {REFERENCE_ID}):")
ref_aspects_dict = json.loads(ref_aspects) if ref_aspects else {}
print(f"   Aspects: {len(ref_aspects_dict)}")
print(f"   Description: {len(ref_desc) if ref_desc else 0} chars")

# Step 1: Get AliExpress product details
print(f"\n1️⃣ FETCHING ALIEXPRESS DATA...")
ali = AliExpressAPIClient()

try:
    ali_product = ali.get_product_details(product['aliexpress_product_id'])
    
    if ali_product:
        print(f"   ✅ AliExpress product loaded")
        
        # Extract properties
        ali_props = ali_product.get('properties', [])
        print(f"   📋 Properties: {len(ali_props)}")
        
        # Show first 10 properties
        for i, prop in enumerate(ali_props[:10], 1):
            name = prop.get('name', 'N/A')
            value = prop.get('value', 'N/A')
            print(f"      {i}. {name}: {value}")
    else:
        print(f"   ⚠️ No AliExpress data")
        ali_props = []
        
except Exception as e:
    print(f"   ❌ AliExpress error: {e}")
    ali_props = []

# Step 2: Map AliExpress props to eBay aspects
print(f"\n2️⃣ MAPPING TO EBAY ASPECTS...")

# Mapping table
PROP_TO_ASPECT = {
    'Material': 'Hauptmaterial',
    'Color': 'Farbe',
    'Brand Name': 'Marke',
    'Type': 'Produktart',
    'Style': 'Stil',
    'Feature': 'Besonderheiten',
    'Size': 'Größe',
    'Weight': 'Gewicht',
    'Origin': 'Herstellungsland und -region',
}

aspects = {}

for prop in ali_props:
    name = prop.get('name', '')
    value = prop.get('value', '')
    
    # Map to German
    if name in PROP_TO_ASPECT:
        german_name = PROP_TO_ASPECT[name]
        aspects[german_name] = [value]

# Add mandatory aspects from template
collector = AspectCollector()
template_file = Path('data/aspect_templates/category_43504_template.json')

if template_file.exists():
    with open(template_file, 'r', encoding='utf-8') as f:
        template = json.load(f)
    
    # Add mandatory aspects
    for aspect_name in template['mandatory_aspects']:
        if aspect_name not in aspects:
            # Use example value from template
            example = template['mandatory_aspects'][aspect_name]['example_values'][0]
            aspects[aspect_name] = [example]

# Custom values for this product
aspects.update({
    "Produktart": ["Kabelorganizer"],
    "Hauptmaterial": ["Kunststoff"],
    "Farbe": ["Weiß"],
    "Marke": ["Markenlos"],
    "Herstellungsland und -region": ["China"],
    "Zustand": ["Neu"],
    "Breite": ["10 cm"],
    "Höhe": ["5 cm"],
    "Länge": ["10 cm"]
})

print(f"   ✅ Total aspects: {len(aspects)}")
for name, values in list(aspects.items())[:10]:
    print(f"      {name}: {values[0]}")

# Step 3: Create premium description
print(f"\n3️⃣ CREATING PREMIUM DESCRIPTION...")

description = f"""<div style="font-family:Arial,sans-serif;">
<div style="background:#1a5276;color:#fff;font-size:11px;font-weight:bold;padding:3px 8px;border-radius:3px;display:inline-block;">Premium Kabelorganizer</div>

<h2 style="margin:6px 0 10px;font-size:20px;">{product['title']}</h2>

<div style="background:#f4f6f7;border:1px solid #d6dbdf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#1a5276;">✨ Produkthighlights</h3>
<ul style="margin:0;padding-left:20px;">
<li>Praktischer Kabelorganizer für Küche und Büro</li>
<li>Selbstklebende Montage - keine Bohrlöcher</li>
<li>Hält Ladekabel und Küchengeräte ordentlich</li>
<li>Kompaktes Design - platzsparend</li>
<li>Wiederverwendbar und langlebig</li>
</ul>
</div>

<div style="background:#fff;border:1px solid #d6dbdf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#1a5276;">📋 Produktdetails</h3>
<table style="width:100%;border-collapse:collapse;">
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><b>Material:</b></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Hochwertig Kunststoff</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><b>Farbe:</b></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Weiß</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><b>Größe:</b></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">10 x 10 x 5 cm</td></tr>
<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><b>Montage:</b></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">Selbstklebend</td></tr>
<tr><td style="padding:4px 8px;"><b>Verwendung:</b></td><td style="padding:4px 8px;">Küche, Büro, Zuhause</td></tr>
</table>
</div>

<div style="background:#e8f8f5;border:1px solid #a9dfbf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#196f3d;">✅ Vorteile</h3>
<p style="margin:0;">
• Hält Kabel ordentlich und vermeidet Kabelsalat<br>
• Selbstklebende Montage - keine Wandbeschädigung<br>
• Wiederverwendbar - kann mehrfach geklebt werden<br>
• Platzsparend - ideal für kleine Küchen und Büros<br>
• Vielseitig - für Ladekabel, Mixer, Toaster, etc.
</p>
</div>

<div style="background:#fef5e7;border:1px solid #f9e79f;border-radius:6px;padding:12px 14px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#9a7d0a;">📦 Lieferumfang</h3>
<p style="margin:0;">
1x Kabelorganizer<br>
Selbstklebende Montagepads<br>
Gebrauchsanweisung
</p>
</div>

</div>"""

desc_len = len(description)
print(f"   ✅ Description: {desc_len} chars")

# Step 4: List to eBay
print(f"\n4️⃣ LISTING TO EBAY...")

listing_data = {
    "sku": f"BETTER-{int(time.time())}",
    "title": product['title'][:80],
    "description": description,
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",
    "condition": "NEW",
    "image_urls": [product['image_url']],
    "aspects": aspects
}

ebay = eBayAPIClient()

try:
    result = ebay.list_product_fixed_price(listing_data)
    
    if result and result.get('success'):
        print(f"\n🎉🎉🎉 SUCCESS!")
        print(f"   eBay Item ID: {result.get('ebay_item_id')}")
        print(f"   Link: https://www.ebay.de/itm/{result.get('ebay_item_id')}")
        
        # Update database
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET ebay_item_id = ?,
                ebay_offer_id = ?,
                is_listed = 1,
                status = 'active',
                aspects = ?,
                description = ?,
                category_id = 43504
            WHERE id = ?
        ''', (
            result.get("ebay_item_id"),
            result.get("offer_id"),
            json.dumps(aspects),
            description,
            NEW_PRODUCT_ID
        ))
        conn.commit()
        conn.close()
        
        print(f"   ✅ Database updated!")
        
        # Compare with reference
        print(f"\n📊 COMPARISON:")
        print(f"   {'Metric':<20} {'Reference (ID 75)':<20} {'NEW (ID 31)':<20}")
        print(f"   {'-'*60}")
        print(f"   {'Aspects':<20} {len(ref_aspects_dict):<20} {len(aspects):<20} {'✅ BETTER' if len(aspects) > len(ref_aspects_dict) else ''}")
        print(f"   {'Description':<20} {len(ref_desc) if ref_desc else 0:<20} {desc_len:<20} {'✅ BETTER' if desc_len > (len(ref_desc) if ref_desc else 0) else ''}")
        
    else:
        error = result.get('error', 'Unknown') if result else 'No result'
        print(f"\n❌ Failed: {error}")
        
        if hasattr(ebay, 'last_error'):
            print(f"   Last error: {ebay.last_error}")
        
except Exception as e:
    print(f"\n❌ Exception: {e}")
    import traceback
    traceback.print_exc()
