"""
LİNKSİZ ÜRÜNLER - eBay'DEN OTOMATIK KALDIRMA
==============================================
REMOVED_NO_LINK durumundaki ürünleri eBay'den kaldırır.
Tedarikçi linki olmayan ürünler fulfillment riski taşır.
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.ebay_client import eBayAPIClient

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/remove_no_link.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def remove_no_link_products():
    """LİNKSİZ ürünleri eBay'den kaldır"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🗑️  LİNKSİZ ÜRÜNLER eBay'DEN KALDIRILIYOR")
    logger.info("=" * 70)
    logger.info("")
    
    # Database bağlantısı
    db_path = project_root / 'data' / 'dropshipping.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # REMOVED_NO_LINK ürünleri bul
    cursor.execute('''
        SELECT id, title, ebay_item_id, sku_id, ebay_price
        FROM products
        WHERE status = 'REMOVED_NO_LINK'
        AND ebay_item_id IS NOT NULL
        AND ebay_item_id != ''
        ORDER BY id
    ''')
    
    products = cursor.fetchall()
    
    if not products:
        logger.info("✅ Kaldırılacak linksiz ürün yok")
        conn.close()
        return
    
    logger.info(f"📋 Bulunan linksiz ürün: {len(products)}")
    logger.info("")
    
    # eBay client
    ebay = eBayAPIClient()
    
    removed_count = 0
    failed_count = 0
    
    for pid, title, ebay_id, sku, price in products:
        logger.info(f"🗑️  [{pid}] {title[:50]}")
        logger.info(f"   eBay ID: {ebay_id} | SKU: {sku} | €{price}")
        
        try:
            # eBay'den offer'ı bul
            response = ebay._request('GET', f'/sell/inventory/v1/offer', params={'sku': sku})
            
            if response and 'offers' in response and response['offers']:
                offer_id = response['offers'][0].get('offerId')
                
                if offer_id:
                    # Offer'ı withdraw et (unpublish)
                    withdraw_response = ebay._request(
                        'POST',
                        f'/sell/inventory/v1/offer/{offer_id}/withdraw'
                    )
                    
                    if withdraw_response:
                        logger.info(f"   ✅ eBay'den kaldırıldı (offer {offer_id})")
                        
                        # Database güncelle
                        cursor.execute('''
                            UPDATE products
                            SET is_listed = 0,
                                status = 'DELISTED_NO_LINK',
                                updated_at = ?
                            WHERE id = ?
                        ''', (datetime.now().isoformat(), pid))
                        
                        removed_count += 1
                    else:
                        logger.warning(f"   ⚠️  Withdraw başarısız")
                        failed_count += 1
                else:
                    logger.warning(f"   ⚠️  Offer ID bulunamadı")
                    failed_count += 1
            else:
                logger.warning(f"   ⚠️  Offer bulunamadı (zaten kaldırılmış olabilir)")
                
                # Database'i güncelle yine de
                cursor.execute('''
                    UPDATE products
                    SET is_listed = 0,
                        status = 'DELISTED_NO_LINK',
                        updated_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), pid))
                
                removed_count += 1
        
        except Exception as e:
            logger.error(f"   ❌ Hata: {e}")
            failed_count += 1
        
        logger.info("")
    
    # Commit
    conn.commit()
    conn.close()
    
    logger.info("=" * 70)
    logger.info("✅ KALDIRMA TAMAMLANDI")
    logger.info("=" * 70)
    logger.info(f"✅ Kaldırılan: {removed_count}")
    logger.info(f"❌ Başarısız: {failed_count}")
    logger.info("")

if __name__ == "__main__":
    remove_no_link_products()
