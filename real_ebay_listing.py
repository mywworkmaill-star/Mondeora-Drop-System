"""
GERÇEK eBay LİSTELEME - 5 ÜRÜN
================================
Database'deki ürünleri eBay'e GERÇEKTEN ekler
"""

import sqlite3
import logging
import os
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
    logger.info("🚀 GERÇEK eBay LİSTELEME BAŞLADI")
    logger.info("=" * 70)
    logger.info("")
    
    # is_listed=1 ama eBay'de offer'ı olmayan ürünler
    cursor.execute('''
        SELECT id, title, aliexpress_product_id, aliexpress_price, ebay_price, sku_id, category
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
        return
    
    # eBay policy IDs
    policies = {
        'payment': os.getenv('EBAY_PAYMENT_POLICY_ID'),
        'return': os.getenv('EBAY_RETURN_POLICY_ID'),
        'fulfillment': os.getenv('EBAY_FULFILLMENT_POLICY_ID'),
        'location': os.getenv('EBAY_MERCHANT_LOCATION_KEY')
    }
    
    logger.info(f"📋 eBay Policies:")
    for k, v in policies.items():
        logger.info(f"   {k}: {v if v else '❌ YOK'}")
    logger.info("")
    
    success_count = 0
    
    for pid, title, ali_id, ali_price, ebay_price, sku, category in products:
        logger.info(f"🔵 [{pid}] {title[:45]}")
        logger.info(f"   SKU: {sku}")
        logger.info(f"   Fiyat: €{ebay_price} (Maliyet: €{ali_price})")
        
        try:
            # 1. Inventory Item Ekle
            inventory_data = {
                'product': {
                    'title': title,
                    'description': f"High quality {title}. Fast shipping from Germany.",
                    'imageUrls': ['https://i.ebayimg.com/images/g/placeholder.jpg']
                },
                'condition': 'NEW',
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': 10
                    }
                }
            }
            
            inv_resp = ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_data)
            logger.info(f"   ✅ Inventory item eklendi")
            
            # 2. Offer Oluştur
            offer_data = {
                'sku': sku,
                'marketplaceId': 'EBAY_DE',
                'format': 'FIXED_PRICE',
                'listingPolicies': {
                    'paymentPolicyId': policies['payment'],
                    'returnPolicyId': policies['return'],
                    'fulfillmentPolicyId': policies['fulfillment']
                },
                'pricingSummary': {
                    'price': {
                        'value': str(ebay_price),
                        'currency': 'EUR'
                    }
                },
                'merchantLocationKey': policies['location'],
                'categoryId': '1249'  # Pet Supplies
            }
            
            offer_resp = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
            
            if not offer_resp or 'offerId' not in offer_resp:
                logger.error(f"   ❌ Offer oluşturulamadı: {offer_resp}")
                continue
            
            offer_id = offer_resp['offerId']
            logger.info(f"   ✅ Offer oluşturuldu: {offer_id}")
            
            # 3. Publish Et
            publish_resp = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
            
            if not publish_resp or 'listingId' not in publish_resp:
                logger.error(f"   ❌ Publish başarısız: {publish_resp}")
                continue
            
            ebay_item_id = publish_resp['listingId']
            logger.info(f"   ✅ eBay'de yayınlandı: {ebay_item_id}")
            
            # 4. Database Güncelle
            cursor.execute('''
                UPDATE products
                SET ebay_item_id = ?,
                    ebay_offer_id = ?
                WHERE id = ?
            ''', (ebay_item_id, offer_id, pid))
            
            logger.info(f"   ✅ Database güncellendi")
            success_count += 1
            
        except Exception as e:
            logger.error(f"   ❌ Hata: {e}")
            import traceback
            traceback.print_exc()
        
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
