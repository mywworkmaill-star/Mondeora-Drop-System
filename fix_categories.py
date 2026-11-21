#!/usr/bin/env python3
"""15 görünmeyen ilanın kategori düzeltmesi"""
import sqlite3
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

EBAY_TOKEN = os.getenv('EBAY_ACCESS_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {EBAY_TOKEN}',
    'Content-Type': 'application/json',
    'Content-Language': 'de-DE'
}

# Görünmeyen 15 ilan
INVISIBLE_ITEMS = [
    ('860134873775', 'Pop-Up Maus'),
    ('860134874458', 'Katze Puzzle'),
    ('860134905415', 'Hundespielzeugball'),
    ('860135446221', 'Holz Katze Puzzles'),
    ('860133996385', 'Aufbewahrungstasche'),
    ('860134885755', 'Edelstahl-Käfig'),  # 0 SONUÇ - KRİTİK
    ('860134886090', 'Mini Wärme Tasche'),
    ('860138544077', 'Schraubenorganizer-Box'),
    ('860138359448', 'Müll Taschen Halter'),
    ('860139499815', 'Fernbedienungs-Organizer'),
    ('860139500259', 'Kabelbinder-Organizer'),
    ('860139545709', 'Mehrzweck haken'),
    ('860139559198', 'Türhaken'),
    ('860139554274', 'Angelgerät-Box'),
    ('860139559384', 'Müllbeutelhalter'),
]

def get_sku_for_ebay_id(ebay_item_id):
    """eBay item ID'den SKU al"""
    conn = sqlite3.connect('data/dropshipping.db')
    c = conn.cursor()
    c.execute('SELECT sku_id, title FROM products WHERE ebay_item_id=?', (ebay_item_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

def get_current_category(sku):
    """Mevcut kategoriyi Inventory API'den al"""
    try:
        # Önce offer'dan kategori al
        r = requests.get(
            f'https://api.ebay.com/sell/inventory/v1/offer',
            headers=HEADERS,
            params={'sku': sku},
            timeout=15
        )
        if r.status_code == 200:
            offers = r.json().get('offers', [])
            if offers:
                offer = offers[0]
                return {
                    'categoryId': offer.get('categoryId'),
                    'offerId': offer.get('offerId'),
                    'offer_data': offer
                }
    except Exception as e:
        print(f"  ⚠️ Offer alma hatası: {e}")
    return None

def get_category_suggestions(query):
    """eBay Taxonomy API'den kategori önerileri al"""
    try:
        r = requests.get(
            'https://api.ebay.com/commerce/taxonomy/v1/category_tree/77/get_category_suggestions',
            headers=HEADERS,
            params={'q': query},
            timeout=15
        )
        if r.status_code == 200:
            suggestions = r.json().get('categorySuggestions', [])
            return suggestions[:5]  # İlk 5 öneri
    except Exception as e:
        print(f"  ⚠️ Taxonomy hatası: {e}")
    return []

def vote_best_category(title):
    """Birden fazla sorgu ile en iyi kategoriyi oyla"""
    words = title.split()
    queries = [
        title,  # Tam başlık
        ' '.join(words[:4]),  # İlk 4 kelime
        ' '.join(words[-4:]),  # Son 4 kelime
    ]
    
    # Kelime bazlı sorgular (sayı olmayan)
    filtered_words = [w for w in words if not w.isdigit()]
    if len(filtered_words) >= 2:
        queries.append(' '.join(filtered_words[:3]))
    
    vote_map = {}
    all_suggestions = []
    
    for query in queries:
        if not query.strip():
            continue
        print(f"    Sorgu: {query[:50]}")
        suggestions = get_category_suggestions(query)
        
        if suggestions:
            top = suggestions[0]
            cat_id = top['category']['categoryId']
            cat_name = top['category']['categoryName']
            
            if cat_id not in vote_map:
                vote_map[cat_id] = {'count': 0, 'name': cat_name, 'data': top}
            vote_map[cat_id]['count'] += 1
            all_suggestions.extend(suggestions)
        
        time.sleep(0.3)  # Rate limit
    
    if not vote_map:
        return None
    
    # En çok oy alan
    best = max(vote_map.items(), key=lambda x: x[1]['count'])
    confidence = best[1]['count'] / len(queries)
    
    return {
        'categoryId': best[0],
        'categoryName': best[1]['name'],
        'confidence': confidence,
        'votes': best[1]['count'],
        'total_queries': len(queries),
        'needs_review': confidence < 0.5
    }

def update_offer_category(offer_id, offer_data, new_category_id):
    """Offer kategorisini güncelle"""
    try:
        # Tam payload gerekiyor (eksik alan = 400)
        payload = {
            'sku': offer_data.get('sku'),
            'marketplaceId': 'EBAY_DE',
            'format': 'FIXED_PRICE',
            'listingDescription': offer_data.get('listingDescription', ''),
            'pricingSummary': offer_data.get('pricingSummary', {}),
            'categoryId': str(new_category_id),
            'merchantLocationKey': offer_data.get('merchantLocationKey', 'default-warehouse'),
            'listingPolicies': offer_data.get('listingPolicies', {}),
        }
        
        r = requests.put(
            f'https://api.ebay.com/sell/inventory/v1/offer/{offer_id}',
            headers=HEADERS,
            json=payload,
            timeout=20
        )
        
        if r.status_code in (200, 204):
            return True
        else:
            print(f"    ⚠️ Güncelleme hatası: {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        print(f"    ⚠️ Güncelleme exception: {e}")
        return False

def main():
    print("=== 15 GÖRÜNMEYEN İLANIN KATEGORİ DÜZELTMESİ ===\n")
    
    results = []
    updated_count = 0
    
    for ebay_id, short_title in INVISIBLE_ITEMS:
        print(f"\n[{ebay_id}] {short_title}")
        
        # SKU al
        sku, full_title = get_sku_for_ebay_id(ebay_id)
        if not sku:
            print(f"  ❌ SKU bulunamadı!")
            results.append({
                'ebay_id': ebay_id,
                'title': short_title,
                'status': 'SKU_NOT_FOUND'
            })
            continue
        
        print(f"  SKU: {sku}")
        print(f"  Başlık: {full_title[:60]}")
        
        # Mevcut kategori
        current = get_current_category(sku)
        if not current:
            print(f"  ❌ Mevcut offer bulunamadı!")
            results.append({
                'ebay_id': ebay_id,
                'sku': sku,
                'title': short_title,
                'status': 'NO_OFFER'
            })
            continue
        
        current_cat_id = current['categoryId']
        print(f"  Mevcut Kategori: {current_cat_id}")
        
        # Doğru kategoriyi bul
        suggested = vote_best_category(full_title or short_title)
        if not suggested:
            print(f"  ⚠️ Kategori önerisi alınamadı!")
            results.append({
                'ebay_id': ebay_id,
                'sku': sku,
                'title': short_title,
                'current_category': current_cat_id,
                'status': 'NO_SUGGESTION'
            })
            continue
        
        print(f"  Önerilen: {suggested['categoryId']} - {suggested['categoryName']}")
        print(f"  Güven: {suggested['confidence']:.2f} ({suggested['votes']}/{suggested['total_queries']})")
