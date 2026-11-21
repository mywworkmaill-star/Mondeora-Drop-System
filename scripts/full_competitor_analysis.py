#!/usr/bin/env python3
"""
Full Competitor Analysis
=========================

Complete competitor intelligence: aspects, title, price, features - EVERYTHING!

COLLECTS:
1. Aspects (item specifics)
2. Title patterns & keywords
3. Pricing (item + shipping)
4. Description features
5. Image count
6. Shipping details

USAGE:
    python scripts/full_competitor_analysis.py <product_id>
    python scripts/full_competitor_analysis.py <product_id> --output report.json
"""

import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient

# Import our other analyzers
from scripts.scrape_competitor_aspects import scrape_competitor_aspects
from scripts.optimize_title_from_competitors import optimize_title_from_competitors
from scripts.price_intelligence import price_intelligence
from scripts.enrich_description_from_competitors import enrich_description_from_competitors


def full_competitor_analysis(ebay, ali, product_id):
    """
    Complete competitor analysis - ALL data!
    
    Args:
        ebay: eBay client
        ali: AliExpress client
        product_id: AliExpress product ID
    
    Returns:
        dict: Complete analysis report
    """
    print(f"\n{'='*70}")
    print(f"FULL COMPETITOR ANALYSIS")
    print(f"{'='*70}\n")
    print(f"  🎯 Product ID: {product_id}\n")
    
    # Get product from DB
    import sqlite3
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.title, p.ebay_price, pv.cost, p.ebay_item_id
        FROM products p
        LEFT JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.aliexpress_product_id = ?
        LIMIT 1
    ''', (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"  ❌ Product not found in database")
        return None
    
    title, current_price, cost, ebay_item_id = row
    
    print(f"  📝 Title: {title}")
    if current_price:
        print(f"  💰 Current Price: €{current_price:.2f}")
    if cost:
        print(f"  💵 Cost: €{cost:.2f}")
    if ebay_item_id:
        print(f"  🔗 eBay Item: {ebay_item_id}")
    print()
    
    # Results
    results = {
        'product_id': product_id,
        'title': title,
        'current_price': current_price,
        'cost': cost,
        'ebay_item_id': ebay_item_id,
        'timestamp': datetime.now().isoformat()
    }
    
    # 1. ASPECTS
    print(f"  {'='*70}")
    print(f"  1/4: SCRAPING COMPETITOR ASPECTS")
    print(f"  {'='*70}")
    
    try:
        aspects = scrape_competitor_aspects(product_id)
        results['aspects'] = {
            'merged_aspects': aspects if aspects else {},
            'count': len(aspects) if aspects else 0
        }
        print(f"  ✅ Scraped {results['aspects']['count']} aspects\n")
    except Exception as e:
        print(f"  ❌ Aspect scraping failed: {e}\n")
        results['aspects'] = {'error': str(e)}
    
    # 2. TITLE OPTIMIZATION
    print(f"  {'='*70}")
    print(f"  2/4: ANALYZING TITLE PATTERNS")
    print(f"  {'='*70}")
    
    try:
        title_analysis = optimize_title_from_competitors(ebay, product_id, title)
        results['title'] = title_analysis
        print(f"  ✅ Analyzed {title_analysis['competitors_analyzed']} competitor titles\n")
    except Exception as e:
        print(f"  ❌ Title analysis failed: {e}\n")
        results['title'] = {'error': str(e)}
    
    # 3. PRICE INTELLIGENCE
    print(f"  {'='*70}")
    print(f"  3/4: ANALYZING COMPETITOR PRICES")
    print(f"  {'='*70}")
    
    try:
        price_analysis = price_intelligence(ebay, product_id, title, current_price, cost, strategy='undercut')
        results['pricing'] = price_analysis
        print(f"  ✅ Analyzed {price_analysis['competitors_analyzed']} competitor prices\n")
    except Exception as e:
        print(f"  ❌ Price analysis failed: {e}\n")
        results['pricing'] = {'error': str(e)}
    
    # 4. DESCRIPTION ENRICHMENT
    print(f"  {'='*70}")
    print(f"  4/4: EXTRACTING DESCRIPTION FEATURES")
    print(f"  {'='*70}")
    
    try:
        desc_analysis = enrich_description_from_competitors(ebay, product_id, title)
        results['description'] = desc_analysis
        if desc_analysis:
            print(f"  ✅ Extracted from {desc_analysis['competitors_analyzed']} descriptions\n")
    except Exception as e:
        print(f"  ❌ Description analysis failed: {e}\n")
        results['description'] = {'error': str(e)}
    
    # SUMMARY
    print(f"\n  {'='*70}")
    print(f"  ANALYSIS COMPLETE!")
    print(f"  {'='*70}\n")
    
    # Count successes
    successes = sum(1 for k in ['aspects', 'title', 'pricing', 'description'] 
                    if k in results and 'error' not in results[k])
    
    print(f"  ✅ Successful analyses: {successes}/4\n")
    
    # Show key findings
    print(f"  📊 KEY FINDINGS:")
    print(f"  {'─'*70}")
    
    # Aspects
    if 'aspects' in results and 'count' in results['aspects']:
        print(f"  🏆 Competitor Aspects: {results['aspects']['count']}")
        for name, value in list(results['aspects']['merged_aspects'].items())[:5]:
            print(f"      • {name}: {value}")
    
    # Title
    if 'title' in results and 'optimized_title' in results['title']:
        print(f"\n  📝 Title Optimization:")
        print(f"      Original:  {results['title']['original_title'][:50]}...")
        print(f"      Optimized: {results['title']['optimized_title'][:50]}...")
    
    # Pricing
    if 'pricing' in results and 'recommendation' in results['pricing']:
        rec = results['pricing']['recommendation']
        print(f"\n  💰 Price Recommendation:")
        print(f"      Current:     €{current_price:.2f}" if current_price else "      Current:     N/A")
        print(f"      Recommended: €{rec['recommended_price']:.2f}")
        print(f"      Strategy:    {rec['strategy']}")
        if rec.get('profit_margin'):
            print(f"      Margin:      {rec['profit_margin']*100:.1f}%")
    
    # Description
    if 'description' in results and 'merged_features' in results['description']:
        feat_count = len(results['description']['merged_features'])
        print(f"\n  📋 Description Features: {feat_count} common features")
    
    print(f"  {'─'*70}\n")
    
    return results


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Full competitor analysis')
    parser.add_argument('product_id', help='AliExpress product ID')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize clients
    ebay = eBayRESTClient()
    
    from src.api.aliexpress_client import AliExpressAPIClient
    ali = AliExpressAPIClient()
    
    # Analyze
    result = full_competitor_analysis(ebay, ali, args.product_id)
    
    if not result:
        return 1
    
    # Save if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 Saved full report to {output_path}\n")
    
    print(f"  {'='*70}")
    print(f"  ✅ COMPLETE COMPETITOR INTELLIGENCE GATHERED!")
    print(f"  {'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
