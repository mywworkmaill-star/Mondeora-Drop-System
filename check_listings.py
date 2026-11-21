import os, json
from dotenv import load_dotenv
load_dotenv()

import requests as req

token = os.getenv('EBAY_ACCESS_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

# İlanların bilgileri (context'ten)
listings = {
    '860134874458': {'name': 'Katzen-Puzzle', 'issues': 'Kelime tekrarı: Katze, Indoor'},
    '860134884632': {'name': 'Seifenball', 'issues': 'Kelime tekrarı: Seifenball+Seifen-Stressball'},
    '860134905415': {'name': 'Hundespielzeugball', 'issues': 'N/A'},
    '860135446221': {'name': 'Holz Puzzles', 'issues': 'Kelime tekrarı: Holz'}
}

results = {}

# Her ilan için Browse API ile bilgi al
for ebay_id, info in listings.items():
    try:
        # Önce get_items_by_item_group ile dene (variation grubu için)
        r = req.get(
            'https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group',
            headers=HEADERS,
            params={'item_group_id': ebay_id},
            timeout=20
        )
        
        if r.status_code == 200:
            data = r.json()
            items = data.get('items', [])
            if items:
                first_item = items[0]
                results[ebay_id] = {
                    'type': 'variation_group',
                    'title': first_item.get('title', ''),
                    'image': first_item.get('image', {}).get('imageUrl', ''),
                    'variant_count': len(items),
                    'issues': info['issues']
                }
            else:
                results[ebay_id] = {'error': 'No items in group'}
        else:
            # Variation değilse normal item olarak dene
            r2 = req.get(
                'https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id',
                headers=HEADERS,
                params={'legacy_item_id': ebay_id},
                timeout=20
            )
            if r2.status_code == 200:
                data = r2.json()
                results[ebay_id] = {
                    'type': 'single_item',
                    'title': data.get('title', ''),
                    'image': data.get('image', {}).get('imageUrl', ''),
                    'issues': info['issues']
                }
            else:
                results[ebay_id] = {'error': f'Both APIs failed: {r.status_code}, {r2.status_code}'}
    
    except Exception as e:
        results[ebay_id] = {'error': str(e)}

print(json.dumps(results, indent=2, ensure_ascii=False))
