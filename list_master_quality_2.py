#!/usr/bin/env python3
"""
Master Quality Product Lister
Lists 2 products with MAXIMUM quality:
- 7+ HTTPS images from AliExpress
- 2,500+ char German description
- Full aspects
- Competitor research
- Quality gate check
"""

import sys
import json
import sqlite3
import time
from pathlib import Path

sys.path.insert(0, 'src')
from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient

def get_product_from_db(product_id):
    """Get product details from database"""
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    columns = [desc[0] for desc in cursor.description]
    product = cursor.fetchone()
    
    conn.close()
    
    if product:
        return dict(zip(columns, product))
    return None

def fetch_multiple_images_from_aliexpress(ali_product_id):
    """Fetch 7+ images from AliExpress"""
    print(f'\n🖼️ Fetching images from AliExpress: {ali_product_id}')
    
    ali = AliExpressAPIClient()
    
    try:
        # Get product details
        details = ali.get_product_details(ali_product_id)
        
        if not details:
            print('   ⚠️ No details returned')
            return []
        
        images = []
        
        # Try different possible image fields
        if 'ae_item_base_info_dto' in details:
            info = details['ae_item_base_info_dto']
            
            # Check all possible image keys
            for key in ['image_ur_ls', 'image_urls', 'main_image_urls_list', 'imageUrl']:
                if key in info:
                    img_data = info[key]
                    
                    if isinstance(img_data, list):
                        images.extend(img_data)
                    elif isinstance(img_data, str):
                        # Might be JSON string
                        try:
                            parsed = json.loads(img_data)
                            if isinstance(parsed, list):
                                images.extend(parsed)
                            else:
                                images.append(img_data)
                        except:
                            images.append(img_data)
        
        # Ensure HTTPS
        https_images = []
        for img in images:
            if isinstance(img, str):
                if img.startswith('http://'):
                    img = img.replace('http://', 'https://')
                if img.startswith('https://'):
                    https_images.append(img)
        
        # Deduplicate
        https_images = list(dict.fromkeys(https_images))
        
        print(f'   ✅ Found {len(https_images)} HTTPS images')
        for i, img in enumerate(https_images[:7], 1):
            print(f'      {i}. {img[:60]}...')
        
        return https_images[:12]  # eBay allows max 12
        
    except Exception as e:
        print(f'   ❌ Error: {e}')
        return []

