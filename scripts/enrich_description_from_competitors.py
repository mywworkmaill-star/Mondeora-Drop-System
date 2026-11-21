#!/usr/bin/env python3
"""
Description Enrichment from Competitors
========================================

Extract features, bullets, and highlights from competitor descriptions.

STRATEGY:
1. Find 5-10 competitors
2. Extract their description HTML/text
3. Find common bullet points and features
4. Merge into our description

USAGE:
    python scripts/enrich_description_from_competitors.py <product_id>
    python scripts/enrich_description_from_competitors.py <product_id> --output features.json
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import quote

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from scripts.optimize_title_from_competitors import extract_search_keywords


def extract_features_from_description(description_html):
    """
    Extract bullet points and features from HTML description.
    
    Returns:
        list: [feature1, feature2, ...]
    """
    if not description_html:
        return []
    
    features = []
    
    # Remove HTML tags but keep line breaks
    text = re.sub(r'<br\s*/?>','\n', description_html, flags=re.IGNORECASE)
    text = re.sub(r'<li>', '\n• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Split by lines
    lines = text.split('\n')
    
    # Extract lines that look like features
    for line in lines:
        line = line.strip()
        
        # Skip empty or very short
        if not line or len(line) < 10:
            continue
        
        # Skip very long (probably description text, not bullet)
        if len(line) > 150:
            continue
        
        # Look for bullet-like patterns
        is_bullet = False
        
        # Starts with bullet char
        if line.startswith('•') or line.startswith('-') or line.startswith('*'):
            is_bullet = True
            line = line[1:].strip()
        
        # Contains feature keywords
        feature_keywords = [
            'material', 'größe', 'farbe', 'gewicht', 'abmessungen',
            'lieferumfang', 'eigenschaften', 'merkmale', 'besonderheiten',
            'spülmaschinenfest', 'rostfrei', 'klappbar', 'platzsparend',
            'premium', 'hochwertig', 'stabil', 'langlebig'
        ]
        
        if any(kw in line.lower() for kw in feature_keywords):
            is_bullet = True
        
        # Has colon (key: value format)
        if ':' in line and len(line.split(':')[0]) < 30:
            is_bullet = True
        
        if is_bullet:
            # Clean
            line = line.strip('•-*. ')
            if line:
                features.append(line)
    
    return features


def get_competitor_descriptions(ebay, title, limit=5):
    """
    Get competitor item descriptions.
    
    Returns:
        list: [
            {
                'item_id': str,
                'title': str,
                'description': str,
                'features': [str, ...]
            },
            ...
        ]
    """
    # Search competitors
    query = extract_search_keywords(title, max_words=2)
    print(f"  🔍 Search query: '{query}'")
    
    try:
        response = ebay._request('GET', f'/buy/browse/v1/item_summary/search', params={
            'q': query,
            'limit': limit,
            'filter': 'buyingOptions:{FIXED_PRICE}'
        })
        
        items = response.get('itemSummaries', [])
        
        competitors = []
        for item in items[:limit]:
            item_id = item.get('itemId', '')
            title = item.get('title', '')
            
            if not item_id:
                continue
            
            # Get full item details (has description)
            try:
                # item_id already has v1|xxx|0 format from search
                full_item_id = quote(item_id, safe='')
                full_item = ebay._request('GET', f'/buy/browse/v1/item/{full_item_id}')
                
                description = full_item.get('description', '')
                
                # Extract features
                features = extract_features_from_description(description)
                
                competitors.append({
                    'item_id': item_id,
                    'title': title,
                    'description': description[:500] if description else '',  # Truncate for storage
                    'features': features
                })
                
            except Exception as e:
                print(f"    ⚠️  Failed to get details for {item_id}: {e}")
                continue
        
        return competitors
        
    except Exception as e:
        print(f"  ❌ Search failed: {e}")
        return []


def merge_features(all_features, min_frequency=2):
    """
    Merge features from multiple competitors.
    
    Args:
        all_features: [[features1], [features2], ...]
        min_frequency: Minimum times a feature must appear
    
    Returns:
        list: [feature, ...] sorted by frequency
    """
    # Flatten
    flat_features = []
    for features in all_features:
        flat_features.extend(features)
    
    # Normalize (lowercase, strip)
    normalized = [f.lower().strip() for f in flat_features]
    
    # Count
    freq = Counter(normalized)
    
    # Filter by frequency
    common = [(f, count) for f, count in freq.items() if count >= min_frequency]
    
    # Sort by frequency
    common.sort(key=lambda x: x[1], reverse=True)
    
    return [f for f, count in common]


def enrich_description_from_competitors(ebay, product_id, title):
    """
    Enrich description with competitor features.
    
    Returns:
        dict: {
            'product_id': str,
            'title': str,
            'competitors_analyzed': int,
            'all_features': [[str, ...], ...],
            'merged_features': [str, ...],
            'unique_features': [str, ...],
            'competitor_data': [...]
        }
    """
    print(f"\n{'='*60}")
    print(f"DESCRIPTION ENRICHMENT")
    print(f"{'='*60}\n")
    
    print(f"  📝 Product: {title[:60]}...\n")
    
    # Get competitors
    print(f"  🔍 Searching competitors on eBay.de...")
    competitors = get_competitor_descriptions(ebay, title, limit=5)
    
    if not competitors:
        print(f"  ❌ No competitors found")
        return None
    
    print(f"  ✅ Found {len(competitors)} competitors\n")
    
    # Extract features
    all_features = [c['features'] for c in competitors]
    
    print(f"  📊 Features per competitor:")
    for i, comp in enumerate(competitors, 1):
        print(f"    {i}. {len(comp['features'])} features")
        for feature in comp['features'][:3]:
            print(f"       • {feature[:60]}...")
    print()
    
    # Merge common features
    merged = merge_features(all_features, min_frequency=2)
    
    print(f"  🔗 Merged features (appear in 2+ competitors):")
    for feature in merged[:10]:
        print(f"    ✅ {feature}")
    print()
    
    # Get unique features (appear only once but high-value)
    all_flat = []
    for features in all_features:
        all_flat.extend([f.lower().strip() for f in features])
    
    freq = Counter(all_flat)
    unique = [f for f, count in freq.items() if count == 1]
    
    print(f"  💎 Unique features (appear once): {len(unique)}")
    if unique:
        for feature in unique[:5]:
            print(f"    • {feature[:60]}...")
    print()
    
    print(f"  {'='*60}")
    print(f"  SUMMARY")
    print(f"  {'='*60}")
    print(f"  Competitors analyzed: {len(competitors)}")
    print(f"  Total features extracted: {len(all_flat)}")
    print(f"  Common features (2+): {len(merged)}")
    print(f"  Unique features (1): {len(unique)}")
    print(f"  {'='*60}\n")
    
    return {
        'product_id': product_id,
        'title': title,
        'competitors_analyzed': len(competitors),
        'all_features': all_features,
        'merged_features': merged,
        'unique_features': unique[:20],  # Limit to top 20
        'competitor_data': competitors,
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich description from competitor analysis')
    parser.add_argument('product_id', help='AliExpress product ID')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get product title from DB
    import sqlite3
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title FROM products WHERE aliexpress_product_id = ?', (args.product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ Product {args.product_id} not found in database")
        return 1
    
    title = row[0]
    
    # Analyze
    result = enrich_description_from_competitors(ebay, args.product_id, title)
    
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
