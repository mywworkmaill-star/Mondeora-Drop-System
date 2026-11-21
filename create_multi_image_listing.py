#!/usr/bin/env python3
"""
Multi-Image Listing - Better than ID 75
Uses AliExpress multi-images + Category template
"""

import sys
import json
import sqlite3
import time
from pathlib import Path

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient
from scripts.aspect_collector import AspectCollector
from extract_product_aspects import build_product_specific_aspects
from generate_product_description import generate_product_description
from src.quality.listing_validator import ListingQualityGate
from src.validators.link_validator import AliExpressLinkValidator
from src.vision.aspect_extractor import VisionAspectExtractor  # 🔍 NEW: Vision integration

def get_aliexpress_images(ali, aliexpress_product_id):
    """Get ALL images from AliExpress"""
    try:
        product = ali.get_product_details(aliexpress_product_id)
        
        if not product:
            return []
        
        # image_urls is a STRING with semicolon separator!
        image_urls_str = product.get('image_urls', '')
        
        if isinstance(image_urls_str, str) and image_urls_str:
            # Split by semicolon
            images = [img.strip() for img in image_urls_str.split(';') if img.strip()]
            
            # Filter HTTPS only
            https_images = [img for img in images if img.startswith('https://')]
            
            print(f"   ✅ Found {len(https_images)} HTTPS images from AliExpress")
            return https_images
        
        return []
        
    except Exception as e:
        print(f"   ⚠️ AliExpress image error: {e}")
        return []


