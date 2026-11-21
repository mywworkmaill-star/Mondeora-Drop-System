#!/usr/bin/env python3
"""
Apply Competitor Intelligence to All Listings
==============================================

Apply title and price recommendations from batch analysis to all active listings.

USAGE:
    python scripts/apply_competitor_intelligence.py
    python scripts/apply_competitor_intelligence.py --dry-run
    python scripts/apply_competitor_intelligence.py --titles-only
    python scripts/apply_competitor_intelligence.py --prices-only
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient


def load_latest_batch_analysis():
    """Load latest batch competitor analysis."""
    analysis_dir = ROOT / 'data' / 'audit' / 'competitor_analysis'
    
    if not analysis_dir.exists():
        print(f"❌ No analysis directory found")
        return None
    
    # Find latest summary
    summaries = list(analysis_dir.glob('batch_summary_*.json'))
    
    if not summaries:
        print(f"❌ No batch analysis found")
        return None
    
    latest = max(summaries, key=lambda p: p.stat().st_mtime)
    
    print(f"📋 Loading: {latest.name}\n")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_titles(ebay, products, dry_run=False):
    """
    Apply optimized titles to eBay listings.
    
    Args:
        ebay: eBay client
        products: List of products with optimized_title
        dry_run: If True, don't actually update
    
    Returns:
        dict: Stats
    """
    print(f"\n{'='*70}")
    print(f"APPLY OPTIMIZED TITLES")
    print(f"{'='*70}\n")
    
    stats = {'total': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    
    for product in products:
        if 'optimized_title' not in product:
            continue
        
        product_id = product['product_id']
        original = product['title']
        optimized = product['optimized_title']
        
        # Skip if same
        if original == optimized:
            continue
        
        stats['total'] += 1
        
        print(f"[{stats['total']}] {product_id}")
        print(f"  Original:  {original[:60]}...")
        print(f"  Optimized: {optimized[:60]}...")
        
        if dry_run:
            print(f"  🔍 DRY RUN - would update")
            stats['updated'] += 1
            continue
        
        try:
            # Update database
            conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products
                SET title = ?
                WHERE aliexpress_product_id = ?
            ''', (optimized, product_id))
            
            conn.commit()
            conn.close()
            
            print(f"  ✅ Database updated")
            
            # TODO: Update eBay listing title via API
            # (Requires inventory item update)
            
            stats['updated'] += 1
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            stats['failed'] += 1
    
    return stats


def apply_prices(ebay, products, dry_run=False, min_change=0):
    """
    Apply recommended prices to eBay listings.
    
    Args:
        ebay: eBay client
        products: List of products with recommended_price
        dry_run: If True, don't actually update
        min_change: Minimum price change to apply (abs value)
    
    Returns:
        dict: Stats
    """
    print(f"\n{'='*70}")
    print(f"APPLY RECOMMENDED PRICES")
    print(f"{'='*70}\n")
    
    if min_change > 0:
        print(f"  ⚙️  Filter: Minimum change >= €{min_change}\n")
    
    stats = {'total': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    
    for product in products:
        if 'recommended_price' not in product or 'current_price' not in product:
            continue
        
        if not product['recommended_price'] or not product['current_price']:
            continue
        
        product_id = product['product_id']
        current = product['current_price']
        recommended = product['recommended_price']
        change = recommended - current
        
        # Skip if below threshold
        if abs(change) < min_change:
            continue
        
        stats['total'] += 1
        
        change_pct = (change / current * 100) if current > 0 else 0
        
        print(f"[{stats['total']}] {product_id}")
        print(f"  {product['title'][:50]}...")
        print(f"  Current:     €{current:.2f}")
        print(f"  Recommended: €{recommended:.2f}")
        print(f"  Change:      €{change:+.2f} ({change_pct:+.1f}%)")
        
        if dry_run:
            print(f"  🔍 DRY RUN - would update")
            stats['updated'] += 1
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
            
            # TODO: Update eBay offer price via API
            # (Requires offer update)
            
            stats['updated'] += 1
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            stats['failed'] += 1
    
    return stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apply competitor intelligence to all listings')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--titles-only', action='store_true', help='Only update titles')
    parser.add_argument('--prices-only', action='store_true', help='Only update prices')
    parser.add_argument('--min-price-change', type=float, default=5, 
                        help='Minimum price change to apply (default: €5)')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Load batch analysis
    analysis = load_latest_batch_analysis()
    
    if not analysis:
        return 1
    
    # Get successful products
    products = [p for p in analysis['products'] if p['status'] == 'success']
    
    print(f"📦 Found {len(products)} analyzed products\n")
    
    if args.dry_run:
        print(f"🔍 DRY RUN MODE (no changes will be made)\n")
    
    # Apply titles
    if not args.prices_only:
        title_stats = apply_titles(ebay, products, dry_run=args.dry_run)
        
        print(f"\n📝 Title Update Summary:")
        print(f"  Total: {title_stats['total']}")
        print(f"  ✅ Updated: {title_stats['updated']}")
        print(f"  ❌ Failed: {title_stats['failed']}")
    
    # Apply prices
    if not args.titles_only:
        price_stats = apply_prices(ebay, products, dry_run=args.dry_run, 
                                   min_change=args.min_price_change)
        
        print(f"\n💰 Price Update Summary:")
        print(f"  Total: {price_stats['total']}")
        print(f"  ✅ Updated: {price_stats['updated']}")
        print(f"  ❌ Failed: {price_stats['failed']}")
    
    print(f"\n{'='*70}")
    
    if args.dry_run:
        print(f"✅ DRY RUN COMPLETE - No changes made")
    else:
        print(f"✅ UPDATES APPLIED")
        print(f"\n⚠️  Note: eBay listings need manual refresh or API update")
        print(f"   Database updated, but eBay API update not yet implemented")
    
    print(f"{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
