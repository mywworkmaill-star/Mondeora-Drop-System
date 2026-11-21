#!/usr/bin/env python3
"""
Price Intelligence from Competitors
====================================

Analyze competitor prices and calculate optimal competitive pricing.

STRATEGY:
1. Find 5-10 competitors for same product
2. Extract their prices
3. Calculate price range (min, max, avg, median)
4. Recommend competitive price based on strategy

PRICING STRATEGIES:
- undercut: 5-10% below average (win on price)
- match: Same as average (standard)
- premium: 5-10% above average (perceived quality)
- aggressive: Lowest competitor price - 5%

USAGE:
    python scripts/price_intelligence.py <product_id>
    python scripts/price_intelligence.py <product_id> --strategy undercut
"""

import sys
import json
import statistics
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from scripts.optimize_title_from_competitors import extract_search_keywords


def search_competitor_prices(ebay, title, limit=10):
    """
    Search eBay.de for competitor prices.
    
    Returns:
        list: [(item_id, title, price, shipping_cost), ...]
    """
    # Extract search query
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
            
            # Price
            price_obj = item.get('price', {})
            price = float(price_obj.get('value', 0))
            currency = price_obj.get('currency', 'EUR')
            
            # Shipping
            shipping_obj = item.get('shippingOptions', [{}])[0] if item.get('shippingOptions') else {}
            shipping_cost_obj = shipping_obj.get('shippingCost', {})
            shipping_cost = float(shipping_cost_obj.get('value', 0))
            
            # Total price (item + shipping)
            total_price = price + shipping_cost
            
            if item_id and title and price > 0:
                competitors.append({
                    'item_id': item_id,
                    'title': title,
                    'price': price,
                    'shipping_cost': shipping_cost,
                    'total_price': total_price,
                    'currency': currency
                })
        
        return competitors
        
    except Exception as e:
        print(f"  ❌ Search failed: {e}")
        return []


def calculate_price_stats(prices):
    """
    Calculate price statistics.
    
    Args:
        prices: list of floats
    
    Returns:
        dict: {min, max, avg, median, std_dev}
    """
    if not prices:
        return {}
    
    return {
        'min': min(prices),
        'max': max(prices),
        'avg': statistics.mean(prices),
        'median': statistics.median(prices),
        'std_dev': statistics.stdev(prices) if len(prices) > 1 else 0,
        'count': len(prices)
    }


def recommend_price(stats, strategy='undercut', cost=None, min_margin=0.30):
    """
    Recommend optimal price based on strategy.
    
    Args:
        stats: Price statistics dict
        strategy: 'undercut', 'match', 'premium', 'aggressive'
        cost: Our product cost (for margin calculation)
        min_margin: Minimum profit margin (default 30%)
    
    Returns:
        dict: {
            'recommended_price': float,
            'strategy': str,
            'reason': str,
            'profit_margin': float (if cost provided)
        }
    """
    if not stats:
        return None
    
    avg_price = stats['avg']
    min_price = stats['min']
    max_price = stats['max']
    median_price = stats['median']
    
    # Calculate recommended price based on strategy
    if strategy == 'undercut':
        # 5-10% below average
        recommended = avg_price * 0.93  # 7% below avg
        reason = f"7% below average (€{avg_price:.2f})"
        
    elif strategy == 'match':
        # Match median (more stable than average)
        recommended = median_price
        reason = f"Match market median"
        
    elif strategy == 'premium':
        # 5-10% above average
        recommended = avg_price * 1.07  # 7% above avg
        reason = f"7% above average (€{avg_price:.2f})"
        
    elif strategy == 'aggressive':
        # Lowest competitor - 5%
        recommended = min_price * 0.95
        reason = f"5% below lowest competitor (€{min_price:.2f})"
        
    else:
        # Default: match median
        recommended = median_price
        reason = f"Default: match median"
    
    # Check minimum margin if cost provided
    if cost:
        profit_margin = (recommended - cost) / recommended if recommended > 0 else 0
        
        # Enforce minimum margin
        if profit_margin < min_margin:
            min_price_for_margin = cost / (1 - min_margin)
            recommended = max(recommended, min_price_for_margin)
            reason += f" (adjusted for {min_margin*100:.0f}% margin)"
            profit_margin = (recommended - cost) / recommended
    else:
        profit_margin = None
    
    return {
        'recommended_price': round(recommended, 2),
        'strategy': strategy,
        'reason': reason,
        'profit_margin': round(profit_margin, 3) if profit_margin else None,
        'profit_amount': round(recommended - cost, 2) if cost else None
    }


