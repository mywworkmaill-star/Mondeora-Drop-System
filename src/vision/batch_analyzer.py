"""
Batch Vision Analysis
Analyze multiple products at once and cache results
"""

import sys
import sqlite3
import time
from src.vision.aspect_extractor import VisionAspectExtractor


def batch_analyze(product_ids, delay=3):
    """
    Batch analyze multiple products
    
    Args:
        product_ids: List of product IDs
        delay: Seconds to wait between calls (rate limiting)
    """
    
    print(f"\n{'='*80}")
    print(f"BATCH VISION ANALYSIS")
    print(f"{'='*80}")
    print(f"Products: {len(product_ids)}")
    print(f"Rate limit delay: {delay}s between calls")
    
    # Get products
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(product_ids))
    cursor.execute(f'''
        SELECT id, title, image_url
        FROM products
        WHERE id IN ({placeholders})
    ''', product_ids)
    
    products = cursor.fetchall()
    conn.close()
    
    if not products:
        print("❌ No products found")
        return []
    
    print(f"Found: {len(products)} products\n")
    
    # Analyze each
    extractor = VisionAspectExtractor()
    results = []
    
    for idx, (pid, title, image_url) in enumerate(products, 1):
        print(f"\n[{idx}/{len(products)}] Product {pid}")
        print(f"   Title: {title[:50]}...")
        
        # Analyze
        result = extractor.get_cached_or_analyze(pid, image_url)
        results.append(result)
        
        # Show summary
        if result['status'] == 'success':
            print(f"   ✅ Confidence: {result['confidence_score']}%")
            if result['aspects']:
                aspects_str = ', '.join(result['aspects'].keys())
                print(f"   📊 Aspects: {aspects_str}")
        else:
            print(f"   ❌ Failed")
        
        # Rate limit (except last)
        if idx < len(products):
            print(f"   ⏳ Waiting {delay}s...")
            time.sleep(delay)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"BATCH COMPLETE")
    print(f"{'='*80}")
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    avg_confidence = sum(r['confidence_score'] for r in results if r['status'] == 'success') / success_count if success_count > 0 else 0
    
    print(f"Success: {success_count}/{len(results)}")
    print(f"Average Confidence: {avg_confidence:.1f}%")
    
    # Aspect coverage
    aspect_counts = {}
    for r in results:
        if r['status'] == 'success':
            for aspect in r['aspects'].keys():
                aspect_counts[aspect] = aspect_counts.get(aspect, 0) + 1
    
    if aspect_counts:
        print(f"\nAspect Coverage:")
        for aspect, count in sorted(aspect_counts.items(), key=lambda x: -x[1]):
            print(f"   {aspect}: {count}/{len(results)} ({count*100//len(results)}%)")
    
    return results


def analyze_ready_products(limit=10):
    """Analyze products ready for listing"""
    
    # Get ready products
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM products
        WHERE ebay_item_id IS NULL
        AND is_listed = 0
        AND image_url IS NOT NULL
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    product_ids = [r[0] for r in rows]
    
    if not product_ids:
        print("❌ No ready products found")
        return []
    
    return batch_analyze(product_ids)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Manual product IDs
        if ',' in sys.argv[1]:
            # Comma-separated: 39,29,37
            product_ids = [int(x.strip()) for x in sys.argv[1].split(',')]
            batch_analyze(product_ids)
        else:
            # Single count: analyze N ready products
            count = int(sys.argv[1])
            analyze_ready_products(count)
    else:
        # Default: analyze 10 ready products
        analyze_ready_products(10)
