"""
TAM OTOMATİK LİSTİNG SİSTEMİ
============================
eBay Real Categories + Bulletproof Listing entegrasyonu
%100 otomatik - cron job ile çalışır
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Import existing systems
from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
from database.models import Product, get_session
from sqlalchemy import create_engine

# Import bulletproof components
from aliexpress_diversity_fix import search_with_diversity
from smart_product_scorer import SmartProductScorer

# Import NEW smart category selector
from smart_category_selector import SmartCategorySelector

# =====================================
# LOGGING
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('data/auto_listing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =====================================
# VERO BRANDS
# =====================================
VERO_BRANDS = [
    'apple', 'iphone', 'ipad', 'samsung', 'nike', 'adidas',
    'louis vuitton', 'gucci', 'prada', 'chanel', 'rolex',
    'disney', 'marvel', 'lego', 'playstation', 'xbox',
    'nintendo', 'supreme', 'off-white', 'balenciaga'
]

# =====================================
# HELPERS
# =====================================
def check_vero(title, description=''):
    """VERO brand kontrolü"""
    text = f"{title} {description}".lower()
    for brand in VERO_BRANDS:
        if brand in text:
            return False, f"VeRO risk: {brand}"
    return True, "Safe"

def calculate_price(ali_price, min_margin=25.0):
    """Fiyat hesapla (eBay fees dahil)"""
    EBAY_FEES = 0.154  # 15.4% (FVF + payment)
    
    # Min margin için gerekli fiyat
    target_price = ali_price + min_margin
    
    # Fees dahil final price
    final_price = target_price / (1 - EBAY_FEES)
    
    # Gerçek margin
    fees = final_price * EBAY_FEES
    net_margin = final_price - ali_price - fees
    
    return {
        'final_price': round(final_price, 2),
        'net_margin': round(net_margin, 2),
        'margin_percent': round((net_margin / ali_price) * 100, 1)
    }

# =====================================
# MAIN LISTING FUNCTION
# =====================================
def auto_list_products(
    keyword="pet toy",
    category_hint="PET",
    count=3,
    min_stock=10,
    min_margin=25.0
):
    """
    TAM OTOMATİK LİSTİNG
    
    Args:
        keyword: AliExpress arama kelimesi
        category_hint: Kategori ipucu (PET, PHONE, vb)
        count: Kaç ürün listelenecek
        min_stock: Minimum stok
        min_margin: Minimum kar (EUR)
    """
    
    logger.info("=" * 70)
    logger.info("🚀 TAM OTOMATİK LİSTİNG BAŞLADI")
    logger.info("=" * 70)
    logger.info(f"Keyword: {keyword}")
    logger.info(f"Category: {category_hint}")
    logger.info(f"Target: {count} ürün")
    logger.info("")
    
    # Initialize
    ali = AliExpressAPIClient()
    ebay = eBayAPIClient()
    selector = SmartCategorySelector()
    engine = create_engine(f"sqlite:///{os.path.join('data', 'dropshipping.db')}")
    
    success_count = 0
    results = []
    
    # STEP 1: AliExpress'ten ürün ara
    logger.info("📦 STEP 1: AliExpress ürün arama")
    logger.info("─" * 70)
    
    try:
        products = search_with_diversity(
            ali_client=ali,
            keyword=keyword,
            target_count=count * 3,  # Daha fazla ara, filtrele
            max_attempts=3
        )
        
        logger.info(f"✅ {len(products)} ürün bulundu")
        
    except Exception as e:
        logger.error(f"❌ AliExpress arama hatası: {e}")
        return {'success': 0, 'failed': count, 'results': []}
    
    logger.info("")
    
    # STEP 2: Her ürünü işle
    logger.info("🔧 STEP 2: Ürün işleme ve listeleme")
    logger.info("─" * 70)
    
    for idx, product in enumerate(products, 1):
        if success_count >= count:
            break
        
        # Ürün ID'yi al
        product_id = product.get('product_id')
        if not product_id:
            logger.warning(f"[{idx}] Ürün ID yok, atlandı")
            continue
        
        logger.info(f"\n[{idx}/{len(products)}] ID: {product_id}")
        
        try:
            # 2.0 DETAYLI ÜRÜN BİLGİSİ AL
            logger.info(f"   🔍 Detaylı bilgi alınıyor...")
            
            try:
                product_detail = ali.get_product_details(product_id)
            except Exception as e:
                logger.warning(f"   ⏭️  Atlandı: Detay alınamadı ({e})")
                continue
            
            # Title
            title = product_detail.get('product_title', '')
            if not title:
                logger.warning(f"   ⏭️  Atlandı: Başlık yok")
                continue
            
            logger.info(f"   📦 {title[:50]}")
            
            # 2.1 VERO kontrolü
            is_safe, reason = check_vero(title)
            
            if not is_safe:
                logger.warning(f"   ⏭️  Atlandı: {reason}")
                continue
            
            logger.info(f"   ✅ VeRO: Safe")
            
            # 2.2 Fiyat kontrolü (DETAYDAN AL!)
            ali_price = product_detail.get('target_sale_price')
            if not ali_price or ali_price == '0':
                ali_price = product_detail.get('target_original_price')
            
            if not ali_price or ali_price == '0':
                # Son çare: min/max price
                ali_price = product_detail.get('target_min_price')
            
            if not ali_price:
                logger.warning(f"   ⏭️  Atlandı: Fiyat yok")
                continue
            
            # Convert to EUR (assuming USD)
            ali_price_eur = ali_price * 0.92  # Rough conversion
            
            logger.info(f"   💰 AliExpress: ${ali_price} (~€{ali_price_eur:.2f})")
            
            # 2.3 Fiyat hesapla
            pricing = calculate_price(ali_price_eur, min_margin)
            
            if pricing['net_margin'] < min_margin:
                logger.warning(f"   ⏭️  Atlandı: Düşük margin €{pricing['net_margin']:.2f}")
                continue
            
            logger.info(f"   💵 eBay: €{pricing['final_price']} (Kar: €{pricing['net_margin']:.2f}, {pricing['margin_percent']}%)")
            
            # 2.4 Smart kategori seç
            cat_id = selector.select_category(title, category_hint)
            cat_info = selector.get_category_info(cat_id)
            
            if cat_info:
                logger.info(f"   📁 Kategori: {cat_id} - {cat_info['name']}")
            else:
                logger.info(f"   📁 Kategori: {cat_id}")
            
            # 2.5 SKU oluştur
            ali_id = product.get('product_id', 'unknown')
            sku = f"AUTO-{category_hint.upper()}-{ali_id}"
            
            logger.info(f"   🏷️  SKU: {sku}")
            
            # 2.6 eBay'e listele
            logger.info(f"   🚀 eBay'e listeleniyor...")
            
            # Resim URL (detaydan al)
            image_url = product_detail.get('product_main_image_url', 'https://i.ebayimg.com/images/g/placeholder.jpg')
            
            result = ebay.list_product_fixed_price({
                'sku': sku,
                'title': title[:80],  # eBay max 80 char
                'description': f"High quality {title}. Fast shipping from Germany.",
                'price': pricing['final_price'],
                'quantity': 10,
                'image_url': image_url,
                'category_id': cat_id
            })
            
            if result.get('success'):
                ebay_id = result['ebay_item_id']
                offer_id = result['offer_id']
                
                logger.info(f"   ✅ Listelendi: https://www.ebay.de/itm/{ebay_id}")
                logger.info(f"   🆔 Offer ID: {offer_id}")
                
                # 2.7 Database'e kaydet
                try:
                    session = get_session(engine)
                    
                    new_product = Product(
                        aliexpress_product_id=str(ali_id),
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
                    
                    logger.info(f"   💾 Database: Kaydedildi")
                    
                except Exception as e:
                    logger.error(f"   ⚠️  Database hatası: {e}")
                
                # Success!
                success_count += 1
                results.append({
                    'sku': sku,
                    'ebay_id': ebay_id,
                    'title': title[:50],
                    'price': pricing['final_price'],
                    'margin': pricing['net_margin']
                })
                
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"   ❌ Listeleme başarısız: {error}")
                
        except Exception as e:
            logger.error(f"   ❌ İşleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    # SUMMARY
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
    
    return {
        'success': success_count,
        'target': count,
        'results': results
    }


# =====================================
# CLI INTERFACE
# =====================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Otomatik eBay Listing')
    parser.add_argument('--keyword', default='pet toy', help='AliExpress arama kelimesi')
    parser.add_argument('--category', default='PET', help='Kategori ipucu (PET, PHONE)')
    parser.add_argument('--count', type=int, default=3, help='Kaç ürün listelenecek')
    parser.add_argument('--margin', type=float, default=25.0, help='Minimum kar (EUR)')
    
    args = parser.parse_args()
    
    result = auto_list_products(
        keyword=args.keyword,
        category_hint=args.category,
        count=args.count,
        min_margin=args.margin
    )
    
    # Exit code
    if result['success'] >= result.get('target', args.count):
        exit_code = 0
    else:
        exit_code = 1
    sys.exit(exit_code)
