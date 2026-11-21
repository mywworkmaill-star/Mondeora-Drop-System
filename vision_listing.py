"""
Vision-enabled listing creation
Integrates vision aspect extraction with listing pipeline
"""

import sys
import sqlite3
from src.vision.aspect_extractor import VisionAspectExtractor


def create_vision_enhanced_listing(product_id):
    """Create listing with vision-extracted aspects"""
    
    # Get product
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, image_url, ali_product_id, price
        FROM products
        WHERE id = ?
    ''', (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        print(f"❌ Product {product_id} not found")
        return False
    
    pid, title, image_url, ali_id, price = product
    
    print(f"\n{'='*80}")
    print(f"VISION-ENHANCED LISTING - Product {pid}")
    print(f"{'='*80}")
    print(f"Title: {title[:60]}...")
    print(f"Image: {image_url[:60]}...")
    
    # Step 1: Vision analysis
    print(f"\n📸 Step 1: Vision Aspect Extraction")
    print(f"{'='*80}")
    
    extractor = VisionAspectExtractor()
    vision_result = extractor.get_cached_or_analyze(pid, image_url)
    
    if vision_result['status'] == 'success':
        print(f"✅ Vision analysis complete!")
        print(f"   Confidence: {vision_result['confidence_score']}%")
        
        if vision_result['aspects']:
            print(f"\n   Extracted Aspects:")
            for key, value in vision_result['aspects'].items():
                print(f"      {key}: {value}")
        
        if vision_result['low_confidence']:
            print(f"\n   ⚠️  Low Confidence (not used):")
            for key, data in vision_result['low_confidence'].items():
                print(f"      {key}: {data['value']} ({data['confidence']}%)")
    else:
        print(f"⚠️  Vision analysis failed, using fallback")
        vision_result['aspects'] = {}
    
    # Step 2: Call original listing script with vision aspects
    print(f"\n📝 Step 2: Create eBay Listing")
    print(f"{'='*80}")
    print(f"Calling standard listing pipeline with vision aspects...")
    
    # Import and call original script
    # NOTE: This would integrate with existing create_multi_image_listing.py
    # For now, show what would be passed
    
    print(f"\nVision Aspects to merge:")
    print(vision_result['aspects'])
    
    print(f"\n✅ Ready for listing creation!")
    print(f"   Run: python create_multi_image_listing.py {pid}")
    print(f"   Vision aspects will be auto-merged from cache")
    
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python vision_listing.py <product_id>")
        sys.exit(1)
    
    product_id = int(sys.argv[1])
    create_vision_enhanced_listing(product_id)
