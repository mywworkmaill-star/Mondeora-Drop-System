"""Rakip fiyat kontrolü script - production"""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import requests

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayAPIClient


def extract_key_terms(title):
    """Başlıktan en önemli kelimeleri çıkar"""
    stopwords = {'für', 'mit', 'und', 'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine'}
    words = title.lower().split()
    keywords = [w for w in words if len(w) > 3 and w not in stopwords][:4]
    return ' '.join(keywords)


def check_competitor_prices(product_title, our_price, category_hint=None):
    """eBay.de'de rakipleri ara ve fiyat karşılaştır"""
    client = eBayAPIClient()
    
    search_terms = extract_key_terms(product_title)
    
    headers = {
        'Authorization': f'Bearer {client.access_token}',
        'Content-Type': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE'
    }
    
    params = {
        'q': search_terms,
        'limit': 20,
        'sort': 'price',
        'filter': 'deliveryCountry:DE,price:[3..50],priceCurrency:EUR'
    }
    
    try:
        response = requests.get(
            'https://api.ebay.com/buy/browse/v1/item_summary/search',
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            return {'error': 'API failed', 'use_fallback': True}
        
        items = response.json().get('itemSummaries', [])
        prices = []
        
        for item in items[:15]:
            price_info = item.get('price', {})
            if price_info.get('currency') == 'EUR':
                price = float(price_info.get('value', 0))
                if 3 <= price <= 50:
                    prices.append(price)
        
        if not prices:
            return {'error': 'No competitors found', 'use_fallback': True}
        
        # İstatistikler
        avg_price = sum(prices) / len(prices)
        median_price = sorted(prices)[len(prices)//2]
        min_price = min(prices)
        max_price = max(prices)
        
        # Bizim pozisyonumuz
        our_percentile = sum(1 for p in prices if p < our_price) / len(prices) * 100
        
        # Karar
        if our_price > median_price * 1.5:
            status = 'TOO_HIGH'
            recommendation = 'REJECT - Fiyat çok yüksek'
            suggested_price = round(median_price * 1.10, 2)
        elif our_price > median_price * 1.25:
            status = 'HIGH'
            recommendation = 'ADJUST - Fiyat yüksek'
            suggested_price = round(median_price * 1.15, 2)
        elif our_price > median_price * 1.15:
            status = 'SLIGHTLY_HIGH'
            recommendation = 'CONSIDER_ADJUST'
            suggested_price = round(median_price * 1.10, 2)
        else:
            status = 'COMPETITIVE'
            recommendation = 'OK - Rekabetçi'
            suggested_price = our_price
        
        return {
            'status': status,
            'recommendation': recommendation,
            'our_price': our_price,
            'suggested_price': suggested_price,
            'competitor_count': len(prices),
            'stats': {
                'min': round(min_price, 2),
                'median': round(median_price, 2),
                'avg': round(avg_price, 2),
                'max': round(max_price, 2)
            },
            'our_position_percentile': round(our_percentile, 1),
            'price_vs_median_pct': round((our_price / median_price - 1) * 100, 1) if median_price > 0 else 0
        }
    
    except Exception as e:
        return {
            'error': str(e),
            'error_type': type(e).__name__,
            'use_fallback': True
        }


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Kullanım: python check_product_price.py '<product_title>' <price>")
        sys.exit(1)
    
    title = sys.argv[1]
    price = float(sys.argv[2])
    
    result = check_competitor_prices(title, price)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Karar
    if result.get('status') == 'TOO_HIGH':
        print(f"\n❌ REDDET: Fiyat çok yüksek ({price} EUR vs {result['stats']['median']} EUR medyan)")
        sys.exit(1)
    elif result.get('status') in ['HIGH', 'SLIGHTLY_HIGH']:
        print(f"\n⚠️ UYARI: Fiyat yüksek - {result['suggested_price']} EUR önerilir")
        sys.exit(0)
    else:
        print(f"\n✅ ONAY: Rekabetçi fiyat")
        sys.exit(0)