def create_premium_listing(product_id):
    """Create premium listing with multi-images"""
    
    print("🏆 CREATING PREMIUM MULTI-IMAGE LISTING")
    print("=" * 70)
    
    # Get product
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    columns = [desc[0] for desc in cursor.description]
    result = cursor.fetchone()
    
    if not result:
        print(f"❌ Product ID {product_id} not found in database")
        conn.close()
        return False
    
    product = dict(zip(columns, result))
    
    # ⚠️ CRITICAL: Check if already listed
    if product.get('ebay_item_id'):
        print(f"\n❌ ALREADY LISTED!")
        print(f"   eBay Item ID: {product['ebay_item_id']}")
        print(f"   Link: https://www.ebay.de/itm/{product['ebay_item_id']}")
        print(f"\n⚠️ Skipping duplicate listing per user instruction:")
        print(f"   'Ayni ürünleri listeleme' (Do not list the same products)")
        conn.close()
        return False
    
    conn.close()
    
    print(f"\n📦 PRODUCT (ID {product_id}):")
    print(f"   Title: {product['title'][:60]}")
    print(f"   Price: €{product['ebay_price']}")
    print(f"   AliExpress: {product['aliexpress_product_id']}")
    
    # Step 0: Link Validation
    print(f"\n0️⃣ LINK VALIDATION...")
    link_validator = AliExpressLinkValidator()
    link_result = link_validator.test_link(product['aliexpress_product_id'])
    
    # Update database with link status
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products
        SET 
            link_status = ?,
            link_tested_at = ?,
            link_http_code = ?
        WHERE id = ?
    ''', (
        link_result['status'],
        link_result['tested_at'].isoformat(),
        link_result['http_code'],
        product_id
    ))
    conn.commit()
    conn.close()
    
    # Status emoji
    status_emoji = {
        'public': '✅',
        'dropship_only': '⚠️',
        'not_found': '❌',
        'error': '❌'
    }.get(link_result['status'], '❓')
    
    print(f"   {status_emoji} Status: {link_result['status'].upper()}")
    print(f"   HTTP: {link_result['http_code']}")
    print(f"   Message: {link_result['message']}")
    
    # Block if not found or error
    if link_result['status'] in ['not_found', 'error']:
        print(f"\n❌ LINK VALIDATION FAILED")
        print(f"   Cannot list product with broken/missing link")
        print(f"   Status: {link_result['status']}")
        return False
    
    # Warn if dropship-only
    if link_result['status'] == 'dropship_only':
        print(f"\n⚠️  WARNING: Dropship-only product")
        print(f"   Customers cannot view on AliExpress")
        print(f"   Proceeding with listing...")
    
    # Step 1: Get multi-images from AliExpress + product data
    print(f"\n1️⃣ FETCHING MULTI-IMAGES...")
    ali = AliExpressAPIClient()
    
    # Get full product data for multi-source extraction
    ali_data = None
    try:
        ali_data = ali.get_product_details(product['aliexpress_product_id'])
    except:
        pass
    
    ali_images = get_aliexpress_images(ali, product['aliexpress_product_id'])
    
    if ali_images:
        # Take first 7 images (eBay limit)
        images = ali_images[:7]
        print(f"   ✅ Using {len(images)} images")
        for i, img in enumerate(images, 1):
            print(f"      {i}. {img[:80]}...")
    else:
        # Fallback to database image
        images = [product['image_url']] if product.get('image_url') else []
        print(f"   ⚠️ Fallback to database: {len(images)} image")
    
    # Step 2: Build PRODUCT-SPECIFIC aspects
    print(f"\n2️⃣ BUILDING PRODUCT-SPECIFIC ASPECTS...")
    
    # 🔍 Step 2.1: VISION ANALYSIS (NEW!)
    print(f"\n   🔍 Vision Analysis...")
    vision_result = None
    vision_aspects = {}
    
    if images and len(images) > 0:
        try:
            extractor = VisionAspectExtractor()
            vision_result = extractor.get_cached_or_analyze(
                product_id=product_id,
                image_url=images[0],  # Use first image
                product_type='organizer'
            )
            
            if vision_result['status'] == 'success':
                confidence = vision_result['confidence_score']
                vision_aspects = vision_result['aspects']
                
                print(f"   ✅ Vision confidence: {confidence}%")
                
                if vision_aspects:
                    print(f"   📸 Vision extracted:")
                    for key, value in vision_aspects.items():
                        print(f"      • {key}: {value}")
                else:
                    print(f"   ⚠️  No high-confidence aspects (threshold: 80%)")
            else:
                print(f"   ⚠️  Vision analysis failed, using title-based extraction")
        except Exception as e:
            print(f"   ⚠️  Vision error: {e}")
            print(f"   → Fallback to title-based extraction")
    else:
        print(f"   ⚠️  No images available, skipping vision")
    
    # Step 2.2: Title + AliExpress extraction
    print(f"\n   📝 Title + AliExpress extraction...")
    
    # Import product-specific aspect extractor
    from extract_product_aspects import build_product_specific_aspects
    
    collector = AspectCollector()
    template_file = Path('data/aspect_templates/category_43504_template.json')
    
    template_aspects = {}
    if template_file.exists():
        with open(template_file, 'r', encoding='utf-8') as f:
            template_aspects = json.load(f)
    
    # Extract PRODUCT-SPECIFIC aspects from title + AliExpress + VISION (MULTI-SOURCE!)
    aspects = build_product_specific_aspects(
        product['title'], 
        template_aspects, 
        ali_data,
        vision_aspects=vision_aspects  # 🔍 NEW: Pass vision aspects!
    )
    
    print(f"   ✅ Total aspects: {len(aspects)}")
    print(f"   ✅ Produktart: {aspects.get('Produktart', ['N/A'])[0]} (from title)")
    
    # Show vision-enhanced aspects
    if vision_aspects:
        if 'Material' in vision_aspects:
            print(f"   🔍 Material: {aspects.get('Material', ['N/A'])[0]} (vision-verified)")
        if 'Farbe' in vision_aspects:
            print(f"   🔍 Farbe: {aspects.get('Farbe', ['N/A'])[0]} (vision-verified)")
        if 'Besonderheiten' in vision_aspects:
            print(f"   🔍 Besonderheiten: {', '.join(aspects.get('Besonderheiten', ['N/A'])[:3])}... (vision-enhanced)")
    
    if aspects.get('Kapazität', ['Standard'])[0] != 'Standard':
        print(f"   ✅ Kapazität: {aspects.get('Kapazität', ['N/A'])[0]} (from title)")
    print(f"   ✅ Zimmer: {aspects.get('Zimmer', ['N/A'])[0]} (inferred)")
    
    # Step 3: PRODUCT-SPECIFIC description
    print(f"\n3️⃣ CREATING PRODUCT-SPECIFIC DESCRIPTION...")
    
    # Import product-specific description generator
    from generate_product_description import generate_product_description
    
    # Generate unique description based on product attributes
    description = generate_product_description(
        title=product['title'],
        produktart=aspects.get('Produktart', ['Organizer'])[0],
        zimmer=aspects.get('Zimmer', ['Universell'])[0],
        kapazitaet=aspects.get('Kapazität', ['Standard'])[0],
        besonderheiten=aspects.get('Besonderheiten', ['Standard'])
    )
    
    print(f"   ✅ Description: {len(description)} chars")
    print(f"   ✅ Type: {aspects.get('Produktart', ['N/A'])[0]} (product-specific content)")
    
    # Step 3.5: QUALITY GATE VALIDATION
    print(f"\n🔍 QUALITY GATE VALIDATION...")
    
    gate = ListingQualityGate()
    validation = gate.validate({
        'title': product['title'][:80],
        'description': description,
        'images': images,
        'aspects': aspects,
        'price': float(product['ebay_price']),
        'vision_confidence': vision_result['confidence_score'] if vision_result else 0  # 🔍 NEW!
    })
    
    print(f"   Score: {validation['score']}/100 ({validation['status']})")
    
    if validation['errors']:
        for error in validation['errors'][:3]:  # Show first 3
            print(f"   {error}")
    
    if validation['status'] == 'FAIL':
        print(f"\n❌ QUALITY GATE FAILED - Score {validation['score']}/100")
        print("   Fix critical errors before listing!")
        return False
    
    # Step 4: List to eBay
    print(f"\n4️⃣ LISTING TO EBAY...")
    
    listing_data = {
        "sku": f"MULTI-{int(time.time())}",
        "title": product['title'][:80],
        "description": description,
        "price": float(product['ebay_price']),
        "quantity": 10,
        "category_id": "43504",
        "condition": "NEW",
        "image_urls": images,  # MULTI-IMAGE!
        "aspects": aspects
    }
    
    print(f"   📸 Images: {len(images)} adet")
    
    ebay = eBayAPIClient()
    
    try:
        result = ebay.list_product_fixed_price(listing_data)
        
        if result and result.get('success'):
            print(f"\n🎉🎉🎉 SUCCESS!")
            print(f"   eBay Item ID: {result.get('ebay_item_id')}")
            print(f"   Link: https://www.ebay.de/itm/{result.get('ebay_item_id')}")
            
            # Update database
            conn = sqlite3.connect('data/dropshipping.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE products
                SET ebay_item_id = ?,
                    ebay_offer_id = ?,
                    is_listed = 1,
                    status = 'active',
                    aspects = ?,
                    description = ?,
                    category_id = 43504
                WHERE id = ?
            ''', (
                result.get("ebay_item_id"),
                result.get("offer_id"),
                json.dumps(aspects),
                description,
                product_id
            ))
            conn.commit()
            conn.close()
            
            print(f"   ✅ Database updated!")
            
            # Quality report
            print(f"\n📊 QUALITY REPORT:")
            print(f"   {'Metric':<20} {'Value':<20} {'Status':<20}")
            print(f"   {'-'*60}")
            print(f"   {'Images':<20} {len(images):<20} {'✅ GOOD' if len(images) >= 7 else '⚠️ OK' if len(images) >= 3 else '❌ LOW'}")
            print(f"   {'Aspects':<20} {len(aspects):<20} {'✅ EXCELLENT' if len(aspects) >= 20 else '✅ GOOD'}")
            print(f"   {'Description':<20} {len(description):<20} {'✅ GOOD' if len(description) >= 2500 else '✅ OK'}")
            
            return True
            
        else:
            error = result.get('error', 'Unknown') if result else 'No result'
            print(f"\n❌ Failed: {error}")
            
            if hasattr(ebay, 'last_error'):
                print(f"   Last error: {ebay.last_error}")
            
            return False
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Test with product ID
    product_id = int(sys.argv[1]) if len(sys.argv) > 1 else 31
    
    success = create_premium_listing(product_id)
    
    if success:
        print(f"\n✅ Listing created successfully!")
    else:
        print(f"\n❌ Listing failed!")
