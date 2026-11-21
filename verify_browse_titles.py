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

# Beklenen yeni başlıklar
expected_titles = {
    '860134874458': 'Katzenspielzeug Filz mit Bällen Interaktives Beschäftigungsspielzeug 30cm',
    '860134884632': 'Antistressball Squishy Seifenoptik Drückbar Fidget Spielzeug',
    '860134905415': 'Hundespielzeug Ball Bissfest Zahnreinigung Kauspielzeug für Hunde',
    '860135446221': 'Katzenpuzzle 50 Teile Tier-Puzzle Kinder Lernspielzeug Steckpuzzle'
}

print("=== BROWSE API DOĞRULAMA (Alıcı Görünümü) ===\n")

all_ok = True

for ebay_id, expected in expected_titles.items():
    try:
        # Browse API ile variation grubu sorgula
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
                actual_title = items[0].get('title', '')
                match = actual_title == expected
                
                print(f"[{ebay_id}]")
                print(f"  Beklenen: {expected}")
                print(f"  Gerçek:   {actual_title}")
                print(f"  Durum:    {'✓ EŞLEŞİYOR' if match else '✗ UYUŞMUYOR'}")
                print(f"  Varyant:  {len(items)} adet")
                print()
                
                if not match:
                    all_ok = False
            else:
                print(f"[{ebay_id}] HATA: Grup içinde item yok")
                all_ok = False
        else:
            print(f"[{ebay_id}] HATA: Browse API {r.status_code}")
            print(f"  {r.text[:200]}")
            all_ok = False
            
    except Exception as e:
        print(f"[{ebay_id}] HATA: {e}")
        all_ok = False

print("\n" + "="*60)
if all_ok:
    print("✓ TÜM İLANLAR DOĞRULANDI - Alıcılar yeni başlıkları görüyor!")
else:
    print("✗ Bazı ilanlar doğrulanamadı veya eşleşmiyor")
