#!/usr/bin/env python3
"""
Title Optimizer from Competitors
=================================

Analyze competitor titles and optimize our title for eBay.de search ranking.

STRATEGY:
1. Find 5-10 competitors for same product
2. Extract keywords from their titles
3. Find most common patterns
4. Build optimized title with high-value keywords

USAGE:
    python scripts/optimize_title_from_competitors.py <product_id>
    python scripts/optimize_title_from_competitors.py <product_id> --current-title "..."
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def extract_search_keywords(title, max_words=3):
    """
    Extract core product keywords from title for competitor search.
    
    Strategy: Take last N meaningful words (product type usually at end).
    """
    # Remove special chars and extra spaces
    clean = re.sub(r'[^\w\s-]', ' ', title.lower())
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Split into words
    words = clean.split()
    
    # Filter out noise words
    noise = {
        'für', 'mit', 'und', 'oder', 'der', 'die', 'das', 'den', 'dem',
        'ein', 'eine', 'einem', 'einen', 'aus', 'auf', 'in', 'zu',
        'von', 'bei', 'nach', 'über', 'unter', 'vor', 'hinter'
    }
    
    # Keep only meaningful words (>3 chars, not noise)
    meaningful = [w for w in words if len(w) > 3 and w not in noise]
    
    # Take last N words (product type at end)
    core_keywords = meaningful[-max_words:] if len(meaningful) >= max_words else meaningful
    
    return ' '.join(core_keywords)


def tokenize_title(title):
    """
    Tokenize title into words.
    
    Returns:
        list: [word1, word2, ...]
    """
    # Remove special chars (dash at end to avoid range error)
    clean = re.sub(r'[^\w\säöüÄÖÜß-]', ' ', title)
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    # Split
    words = clean.lower().split()
    
    # Filter noise
    noise = {
        'für', 'mit', 'und', 'oder', 'der', 'die', 'das', 'den', 'dem',
        'ein', 'eine', 'einem', 'einen', 'aus', 'auf', 'in', 'zu',
        'von', 'bei', 'nach', 'über', 'unter', 'vor', 'hinter', 'am', 'im'
    }
    
    return [w for w in words if w not in noise and len(w) > 2]


def extract_patterns(titles):
    """
    Extract keyword patterns from competitor titles.
    
    Returns:
        dict: {
            'keywords': {word: count, ...},
            'bigrams': {(word1, word2): count, ...},
            'avg_length': int,
            'common_prefixes': [prefix, ...],
            'common_suffixes': [suffix, ...]
        }
    """
    all_keywords = []
    all_bigrams = []
    lengths = []
    
    for title in titles:
        # Tokenize
        words = tokenize_title(title)
        all_keywords.extend(words)
        lengths.append(len(title))
        
        # Extract bigrams (2-word phrases)
        for i in range(len(words) - 1):
            all_bigrams.append((words[i], words[i+1]))
    
    # Count frequency
    keyword_freq = Counter(all_keywords)
    bigram_freq = Counter(all_bigrams)
    
    # Find common prefixes (first 2 words)
    prefixes = []
    for title in titles:
        words = tokenize_title(title)
        if len(words) >= 2:
            prefixes.append(' '.join(words[:2]))
    prefix_freq = Counter(prefixes)
    
    # Find common suffixes (last 2 words)
    suffixes = []
    for title in titles:
        words = tokenize_title(title)
        if len(words) >= 2:
            suffixes.append(' '.join(words[-2:]))
    suffix_freq = Counter(suffixes)
    
    return {
        'keywords': dict(keyword_freq.most_common(20)),
        'bigrams': {' '.join(k): v for k, v in bigram_freq.most_common(10)},
        'avg_length': int(sum(lengths) / len(lengths)) if lengths else 0,
        'common_prefixes': [k for k, v in prefix_freq.most_common(5)],
        'common_suffixes': [k for k, v in suffix_freq.most_common(5)]
    }


def search_competitors_on_ebay(ebay, title, limit=10):
    """
    Search eBay.de for competitor listings.
    
    Returns:
        list: [(item_id, title, price), ...]
    """
    # Extract search query (core keywords)
    query = extract_search_keywords(title, max_words=2)
    
    print(f"  🔍 Search query: '{query}'")
    
    try:
        # Search
        response = ebay._request('GET', f'/buy/browse/v1/item_summary/search', params={
            'q': query,
            'limit': limit,
            'filter': 'buyingOptions:{FIXED_PRICE}'
        })
        
        items = response.get('itemSummaries', [])
        
        competitors = []
        for item in items:
            item_id = item.get('itemId', '')
            title = item.get('title', '')
            price = item.get('price', {}).get('value', 0)
            
            if item_id and title:
                competitors.append((item_id, title, float(price)))
        
        return competitors
        
    except Exception as e:
        print(f"  ❌ Search failed: {e}")
        return []


def build_optimized_title(current_title, patterns, max_length=80):
    """
    Build optimized title using competitor patterns.
    
    Strategy:
    1. Keep core product keywords from current title
    2. Add high-frequency keywords from competitors
    3. Use common prefix/suffix patterns
    4. Stay under 80 chars (eBay.de limit)
    
    Returns:
        str: Optimized title
    """
    # Tokenize current title
    current_words = tokenize_title(current_title)
    
    # Get high-value keywords from competitors (top 10)
    competitor_keywords = list(patterns['keywords'].keys())[:10]
    
    # Start with most common prefix if good
    prefixes = patterns['common_prefixes']
    prefix = prefixes[0] if prefixes else None
    
    # Core words (from current title)
    core_words = current_words[:5]  # Keep first 5 words as base
    
    # Add missing high-value keywords
    added_keywords = []
    for keyword in competitor_keywords:
        if keyword not in current_words and len(added_keywords) < 5:
            added_keywords.append(keyword)
    
    # Build title parts
    parts = []
    
    # Add core
    parts.extend(core_words)
    
    # Add high-value keywords
    parts.extend(added_keywords)
    
    # Join and capitalize
    optimized = ' '.join(parts)
    optimized = optimized.title()
    
    # Truncate to 80 chars
    if len(optimized) > max_length:
        optimized = optimized[:max_length].rsplit(' ', 1)[0]
    
    return optimized


def optimize_title_from_competitors(ebay, product_id, current_title=None):
    """
    Optimize title by analyzing competitor titles.
    
    Args:
        ebay: eBay client
        product_id: AliExpress product ID (for audit trail)
        current_title: Current title (if available)
    
    Returns:
        dict: {
            'original_title': str,
            'optimized_title': str,
            'competitors_analyzed': int,
            'patterns': dict,
            'competitor_titles': [str, ...],
            'competitor_prices': [float, ...]
        }
    """
    print(f"\n{'='*60}")
    print(f"TITLE OPTIMIZATION")
    print(f"{'='*60}\n")
    
    if not current_title:
        print(f"  ⚠️  No current title provided")
        return None
    
    print(f"  📝 Current title: {current_title}")
    print(f"  📏 Length: {len(current_title)} chars\n")
    
    # Search competitors
    print(f"  🔍 Searching competitors on eBay.de...")
    competitors = search_competitors_on_ebay(ebay, current_title, limit=10)
    
    if not competitors:
        print(f"  ❌ No competitors found")
        return None
    
    print(f"  ✅ Found {len(competitors)} competitors\n")
    
    # Extract titles and prices
    competitor_titles = [title for _, title, _ in competitors]
    competitor_prices = [price for _, _, price in competitors]
    
    # Show some examples
    print(f"  📋 Example competitor titles:")
    for i, (_, title, price) in enumerate(competitors[:5], 1):
        print(f"    {i}. {title[:60]}... (€{price:.2f})")
    
    # Extract patterns
    print(f"\n  🔍 Analyzing keyword patterns...")
    patterns = extract_patterns(competitor_titles)
    
    print(f"\n  📊 Top keywords:")
    for keyword, count in list(patterns['keywords'].items())[:10]:
        print(f"    • {keyword}: {count}x")
    
    print(f"\n  📊 Top bigrams:")
    for bigram, count in list(patterns['bigrams'].items())[:5]:
        print(f"    • {bigram}: {count}x")
    
    print(f"\n  📏 Average title length: {patterns['avg_length']} chars")
    
    # Build optimized title
    print(f"\n  ⚙️  Building optimized title...")
    optimized_title = build_optimized_title(current_title, patterns, max_length=80)
    
    print(f"\n  {'='*60}")
    print(f"  RESULT")
    print(f"  {'='*60}")
    print(f"  Original:  {current_title}")
    print(f"  Optimized: {optimized_title}")
    print(f"  Length:    {len(current_title)} → {len(optimized_title)} chars")
    print(f"  {'='*60}\n")
    
    return {
        'product_id': product_id,
        'original_title': current_title,
        'optimized_title': optimized_title,
        'competitors_analyzed': len(competitors),
        'patterns': patterns,
        'competitor_titles': competitor_titles,
        'competitor_prices': competitor_prices,
        'avg_competitor_price': sum(competitor_prices) / len(competitor_prices) if competitor_prices else 0,
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimize title from competitor analysis')
    parser.add_argument('product_id', help='AliExpress product ID')
    parser.add_argument('--current-title', help='Current title to optimize')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get current title from DB if not provided
    current_title = args.current_title
    if not current_title:
        import sqlite3
        conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM products WHERE aliexpress_product_id = ?', (args.product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            current_title = row[0]
        else:
            print(f"❌ Product {args.product_id} not found in database")
            print(f"💡 Use --current-title to provide a title")
            return 1
    
    # Optimize
    result = optimize_title_from_competitors(ebay, args.product_id, current_title)
    
    if not result:
        return 1
    
    # Save if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved to {output_path}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
