"""
Pre-Listing Vision Analyzer
Run BEFORE listing pipeline to cache vision aspects

WORKFLOW:
1. Load product(s) from database
2. Vision analyze images (Hermes context)
3. Parse and validate results
4. Cache to database
5. Ready for listing pipeline (uses cache)

Usage:
  python pre_listing_vision.py <product_id>
  python pre_listing_vision.py --batch <id1,id2,id3>
  python pre_listing_vision.py --all-ready
"""

import sys
sys.path.insert(0, '.')

from src.vision.vision_cache import VisionCache, parse_vision_json, convert_to_ebay_aspects
import sqlite3
import argparse


def build_vision_prompt(product_title, product_type='organizer'):
    """Build structured vision prompt"""
    
    return f"""Analyze this {product_type} product image and provide:

1. MATERIAL: What material(s) is it made of?
   Options: Kunststoff, Metall, Stoff, Holz, Silikon, Edelstahl, Glas, Bambus
   Be specific. If multiple materials, list all.

2. COLOR: What color(s) are visible?
   Main color first, then additional colors.
   German names: Schwarz, Weiß, Grau, Blau, Rot, Grün, Gelb, Rosa, Lila, Braun, Beige, Transparent

3. FEATURES: What key features do you see?
   - Number of compartments/pockets (count them exactly)
   - Mounting type (Selbstklebend, Wandmontage, Freistehend, Saugnapf)
   - Special mechanisms (Faltbar, Stapelbar, Drehbar, Verstellbar, Ausziehbar)
   - Closures (Reißverschluss, Klettverschluss, Deckel, Magnetisch)
   - Surface (Matt, Glänzend, Transparent, Undurchsichtig)

4. CONFIDENCE: Rate your confidence for each answer (0-100%)

IMPORTANT: 
- Only list features you can SEE in the image
- Count exact numbers (e.g., "4 Fächer" not "mehrere Fächer")
- Use German product terminology
- If unsure, give lower confidence

Format response as JSON:
{{
  "material": {{"value": "Kunststoff", "confidence": 95}},
  "color": {{"value": ["Weiß", "Transparent"], "confidence": 90}},
  "features": {{"value": ["Selbstklebend", "2 Fächer", "Wandmontage"], "confidence": 85}}
}}

Product title for context: "{product_title}"
"""


def analyze_product(product_id, force=False):
    """
    Analyze one product with vision
    
    Args:
        product_id: Product ID
        force: Force re-analysis even if cached
    
    Returns:
        dict with success status and results
    """
    
    cache = VisionCache()
    
    # Check cache first
    if not force:
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        cursor.execute('SELECT image_url FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            cached = cache.get_cached(product_id, row[0])
            if cached:
                print(f'⚡ Using cached result (confidence: {cached["confidence_score"]}%)')
                return {
                    'success': True,
                    'product_id': product_id,
                    'cached': True,
                    'aspects': cached['aspects'],
                    'confidence': cached['confidence_score']
                }
    
    # Load product
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT title, image_url
        FROM products
        WHERE id = ?
    ''', (product_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {'success': False, 'error': 'Product not found'}
    
    title, image_url = row
    
    if not image_url:
        return {'success': False, 'error': 'No image URL'}
    
    # Get main image (first one)
    main_image = image_url.split(',')[0].strip()
    
    print(f'🔍 Analyzing Product {product_id}...')
    print(f'   Title: {title[:50]}...')
    print(f'   Image: {main_image[:60]}...')
    print()
    
    # Build prompt
    prompt = build_vision_prompt(title)
    
    # Return for manual vision call
    return {
        'success': False,
        'needs_vision': True,
        'product_id': product_id,
        'image_url': main_image,
        'prompt': prompt,
        'title': title
    }


def cache_vision_result(product_id, image_url, vision_response):
    """
    Parse vision response and cache it
    
    Args:
        product_id: Product ID
        image_url: Image URL
        vision_response: Raw vision API response text
    
    Returns:
        dict with cached aspects and confidence
    """
    
    print('📝 Parsing vision response...')
    
    # Parse JSON
    try:
        vision_data = parse_vision_json(vision_response)
        print('✅ JSON parsed')
    except Exception as e:
        print(f'❌ Parse error: {str(e)[:100]}')
        return {'success': False, 'error': 'Parse failed'}
    
    # Convert to eBay format (threshold 80%)
    aspects, confidence = convert_to_ebay_aspects(vision_data, threshold=80)
    
    print()
    print(f'🎯 Confidence: {confidence}%')
    print()
    print('Extracted aspects:')
    for key, values in aspects.items():
        print(f'  {key}: {", ".join(values)}')
    
    # Cache
    cache = VisionCache()
    cache.save(product_id, image_url, aspects, confidence, raw_response=vision_response)
    
    print()
    print('✅ Cached to database (7-day TTL)')
    
    return {
        'success': True,
        'product_id': product_id,
        'aspects': aspects,
        'confidence': confidence
    }


def main():
    parser = argparse.ArgumentParser(description='Pre-listing vision analyzer')
    parser.add_argument('product_id', type=int, nargs='?', help='Single product ID')
    parser.add_argument('--batch', help='Comma-separated product IDs')
    parser.add_argument('--all-ready', action='store_true', help='Analyze all ready_to_list products')
    parser.add_argument('--force', action='store_true', help='Force re-analysis')
    
    args = parser.parse_args()
    
    if args.batch:
        product_ids = [int(x.strip()) for x in args.batch.split(',')]
    elif args.all_ready:
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM products 
            WHERE status = 'ready_to_list' 
              AND image_url IS NOT NULL
            LIMIT 20
        ''')
        product_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f'Found {len(product_ids)} ready products')
        print()
    elif args.product_id:
        product_ids = [args.product_id]
    else:
        print('Usage: python pre_listing_vision.py <product_id>')
        print('   or: python pre_listing_vision.py --batch 1,2,3')
        print('   or: python pre_listing_vision.py --all-ready')
        return
    
    print('=' * 80)
    print('PRE-LISTING VISION ANALYZER')
    print('=' * 80)
    print()
    
    results = []
    needs_manual = []
    
    for pid in product_ids:
        result = analyze_product(pid, force=args.force)
        
        if result.get('needs_vision'):
            # Manual vision call needed
            needs_manual.append(result)
        else:
            results.append(result)
        
        print()
    
    # Summary
    print('=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print()
    
    if results:
        success_count = sum(1 for r in results if r.get('success'))
        cached_count = sum(1 for r in results if r.get('cached'))
        
        print(f'Completed: {success_count}/{len(results)}')
        print(f'From cache: {cached_count}')
        print()
    
    if needs_manual:
        print(f'⚠️  {len(needs_manual)} products need MANUAL vision call:')
        print()
        
        for item in needs_manual:
            print(f'Product {item["product_id"]}:')
            print(f'  Title: {item["title"][:50]}')
            print(f'  Image: {item["image_url"][:60]}')
            print()
            print('Vision call needed in Hermes context:')
            print()
            print(f'vision_analyze(')
            print(f'    image_url="{item["image_url"]}",')
            print(f'    question="""')
            print(item["prompt"])
            print(f'    """')
            print(f')')
            print()
            print('Then cache result:')
            print(f'cache_vision_result({item["product_id"]}, "{item["image_url"]}", vision_response)')
            print()
            print('-' * 80)
            print()


if __name__ == '__main__':
    main()
