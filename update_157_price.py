"""Update ID 157 eBay price from €36.99 to €22.99"""
import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

# ID 157 bilgileri
product_id = 157
ebay_item_id = '860159069263'
offer_id = '365176523011'

old_price = 36.99
new_price = 22.99

print('=' * 80)
print('ID 157 - FİYAT GÜNCELLEMESİ')
print('=' * 80)
print()
print(f'eBay Item ID: {ebay_item_id}')
print(f'Offer ID:     {offer_id}')
print()
print(f'Eski Fiyat:   €{old_price:.2f}')
print(f'Yeni Fiyat:   €{new_price:.2f}')
print(f'İndirim:      -€{old_price - new_price:.2f} ({((old_price - new_price) / old_price * 100):.0f}%)')
print()

# Step 1: Update offer via API
print('Step 1: eBay offer fiyatı güncelleniyor...')

try:
    # Update offer price
    update_data = {
        'offerId': offer_id,
        'pricingSummary': {
            'price': {
                'currency': 'EUR',
                'value': str(new_price)
            }
        }
    }
    
    response = ebay._request(
        'PUT',
        f'/sell/inventory/v1/offer/{offer_id}',
        json=update_data
    )
    
    print(f'   ✅ eBay offer güncellendi: {offer_id}')
    print()
    
except Exception as e:
    print(f'   ⚠️ Hata: {str(e)}')
    print('   Manuel güncelleme gerekebilir (Seller Hub)')
    print()

# Step 2: Update database
print('Step 2: Database güncelleniyor...')

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

try:
    cursor.execute('''
        UPDATE products
        SET ebay_price = ?,
            updated_at = datetime('now')
        WHERE id = ?
    ''', (new_price, product_id))
    
    conn.commit()
    
    print(f'   ✅ Database güncellendi: ID {product_id}')
    print()
    
except Exception as e:
    print(f'   ❌ Database hatası: {str(e)}')
    print()

conn.close()

# Step 3: Verify
print('Step 3: Doğrulama...')
print()

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT 
        ebay_price,
        aliexpress_price,
        shipping_cost
    FROM products
    WHERE id = ?
''', (product_id,))

row = cursor.fetchone()
conn.close()

if row:
    db_price, ali_price, shipping = row
    cost = ali_price + (shipping or 0)
    fee = db_price * 0.11
    profit = db_price - cost - fee
    markup = ((db_price - cost) / cost) * 100
    
    print('=' * 80)
    print('✅ GÜNCELLENMİŞ FİYATLANDIRMA:')
    print('=' * 80)
    print()
    print(f'Tedarik:          €{cost:.2f}')
    print(f'eBay Fiyat:       €{db_price:.2f}')
    print(f'eBay Fee (11%):   -€{fee:.2f}')
    print(f'─────────────────────────────')
    print(f'NET KAR:          €{profit:.2f} ✅')
    print()
    print(f'Tedarikten:       %{markup:.0f} daha fazla ({db_price/cost:.1f}x)')
    print()
    print(f'🔗 eBay Link: https://www.ebay.de/itm/{ebay_item_id}')
    print('   (Fiyat değişikliği 5-10 dakika içinde görünür)')
    print()

print('=' * 80)
print('✅ TAMAMLANDI!')
print('=' * 80)
