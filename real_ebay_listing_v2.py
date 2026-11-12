"""
GERÇEK eBay LİSTELEME - list_product_fixed_price kullanarak
"""

import sqlite3
import logging
from pathlib import Path
from dotenv import load_dotenv
import sys

sys.path.insert(0, str(Path(__file__).parent))
from src.api.ebay_client import eBayAPIClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def list_to_ebay():
    db_path = Path('data/dropshipping.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    ebay = eBayAPIClient()
    
    logger.info("=" * 70)
    logger.info("🚀 GERÇEK eBay LİSTELEME (list_product_fixed_price)")
    logger.info("=" * 70)
    logger.info("")
    
    # is_listed=1 ama ebay_offer_id olmayan ürünler
    cursor.execute('''
        SELECT id, title, aliexpress_product_id, ebay_price, sku_id, category
        FROM products
        WHERE is_listed = 1
        AND (ebay_offer_id IS NULL OR ebay_offer_id = '')
        LIMIT 5
    ''')
    
    products = cursor.fetchall()
    logger.info(f"📦 Listelenecek Ürün: {len(products)}")
    logger.info("")
    
    if not products:
        logger.info("✅ Tüm ürünler zaten eBay'de!")
        conn.close()
        return
    
    success_count = 0
    
    for pid, title, ali_id, ebay_price, sku, category in products:
        logger.info(f"🔵 [{pid}] {title[:45]}")
        logger.info(f"   SKU: {sku}")
        logger.info(f"   Fiyat: €{ebay_price}")
        
        try:
            # list_product_fixed_price kullan
            result = ebay.list_product_fixed_price({
                'sku': sku,
                'title': title,
                'description': f"High quality {title}. Fast shipping from Germany.",
                'price': ebay_price,
                'quantity': 10,
                'image_url': 'https://i.ebayimg.com/images/g/placeholder.jpg',
                'category_id': '20741'  # Pet Supplies (doğru ID)
            })
            
            if result['success']:
                ebay_item_id = result['ebay_item_id']
                offer_id = result['offer_id']
                
                logger.info(f"   ✅ eBay'de yayınlandı!")
                logger.info(f"   Item ID: {ebay_item_id}")
                logger.info(f"   Offer ID: {offer_id}")
                
                # Database güncelle
                cursor.execute('''
                    UPDATE products
                    SET ebay_item_id = ?,
                        ebay_offer_id = ?
                    WHERE id = ?
                ''', (ebay_item_id, offer_id, pid))
                
                success_count += 1
            else:
                error = result.get('error', 'Bilinmeyen hata')
                logger.error(f"   ❌ Başarısız: {error}")
                # Detaylı hata
                if hasattr(ebay, 'last_error') and ebay.last_error:
                    logger.error(f"   Detay: {ebay.last_error}")
                
        except Exception as e:
            logger.error(f"   ❌ Hata: {e}")
        
        logger.info("")
    
    conn.commit()
    conn.close()
    
    logger.info("=" * 70)
    logger.info("✅ LİSTELEME TAMAMLANDI")
    logger.info("=" * 70)
    logger.info(f"✅ Başarılı: {success_count}/{len(products)}")
    logger.info("")

if __name__ == "__main__":
    list_to_ebay()
