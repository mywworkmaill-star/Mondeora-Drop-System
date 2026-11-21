#!/usr/bin/env python3
"""
Cassini Optimization - Traffic Root Cause Analysis
CRITICAL aksiyonu: eBay Browse API ile gerçek arama sıralamasını kontrol et

21/21 ilanda ZERO traffic var - bu script her ilanın gerçek Best Match
sıralamasını ölçer ve ilk 200'de olup olmadığını tespit eder.

Çalıştırma:
    python scripts/traffic_audit.py
    
Çıktı: data/traffic_audit_results.json
"""
import sys
sys.path.insert(0, '.')

import requests
import json
import os
from src.database.models import Product, get_session, init_database
from datetime import datetime


def get_access_token():
    """eBay OAuth token al - mevcut eBayAPIClient kullan"""
    from src.api.ebay_client import eBayAPIClient
    
    ebay = eBayAPIClient()
    result = ebay.refresh_access_token(force=True)
    
    if not result.get('success'):
        raise ValueError(f"Token refresh failed: {result.get('error')}")
    
    return ebay.access_token


def extract_keywords(title, max_words=3):
    """Başlıktan core keyword'leri çıkar"""
    # Almanca stop words
    stop_words = {'und', 'der', 'die', 'das', 'mit', 'für', 'aus', 'von', 'ein', 'eine', 'einen'}
    
    words = title.split()
    keywords = []
    
    for word in words:
        # Stop word veya sayı/sembol atlama
        if word.lower() in stop_words or not word.isalpha():
            continue
        keywords.append(word)
        if len(keywords) >= max_words:
            break
    
    return ' '.join(keywords)


def search_browse_api(access_token, query, limit=200):
    """eBay Browse API ile arama yap"""
    url = 'https://api.ebay.com/buy/browse/v1/item_summary/search'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE',
        'X-EBAY-C-ENDUSERCTX': 'contextualLocation=country=DE'
    }
    params = {
        'q': query,
        'limit': limit
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ❌ API Error: {e}")
        return None


def main():
    print(f"{'='*70}")
    print(f"Cassini Traffic Root Cause Analysis")
    print(f"eBay Browse API - Best Match Ranking Check")
    print(f"{'='*70}\n")
    
    # Access token al
    print("Authenticating with eBay API...")
    try:
        access_token = get_access_token()
        print("✓ Authentication successful\n")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)
    
    # Database
    db = init_database()
    
    results = []
    not_found_in_top_200 = []
    
    with get_session(db) as session:
        products = session.query(Product).filter_by(status='active').all()
        total = len(products)
        
        print(f"Analyzing {total} active listings...\n")
        
        for i, product in enumerate(products, 1):
            item_id = product.ebay_item_id
            title = product.title
            pid = product.aliexpress_product_id
            
            # Core keyword'leri çıkar
            query = extract_keywords(title)
            
            print(f"[{i}/{total}] {item_id}")
            print(f"  Title: {title[:60]}...")
            print(f"  Query: '{query}'")
            
            # Browse API search
            data = search_browse_api(access_token, query)
            
            if not data:
                results.append({
                    'item_id': item_id,
                    'pid': pid,
                    'title': title,
                    'query': query,
                    'error': 'API call failed',
                    'found_in_top_200': None,
                    'position': None,
                    'total_results': None
                })
                print(f"  ⚠️  API call failed")
                print()
                continue
            
            # Sonuçlarda ara
            found = False
            position = None
            total_results = data.get('total', 0)
            
            if 'itemSummaries' in data:
                for pos, item in enumerate(data['itemSummaries'], 1):
                    # Legacy item ID karşılaştır
                    legacy_id = item.get('legacyItemId', '')
                    if item_id in legacy_id or legacy_id in item_id:
                        found = True
                        position = pos
                        break
            
            result = {
                'item_id': item_id,
                'pid': pid,
                'title': title,
                'query': query,
                'found_in_top_200': found,
                'position': position,
                'total_results': total_results,
                'error': None
            }
            results.append(result)
            
            if found:
                print(f"  ✓ FOUND at position #{position} (out of {total_results} total)")
            else:
                print(f"  ❌ NOT FOUND in top 200 (total results: {total_results})")
                not_found_in_top_200.append(result)
            
            print()
    
    # Rapor kaydet
    output_file = 'data/traffic_audit_results.json'
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_listings': total,
        'found_in_top_200': total - len(not_found_in_top_200),
        'not_found_in_top_200': len(not_found_in_top_200),
        'results': results,
        'not_found_details': not_found_in_top_200
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Özet
    print(f"{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total listings analyzed: {total}")
    print(f"Found in top 200: {total - len(not_found_in_top_200)} ({((total - len(not_found_in_top_200)) / total * 100):.1f}%)")
    print(f"NOT found in top 200: {len(not_found_in_top_200)} ({(len(not_found_in_top_200) / total * 100):.1f}%)")
    print(f"\nFull report saved to: {output_file}")
    print(f"{'='*70}\n")
    
    if len(not_found_in_top_200) > 0:
        print("❌ CRITICAL ISSUE: These listings are NOT visible in search results:")
        for r in not_found_in_top_200[:10]:  # İlk 10'u göster
            print(f"  - {r['item_id']}: '{r['query']}' ({r['total_results']} total results)")
        
        if len(not_found_in_top_200) > 10:
            print(f"  ... and {len(not_found_in_top_200) - 10} more (see JSON report)")
        
        print("\nRECOMMENDED ACTIONS:")
        print("  1. Review category assignments (may be in wrong category)")
        print("  2. Optimize titles with higher-volume keywords")
        print("  3. Increase Promoted Listings bid (%5 → %8)")
        print("  4. Check if listings are actually active on eBay.de")
        print("\nReferences:")
        print("  - ebay-category-resolution skill")
        print("  - ebay-de-keyword-titles skill")
        print("  - ebay-listing-optimizer skill - 'new listing visibility' section")
    else:
        print("✓ All listings found in search results!")
        print("\nSince all listings ARE visible but have ZERO traffic,")
        print("the issue is likely:")
        print("  1. Low ranking (position >50)")
        print("  2. Poor title/thumbnail CTR")
        print("  3. Price competitiveness")
        print("\nRun optimize_prices.py and update titles.")


if __name__ == '__main__':
    main()
