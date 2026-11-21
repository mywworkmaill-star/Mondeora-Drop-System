"""Update all ready_to_list products with 3.1x markup (212% above cost)"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

# Get all ready_to_list products
cursor.execute('''
    SELECT 
        id,
        aliexpress_product_id,
        title,
        aliexpress_price,
        shipping_cost,
        ebay_price
    FROM products
    WHERE status = 'ready_to_list'
    AND is_listed = 0
    AND aliexpress_price IS NOT NULL
    AND aliexpress_price > 0
    ORDER BY id
''')

products = cursor.fetchall()

print('=' * 80)
print('TOPLU FİYAT GÜNCELLEMESİ - 3.1x MARKUP (%212)')
print('=' * 80)
print()
print(f'Toplam: {len(products)} ürün')
print()

if len(products) == 0:
    print('⚠️  Güncellenecek ürün bulunamadı')
    conn.close()
    exit(0)

updated = 0
errors = 0

print('GÜNCELLENİYOR...')
print('-' * 80)
print()

for pid, ali_id, title, ali_price, shipping, old_ebay_price in products:
    try:
        # Calculate new price with 3.1x markup
        cost = float(ali_price) + float(shipping or 0)
        new_price = round(cost * 3.1, 2)
        
        # Calculate profit
        fee = new_price * 0.11
        profit = new_price - cost - fee
        
        # Update database
        cursor.execute('''
            UPDATE products
            SET ebay_price = ?,
                updated_at = ?
            WHERE id = ?
        ''', (new_price, datetime.now().isoformat(), pid))
        
        # Print update
        old_price_str = f'€{old_ebay_price:.2f}' if old_ebay_price else 'NULL'
        
        print(f'✅ ID {pid}: {old_price_str} → €{new_price:.2f} (Tedarik: €{cost:.2f}, Kar: €{profit:.2f})')
        
        updated += 1
        
    except Exception as e:
        print(f'❌ ID {pid}: Hata - {str(e)}')
        errors += 1

# Commit changes
conn.commit()
conn.close()

print()
print('=' * 80)
print('ÖZET:')
print('=' * 80)
print()
print(f'✅ Güncellenen:  {updated} ürün')
print(f'❌ Hata:         {errors} ürün')
print()
print('🎯 Tüm ürünler artık 3.1x markup ile fiyatlandırıldı!')
print('   (Tedarikten %212 daha fazla)')
print()
