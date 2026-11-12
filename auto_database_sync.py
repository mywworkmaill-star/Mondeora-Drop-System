"""
AUTOMATIC DATABASE SYNCHRONIZATION SYSTEM
==========================================

Bu sistem her durumda database'in eBay ile senkronize olmasını garanti eder:

1. eBay'deki TÜM aktif ürünleri çeker
2. Database ile karşılaştırır
3. Eksik ürünleri otomatik ekler
4. Silinen ürünleri status='DELISTED' yapar
5. Fiyat değişikliklerini günceller

Her 1 saatte bir otomatik çalışır!
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.ebay_client import eBayAPIClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_database_sync.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AutoDatabaseSync:
    """Otomatik eBay ↔ Database senkronizasyon sistemi"""
    
    def __init__(self):
        self.ebay = eBayAPIClient()
        self.db_path = project_root / 'data' / 'dropshipping.db'
        
    def get_ebay_active_listings(self):
        """eBay'den tüm aktif listingleri çek"""
        logger.info("📡 eBay'den aktif listingler çekiliyor...")
        
        try:
            # Get all inventory items (REST API)
            all_items = []
            offset = 0
            limit = 100
            
            while True:
                # Construct request (use params dict, not query string in path)
                path = '/sell/inventory/v1/inventory_item'
                params = {'offset': offset, 'limit': limit}
                response = self.ebay._request('GET', path, params=params)
                
                if not response or 'inventoryItems' not in response:
                    break
                
                items = response['inventoryItems']
                if not items:
                    break
                
                all_items.extend(items)
                
                # Check if there are more
                total = response.get('total', 0)
                if offset + limit >= total:
                    break
                    
                offset += limit
            
            logger.info(f"✅ eBay'den {len(all_items)} inventory item çekildi")
            
            # Her inventory item için offer bilgisini al
            active_listings = []
            
            for item in all_items:
                sku = item.get('sku')
                if not sku:
                    continue
                
                # Get offer for this SKU
                try:
                    offer_path = '/sell/inventory/v1/offer'
                    offer_response = self.ebay._request('GET', offer_path, params={'sku': sku})
                    
                    if offer_response and 'offers' in offer_response:
                        offers = offer_response['offers']
                        
                        for offer in offers:
                            listing = offer.get('listing', {})
                            
                            if listing.get('listingStatus') == 'ACTIVE':
                                # Extract details
                                product = item.get('product', {})
                                pricing = offer.get('pricingSummary', {}).get('price', {})
                                availability = item.get('availability', {}).get('shipToLocationAvailability', {})
                                
                                active_listings.append({
                                    'ebay_item_id': listing.get('listingId'),
                                    'sku': sku,
                                    'title': product.get('title', 'No title'),
                                    'ebay_price': float(pricing.get('value', 0)),
                                    'currency': pricing.get('currency', 'EUR'),
                                    'quantity': availability.get('quantity', 0),
                                    'offer_id': offer.get('offerId'),
                                    'category_id': offer.get('categoryId'),
                                    'sold_quantity': listing.get('soldQuantity', 0),
                                    'image_urls': product.get('imageUrls', [])
                                })
                
                except Exception as e:
                    logger.warning(f"⚠️  SKU {sku} için offer alınamadı: {e}")
                    continue
            
            logger.info(f"✅ {len(active_listings)} aktif listing bulundu")
            return active_listings
            
        except Exception as e:
            logger.error(f"❌ eBay'den listing çekme hatası: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_database_products(self):
        """Database'den tüm ürünleri çek"""
        logger.info("📊 Database'den ürünler çekiliyor...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                ebay_item_id,
                sku_id,
                title,
                ebay_price,
                status,
                aliexpress_product_id
            FROM products
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        products = {}
        for row in rows:
            ebay_id, sku, title, price, status, ali_id = row
            products[ebay_id] = {
                'sku': sku,
                'title': title,
                'ebay_price': price,
                'status': status,
                'aliexpress_product_id': ali_id
            }
        
        logger.info(f"✅ Database'de {len(products)} ürün var")
        return products
    
    def extract_aliexpress_id(self, sku):
        """SKU'dan AliExpress product ID'yi çıkar"""
        if not sku:
            return None
        
        # SKU formatları:
        # AUTO-PET-1005007756879885
        # VAR-1005013457960792-1
        # AE-1005009759780480
        
        parts = sku.split('-')
        for part in parts:
            if part.isdigit() and len(part) >= 10:
                return part
        
        return None
    
    def sync_ebay_to_database(self):
        """eBay'deki ürünleri database ile senkronize et"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("🔄 OTOMATİK DATABASE SYNC BAŞLADI")
        logger.info("=" * 70)
        logger.info("")
        
        # 1. eBay'den aktif listingleri al
        ebay_listings = self.get_ebay_active_listings()
        
        if not ebay_listings:
            logger.warning("⚠️  eBay'den listing alınamadı, sync iptal edildi")
            return
        
        # 2. Database'den mevcut ürünleri al
        db_products = self.get_database_products()
        
        # 3. Karşılaştır ve sync et
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        added_count = 0
        updated_count = 0
        delisted_count = 0
        
        # eBay'deki her ürün için
        ebay_item_ids = set()
        
        for listing in ebay_listings:
            ebay_id = listing['ebay_item_id']
            ebay_item_ids.add(ebay_id)
            
            if not ebay_id or ebay_id == 'None':
                continue
            
            # Database'de var mı?
            if ebay_id not in db_products:
                # YOK - Ekle!
                logger.info(f"➕ Yeni ürün ekleniyor: {ebay_id} - {listing['title'][:50]}...")
                
                # AliExpress ID'yi çıkar
                ali_id = self.extract_aliexpress_id(listing['sku'])
                
                try:
                    cursor.execute('''
                        INSERT INTO products (
                            ebay_item_id,
                            sku_id,
                            aliexpress_product_id,
                            title,
                            ebay_price,
                            currency,
                            ebay_offer_id,
                            category_id,
                            status,
                            created_at,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        ebay_id,
                        listing['sku'],
                        ali_id,
                        listing['title'],
                        listing['ebay_price'],
                        listing['currency'],
                        listing['offer_id'],
                        listing['category_id'],
                        'AUTO_SYNCED',
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    
                    added_count += 1
                    logger.info(f"   ✅ Eklendi! AliExpress ID: {ali_id}")
                    
                except Exception as e:
                    logger.error(f"   ❌ Ekleme hatası: {e}")
                    continue
            
            else:
                # VAR - Fiyat kontrolü yap
                db_product = db_products[ebay_id]
                
                # Fiyat değişmiş mi?
                if abs(float(db_product['ebay_price'] or 0) - listing['ebay_price']) > 0.01:
                    logger.info(f"💰 Fiyat güncelleniyor: {ebay_id}")
                    logger.info(f"   Eski: €{db_product['ebay_price']} → Yeni: €{listing['ebay_price']}")
                    
                    try:
                        cursor.execute('''
                            UPDATE products
                            SET ebay_price = ?,
                                updated_at = ?
                            WHERE ebay_item_id = ?
                        ''', (
                            listing['ebay_price'],
                            datetime.now().isoformat(),
                            ebay_id
                        ))
                        
                        updated_count += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Güncelleme hatası: {e}")
                
                # Status kontrolü - REMOVED olanları tekrar ACTIVE yap
                if db_product['status'] in ['REMOVED_LOW_PROFIT', 'DELISTED']:
                    logger.info(f"🔄 Status güncelleniyor: {ebay_id}")
                    logger.info(f"   {db_product['status']} → AUTO_SYNCED")
                    
                    try:
                        cursor.execute('''
                            UPDATE products
                            SET status = 'AUTO_SYNCED',
                                updated_at = ?
                            WHERE ebay_item_id = ?
                        ''', (
                            datetime.now().isoformat(),
                            ebay_id
                        ))
                        
                        updated_count += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Status güncelleme hatası: {e}")
        
        # Database'de olup eBay'de olmayanları işaretle
        for db_id, db_product in db_products.items():
            if db_id not in ebay_item_ids:
                # Database'de var ama eBay'de yok
                if db_product['status'] not in ['DELISTED', 'REMOVED_LOW_PROFIT']:
                    logger.info(f"🗑️  eBay'de yok artık: {db_id}")
                    
                    try:
                        cursor.execute('''
                            UPDATE products
                            SET status = 'DELISTED',
                                updated_at = ?
                            WHERE ebay_item_id = ?
                        ''', (
                            datetime.now().isoformat(),
                            db_id
                        ))
                        
                        delisted_count += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Delisting hatası: {e}")
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        # Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ SYNC TAMAMLANDI!")
        logger.info("=" * 70)
        logger.info(f"➕ Eklenen:     {added_count} ürün")
        logger.info(f"💰 Güncellenen: {updated_count} ürün")
        logger.info(f"🗑️  Delisted:    {delisted_count} ürün")
        logger.info(f"📊 eBay'de:     {len(ebay_listings)} aktif listing")
        logger.info(f"📊 Database'de: {len(db_products) + added_count - delisted_count} ürün")
        logger.info("=" * 70)
        logger.info("")
        
        return {
            'added': added_count,
            'updated': updated_count,
            'delisted': delisted_count,
            'ebay_total': len(ebay_listings),
            'db_total': len(db_products) + added_count
        }

def main():
    """Ana fonksiyon"""
    try:
        sync = AutoDatabaseSync()
        result = sync.sync_ebay_to_database()
        
        logger.info("🎉 Otomatik sync başarılı!")
        return result
        
    except Exception as e:
        logger.error(f"❌ Sync hatası: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    main()
