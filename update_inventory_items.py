import os, json, sqlite3
from dotenv import load_dotenv
load_dotenv()

import requests as req

token = os.getenv('EBAY_ACCESS_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

# Yeni başlıklar
new_titles = {
    '1005009659236961': 'Katzenspielzeug Filz mit Bällen Interaktives Beschäftigungsspielzeug 30cm',
    '1005011535580954': 'Antistressball Squishy Seifenoptik Drückbar Fidget Spielzeug',
    '1005006907344602': 'Hundespielzeug Ball Bissfest Zahnreinigung Kauspielzeug für Hunde',
    '1005010397611220': 'Katzenpuzzle 50 Teile Tier-Puzzle Kinder Lernspielzeug Steckpuzzle'
}

# DB'den varyantları al
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row

print("=== INVENTORY ITEM (SKU) BAŞLIKLARINI GÜNCELLEME ===\n")

for ae_id, new_title in new_titles.items():
    print(f"\n[AliExpress ID: {ae_id}]")
    print(f"  Yeni Başlık: {new_title}")
    
    # Bu ürüne ait tüm varyantları bul
    variants = db.execute(
        'SELECT sku FROM product_variants WHERE product_id IN (SELECT id FROM products WHERE aliexpress_product_id = ?)',
        (ae_id,)
    ).fetchall()
    
    print(f"  Varyant Sayısı: {len(variants)}")
    
    for v in variants:
        sku = v['sku']
        print(f"    SKU: {sku}")
        
        try:
            # Mevcut inventory_item'ı al
            r = req.get(
                f'https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}',
                headers=HEADERS,
                timeout=20
            )
            
            if r.status_code != 200:
                print(f"      → HATA: Okunamadı ({r.status_code})")
                continue
            
            item_data = r.json()
            
            # Sadece title'ı güncelle
            item_data['product']['title'] = new_title
            
            # PUT ile güncelle
            r2 = req.put(
                f'https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}',
                headers=HEADERS,
                json=item_data,
                timeout=30
            )
            
            if r2.status_code in [200, 204]:
                print(f"      → ✓ Güncellendi")
            else:
                print(f"      → HATA: {r2.status_code}")
                print(f"         {r2.text[:150]}")
                
        except Exception as e:
            print(f"      → HATA: {e}")

db.close()
print("\n\n=== TAMAMLANDI ===")
