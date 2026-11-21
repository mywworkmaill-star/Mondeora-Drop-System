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

# Test: İlk grup bilgisini al ve yapısını incele
group_key = 'GRP-1005009659236961'

print(f"=== Testing {group_key} ===\n")

try:
    r = req.get(
        f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{group_key}',
        headers=HEADERS,
        timeout=20
    )
    
    print(f"Status Code: {r.status_code}")
    print(f"\nResponse Headers:")
    for k, v in r.headers.items():
        if k.lower() in ['content-type', 'content-length']:
            print(f"  {k}: {v}")
    
    print(f"\nResponse Body:")
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    else:
        print(r.text[:500])
        
except Exception as e:
    print(f"HATA: {e}")
