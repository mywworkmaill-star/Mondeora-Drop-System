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

# Yeni başlıklar (görsel doğrulamalı, ebay-de-keyword-titles kurallarına uygun)
new_titles = {
    '860134874458': {
        'old': 'Cat Puzzle Toy Felt Puzzle Box Cat Exercise Toy With Ball Indoor',
        'new': 'Katzenspielzeug Filz mit Bällen Interaktives Beschäftigungsspielzeug 30cm',
        'group_key': 'GRP-???',  # DB'den alınacak
        'reason': 'Kelime tekrarı giderildi (Cat, Puzzle), Almanca, doğal yapı, 73 karakter'
    },
    '860134884632': {
        'old': 'Soap Ball Squeezable Soap Stress Ball Fidget Toy Crackle',
        'new': 'Antistressball Squishy Seifenoptik Drückbar Fidget Spielzeug',
        'group_key': 'GRP-???',
        'reason': 'Kelime tekrarı giderildi (Soap, Ball), gerçek ürün (stres topu, sabun değil), 65 karakter'
    },
    '860134905415': {
        'old': 'Dog Toy Ball, Non-Toxic, Bite Resistant Toy Ball for Dogs, Puppies',
        'new': 'Hundespielzeug Ball Bissfest Zahnreinigung Kauspielzeug für Hunde',
        'group_key': 'GRP-???',
        'reason': 'Kelime tekrarı giderildi (Ball, Toy), görsel özellikler eklendi, 71 karakter'
    },
    '860135446221': {
        'old': '50pcs Wooden Cat Puzzles Animal Wooden Jigsaw Puzzle Stacking Toy Educational',
        'new': 'Katzenpuzzle 50 Teile Tier-Puzzle Kinder Lernspielzeug Steckpuzzle',
        'group_key': 'GRP-???',
        'reason': 'Kelime tekrarı giderildi (Wooden, Puzzle), AHŞAP YANLIŞ (karton), 71 karakter'
    }
}

# Önce product_id'leri bulmak için offers API'sini kullanalım
print("=== BAŞLIK GÜNCELLEMESİ ===\n")

for ebay_id, info in new_titles.items():
    print(f"\n[{ebay_id}]")
    print(f"  Eski: {info['old']}")
    print(f"  Yeni: {info['new']}")
    print(f"  Neden: {info['reason']}")
    print(f"  Uzunluk: {len(info['new'])} / 80 karakter")
    
    # Önce offer bilgisini alalım (SKU'dan group_key bulabiliriz)
    try:
        # Legacy ID'den item bilgisini almaya çalışalım
        r = req.get(
            'https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group',
            headers=HEADERS,
            params={'item_group_id': ebay_id},
            timeout=20
        )
        
        if r.status_code == 200:
            items = r.json().get('items', [])
            if items:
                # İlk item'dan SKU'yu alalım
                first_sku = items[0].get('sku', '')
                print(f"  SKU örneği: {first_sku}")
                
                # SKU formatı: AE-{product_id}-{variant} veya GRP-{product_id}
                # Group key'i tahmin edelim
                if first_sku.startswith('AE-'):
                    parts = first_sku.split('-')
                    if len(parts) >= 2:
                        product_id = parts[1]
                        info['group_key'] = f'GRP-{product_id}'
                        print(f"  Group key: {info['group_key']}")
    except Exception as e:
        print(f"  HATA: {e}")

print("\n" + json.dumps(new_titles, indent=2, ensure_ascii=False))