def price_intelligence(ebay, product_id, title, current_price=None, cost=None, strategy='undercut'):
    """
    Full price intelligence analysis.
    
    Args:
        ebay: eBay client
        product_id: AliExpress product ID
        title: Product title
        current_price: Our current price (if any)
        cost: Our product cost
        strategy: Pricing strategy
    
    Returns:
        dict: Full price analysis
    """
    print(f"\n{'='*60}")
    print(f"PRICE INTELLIGENCE")
    print(f"{'='*60}\n")
    
    print(f"  📝 Product: {title[:60]}...")
    if current_price:
        print(f"  💰 Current price: €{current_price:.2f}")
    if cost:
        print(f"  💵 Cost: €{cost:.2f}")
        if current_price:
            margin = (current_price - cost) / current_price if current_price > 0 else 0
            print(f"  📊 Current margin: {margin*100:.1f}%")
    print()
    
    # Search competitors
    print(f"  🔍 Searching competitor prices on eBay.de...")
    competitors = search_competitor_prices(ebay, title, limit=10)
    
    if not competitors:
        print(f"  ❌ No competitors found")
        return None
    
    print(f"  ✅ Found {len(competitors)} competitors\n")
    
    # Show examples
    print(f"  📋 Competitor prices:")
    for i, comp in enumerate(competitors[:5], 1):
        shipping_note = f" (+€{comp['shipping_cost']:.2f} shipping)" if comp['shipping_cost'] > 0 else " (free shipping)"
        print(f"    {i}. €{comp['price']:.2f}{shipping_note} = €{comp['total_price']:.2f} total")
        print(f"       {comp['title'][:55]}...")
    print()
    
    # Calculate stats (use total_price for fair comparison)
    total_prices = [c['total_price'] for c in competitors]
    item_prices = [c['price'] for c in competitors]
    
    stats_total = calculate_price_stats(total_prices)
    stats_item = calculate_price_stats(item_prices)
    
    print(f"  📊 Price statistics (TOTAL with shipping):")
    print(f"    Min:    €{stats_total['min']:.2f}")
    print(f"    Max:    €{stats_total['max']:.2f}")
    print(f"    Avg:    €{stats_total['avg']:.2f}")
    print(f"    Median: €{stats_total['median']:.2f}")
    if stats_total['std_dev'] > 0:
        print(f"    StdDev: €{stats_total['std_dev']:.2f}")
    print()
    
    print(f"  📊 Price statistics (ITEM only, no shipping):")
    print(f"    Min:    €{stats_item['min']:.2f}")
    print(f"    Max:    €{stats_item['max']:.2f}")
    print(f"    Avg:    €{stats_item['avg']:.2f}")
    print(f"    Median: €{stats_item['median']:.2f}")
    print()
    
    # Recommend price (use item stats for our item price)
    print(f"  ⚙️  Calculating recommended price...")
    print(f"  Strategy: {strategy}")
    print()
    
    recommendation = recommend_price(stats_item, strategy=strategy, cost=cost, min_margin=0.30)
    
    print(f"  {'='*60}")
    print(f"  RECOMMENDATION")
    print(f"  {'='*60}")
    print(f"  Recommended: €{recommendation['recommended_price']:.2f}")
    print(f"  Strategy:    {recommendation['strategy']}")
    print(f"  Reason:      {recommendation['reason']}")
    if recommendation['profit_margin']:
        print(f"  Margin:      {recommendation['profit_margin']*100:.1f}% (€{recommendation['profit_amount']:.2f} profit)")
    
    if current_price:
        diff = recommendation['recommended_price'] - current_price
        pct_change = (diff / current_price * 100) if current_price > 0 else 0
        print(f"  Change:      €{diff:+.2f} ({pct_change:+.1f}%)")
    
    print(f"  {'='*60}\n")
    
    return {
        'product_id': product_id,
        'title': title,
        'current_price': current_price,
        'cost': cost,
        'competitors_analyzed': len(competitors),
        'competitor_prices': competitors,
        'stats_total': stats_total,
        'stats_item': stats_item,
        'recommendation': recommendation,
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Price intelligence from competitor analysis')
    parser.add_argument('product_id', help='AliExpress product ID')
    parser.add_argument('--strategy', choices=['undercut', 'match', 'premium', 'aggressive'], 
                        default='undercut', help='Pricing strategy')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize
    ebay = eBayRESTClient()
    
    # Get product from DB
    import sqlite3
    conn = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.title, p.ebay_price, pv.cost
        FROM products p
        LEFT JOIN product_variants pv ON p.id = pv.product_id
        WHERE p.aliexpress_product_id = ?
        LIMIT 1
    ''', (args.product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ Product {args.product_id} not found in database")
        return 1
    
    title, current_price, cost = row
    
    # Analyze
    result = price_intelligence(
        ebay, 
        args.product_id, 
        title,
        current_price=current_price,
        cost=cost,
        strategy=args.strategy
    )
    
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
