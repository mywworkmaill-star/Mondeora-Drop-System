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

# DB'den bilgileri al
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row

listing_ids = ['860134874458', '860134884632', '860134905415', '860135446221']
results = {}

print("=== VARYASYON İLANLARI BİLGİ TOPLAMA ===\n")

for ebay_id in listing_ids:
    row = db.execute(
        'SELECT id, ebay_item_id, aliexpress_product_id, title, category_id FROM products WHERE ebay_item_id = ?',
        (ebay_id,)
    ).fetchone()
    
    if row:
        group_key = f"GRP-{row['aliexpress_product_id']}"
        
        results[ebay_id] = {
            'db_id': row['id'],
            'aliexpress_product_id': row['aliexpress_product_id'],
            'group_key': group_key,
            'db_title': row['title'],
            'category_id': row['category_id']
        }
        
        # eBay'den mevcut grup başlığını al
        try:
            r = req.get(
                f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}',
                headers=HEADERS,
                timeout=20
            )
            if r.status_code == 200:
                group_data = r.json()
                results[ebay_id]['ebay_title'] = group_data.get('product', {}).get('title', '')
            else:
                results[ebay_id]['ebay_title'] = f'ERROR {r.status_code}'
        except Exception as e:
            results[ebay_id]['ebay_title'] = f'ERROR: {e}'
        
        print(f"{ebay_id}:")
        print(f"  DB ID: {row['id']}")
        print(f"  AliExpress ID: {row['aliexpress_product_id']}")
        print(f"  Group Key: {group_key}")
        print(f"  DB Title: {row['title']}")
        print(f"  eBay Title: {results[ebay_id].get('ebay_title', 'N/A')}")
        print()

db.close()

print("\n=== JSON ===")
print(json.dumps(results, indent=2, ensure_ascii=False))
