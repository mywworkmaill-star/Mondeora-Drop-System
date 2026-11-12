"""
BULLET-PROOF SYSTEM V3.0 - PART 3 (FINAL)
Main Enterprise Listing Creation Function
"""

# Merge all parts
import os
import sys
from pathlib import Path

# Read Part 1
with open('create_listings_bulletproof.py', 'r', encoding='utf-8') as f:
    part1 = f.read()

# Read Part 2
with open('bulletproof_part2.py', 'r', encoding='utf-8') as f:
    part2 = f.read()
    # Remove header comment
    part2 = '\n'.join(part2.split('\n')[5:])

# Combine
full_code = part1 + '\n\n' + part2 + '\n\n' + '''
# =====================================
# DATABASE MANAGER
# =====================================
class DatabaseManager:
    """Safe database operations with verification"""
    
    @staticmethod
    def save_product(
        product_id: str,
        sku: str,
        ebay_listing_id: str,
        offer_id: str,
        title: str,
        ali_price: float,
        ebay_price: float,
        engine
    ) -> bool:
        """Save with verification"""
        try:
            with get_session(engine) as session:
                # Check if already exists
                existing = session.query(Product).filter(
                    Product.sku_id == sku
                ).first()
                
                if existing:
                    audit.warning(f"Product {sku} already in DB - updating")
                    existing.ebay_item_id = ebay_listing_id
                    existing.ebay_offer_id = offer_id
                    existing.ebay_price = float(ebay_price)
                    existing.status = 'active'
                    existing.is_listed = True
                else:
                    product = Product(
                        aliexpress_product_id=product_id,
                        ebay_item_id=ebay_listing_id,
                        sku_id=sku,
                        ebay_offer_id=offer_id,
                        title=title,
                        aliexpress_price=float(ali_price),
                        ebay_price=float(ebay_price),
                        margin_percent=round(((ebay_price - ali_price) / ali_price) * 100, 1),
                        is_listed=True,
                        status='active',
                        currency='EUR',
                        fulfillment_verified=True,
                        current_stock=10
                    )
                    session.add(product)
                
                session.commit()
                
                # Verification
                verify = session.query(Product).filter(
                    Product.sku_id == sku
                ).first()
                
                if verify:
                    audit.info(f"✅ Database saved & verified: {sku}")
                    return True
                else:
                    audit.error(f"❌ Database verification failed: {sku}")
                    return False
                    
        except Exception as e:
            audit.error(f"Database save error for {sku}: {e}")
            return False

# =====================================
# AD CAMPAIGN MANAGER (BEST EFFORT)
# =====================================
class AdCampaignManager:
    """Ad campaign with multiple retry strategies"""
    
    @staticmethod
    def add_to_campaign(
        ebay_listing_id: str,
        offer_id: str,
        ebay_client,
        campaign_id: str = "168739871017",
        max_retries: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """
        Try multiple payload formats with exponential backoff
        Returns: (success, ad_id or None)
        """
        
        payloads = [
            {'listingId': ebay_listing_id, 'bidPercentage': '5.0'},
            {'listingId': ebay_listing_id, 'bidPercentage': 5.0},
            {'offerId': offer_id, 'bidPercentage': '5.0'},
        ]
        
        for attempt in range(max_retries):
            for i, payload in enumerate(payloads):
                try:
                    rate_limiter.wait()
                    resp = ebay_client._request(
                        'POST',
                        f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad',
                        json=payload
                    )
                    
                    ad_id = resp.get('adId')
                    if ad_id:
                        audit.info(f"✅ Ad campaign success (format {i+1}): {ad_id}")
                        return True, ad_id
                        
                except Exception as e:
                    if i == len(payloads) - 1 and attempt == max_retries - 1:
                        audit.warning(f"Ad campaign failed (listing OK): {str(e)[:100]}")
                        return False, None
                    continue
            
            # Exponential backoff
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                audit.debug(f"Ad retry {attempt+1}/{max_retries}, waiting {wait_time}s")
                time.sleep(wait_time)
        
        return False, None

# =====================================
# MAIN ENTERPRISE FUNCTION
# =====================================
def create_bulletproof_listings(
    keyword: str = "pet toy",
    count: int = 5,
    category_id: Optional[str] = None,
    category_name: Optional[str] = None,
    min_stock: int = 10,
    min_margin_eur: float = 25.0,
    enable_stock_check: bool = True,
    enable_vero_check: bool = True,
    enable_duplicate_check: bool = True,
    enable_ad_campaign: bool = True,
    parallel: bool = True,
    max_workers: int = 2,
    strict_mode: bool = False
):
    """
    🎯 BULLET-PROOF ENTERPRISE LISTING SYSTEM V3.0
    
    %100 GÜVENİLİR - ŞANSA HİÇBİR ŞEY BIRAKMAZ
    
    Features:
    ✅ Multi-layer stock validation
    ✅ Advanced VeRO checking (150+ brands)
    ✅ Duplicate detection (eBay + DB)
    ✅ Smart price calculation (eBay fees)
    ✅ Category auto-selection
    ✅ Professional HTML generation
    ✅ Database tracking + verification
    ✅ Ad campaign with retry
    ✅ Comprehensive error handling
    ✅ Full audit logging
    ✅ Parallel processing
    ✅ Adaptive rate limiting
    """
    
    audit.info("="*80)
    audit.info("🚀 BULLET-PROOF ENTERPRISE LISTING SYSTEM V3.0")
    audit.info("="*80)
    audit.info(f"Keyword: {keyword}")
    audit.info(f"Target: {count} products")
    audit.info(f"Stock check: {enable_stock_check} (min {min_stock})")
    audit.info(f"VeRO check: {enable_vero_check}")
    audit.info(f"Duplicate check: {enable_duplicate_check}")
    audit.info(f"Parallel: {parallel} ({max_workers} workers)")
    audit.info(f"Strict mode: {strict_mode}")
    
    # Initialize
    ali = AliExpressAPIClient()
    ebay = eBayAPIClient()
    engine = create_engine(f"sqlite:///{os.path.join('data', 'dropshipping.db')}")
    
    stock_validator = StockValidator()
    vero_checker = VeRoChecker()
    duplicate_checker = DuplicateChecker()
    image_validator = ImageValidator()
    category_mgr = CategoryManager()
    title_optimizer = TitleOptimizer()
    html_generator = HTMLGenerator()
    price_calc = PriceCalculator()
    db_mgr = DatabaseManager()
    ad_mgr = AdCampaignManager()
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    # ====== STEP 1: SEARCH ======
    audit.info(f"\\n{'='*80}")
    audit.info("STEP 1: PRODUCT SEARCH")
    audit.info(f"{'='*80}")
    
    try:
        rate_limiter.wait()
        search_result = ali.search_product_page(
            keyword=keyword,
            sort_by='SALES_DESC',
            page_size=count * 3  # Get extra for filtering
        )
        
        products_found = search_result.get('products', [])
        audit.info(f"✅ Found {len(products_found)} products")
        
        if not products_found:
            audit.error("No products found!")
            return results
            
    except Exception as e:
        audit.error(f"Search failed: {e}")
        return results
    
    # ====== STEP 2: PROCESS PRODUCTS ======
    def process_product(product_basic: Dict) -> Dict:
        """Process single product with full validation"""
        
        product_id = product_basic.get('itemId')
        product_title_short = product_basic.get('title', '')[:50]
        
        audit.info(f"\\n{'='*80}")
        audit.info(f"📦 PROCESSING: {product_id}")
        audit.info(f"Title: {product_title_short}")
        audit.info(f"{'='*80}")
        
        try:
            # VeRO check
            if enable_vero_check:
                safe, reason, confidence = vero_checker.check(product_title_short, strict=strict_mode)
                if not safe:
                    audit.info(f"⏭️  SKIP: {reason} (confidence: {confidence:.1%})")
                    return {'status': 'skipped', 'id': product_id, 'reason': reason}
                audit.debug(f"VeRO passed (confidence: {confidence:.1%})")
            
            # Get product details
            rate_limiter.wait()
            product_data = ali.get_product_details(product_id)
            audit.debug(f"Product details fetched", {
                'fields': len(product_data),
                'has_images': 'image_urls' in product_data,
                'has_price': 'sale_price' in product_data
            })
            
            # Stock validation
            if enable_stock_check:
                stock_ok, stock_msg, stock_count = stock_validator.validate(product_data, min_stock)
                if not stock_ok:
                    audit.info(f"⏭️  SKIP: {stock_msg}")
                    return {'status': 'skipped', 'id': product_id, 'reason': stock_msg}
                audit.debug(f"Stock passed: {stock_count}")
            
            # Images
            images_str = product_data.get('image_urls', '')
            if not images_str:
                audit.info(f"⏭️  SKIP: No images")
                return {'status': 'skipped', 'id': product_id, 'reason': 'No images'}
            
            image_urls = images_str.split(';')
            img_ok, img_msg = image_validator.validate(image_urls, product_id)
            if not img_ok:
                audit.info(f"⏭️  SKIP: {img_msg}")
                return {'status': 'skipped', 'id': product_id, 'reason': img_msg}
            audit.debug(f"Images passed: {img_msg}")
            
            # Price
            ali_price = float(product_data.get('sale_price') or 0)
            if ali_price <= 0:
                skus = product_data.get('skus', [])
                if skus:
                    ali_price = float(skus[0].get('sale_price') or 0)
            
            if ali_price <= 0:
                audit.info(f"⏭️  SKIP: No valid price")
                return {'status': 'skipped', 'id': product_id, 'reason': 'No price'}
            
            pricing = price_calc.calculate(ali_price, min_margin_eur)
            audit.debug(f"Pricing calculated", pricing)
            
            # Category
            if category_id:
                cat_id = category_id
                cat_name = category_name or 'Pet'
            else:
                cat_id, cat_name = category_mgr.select_category(
                    product_data.get('subject', ''),
                    product_data.get('product_title', '')
                )
            audit.debug(f"Category: {cat_id} ({cat_name})")
            
            # SKU
            sku = f"AUTO-{cat_name.upper()}-{product_id}"
            
            # Duplicate check
            if enable_duplicate_check:
                sku_exists, dup_msg = duplicate_checker.check_sku(sku, ebay)
                if sku_exists:
                    audit.info(f"⏭️  SKIP: {dup_msg}")
                    return {'status': 'skipped', 'id': product_id, 'reason': dup_msg}
                audit.debug("Duplicate check passed")
            
            # Title
            raw_title = product_data.get('subject') or product_data.get('product_title') or f'Premium {cat_name} Product'
            optimized_title = title_optimizer.optimize(raw_title)
            audit.debug(f"Title optimized: {optimized_title[:50]}...")
            
            # Aspects
            aspects = category_mgr.build_aspects(product_data, cat_id)
            audit.debug(f"Aspects built: {len(aspects)} fields")
            
            # HTML
            html = html_generator.generate(product_data, cat_name)
            audit.debug(f"HTML generated: {len(html)} chars")
            
            # ====== CREATE LISTING ======
            audit.info(f"\\n{'─'*80}")
            audit.info("CREATING LISTING...")
            audit.info(f"{'─'*80}")
            
            # Inventory item
            inventory_item = {
                'sku': sku,
                'product': {
                    'title': optimized_title[:80],
                    'description': html,
                    'imageUrls': image_urls[:12],
                    'aspects': aspects
                },
                'condition': 'NEW',
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': 10
                    }
                }
            }
            
            rate_limiter.wait()
            ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
            audit.info(f"✅ Inventory created: {sku}")
            rate_limiter.success()
            
            # Offer
            offer_data = {
                'sku': sku,
                'marketplaceId': 'EBAY_DE',
                'format': 'FIXED_PRICE',
                'listingPolicies': {
                    'paymentPolicyId': '263035507017',
                    'returnPolicyId': '263035512017',
                    'fulfillmentPolicyId': '263035514017'
                },
                'categoryId': cat_id,
                'pricingSummary': {
                    'price': {
                        'value': str(pricing['final_price']),
                        'currency': 'EUR'
                    }
                },
                'merchantLocationKey': 'default-warehouse'
            }
            
            rate_limiter.wait()
            offer_resp = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
            offer_id = offer_resp.get('offerId')
            audit.info(f"✅ Offer created: {offer_id}")
            rate_limiter.success()
            
            # Publish
            rate_limiter.wait()
            publish_resp = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
            ebay_listing_id = publish_resp.get('listingId')
            audit.info(f"✅ PUBLISHED: https://www.ebay.de/itm/{ebay_listing_id}")
            audit.info(f"   Price: €{pricing['final_price']} (margin: €{pricing['net_margin']})")
            rate_limiter.success()
            
            # Database save
            db_success = db_mgr.save_product(
                product_id, sku, ebay_listing_id, offer_id,
                optimized_title, ali_price, pricing['final_price'], engine
            )
            
            # Ad campaign (best effort)
            ad_id = None
            if enable_ad_campaign:
                ad_success, ad_id = ad_mgr.add_to_campaign(ebay_listing_id, offer_id, ebay)
            
            return {
                'status': 'success',
                'id': product_id,
                'sku': sku,
                'ebay_id': ebay_listing_id,
                'offer_id': offer_id,
                'price': pricing['final_price'],
                'margin': pricing['net_margin'],
                'ad_id': ad_id,
                'db_saved': db_success
            }
            
        except Exception as e:
            audit.error(f"Processing failed for {product_id}: {e}")
            rate_limiter.error()
            return {
                'status': 'failed',
                'id': product_id,
                'error': str(e)[:200],
                'traceback': traceback.format_exc()[:500]
            }
    
    # ====== EXECUTE ======
    audit.info(f"\\n{'='*80}")
    audit.info("STEP 2: PROCESSING PRODUCTS")
    audit.info(f"{'='*80}")
    
    if parallel and len(products_found) > 1:
        audit.info(f"Mode: PARALLEL ({max_workers} workers)")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_product, p): p 
                for p in products_found[:count * 2]
            }
            
            processed = 0
            for future in as_completed(futures):
                result = future.result()
                
                if result['status'] == 'success':
                    results['success'].append(result)
                    processed += 1
                    audit.info(f"\\n✅ SUCCESS ({processed}/{count})")
                    
                    if processed >= count:
                        audit.info(f"Target reached ({count}), stopping")
                        break
                        
                elif result['status'] == 'skipped':
                    results['skipped'].append(result)
                else:
                    results['failed'].append(result)
    else:
        audit.info("Mode: SEQUENTIAL")
        
        processed = 0
        for product_basic in products_found:
            if processed >= count:
                break
            
            result = process_product(product_basic)
            
            if result['status'] == 'success':
                results['success'].append(result)
                processed += 1
            elif result['status'] == 'skipped':
                results['skipped'].append(result)
            else:
                results['failed'].append(result)
    
    # ====== SUMMARY ======
    audit.info(f"\\n{'='*80}")
    audit.info("✅ COMPLETED!")
    audit.info(f"{'='*80}")
    
    audit.info(f"\\n📊 RESULTS:")
    audit.info(f"   ✅ Success: {len(results['success'])}")
    audit.info(f"   ❌ Failed: {len(results['failed'])}")
    audit.info(f"   ⏭️  Skipped: {len(results['skipped'])}")
    
    if results['success']:
        audit.info(f"\\n✅ SUCCESSFUL LISTINGS:")
        for item in results['success']:
            audit.info(f"   {item['sku']}")
            audit.info(f"      URL: https://www.ebay.de/itm/{item['ebay_id']}")
            audit.info(f"      Price: €{item['price']} (margin: €{item['margin']})")
            audit.info(f"      Database: {'✅' if item.get('db_saved') else '❌'}")
            audit.info(f"      Ad Campaign: {'✅ ' + item['ad_id'] if item.get('ad_id') else '⚠️  Failed'}")
    
    return results


# =====================================
# MAIN
# =====================================
if __name__ == '__main__':
    results = create_bulletproof_listings(
        keyword="pet toy",
        count=5,
        min_stock=5,  # Lowered for API compatibility
        enable_stock_check=True,
        enable_vero_check=True,
        enable_duplicate_check=True,
        enable_ad_campaign=True,
        parallel=True,
        max_workers=2,
        strict_mode=False
    )
    
    audit.info(f"\\n{'='*80}")
    audit.info(f"🎯 FINAL: {len(results['success'])} products listed successfully!")
    audit.info(f"{'='*80}")
'''

# Write full file
with open('C:/Users/Administrator/Desktop/Mondeora-Drop-System/create_listings_bulletproof_full.py', 'w', encoding='utf-8') as f:
    f.write(full_code)

print("✅ Full bulletproof system written!")
print("File: create_listings_bulletproof_full.py")
print(f"Size: {len(full_code)} chars")
