"""
OFFER CATEGORY FIX + PUBLISH
=============================
Yanlış category ID'li offer'ları düzeltip publish eder
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

def fix_and_publish():
    db_path = Path('data/dropshipping.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    ebay = eBayAPIClient()
    
    logger.info("=" * 70)
    logger.info("🔧 OFFER CATEGORY FIX + PUBLISH")
    logger.info("=" * 70)
    logger.info("")
    
    # is_listed=1 ama ebay_offer_id olmayan
    cursor.execute('''
        SELECT id, title, sku_id, ebay_price
        FROM products
        WHERE is_listed = 1
        AND (ebay_offer_id IS NULL OR ebay_offer_id = '')
        LIMIT 10
    ''')
    
    products = cursor.fetchall()
    logger.info(f"📦 İşlenecek Ürün: {len(products)}")
    logger.info("")
    
    success_count = 0
    
    for pid, title, sku, ebay_price in products:
        logger.info(f"🔵 [{pid}] {title[:45]}")
        logger.info(f"   SKU: {sku}")
        
        try:
            # Mevcut offer'ı al
            offer_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
            
            if not offer_resp or 'offers' not in offer_resp or len(offer_resp['offers']) == 0:
                logger.info(f"   ⚠️  Offer yok - atlanıyor")
                continue
            
            offer = offer_resp['offers'][0]
            offer_id = offer['offerId']
            status = offer.get('status', 'UNKNOWN')
            current_cat = offer.get('categoryId', 'UNKNOWN')
            
            logger.info(f"   📋 Offer: {offer_id} | Status: {status} | Cat: {current_cat}")
            
            if status == 'PUBLISHED':
                # Zaten yayında
                listing_id = offer.get('listing', {}).get('listingId')
                if listing_id:
                    cursor.execute('UPDATE products SET ebay_item_id=?, ebay_offer_id=? WHERE id=?',
                                 (listing_id, offer_id, pid))
                    logger.info(f"   ✅ Zaten yayında - DB güncellendi")
                    success_count += 1
            
            elif status == 'UNPUBLISHED':
                # Category yanlışsa düzelt
                if current_cat != '20741':
                    logger.info(f"   🔧 Category düzeltiliyor: {current_cat} → 20741")
                    
                    # Offer'ı güncelle
                    update_data = {
                        'offerId': offer_id,
                        'sku': sku,
                        'marketplaceId': 'EBAY_DE',
                        'format': 'FIXED_PRICE',
                        'categoryId': '20741',  # Doğru category
                        'merchantLocationKey': 'default-warehouse',
                        'listingPolicies': {
                            'paymentPolicyId': '263035507017',
                            'returnPolicyId': '263035512017',
                            'fulfillmentPolicyId': '263035514017'
                        },
                        'pricingSummary': {
                            'price': {
                                'value': str(ebay_price),
                                'currency': 'EUR'
                            }
                        },
                        'listingDuration': 'GTC',
                        'includeCatalogProductDetails': False
                    }
                    
                    ebay._request('PUT', f'/sell/inventory/v1/offer/{offer_id}', json=update_data)
                    logger.info(f"   ✅ Offer güncellendi")
                
                # Şimdi publish et
                logger.info(f"   🚀 Publish ediliyor...")
                publish_resp = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
                
                if publish_resp and 'listingId' in publish_resp:
                    listing_id = publish_resp['listingId']
                    
                    cursor.execute('UPDATE products SET ebay_item_id=?, ebay_offer_id=? WHERE id=?',
                                 (listing_id, offer_id, pid))
                    
                    logger.info(f"   ✅ YAYINLANDI!")
                    logger.info(f"   🔗 https://www.ebay.de/itm/{listing_id}")
                    success_count += 1
                else:
                    logger.error(f"   ❌ Publish başarısız")
                    
        except Exception as e:
            logger.error(f"   ❌ Hata: {e}")
            import traceback
            traceback.print_exc()
        
        logger.info("")
    
    conn.commit()
    conn.close()
    
    logger.info("=" * 70)
    logger.info("✅ İŞLEM TAMAMLANDI")
    logger.info("=" * 70)
    logger.info(f"✅ Başarılı: {success_count}/{len(products)}")
    logger.info("")

if __name__ == "__main__":
    fix_and_publish()
