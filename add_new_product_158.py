"""Add new product and list with upgraded vision system (all 6 images analyzed)."""
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
import sqlite3
import json
from datetime import datetime

# Initialize
ali = AliExpressAPIClient()
ebay = eBayAPIClient()

ali_product_id = '1005010037299480'  # 6-Pack Adjustable Drawer Organizer

print('=' * 80)
print('YENİ ÜRÜN EKLEME VE LİSTELEME - UPGRADED VİSİON SİSTEMİYLE')
print('=' * 80)
print()
print(f'AliExpress ID: {ali_product_id}')
print()

# Step 1: Get product details
print('Step 1: AliExpress ürün detayları çekiliyor...')
try:
    details = ali.get_product_details(ali_product_id)
    
    if not details:
        print('❌ Ürün detayları alınamadı')
        exit(1)
    
    title = details.get('product_title', '')
    price = details.get('price', 0)
    shipping = details.get('shipping_cost', 0)
    images_str = details.get('image_urls', '')
    
    print(f'✅ Title: {title[:70]}...')
    print(f'   Price: €{price}')
    print(f'   Shipping: €{shipping}')
    
    # Images
    if images_str:
        images = images_str.split(';')
        print(f'   Images: {len(images)} adet')
    else:
        print('❌ Görsel bulunamadı')
        exit(1)
    
    # Calculate eBay price
    cost = float(price) + float(shipping)
    ebay_price = round(cost * 2.5, 2)
    profit = round(ebay_price - cost - (ebay_price * 0.11), 2)
    
    print()
    print(f'💰 Maliyet: €{cost:.2f}')
    print(f'💵 eBay Fiyat: €{ebay_price:.2f}')
    print(f'💵 Kar: €{profit:.2f}')
    print()
    
    if profit < 10:
        print(f'⚠️  Kar çok düşük (€{profit:.2f}), yine de devam ediliyor...')
    
except Exception as e:
    print(f'❌ Hata: {str(e)}')
    exit(1)

# Step 2: Add to database
print('Step 2: Database\'e ekleniyor...')

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

try:
    cursor.execute('''
        INSERT INTO products (
            aliexpress_product_id,
            title,
            aliexpress_price,
            shipping_cost,
            ebay_price,
            image_url,
            status,
            created_at,
            updated_at,
            is_listed,
            currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ali_product_id,
        title,
        price,
        shipping,
        ebay_price,
        ','.join(images),  # Comma-separated for upgraded vision
        'ready_to_list',
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        0,
        'EUR'
    ))
    
    new_id = cursor.lastrowid
    conn.commit()
    
    print(f'✅ Ürün eklendi - Database ID: {new_id}')
    print()

except sqlite3.IntegrityError:
    print('⚠️  Ürün zaten database\'de')
    cursor.execute('SELECT id FROM products WHERE aliexpress_product_id = ?', (ali_product_id,))
    new_id = cursor.fetchone()[0]
    print(f'   Mevcut ID: {new_id}')
    print()

conn.close()

print('=' * 80)
print('✅ PHASE 1 TAMAMLANDI - Ürün database\'de')
print('=' * 80)
print()
print(f'Product ID: {new_id}')
print(f'Images: {len(images)} adet (comma-separated)')
print()
print('⏭️  NEXT: Upgraded vision analysis (all 6 images)')
print('   Bu adım Hermes context\'te çalışmalı (vision_analyze tool)')
print()
print('Komut:')
print(f'   python analyze_and_publish_{new_id}.py')
