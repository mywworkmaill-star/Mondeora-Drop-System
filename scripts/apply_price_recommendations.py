#!/usr/bin/env python3
"""
Apply Price Recommendations
============================

Apply competitor-based price recommendations to eBay listings.

USAGE:
    python scripts/apply_price_recommendations.py
    python scripts/apply_price_recommendations.py --dry-run
    python scripts/apply_price_recommendations.py --min-change 5  # Only apply if change >= €5
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def load_latest_batch_summary():
    """Load the latest batch summary file."""
    summary_dir = ROOT / 'data' / 'audit' / 'competitor_analysis'
    
    if not summary_dir.exists():
        print(f"❌ No batch summaries found in {summary_dir}")
        return None
    
    # Find latest summary
    summaries = list(summary_dir.glob('batch_summary_*.json'))
    
    if not summaries:
        print(f"❌ No batch summary files found")
        return None
    
    latest = max(summaries, key=lambda p: p.stat().st_mtime)
    
    print(f"📋 Loading: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_price_recommendations(dry_run=False, min_change=0):
    """
    Apply price recommendations from competitor analysis.
    
    Args:
        dry_run: If True, don't actually update prices
        min_change: Minimum price change (abs value) to apply
    """
    print(f"\n{'='*70}")
    print(f"APPLY PRICE RECOMMENDATIONS")
    print(f"{'='*70}\n")
    
    if dry_run:
        print(f"  🔍 DRY RUN MODE (no changes will be made)\n")
    
    # Load summary
    summary = load_latest_batch_summary()
    
    if not summary:
        return
    
    # Get successful products with price changes
    products = [p for p in summary['products'] 
                if p['status'] == 'success' 
                and p.get('price_change') is not None
                and abs(p['price_change']) >= min_change]
    
    print(f"  📦 Found {len(products)} products with price recommendations\n")
    
    if min_change > 0:
        print(f"  ⚙️  Filter: Minimum change >= €{min_change}\n")
    
    # Initialize eBay client
    ebay = eBayRESTClient()
    
    # Track results
    results = {
        'total': len(products),
        'updated': 0,
        'skipped': 0,
        'failed': 0,
        'changes': []
    }
    
    # Process each
    for idx, product in enumerate(products, 1):
        product_id = product['product_id']
        title = product['title']
        current = product['current_price']
        recommended = product['recommended_price']
        change = product['price_change']
        change_pct = product['price_change_pct']
        
        print(f"\n[{idx}/{len(products)}] {title[:50]}...")
        print(f"  Current:     €{current:.2f}")
        print(f"  Recommended: €{recommended:.2f}")
        print(f"  Change:      €{change:+.2f} ({change_pct:+.1f}%)")
        
        if dry_run:
            print(f"  ℹ️  DRY RUN - would update")
            results['updated'] += 1
            results['changes'].append({
                'product_id': product_id,
                'title': title,
                'old_price': current,
                'new_price': recommended,
                'change': change,
                'status': 'dry_run'
            })
            continue
        
        try:
            # Update database
            conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products
                SET ebay_price = ?
                WHERE aliexpress_product_id = ?
            ''', (recommended, product_id))
            
            conn.commit()
            conn.close()
            
            print(f"  ✅ Database updated")
            
            # TODO: Update eBay listing price via API
            # This requires getting SKU and updating inventory item
            
            results['updated'] += 1
            results['changes'].append({
                'product_id': product_id,
                'title': title,
                'old_price': current,
                'new_price': recommended,
                'change': change,
                'status': 'success'
            })
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results['failed'] += 1
            results['changes'].append({
                'product_id': product_id,
                'title': title,
                'old_price': current,
                'new_price': recommended,
                'change': change,
                'status': 'failed',
                'error': str(e)
            })
    
    # Summary
    print(f"\n\n{'='*70}")
    print(f"PRICE UPDATE SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"  📊 Results:")
    print(f"  ──────────────────────────────────────────")
    print(f"  Total products:    {results['total']}")
    print(f"  ✅ Updated:        {results['updated']}")
    print(f"  ❌ Failed:         {results['failed']}")
    print(f"  ──────────────────────────────────────────\n")
    
    # Show biggest changes
    changes_sorted = sorted(results['changes'], key=lambda x: abs(x['change']), reverse=True)
    
    print(f"  🎯 Top 10 changes:\n")
    for i, c in enumerate(changes_sorted[:10], 1):
        status_icon = "✅" if c['status'] == 'success' else "🔍" if c['status'] == 'dry_run' else "❌"
        print(f"    {i}. {status_icon} {c['title'][:40]}...")
        print(f"       €{c['old_price']:.2f} → €{c['new_price']:.2f} ({c['change']:+.2f})")
    
    print(f"\n  {'='*70}\n")
    
    # Save report
    if not dry_run and results['updated'] > 0:
        report_file = ROOT / 'data' / 'audit' / f'price_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"  💾 Report saved to: {report_file.name}\n")
    
    return results


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apply price recommendations')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--min-change', type=float, default=0, help='Minimum price change to apply (default: 0)')
    
    args = parser.parse_args()
    
    apply_price_recommendations(dry_run=args.dry_run, min_change=args.min_change)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
