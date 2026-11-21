import os, sys, json, sqlite3
from dotenv import load_dotenv
load_dotenv()

import requests as req

token = os.getenv('EBAY_ACCESS_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

db = sqlite3.connect('mondeora.db')
cursor = db.cursor()
listing_ids = ['860134874458', '860134884632', '860134905415', '860135446221']
results = {}

for ebay_id in listing_ids:
    cursor.execute(
        'SELECT id, ebay_item_id, title, image_url FROM products WHERE ebay_item_id = ?',
        (ebay_id,)
    )
    product = cursor.fetchone()
    
    if product:
        group_key = f'GRP-{product[0]}'
        
        # eBay'den grup bilgisini al
        try:
            r = req.get(
                f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}',
                headers=HEADERS,
                timeout=20
            )
            if r.status_code == 200:
                group_data = r.json()
                current_title = group_data.get('product', {}).get('title', '')
                image_urls = group_data.get('product', {}).get('imageUrls', [])
            else:
                current_title = f'ERROR {r.status_code}'
                image_urls = []
        except Exception as e:
            current_title = f'ERROR: {e}'
            image_urls = []
        
        results[ebay_id] = {
            'db_id': product[0],
            'ebay_item_id': product[1],
            'db_title': product[2],
            'ebay_title': current_title,
            'image_url': product[3],
            'ebay_images': image_urls,
            'group_key': group_key
        }

db.close()
print(json.dumps(results, indent=2, ensure_ascii=False))
