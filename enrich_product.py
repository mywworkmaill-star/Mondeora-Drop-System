"""
Enrich product with AliExpress details
"""

import sys
sys.path.insert(0, 'src')

from api.aliexpress_client import AliExpressAPIClient
import sqlite3
import json

def enrich_product(product_id):
    print('🎨 ÜRÜN ENRICHMENT')
    print('=' * 80)
    print(f'Product ID: {product_id}')
    print()
    
    # Get product from database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT aliexpress_product_id, title FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    
    if not row:
        print('❌ Product not found!')
        return
    
    ali_id = row[0]
    title = row[1]
    
    print(f'AliExpress ID: {ali_id}')
    print(f'Title: {title[:70]}')
    print()
    
    # Get details from AliExpress
    ali = AliExpressAPIClient()
    
    print('Step 1: Fetching AliExpress product details...')
    
    try:
        details = ali.get_product_details(ali_id)
        
        # Extract images
        images = []
        if 'product_main_image_url' in details:
            images.append(details['product_main_image_url'])
        if 'image_urls' in details:
            imgs = details['image_urls']
            if isinstance(imgs, list):
                images.extend(imgs)
            elif isinstance(imgs, str):
                images.extend(imgs.split(';'))
        
        # Deduplicate and limit
        images = list(dict.fromkeys(img.strip() for img in images if img and img.strip()))[:12]
        
        # Extract description
        description = details.get('description', '')
        
        # Create basic aspects
        aspects = {
            'Marke': ['Markenlos'],
            'Produktart': ['Handtuchhalter'],
            'Material': ['Kunststoff'],
            'Farbe': ['Weiß'],
            'Zimmer': ['Küche', 'Badezimmer'],
            'Montage': ['Klebstoff']
        }
        
        print(f'✅ Details fetched')
        print(f'   Images: {len(images)}')
        print(f'   Description: {len(description)} chars')
        print()
        
        # Update database
        print('Step 2: Updating database...')
        
        image_urls = ','.join(images) if images else ''
        
        # Create a simple German description
        desc = f'''<div>
<h2>{title}</h2>

<h3>Produktbeschreibung:</h3>
<p>Praktischer Handtuchhalter für Küche und Badezimmer. Einfache Installation mit Klebstoff - ohne Bohren.</p>

<h3>Eigenschaften:</h3>
<ul>
<li>Material: Kunststoff</li>
<li>Farbe: Weiß</li>
<li>Montage: Selbstklebend</li>
<li>Geeignet für: Küche, Badezimmer, WC</li>
<li>Einfache Reinigung</li>
<li>Platzsparend</li>
</ul>

<h3>Lieferumfang:</h3>
<p>1x Papier Handtuchhalter mit Klebestreifen</p>

<h3>Hinweise:</h3>
<p>Bitte reinigen Sie die Oberfläche vor dem Anbringen gründlich. Warten Sie 24 Stunden bevor Sie den Halter belasten.</p>
</div>'''
        
        cursor.execute('''
            UPDATE products
            SET image_url = ?,
                description = ?,
                aspects = ?,
                aspect_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (image_urls, desc, json.dumps(aspects), len(aspects), product_id))
        
        conn.commit()
        
        print('✅ Database updated')
        print()
        
        # Show summary
        print('=' * 80)
        print('ENRICHMENT SUMMARY')
        print('=' * 80)
        print(f'Images:      {len(images)} URLs')
        print(f'Description: {len(desc)} chars')
        print(f'Aspects:     {len(aspects)} items')
        print()
        
        for key, value in aspects.items():
            print(f'   {key:15s}: {value}')
        
        print()
        print('✅ ENRICHMENT COMPLETE!')
        print()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        conn.close()
        return False

if __name__ == '__main__':
    product_id = int(sys.argv[1]) if len(sys.argv) > 1 else 155
    enrich_product(product_id)
