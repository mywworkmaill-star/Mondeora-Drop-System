#!/usr/bin/env python3
"""
COMPETITOR ASPECT SCRAPER
=========================

Rakip eBay.de listinglerinden aspect bilgilerini topla.
Her ürün için:
1. eBay.de'de benzer ürünleri ara (Browse API)
2. İlk 5 rakip listingi al
3. Her birinden tüm aspect'leri çıkar
4. Topla ve birleştir
5. Kendi ürünümüze ekle

KULLANIM:
    python scripts/scrape_competitor_aspects.py <product_id>
    python scripts/scrape_competitor_aspects.py <product_id> --output aspects.json

UYDURMA DEĞİL - SADECE GERÇEK RAKİP VERİSİ!
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.ebay_client import eBayRESTClient
from src.api.aliexpress_client import AliExpressAPIClient
from src.listing_quality import source


def search_competitors_on_ebay(ebay: eBayRESTClient, search_query: str, category_id: str = None, limit: int = 5):
    """
    Search for competitor listings on eBay.de using Browse API.
    
    Args:
        ebay: eBay REST client
        search_query: Search keywords (product title)
        category_id: eBay category ID (optional)
        limit: Max competitors to return
    
    Returns:
        list: Competitor full item IDs (v1|xxx|xxx format)
    """
    try:
        # Use eBayRESTClient.search_products()
        # Category filtering doesn't work well, skip it
        items = ebay.search_products(search_query[:60], limit=limit)
        
        if not items:
            print(f"  ⚠️  No competitors found")
            return []
        
        # Extract full item IDs (already in v1|xxx|xxx format)
        competitors = []
        for item in items:
            item_id = item.get('itemId')
            if item_id:
                competitors.append(item_id)
        
        print(f"  ✅ Found {len(competitors)} competitors")
        return competitors
        
    except Exception as e:
        print(f"  ❌ Failed to search competitors: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_aspects_from_listing(ebay: eBayRESTClient, item_id: str):
    """
    Get all aspects from an eBay listing using Browse API.
    
    Args:
        ebay: eBay REST client
        item_id: Full eBay item ID (v1|xxx|xxx format)
    
    Returns:
        dict: {aspect_name: value, ...}
    """
    try:
        from urllib.parse import quote
        
        # URL encode the item ID (has | characters)
        encoded_id = quote(item_id, safe='')
        
        # Use Browse API to get item details
        resp = ebay._request('GET', f'/buy/browse/v1/item/{encoded_id}')
        
        if not resp:
            print(f"    ⚠️  No data for item {item_id}")
            return {}
        
        # Extract localizedAspects
        aspects = {}
        for aspect in resp.get('localizedAspects', []):
            name = aspect.get('name')
            value = aspect.get('value')
            
            if name and value:
                # Keep as-is (string)
                aspects[name] = value
        
        print(f"    ✅ {item_id[:30]}...: {len(aspects)} aspects")
        return aspects
        
    except Exception as e:
        print(f"    ❌ Failed to get aspects for {item_id[:30]}...: {e}")
        return {}


def merge_competitor_aspects(competitor_aspects_list):
    """
    Merge aspects from multiple competitors.
    
    Strategy:
    - For each aspect name, take the most common value
    - Skip aspects that vary too much (e.g., color, size)
    - Keep aspects that are consistent across competitors
    
    Args:
        competitor_aspects_list: List of {aspect_name: value} dicts
    
    Returns:
        dict: Merged aspects {aspect_name: value}
    """
    if not competitor_aspects_list:
        return {}
    
    # Count aspect values across all competitors
    aspect_counts = {}
    for aspects in competitor_aspects_list:
        for name, value in aspects.items():
            if name not in aspect_counts:
                aspect_counts[name] = {}
            
            if value not in aspect_counts[name]:
                aspect_counts[name][value] = 0
            
            aspect_counts[name][value] += 1
    
    # Take most common value for each aspect
    merged = {}
    total_competitors = len(competitor_aspects_list)
    
    for name, value_counts in aspect_counts.items():
        # Get most common value
        most_common_value = max(value_counts.items(), key=lambda x: x[1])
        value, count = most_common_value
        
        # Only include if at least 50% of competitors have this value
        # (avoid aspects that vary too much)
        if count >= total_competitors * 0.5:
            merged[name] = value
            print(f"  ✅ {name}: {value} ({count}/{total_competitors} competitors)")
        else:
            print(f"  ⚠️  {name}: skipped (too much variation)")
    
    return merged


def extract_search_keywords(title: str, max_words: int = 1):
    """
    Extract SINGLE core keyword from product title.
    
    Strategy: Take the LAST meaningful noun (usually the product type).
    
    Args:
        title: Product title
        max_words: Max words (default 1 for best results)
    
    Returns:
        str: Search query
    """
    import re
    
    # Clean and split
    clean = re.sub(r'[^\w\säöüß-]', ' ', title.lower())
    
    # Split hyphenated compounds
    clean = clean.replace('-', ' ')
    
    words = clean.split()
    
    # Noise words to skip
    noise = ['für', 'mit', 'und', 'oder', 'the', 'a', 'an', 'von', 'zum', 'zur', 
             'der', 'die', 'das', 'den', 'dem', 'des']
    
    # German compound prefixes to strip
    prefixes = [
        'zusammenklappbar', 'multifunktion', 'hochwertig', 'premium',
        'faltbar', 'tragbar', 'klappbar', 'verstellbar', 'elektrisch',
        'manuell', 'automatisch'
    ]
    
    # Extract meaningful words (nouns, >3 chars)
    keywords = []
    for word in reversed(words):  # Start from end (product type)
        # Skip noise
        if word in noise or len(word) < 4:
            continue
        # Skip prefixes
        if any(word.startswith(p) for p in prefixes):
            continue
        
        keywords.append(word)
        if len(keywords) >= max_words:
            break
    
    # If no keywords, take any word >3 chars
    if not keywords:
        keywords = [w for w in reversed(words) if len(w) >= 4][:max_words]
    
    # Reverse back to original order
    keywords.reverse()
    
    return ' '.join(keywords[:max_words])


def scrape_competitor_aspects(product_id: str, output_path: str = None):
    """
    Main function: scrape competitor aspects for a product.
    
    Args:
        product_id: AliExpress product ID
        output_path: Optional path to save results
    
    Returns:
        dict: Competitor aspects
    """
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPETITOR ASPECTS")
    print(f"Product ID: {product_id}")
    print(f"{'='*60}\n")
    
    # Initialize clients
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    # Get product details from AliExpress
    try:
        res = source.fetch_raw(ali, product_id)
        base_info = res.get('ae_item_base_info_dto', {})
        title = base_info.get('subject', '')
        
        if not title:
            print("❌ No product title found")
            return {}
        
        print(f"📝 Product title: {title[:80]}...")
        
    except Exception as e:
        print(f"❌ Failed to get product details: {e}")
        return {}
    
    # Get eBay category (from database or default)
    # For now, search without category to find any competitors
    category_id = None  # Search all categories for better results
    
    # Search for competitors
    print(f"\n🔍 Searching competitors on eBay.de...")
    
    # Extract generic keywords from title (just the core product type)
    search_keywords = extract_search_keywords(title, max_words=1)
    print(f"  Search query: {search_keywords}")
    
    competitors = search_competitors_on_ebay(ebay, search_keywords, category_id, limit=5)
    
    if not competitors:
        print("❌ No competitors found")
        return {}
    
    # Get aspects from each competitor
    print(f"\n📊 Getting aspects from {len(competitors)} competitors...")
    competitor_aspects_list = []
    
    for item_id in competitors:
        aspects = get_aspects_from_listing(ebay, item_id)
        if aspects:
            competitor_aspects_list.append(aspects)
    
    if not competitor_aspects_list:
        print("❌ No aspects found from competitors")
        return {}
    
    # Merge aspects
    print(f"\n🔀 Merging aspects from {len(competitor_aspects_list)} competitors...")
    merged_aspects = merge_competitor_aspects(competitor_aspects_list)
    
    # Save to file if requested
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        result = {
            'product_id': product_id,
            'competitors_found': len(competitors),
            'competitors_with_aspects': len(competitor_aspects_list),
            'merged_aspects': merged_aspects,
            'raw_competitor_aspects': competitor_aspects_list
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  Competitors found: {len(competitors)}")
    print(f"  Competitors with aspects: {len(competitor_aspects_list)}")
    print(f"  Merged aspects: {len(merged_aspects)}")
    print(f"\n📋 Merged Aspects:")
    for name, value in merged_aspects.items():
        print(f"  - {name}: {value}")
    
    return merged_aspects


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape competitor aspects from eBay.de')
    parser.add_argument('product_id', help='AliExpress product ID')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    
    args = parser.parse_args()
    
    scrape_competitor_aspects(args.product_id, args.output)