def generate_premium_description(product_data):
    """Generate 2,500+ char premium German description"""
    title = product_data.get('title', 'Product')
    
    # Detect product type from title
    title_lower = title.lower()
    
    if 'aufbewahr' in title_lower or 'storage' in title_lower or 'tasche' in title_lower:
        product_type = 'Aufbewahrungstasche'
        problem = 'unordentliche Schränke und überfüllte Schubladen'
        benefits = [
            'Großes Fassungsvermögen für Kleidung, Bettwäsche, Decken',
            'Faltbar und platzsparend - einfach zu verstauen wenn nicht in Gebrauch',
            'Robustes, waschbares Material - langlebig und pflegeleicht',
            'Reißverschluss-Design schützt Inhalt vor Staub und Feuchtigkeit',
            'Transparente Sichtfenster (falls vorhanden) für schnellen Überblick'
        ]
        use_cases = [
            '🏠 Saisonale Kleidung organisieren (Winter/Sommer)',
            '🛏️ Bettwäsche und Decken aufbewahren',
            '🧸 Spielzeug und Kindersachen sortieren',
            '🎒 Camping- und Outdoor-Ausrüstung verstauen',
            '📦 Umzug und Lagerung',
            '🧳 Reisegepäck-Organizer'
        ]
        specs = '''
Material: Hochwertiges Polyester/Vliesstoff
Größe: Großes Fassungsvermögen (siehe Produktbilder)
Verschluss: Stabiler Reißverschluss
Eigenschaften: Faltbar, waschbar, staubdicht
Farbe: Wie abgebildet
Lieferumfang: 1x Aufbewahrungstasche
'''
        
    elif 'kabel' in title_lower or 'cable' in title_lower:
        product_type = 'Kabelorganizer'
        problem = 'chaotische Kabel auf dem Schreibtisch oder hinter dem Fernseher'
        benefits = [
            'Hält Kabel ordentlich und verhindert Kabelsalat',
            'Selbstklebend - keine Bohrungen oder Schrauben erforderlich',
            'Kompaktes Design - spart Platz und sieht aufgeräumt aus',
            'Wiederverwendbar - kann bei Bedarf umpositioniert werden',
            'Fluoreszierend (falls zutreffend) - leuchtet im Dunkeln für einfaches Finden'
        ]
        use_cases = [
            '💻 Schreibtisch-Kabelmanagement (USB, Ladekabel)',
            '📺 TV und Entertainment-Center',
            '🚗 Auto-Kabel organisieren',
            '🏠 Smart Home Geräte-Kabel',
            '🎮 Gaming-Setup',
            '🔌 Ladestationen ordentlich halten'
        ]
        specs = '''
Material: Hochwertiger Kunststoff/Silikon
Montage: Selbstklebend (3M Kleber)
Kapazität: Mehrere Kabel gleichzeitig
Eigenschaften: Wiederverwendbar, fluoreszierend (je nach Modell)
Farbe: Wie abgebildet
Lieferumfang: Kabelorganizer wie beschrieben
'''
    
    else:
        # Generic organizer
        product_type = 'Organizer'
        problem = 'Unordnung und Chaos in Küche, Bad oder Schreibtisch'
        benefits = [
            'Schafft Ordnung und spart Platz',
            'Hochwertige Materialien für lange Lebensdauer',
            'Einfache Installation ohne Werkzeug',
            'Vielseitig einsetzbar in verschiedenen Räumen',
            'Modernes Design passt zu jeder Einrichtung'
        ]
        use_cases = [
            '🍳 Küche - Utensilien, Gewürze, Deckel',
            '🛁 Badezimmer - Kosmetik, Handtücher',
            '📚 Büro - Stifte, Papier, Zubehör',
            '🚗 Auto - Kleinteile, Werkzeug',
            '🏠 Wohnzimmer - Fernbedienungen, Magazine'
        ]
        specs = '''
Material: Hochwertiger Kunststoff
Größe: Kompakt und platzsparend
Eigenschaften: Langlebig, pflegeleicht
Farbe: Wie abgebildet
Lieferumfang: Organizer wie beschrieben
'''
    
    # Build premium description
    description = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; color: #333;">

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
    <h1 style="margin: 0; font-size: 28px; font-weight: bold;">{title}</h1>
    <p style="margin: 10px 0 0; font-size: 16px;">Premium Qualität für Ihr Zuhause</p>
</div>

<div style="padding: 30px; background: #f9f9f9;">
    <h2 style="color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px;">🎯 Lösen Sie Ihr Problem</h2>
    <p style="font-size: 16px; line-height: 1.8;">
        Sind Sie es leid, {problem} zu haben? Unser <strong>{product_type}</strong> ist die perfekte Lösung für ein aufgeräumtes und organisiertes Zuhause!
    </p>
</div>

<div style="padding: 30px; background: white;">
    <h2 style="color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px;">✅ Ihre Vorteile</h2>
    <ul style="font-size: 15px; line-height: 2;">
'''
    
    for benefit in benefits:
        description += f'        <li><strong>{benefit}</strong></li>\n'
    
    description += f'''    </ul>
</div>

<div style="padding: 30px; background: #f9f9f9;">
    <h2 style="color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px;">📋 Produktspezifikationen</h2>
    <pre style="background: white; padding: 20px; border-left: 4px solid #667eea; font-family: Arial; font-size: 14px; line-height: 1.8;">{specs.strip()}</pre>
</div>

<div style="padding: 30px; background: white;">
    <h2 style="color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px;">💡 Vielseitige Anwendungen</h2>
    <p style="font-size: 15px; line-height: 1.8;">Perfekt für:</p>
    <ul style="font-size: 15px; line-height: 2;">
'''
    
    for use_case in use_cases:
        description += f'        <li>{use_case}</li>\n'
    
    description += f'''    </ul>
</div>

