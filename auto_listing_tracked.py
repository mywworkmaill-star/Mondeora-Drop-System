"""
TAM OTOMATİK LİSTİNG - STATE TRACKING İLE
==========================================
Mevcut listing sistemini AutomationRunner ile wrap eder
Her adım database'e kaydedilir
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))
sys.path.insert(0, str(Path(__file__).parent))

import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Core systems
from automation_runner import AutomationRunner
from audit_logger import audit

# Existing systems
from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
from database.models import Product, get_session
from sqlalchemy import create_engine
from aliexpress_diversity_fix import search_with_diversity
from smart_category_selector import SmartCategorySelector

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# VERO BRANDS (Top 50)
# ============================================
VERO_BRANDS = [
    'apple', 'iphone', 'ipad', 'samsung', 'nike', 'adidas',
    'louis vuitton', 'gucci', 'prada', 'chanel', 'rolex',
    'disney', 'marvel', 'lego', 'playstation', 'xbox',
    'nintendo', 'supreme', 'off-white', 'balenciaga',
    'hermes', 'versace', 'armani', 'burberry', 'tiffany',
    'cartier', 'omega', 'tag heuer', 'ray-ban', 'oakley',
    'north face', 'patagonia', 'yeezy', 'jordan', 'converse',
    'vans', 'timberland', 'ugg', 'beats', 'bose',
    'gopro', 'dyson', 'nespresso', 'vitamix', 'kitchenaid',
    'sony', 'canon', 'nikon', 'fujifilm', 'polaroid'
]

def check_vero(title, description=''):
    """VERO brand kontrolü"""
    text = f"{title} {description}".lower()
    for brand in VERO_BRANDS:
        if brand in text:
            return False, f"VeRO risk: {brand}"
    return True, "Safe"

def calculate_price(ali_price, min_margin=25.0):
    """Fiyat hesapla"""
    EBAY_FEES = 0.154
    target_price = ali_price + min_margin
    final_price = target_price / (1 - EBAY_FEES)
    fees = final_price * EBAY_FEES
    net_margin = final_price - ali_price - fees
    
    return {
        'final_price': round(final_price, 2),
        'net_margin': round(net_margin, 2),
        'margin_percent': round((net_margin / ali_price) * 100, 1) if ali_price > 0 else 0
    }

# ============================================
# MAIN LISTING WITH TRACKING
# ============================================
def auto_list_products_tracked(
    keyword="pet toy",
    category_hint="PET",
    count=3,
    min_margin=25.0
):
    """
    Tracked listing automation
    """
    
    # Automation runner başlat
    runner = AutomationRunner('listing_automation')
    
    try:
        # Audit log
        audit.log('listing', 'started', {
            'keyword': keyword,
            'category': category_hint,
            'count': count
        })
        
        logger.info("=" * 70)
        logger.info("🚀 TAM OTOMATİK LİSTİNG (TRACKED)")
        logger.info("=" * 70)
        logger.info(f"Keyword: {keyword}")
        logger.info(f"Category: {category_hint}")
        logger.info(f"Target: {count} ürün")
        logger.info("")
        
        # Initialize clients
        ali = AliExpressAPIClient()
        ebay = eBayAPIClient()
        selector = SmartCategorySelector()
        engine = create_engine(f"sqlite:///{os.path.join('data', 'dropshipping.db')}")
        
        success_count = 0
        results = []
        
        # ========================================
        # STEP 1: AliExpress Product Search
        # ========================================
        def search_products(keyword_input):
            logger.info("📦 STEP 1: AliExpress ürün arama")
            logger.info("─" * 70)
            
            products = search_with_diversity(
                ali_client=ali,
                keyword=keyword_input,
                target_count=count * 3,
                max_attempts=3
            )
            
            audit.log('listing', 'products_found', {
                'keyword': keyword_input,
                'count': len(products)
            })
            
            logger.info(f"✅ {len(products)} ürün bulundu")
            return products
        
        products = runner.run_step(
            'search_aliexpress',
            search_products,
            keyword,
            step_number=1
        )
        
        # Checklist
        runner.check_item(
            'search_aliexpress',
            'products_found',
            len(products) > 0,
            is_critical=True,
            reason=f"Found {len(products)} products"
        )
        
        if len(products) == 0:
            runner.complete(success=False, error_message="No products found")
            return {'success': 0, 'target': count, 'results': []}
        
        logger.info("")
        
        # ========================================
        # STEP 2: Process Each Product
        # ========================================
        logger.info("🔧 STEP 2: Ürün işleme ve listeleme")
        logger.info("─" * 70)
        
        for idx, product in enumerate(products, 1):
            if success_count >= count:
                break
            
            product_id = product.get('product_id')
            if not product_id:
                continue
            
            logger.info(f"\n[{idx}/{len(products)}] ID: {product_id}")
            
            try:
                # 2.1 Get product details
                def get_details(pid):
                    return ali.get_product_details(pid)
                
                product_detail = runner.run_step(
                    f'get_details_{product_id}',
                    get_details,
                    product_id,
                    step_number=2
                )
                
                title = product_detail.get('product_title', '')
                if not title:
                    logger.warning("   ⏭️ Atlandı: Başlık yok")
                    continue
                
                logger.info(f"   📦 {title[:50]}")
                
                # 2.2 VeRO Check
                is_safe, vero_reason = check_vero(title)
                
                runner.check_item(
                    f'product_{product_id}',
                    'vero_safe',
                    is_safe,
                    is_critical=True,
                    reason=vero_reason
                )
                
                if not is_safe:
                    logger.warning(f"   ⏭️ Atlandı: {vero_reason}")
                    
                    runner.log_decision(
                        f'product_{product_id}',
                        'vero_check',
                        'reject',
                        vero_reason
                    )
                    
                    audit.log('listing', 'product_rejected', {
                        'product_id': product_id,
                        'reason': vero_reason
                    }, level='warning')
                    
                    continue
                
                logger.info(f"   ✅ VeRO: Safe")
                
                # 2.3 Price check
                ali_price = product_detail.get('target_sale_price')
                if not ali_price or ali_price == '0':
                    ali_price = product_detail.get('target_original_price')
                
                if not ali_price or ali_price == '0':
                    ali_price = product_detail.get('target_min_price')
                
                if not ali_price:
                    logger.warning("   ⏭️ Atlandı: Fiyat yok")
                    continue
                
                ali_price_eur = float(ali_price) * 0.92
                
                logger.info(f"   💰 AliExpress: ${ali_price} (~€{ali_price_eur:.2f})")
                
                # 2.4 Calculate price
                pricing = calculate_price(ali_price_eur, min_margin)
                
                runner.check_item(
                    f'product_{product_id}',
                    'margin_acceptable',
                    pricing['net_margin'] >= min_margin,
                    is_critical=True,
                    reason=f"Margin: €{pricing['net_margin']:.2f}"
                )
                
                if pricing['net_margin'] < min_margin:
                    logger.warning(f"   ⏭️ Atlandı: Düşük margin €{pricing['net_margin']:.2f}")
                    continue
                
                logger.info(f"   💵 eBay: €{pricing['final_price']} (Kar: €{pricing['net_margin']:.2f})")
                
                # 2.5 Smart category
                cat_id = selector.select_category(title, category_hint)
                cat_info = selector.get_category_info(cat_id)
                
                if cat_info:
                    logger.info(f"   📁 Kategori: {cat_id} - {cat_info['name']}")
                
                # 2.6 SKU
                sku = f"AUTO-{category_hint.upper()}-{product_id}"
                logger.info(f"   🏷️ SKU: {sku}")
                
                # 2.7 eBay listing
                logger.info("   🚀 eBay'e listeleniyor...")
                
                image_url = product_detail.get('product_main_image_url', 
                                              'https://i.ebayimg.com/images/g/placeholder.jpg')
                
                def list_to_ebay(listing_data):
                    return ebay.list_product_fixed_price(listing_data)
                
                result = runner.run_step(
                    f'list_ebay_{product_id}',
                    list_to_ebay,
                    {
                        'sku': sku,
                        'title': title[:80],
                        'description': f"High quality {title}. Fast shipping from Germany.",
                        'price': pricing['final_price'],
                        'quantity': 10,
                        'image_url': image_url,
                        'category_id': cat_id
                    },
                    step_number=3
                )
                
                if result.get('success'):
                    ebay_id = result['ebay_item_id']
                    offer_id = result['offer_id']
                    
                    logger.info(f"   ✅ Listelendi: https://www.ebay.de/itm/{ebay_id}")
                    
                    # 2.8 Database save
                    try:
                        session = get_session(engine)
                        
                        new_product = Product(
                            aliexpress_product_id=str(product_id),
                            title=title,
                            category=category_hint,
                            aliexpress_price=ali_price_eur,
                            ebay_price=pricing['final_price'],
                            margin_percent=pricing['margin_percent'],
                            sku_id=sku,
                            ebay_item_id=ebay_id,
                            ebay_offer_id=offer_id,
                            is_listed=1,
                            status='active'
                        )
                        
                        session.add(new_product)
                        session.commit()
                        session.close()
                        
                        logger.info("   💾 Database: Kaydedildi")
                        
                        audit.log('listing', 'product_listed', {
                            'sku': sku,
                            'ebay_id': ebay_id,
                            'price': pricing['final_price'],
                            'margin': pricing['net_margin']
                        })
                        
                    except Exception as e:
                        logger.error(f"   ⚠️ Database hatası: {e}")
                        audit.log_error('listing', e, {'sku': sku})
                    
                    # Success
                    success_count += 1
                    results.append({
                        'sku': sku,
                        'ebay_id': ebay_id,
                        'title': title[:50],
                        'price': pricing['final_price'],
                        'margin': pricing['net_margin']
                    })
                    
                else:
                    error = result.get('error', 'Unknown')
                    logger.error(f"   ❌ Listeleme başarısız: {error}")
                    
                    audit.log('listing', 'listing_failed', {
                        'product_id': product_id,
                        'error': error
                    }, level='error')
                    
            except Exception as e:
                logger.error(f"   ❌ İşleme hatası: {e}")
                audit.log_error('listing', e, {'product_id': product_id})
        
        # ========================================
        # COMPLETION
        # ========================================
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ LİSTİNG TAMAMLANDI")
        logger.info("=" * 70)
        logger.info(f"✅ Başarılı: {success_count}/{count}")
        logger.info("")
        
        if results:
            logger.info("📋 Listelenen Ürünler:")
            for r in results:
                logger.info(f"   [{r['sku']}] {r['title']}")
                logger.info(f"      URL: https://www.ebay.de/itm/{r['ebay_id']}")
                logger.info(f"      Fiyat: €{r['price']} (Kar: €{r['margin']})")
        
        # Complete automation run
        runner.complete(success=success_count > 0)
        
        # Final audit
        audit.log('listing', 'completed', {
            'success_count': success_count,
            'target': count,
            'run_id': runner.run_id
        })
        
        return {
            'success': success_count,
            'target': count,
            'results': results,
            'run_id': runner.run_id
        }
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        audit.log_error('listing', e)
        runner.complete(success=False, error_message=str(e))
        raise


# ============================================
# CLI
# ============================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto Listing (Tracked)')
    parser.add_argument('--keyword', default='pet toy')
    parser.add_argument('--category', default='PET')
    parser.add_argument('--count', type=int, default=3)
    parser.add_argument('--margin', type=float, default=25.0)
    
    args = parser.parse_args()
    
    result = auto_list_products_tracked(
        keyword=args.keyword,
        category_hint=args.category,
        count=args.count,
        min_margin=args.margin
    )
    
    exit_code = 0 if result['success'] > 0 else 1
    sys.exit(exit_code)
