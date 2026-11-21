#!/usr/bin/env python3
"""
Batch Competitor Analysis
==========================

Run full competitor analysis on ALL products in database.

USAGE:
    python scripts/batch_competitor_analysis.py
    python scripts/batch_competitor_analysis.py --limit 10
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.api.aliexpress_client import AliExpressAPIClient
from scripts.full_competitor_analysis import full_competitor_analysis


def batch_analyze_all_products(limit=None):
    """
    Analyze all products in database.
    
    Args:
        limit: Max products to analyze (None = all)
    """
    print(f"\n{'='*70}")
    print(f"BATCH COMPETITOR ANALYSIS")
    print(f"{'='*70}\n")
    
    # Initialize clients
    ebay = eBayRESTClient()
    ali = AliExpressAPIClient()
    
    # Get all products
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    
    query = '''
        SELECT DISTINCT p.aliexpress_product_id, p.title, p.ebay_item_id
        FROM products p
        WHERE p.ebay_item_id IS NOT NULL
        ORDER BY p.id DESC
    '''
    
    if limit:
        query += f' LIMIT {limit}'
    
    cursor.execute(query)
    products = cursor.fetchall()
    conn.close()
    
    total = len(products)
    print(f"  📦 Found {total} products to analyze\n")
    
    if total == 0:
        print(f"  ⚠️  No products found")
        return
    
    # Create output directory
    output_dir = ROOT / 'data' / 'audit' / 'competitor_analysis'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track results
    results_summary = {
        'total_products': total,
        'successful': 0,
        'failed': 0,
        'products': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Analyze each
    for idx, (product_id, title, ebay_item_id) in enumerate(products, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{total}] ANALYZING: {product_id}")
        print(f"{'='*70}")
        print(f"  Title: {title[:60]}...")
        print(f"  eBay: {ebay_item_id}")
        print()
        
        try:
            # Run analysis
            result = full_competitor_analysis(ebay, ali, product_id)
            
            if result:
                # Save individual report
                output_file = output_dir / f'analysis_{product_id}.json'
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                print(f"\n  ✅ SUCCESS - Saved to {output_file.name}")
                
                # Add to summary
                product_summary = {
                    'product_id': product_id,
                    'title': title,
                    'ebay_item_id': ebay_item_id,
                    'status': 'success',
                    'aspects_count': result.get('aspects', {}).get('count', 0),
                    'competitors_found': result.get('title', {}).get('competitors_analyzed', 0),
                    'current_price': result.get('current_price'),
                    'recommended_price': result.get('pricing', {}).get('recommendation', {}).get('recommended_price'),
                    'price_change': None,
                    'optimized_title': result.get('title', {}).get('optimized_title')
                }
                
                # Calculate price change
                if product_summary['current_price'] and product_summary['recommended_price']:
                    curr = product_summary['current_price']
                    rec = product_summary['recommended_price']
                    product_summary['price_change'] = round(rec - curr, 2)
                    product_summary['price_change_pct'] = round((rec - curr) / curr * 100, 1) if curr > 0 else 0
                
                results_summary['products'].append(product_summary)
                results_summary['successful'] += 1
            else:
                print(f"\n  ❌ FAILED - No result returned")
                results_summary['products'].append({
                    'product_id': product_id,
                    'title': title,
                    'status': 'failed',
                    'error': 'No result returned'
                })
                results_summary['failed'] += 1
                
        except Exception as e:
            print(f"\n  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            
            results_summary['products'].append({
                'product_id': product_id,
                'title': title,
                'status': 'error',
                'error': str(e)
            })
            results_summary['failed'] += 1
    
    # Save summary
    summary_file = output_dir / f'batch_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(results_summary, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n\n{'='*70}")
    print(f"BATCH ANALYSIS COMPLETE!")
    print(f"{'='*70}\n")
    
    print(f"  📊 SUMMARY:")
    print(f"  {'─'*70}")
    print(f"  Total products:    {total}")
    print(f"  ✅ Successful:     {results_summary['successful']}")
    print(f"  ❌ Failed:         {results_summary['failed']}")
    print(f"  Success rate:      {results_summary['successful']/total*100:.1f}%")
    print(f"  {'─'*70}\n")
    
    # Top insights
    successful = [p for p in results_summary['products'] if p['status'] == 'success']
    
    if successful:
        print(f"  💡 KEY INSIGHTS:\n")
        
        # Average aspects added
        avg_aspects = sum(p['aspects_count'] for p in successful) / len(successful)
        print(f"  🏆 Avg competitor aspects: {avg_aspects:.1f}")
        
        # Price changes
        price_changes = [p for p in successful if p.get('price_change') is not None]
        if price_changes:
            avg_price_change = sum(p['price_change'] for p in price_changes) / len(price_changes)
            avg_pct_change = sum(p['price_change_pct'] for p in price_changes) / len(price_changes)
            print(f"  💰 Avg price change: €{avg_price_change:+.2f} ({avg_pct_change:+.1f}%)")
            
            # Biggest opportunities
            sorted_by_change = sorted(price_changes, key=lambda x: abs(x['price_change']), reverse=True)
            print(f"\n  🎯 Top 5 price optimization opportunities:")
            for i, p in enumerate(sorted_by_change[:5], 1):
                print(f"    {i}. {p['title'][:40]}...")
                print(f"       €{p['current_price']:.2f} → €{p['recommended_price']:.2f} ({p['price_change']:+.2f}, {p['price_change_pct']:+.1f}%)")
        
        print(f"\n  {'─'*70}\n")
    
    print(f"  💾 Reports saved to: {output_dir}")
    print(f"  📋 Summary saved to: {summary_file.name}\n")
    
    print(f"  {'='*70}\n")
    
    return results_summary


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch competitor analysis for all products')
    parser.add_argument('--limit', type=int, help='Limit number of products to analyze')
    
    args = parser.parse_args()
    
    batch_analyze_all_products(limit=args.limit)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