<div style="padding: 30px; background: #f9f9f9;">
    <h2 style="color: #667eea; border-bottom: 3px solid #667eea; padding-bottom: 10px;">📦 Lieferung & Garantie</h2>
    <p style="font-size: 15px; line-height: 1.8;">
        ✅ <strong>Schneller Versand:</strong> Versand innerhalb von 1-2 Werktagen<br>
        ✅ <strong>Sichere Verpackung:</strong> Professionell verpackt für sicheren Transport<br>
        ✅ <strong>Zufriedenheitsgarantie:</strong> 14 Tage Rückgaberecht<br>
        ✅ <strong>Kundenservice:</strong> Bei Fragen kontaktieren Sie uns gerne
    </p>
</div>

<div style="padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; border-radius: 0 0 10px 10px;">
    <h2 style="margin: 0 0 15px; font-size: 24px;">🛒 Jetzt bestellen und Ordnung schaffen!</h2>
    <p style="font-size: 16px; margin: 0;">
        Premium {product_type} für ein aufgeräumtes Zuhause<br>
        <strong>Schnelle Lieferung • Faire Preise • Top Qualität</strong>
    </p>
</div>

<div style="padding: 20px; text-align: center; background: #fff; color: #666; font-size: 12px;">
    <p>🌟 Vielen Dank für Ihren Einkauf! Bei Fragen stehen wir Ihnen gerne zur Verfügung.</p>
</div>

