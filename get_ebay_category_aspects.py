"""
EBAY CATEGORY ASPECTS OTOMATİK ÇEKME
getCategorySpecifics API ile zorunlu aspect'leri bulma
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests
import json

load_dotenv()

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("EBAY CATEGORY ASPECTS OTOMATİK ÇEKME")
print("="*70)

# Test kategorileri
CATEGORIES = {
    "20741": "Haustierbedarf (Pet)",
    "9394": "Handy-Zubehör (Phone Accessories)",
    "20326": "Haus & Garten (Home & Garden)",
    "73991": "Fitness & Jogging (Sports)",
    "2984": "Baby (Baby)",
    "20518": "Garten & Terrasse (Garden)"
}

category_aspects = {}

for cat_id, name in CATEGORIES.items():
    print(f"\n{'='*70}")
    print(f"Kategori: {name} ({cat_id})")
    print(f"{'='*70}")
    
    try:
        # Taxonomy API - Category Specifications
        resp = requests.get(
            f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category?category_id={cat_id}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }, timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            aspects = data.get('aspects', [])
            
            required_aspects = []
            recommended_aspects = []
            
            for aspect in aspects:
                aspect_name = aspect.get('localizedAspectName')
                constraint = aspect.get('aspectConstraint', {})
                aspect_required = constraint.get('aspectRequired', False)
                aspect_mode = constraint.get('aspectMode', '')
                
                if aspect_required:
                    required_aspects.append(aspect_name)
                else:
                    recommended_aspects.append(aspect_name)
            
            print(f"\n✅ ZORUNLU ASPECTS ({len(required_aspects)}):")
            for asp in required_aspects[:10]:  # İlk 10
                print(f"   - {asp}")
            
            if len(required_aspects) > 10:
                print(f"   ... ve {len(required_aspects) - 10} tane daha")
            
            print(f"\n📋 ÖNERİLEN ASPECTS ({len(recommended_aspects)}):")
            for asp in recommended_aspects[:5]:  # İlk 5
                print(f"   - {asp}")
            
            if len(recommended_aspects) > 5:
                print(f"   ... ve {len(recommended_aspects) - 5} tane daha")
            
            category_aspects[cat_id] = {
                'name': name,
                'required': required_aspects,
                'recommended': recommended_aspects[:10]  # İlk 10 öneriyi kaydet
            }
            
        else:
            print(f"   ❌ API Hatası: {resp.status_code}")
            print(f"   {resp.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ Hata: {str(e)}")

# JSON'a kaydet
output_file = 'data/ebay_category_aspects_mapping.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(category_aspects, f, indent=2, ensure_ascii=False)

print(f"\n{'='*70}")
print(f"✅ TAMAMLANDI!")
print(f"{'='*70}")

print(f"\n📊 SONUÇ:")
print(f"   Çekilen kategori: {len(category_aspects)}")
print(f"   Kaydedildi: {output_file}")

print(f"\n🎯 KULLANIM:")
print(f"""
# Artık otomatik kullanılabilir:
import json
with open('{output_file}', 'r', encoding='utf-8') as f:
    aspects = json.load(f)

category_id = "20741"
required = aspects[category_id]['required']
# ['Marke', 'Tierart', 'Material', ...]

# Otomatik aspect ekleme:
product_aspects = {{}}
for aspect_name in required:
    if aspect_name == 'Marke':
        product_aspects['Marke'] = ['Markenlos']
    elif aspect_name == 'Tierart':
        product_aspects['Tierart'] = ['Hund']  # veya 'Katze'
    # ... vs
""")

print(f"\n✨ ARTIK TRIAL-ERROR YOK!")
print(f"   Her kategori için aspect'ler bilinir!")
