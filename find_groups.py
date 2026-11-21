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

listing_ids = ['860134874458', '860134884632', '860134905415', '860135446221']
group_info = {}

print("=== GROUP KEY BULMA ===\n")

for ebay_id in listing_ids:
    try:
        # Inventory API'den tüm offer'ları al ve listing_id ile eşleştir
        r = req.get(
            'https://api.ebay.com/sell/inventory/v1/offer',
            headers=HEADERS,
            params={'limit': 200},
            timeout=30
        )
        
        if r.status_code == 200:
            data = r.json()
            offers = data.get('offers', [])
            
            # Bu listing_id ile eşleşen offer'ı bul
            for offer in offers:
                if offer.get('listingId') == ebay_id:
                    # Group key'i bul
                    # Variation ise groupId olmalı
                    sku = offer.get('sku', '')
                    group_id = offer.get('groupIds', [])
                    
                    group_info[ebay_id] = {
                        'sku': sku,
                        'group_ids': group_id,
                        'offer_id': offer.get('offerId'),
                        'format': offer.get('format')
                    }
                    
                    print(f"{ebay_id}:")
                    print(f"  SKU: {sku}")
                    print(f"  Group IDs: {group_id}")
                    print(f"  Offer ID: {offer.get('offerId')}")
                    print()
                    break
            else:
                print(f"{ebay_id}: OFFER BULUNAMADI")
        else:
            print(f"{ebay_id}: API HATASI {r.status_code}")
            
    except Exception as e:
        print(f"{ebay_id}: HATA - {e}")

print("\n" + json.dumps(group_info, indent=2, ensure_ascii=False))