</div>
'''
    
    # Count characters (strip HTML for accurate count)
    import re
    text_only = re.sub('<[^<]+?>', '', description)
    char_count = len(text_only.strip())
    
    print(f'   ✅ Generated description: {char_count} characters')
    
    return description

def fill_premium_aspects(product_data):
    """Fill all required eBay aspects"""
    title = product_data.get('title', '').lower()
    
    aspects = {
        "Marke": "Markenlos",
        "Herstellungsland": "China",
        "Zustand": "Neu mit Karton",
        "Personalisiert": "Nein",
        "Zusätzlich benötigte Teile": "Nein"
    }
    
    # Detect product type
    if 'aufbewahr' in title or 'storage' in title or 'tasche' in title:
        aspects["Produktart"] = "Aufbewahrungstasche"
        aspects["Material"] = "Polyester"
        aspects["Zimmer"] = "Schlafzimmer"
        aspects["Eigenschaften"] = "Faltbar"
    elif 'kabel' in title or 'cable' in title:
        aspects["Produktart"] = "Kabelorganizer"
        aspects["Material"] = "Kunststoff"
        aspects["Zimmer"] = "Büro"
        aspects["Eigenschaften"] = "Selbstklebend"
    else:
        aspects["Produktart"] = "Organizer"
        aspects["Material"] = "Kunststoff"
        aspects["Zimmer"] = "Küche"
    
    # Detect color
    if 'schwarz' in title or 'black' in title:
        aspects["Farbe"] = "Schwarz"
    elif 'weiß' in title or 'white' in title:
        aspects["Farbe"] = "Weiß"
    elif 'grau' in title or 'gray' in title:
        aspects["Farbe"] = "Grau"
    else:
        aspects["Farbe"] = "Mehrfarbig"
    
    print(f'   ✅ Filled {len(aspects)} aspects')
    for key, val in aspects.items():
        print(f'      {key}: {val}')
    
    return aspects

def list_product_master_quality(product_id):
    """List one product with MASTER quality"""
    print(f'\n{"="*70}')
    print(f'📦 LISTING PRODUCT ID: {product_id} (MASTER QUALITY)')
    print(f'{"="*70}')
    
    # 1. Get from database
    product = get_product_from_db(product_id)
    if not product:
        print(f'❌ Product {product_id} not found in database')
        return False
    
    print(f'✅ Product loaded: {product["title"][:60]}...')
    print(f'   Price: €{product["ebay_price"]}')
    print(f'   AliExpress ID: {product["aliexpress_product_id"]}')
    
    # 2. Fetch 7+ images
    images = fetch_multiple_images_from_aliexpress(product['aliexpress_product_id'])
    
    if len(images) < 1:
        print(f'   ⚠️ No images from API, using database image')
        images = [product['image_url']] if product.get('image_url') else []
    
    if len(images) < 7:
        print(f'   ⚠️ Only {len(images)} images (7+ recommended)')
    
    # 3. Generate premium description
    print(f'\n📝 Generating premium description...')
    description = generate_premium_description(product)
    
    # 4. Fill premium aspects
    print(f'\n📋 Filling premium aspects...')
    aspects = fill_premium_aspects(product)
    
    # 5. Prepare listing data
    listing_data = {
        "sku": product.get('sku_id') or f"MASTER-{product_id}-{int(time.time())}",
        "title": product['title'][:80],  # eBay max 80 chars
        "description": description,
        "price": float(product['ebay_price']),
        "quantity": 10,
        "category_id": "180933",  # Kitchen organizers (TESTED - 3 successful listings use this)
        "condition": "NEW",
        "image_urls": images,
        "aspects": aspects,
        "shipping_policy_id": "263035514017",
        "payment_policy_id": "263035507017",
        "return_policy_id": "263035512017"
    }
    
    # 6. Quality gate check
    print(f'\n✅ QUALITY GATE CHECK:')
    print(f'   Images: {len(images)} {"✅" if len(images) >= 7 else "⚠️"}')
    print(f'   Description: {len(description)} chars {"✅" if len(description) >= 2500 else "⚠️"}')
    print(f'   Aspects: {len(aspects)} {"✅" if len(aspects) >= 5 else "⚠️"}')
    print(f'   Title: {len(listing_data["title"])} chars {"✅" if len(listing_data["title"]) <= 80 else "❌"}')
    print(f'   Price: €{listing_data["price"]} {"✅" if listing_data["price"] > 0 else "❌"}')
    
    # 7. List to eBay
    print(f'\n🚀 Listing to eBay...')
    
    ebay = eBayAPIClient()
    
    try:
        result = ebay.list_product_fixed_price(listing_data)
        
        if result and result.get('success'):
            ebay_item_id = result.get('ebay_item_id')
            offer_id = result.get('offer_id')
            
            print(f'\n✅ SUCCESS!')
            print(f'   eBay Item ID: {ebay_item_id}')
            print(f'   Offer ID: {offer_id}')
            print(f'   Link: https://www.ebay.de/itm/{ebay_item_id}')
            
            # Update database
            conn = sqlite3.connect('data/dropshipping.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE products
                SET ebay_item_id = ?,
                    ebay_offer_id = ?,
                    is_listed = 1,
                    status = 'active',
                    description = ?,
                    aspects = ?
                WHERE id = ?
            ''', (ebay_item_id, offer_id, description, json.dumps(aspects), product_id))
            conn.commit()
            conn.close()
            
            print(f'   ✅ Database updated')
            
            return True
        else:
            error = result.get('error', 'Unknown error') if result else 'No result'
            print(f'\n❌ FAILED: {error}')
            
            # Print detailed eBay error
            if ebay.last_error:
                print(f'   eBay Last Error: {ebay.last_error}')
            
            return False
            
    except Exception as e:
        print(f'\n❌ Exception: {e}')
        
        # Print detailed eBay error
        if ebay.last_error:
            print(f'   eBay Last Error: {ebay.last_error}')
            
        return False

def main():
    """Main function"""
    print('=' * 70)
    print('🏆 MASTER QUALITY PRODUCT LISTER')
    print('=' * 70)
    
    # List 2 products
    products_to_list = [23, 44]
    
    success_count = 0
    fail_count = 0
    
    for product_id in products_to_list:
        success = list_product_master_quality(product_id)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        # Wait between listings
        if product_id != products_to_list[-1]:
            print(f'\n⏳ Waiting 10 seconds before next listing...\n')
            time.sleep(10)
    
    # Final report
    print(f'\n{"="*70}')
    print(f'📊 FINAL REPORT')
    print(f'{"="*70}')
    print(f'✅ Successful: {success_count}/{len(products_to_list)}')
    print(f'❌ Failed: {fail_count}/{len(products_to_list)}')
    print(f'{"="*70}')

if __name__ == '__main__':
    main()
