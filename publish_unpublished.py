"""
UNPUBLISHED OFFER'LARI PUBLISH ET
==================================
eBay'de zaten var olan ama yayınlanmamış offer'ları yayınlar
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

def publish_unpublished_offers():
    db_path = Path('data/dropshipping.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    ebay = eBayAPIClient()
    
    logger.info("=" * 70)
    logger.info("🚀 UNPUBLISHED OFFER'LARI PUBLISH ET")
    logger.info("=" * 70)
    logger.info("")
    
    # is_listed=1 ama ebay_offer_id olmayan ürünler
    cursor.execute('''
        SELECT id, title, sku_id
        FROM products
        WHERE is_listed = 1
        AND (ebay_offer_id IS NULL OR ebay_offer_id = '')
        LIMIT 10
    ''')
    
    products = cursor.fetchall()
    logger.info(f"📦 Kontrol Edilecek Ürün: {len(products)}")
    logger.info("")
    
    if not products:
        logger.info("✅ Tüm ürünlerin offer ID'si var!")
        conn.close()
        return
    
    success_count = 0
    
    for pid, title, sku in products:
        logger.info(f"🔵 [{pid}] {title[:45]}")
        logger.info(f"   SKU: {sku}")
        
        try:
            # SKU için offer var mı kontrol et
            offer_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
            
            if not offer_resp or 'offers' not in offer_resp or len(offer_resp['offers']) == 0:
                logger.info(f"   ⚠️  Offer yok - atlanıyor")
                continue
            
            offer = offer_resp['offers'][0]
            offer_id = offer['offerId']
            status = offer.get('status', 'UNKNOWN')
            
            logger.info(f"   📋 Offer ID: {offer_id}")
            logger.info(f"   📊 Status: {status}")
            
            if status == 'PUBLISHED':
                # Zaten yayında - sadece database'i güncelle
                listing_id = offer.get('listing', {}).get('listingId')
                if listing_id:
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?,
                            ebay_offer_id = ?
                        WHERE id = ?
                    ''', (listing_id, offer_id, pid))
                    logger.info(f"   ✅ Zaten yayında - database güncellendi")
                    logger.info(f"   🔗 https://www.ebay.de/itm/{listing_id}")
                    success_count += 1
            
            elif status == 'UNPUBLISHED':
                # Publish et
                logger.info(f"   🚀 Publish ediliyor...")
                publish_resp = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
                
                if publish_resp and 'listingId' in publish_resp:
                    listing_id = publish_resp['listingId']
                    
                    # Database güncelle
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?,
                            ebay_offer_id = ?
                        WHERE id = ?
                    ''', (listing_id, offer_id, pid))
                    
                    logger.info(f"   ✅ YAYINLANDI!")
                    logger.info(f"   🔗 https://www.ebay.de/itm/{listing_id}")
                    success_count += 1
                else:
                    logger.error(f"   ❌ Publish başarısız: {publish_resp}")
            else:
                logger.info(f"   ⚠️  Bilinmeyen status: {status}")
                
        except Exception as e:
            logger.error(f"   ❌ Hata: {e}")
        
        logger.info("")
    
    conn.commit()
    conn.close()
    
    logger.info("=" * 70)
    logger.info("✅ PUBLISH TAMAMLANDI")
    logger.info("=" * 70)
    logger.info(f"✅ Başarılı: {success_count}/{len(products)}")
    logger.info("")

if __name__ == "__main__":
    publish_unpublished_offers()
