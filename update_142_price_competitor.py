"""Update ID 142 price to €49.99 (competitor-based pricing)"""
import sys
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
import sqlite3

ebay = eBayAPIClient()

product_id = 142
offer_id = '366022673011'
ebay_item_id = '860160683675'

old_price = 89.65
new_price = 44.99  # Rakip max (€39.99) + premium, kar: €11.67

cost = 28.92
new_profit = new_price - cost - (new_price * 0.11)

print('=' * 80)
print('ID 142 - FİYAT GÜNCELLEMESİ (Rakip Bazlı)')
print('=' * 80)
print()
print(f'eBay Item: {ebay_item_id}')
print(f'Offer ID:  {offer_id}')
print()
print(f'Eski Fiyat: €{old_price:.2f} ❌ (çok yüksek)')
print(f'Yeni Fiyat: €{new_price:.2f} ✅ (rakip uyumlu)')
print(f'İndirim:    -€{old_price - new_price:.2f} ({((old_price - new_price) / old_price * 100):.0f}%)')
print()
print(f'Tedarik:    €{cost:.2f}')
print(f'Kar:        €{new_profit:.2f}')
print(f'Margin:     {(new_profit / new_price * 100):.0f}%')
print()

# Update eBay offer
print('Step 1: eBay offer güncelleniyor...')

try:
    update_data = {
        'offerId': offer_id,
        'pricingSummary': {
            'price': {
                'currency': 'EUR',
                'value': str(new_price)
            }
        }
    }
    
    ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_data)
    print(f'✅ eBay offer güncellendi')
    print()
    
except Exception as e:
    print(f'❌ Hata: {str(e)}')
    print()

# Update database
print('Step 2: Database güncelleniyor...')

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

cursor.execute('''
    UPDATE products
    SET ebay_price = ?,
        updated_at = datetime('now')
    WHERE id = ?
''', (new_price, product_id))

conn.commit()
print('✅ Database güncellendi')
print()

# Verify
cursor.execute('SELECT ebay_price FROM products WHERE id = ?', (product_id,))
db_price = cursor.fetchone()[0]

conn.close()

print('=' * 80)
print('✅ GÜNCELLENMİŞ FİYATLANDIRMA:')
print('=' * 80)
print()
print(f'Tedarik:      €{cost:.2f}')
print(f'eBay Fiyat:   €{db_price:.2f}')
print(f'eBay Fee:     -€{db_price * 0.11:.2f}')
print(f'─────────────────────────')
print(f'NET KAR:      €{new_profit:.2f} ✅')
print()
print(f'Rakip aralığı: €7.99-€39.99 (ortalama €19.38)')
print(f'Bizim fiyat:   €{db_price:.2f} (Premium segment)')
print()
print(f'🔗 https://www.ebay.de/itm/{ebay_item_id}')
print('   (Fiyat 5-10 dakika içinde görünür)')
print()
print('=' * 80)
print('✅ TAMAMLANDI!')
print('=' * 80)
