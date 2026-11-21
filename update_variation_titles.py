import os, json, sys
from dotenv import load_dotenv
load_dotenv()

import requests as req

token = os.getenv('EBAY_ACCESS_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

# Yeni başlıklar (görsel doğrulamalı)
updates = {
    '860134874458': {
        'group_key': 'GRP-1005009659236961',
        'old_title': 'Katze Puzzle Spielzeug Filz Puzzle Box Katze Übung Spielzeug Mit Ball Indoor',
        'new_title': 'Katzenspielzeug Filz mit Bällen Interaktives Beschäftigungsspielzeug 30cm',
        'reason': 'Kelime tekrarı: Katze, Puzzle → Giderildi'
    },
    '860134884632': {
        'group_key': 'GRP-1005011535580954',
        'old_title': 'Seifenball Quetschbarer Seifen-Stressball Fidget-Spielzeug Knisternder',
        'new_title': 'Antistressball Squishy Seifenoptik Drückbar Fidget Spielzeug',
        'reason': 'Kelime tekrarı: Seifenball+Seifen → Giderildi, gerçek ürün (stres topu)'
    },
    '860134905415': {
        'group_key': 'GRP-1005006907344602',
        'old_title': 'Hundespielzeugball, ungiftiger, bissfester Spielzeugball für Hunde, Welpen',
        'new_title': 'Hundespielzeug Ball Bissfest Zahnreinigung Kauspielzeug für Hunde',
        'reason': 'Kelime tekrarı: ball → Giderildi, görsel özellikler eklendi'
    },
    '860135446221': {
        'group_key': 'GRP-1005010397611220',
        'old_title': '50 stücke Holz Katze Puzzles Tier Holz Puzzle Stapeln Spielzeug Pädagogisches',
        'new_title': 'Katzenpuzzle 50 Teile Tier-Puzzle Kinder Lernspielzeug Steckpuzzle',
        'reason': 'Kelime tekrarı: Holz, Puzzle → Giderildi, AHŞAP YANLIŞ (karton)'
    }
}

# DRY RUN mi yoksa LIVE mi?
live = '--live' in sys.argv

print("=== VARYASYON BAŞLIK GÜNCELLEMESİ ===")
print(f"Mode: {'LIVE UPDATE' if live else 'DRY RUN (--live ile çalıştır)'}\n")

for ebay_id, info in updates.items():
    print(f"\n[{ebay_id}] {info['group_key']}")
    print(f"  Eski: {info['old_title']} ({len(info['old_title'])} char)")
    print(f"  Yeni: {info['new_title']} ({len(info['new_title'])} char)")
    print(f"  Neden: {info['reason']}")
    
    if not live:
        print("  → DRY RUN: Güncelleme yapılmadı")
        continue
    
    # 1. Mevcut grup bilgisini al (title hariç tüm alanları korumak için)
    try:
        r = req.get(
            f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{info["group_key"]}',
            headers=HEADERS,
            timeout=20
        )
        
        if r.status_code != 200:
            print(f"  → HATA: Grup okunamadı ({r.status_code})")
            print(f"     {r.text[:200]}")
            continue
        
        group_data = r.json()
        
        # 2. Sadece title'ı güncelle
        group_data['title'] = info['new_title']
        
        # 3. Grubu güncelle (PUT)
        r2 = req.put(
            f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{info["group_key"]}',
            headers=HEADERS,
            json=group_data,
            timeout=30
        )
        
        if r2.status_code in [200, 204]:
            print(f"  → ✓ BAŞARILI: Grup başlığı güncellendi")
        else:
            print(f"  → HATA: Güncelleme başarısız ({r2.status_code})")
            print(f"     {r2.text[:200]}")
            
    except Exception as e:
        print(f"  → HATA: {e}")

if not live:
    print("\n\n*** DRY RUN tamamlandı. Gerçek güncelleme için '--live' parametresiyle çalıştırın ***")
