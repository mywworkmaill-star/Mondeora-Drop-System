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
            # NOT (Hata 27): Bir inventory item == bir SKU/varyant. Variation-group bir listing'de
            # (coklu renk/beden) BIRDEN FAZLA SKU/offer AYNI listingId'yi (ebay_item_id) paylasir.
            # Burada once HAM (per-SKU) liste toplanir, asagida listingId'ye gore gruplanip
            # variation-group tespiti + fiyat-overwrite onlemesi yapilir (bkz. known-bugs.md Hata 27).
            raw_entries = []
            
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
                                
                                raw_entries.append({
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
            
            # Hata 27 fix: listingId (ebay_item_id) bazında grupla. >1 ham kayit = variation-group
            # (coklu SKU/varyant AYNI listingId'yi paylasiyor) -> TEK bir kayda indir, bu kayda
            # is_variation_group=True isaretle ve fiyati EN DUSUK varyant fiyatiyla temsil et
            # (eBay'in kendi "ab X,XX€" / baslangic-fiyati gosterimiyle tutarli). sync_ebay_to_database()
            # bu bayragi gorunce ebay_price alanini EZMEZ (gercek per-varyant fiyatlar zaten
            # product_variants tablosunda + job variation_sync tarafindan yonetiliyor, bkz. engine.py
            # _has_variants()/inventory_sync/analyze_competition_and_optimize_prices ile AYNI kural).
            by_listing = {}
            for entry in raw_entries:
                by_listing.setdefault(entry['ebay_item_id'], []).append(entry)
            active_listings = []
            variation_groups = 0
            for ebay_id, entries in by_listing.items():
                if len(entries) > 1:
                    variation_groups += 1
                    best = min(entries, key=lambda e: e['ebay_price'])
                    merged = dict(best)
                    merged['is_variation_group'] = True
                    merged['variant_count'] = len(entries)
                    active_listings.append(merged)
                else:
                    entry = dict(entries[0])
                    entry['is_variation_group'] = False
                    active_listings.append(entry)
            
            logger.info(f"✅ {len(active_listings)} aktif listing bulundu "
                       f"({variation_groups} variation-group, {len(raw_entries)} ham SKU/offer kaydi)")
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
                id,
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
        
        # Hata 28: BIRDEN FAZLA urun ayni anda ebay_item_id IS NULL olabilir (henuz eBay'e
        # yayinlanmamis/backfill edilmemis - discovery/blue_ocean/manual_review bekleyen
        # urunler). Hepsini `products[None] = ...` ile TEK bir dict key'inde toplamak
        # (last-write-wins) hepsini -1 haric sync'ten SAKLAR ve "ebay'de yok artik" kontrolunu
        # anlamsiz kilar (yayinlanmamis bir urun zaten "eBay'de bulunamadi" olur, ama bu DELISTED
        # anlamina gelmez). Bu yuzden SADECE gercek (non-null) ebay_item_id'li satirlar bu dict'e
        # girer; NULL'lu satirlar ayri `by_ali_id` listesine (aliexpress_product_id -> satir(lar))
        # gider, backfill eslemesi icin kullanilir (bkz. known-bugs.md Hata 28).
        products = {}
        by_ali_id = {}
        for row in rows:
            row_id, ebay_id, sku, title, price, status, ali_id = row
            info = {
                'id': row_id,
                'sku': sku,
                'title': title,
                'ebay_price': price,
                'status': status,
                'aliexpress_product_id': ali_id,
            }
            if ebay_id:
                products[ebay_id] = info
            if ali_id:
                by_ali_id.setdefault(ali_id, []).append(info)
        
        self._db_products_by_ali_id = by_ali_id
        self._db_total_rows = len(rows)
        logger.info(f"✅ Database'de {len(rows)} ürün var "
                    f"({len(products)} eBay_item_id'li, {len(rows) - len(products)} "
                    f"henüz yayınlanmamış/ebay_item_id yok)")
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
                # Hata 28: once ayni AliExpress urunune ait, ebay_item_id'si HENUZ kaydedilmemis
                # (NULL) bir DB satiri var mi kontrol et. Varsa bu YENI bir urun degil - mevcut
                # satirin eksik ebay_item_id'sini backfill et. Dogrudan INSERT denemek
                # products.aliexpress_product_id UNIQUE kisitina carpar VE o eski NULL-keyed
                # satir asagidaki delisting turunda yanlislikla "eBay'de yok" sayilirdi (artik
                # NULL-keyed satirlar db_products dict'inde hic yer almiyor, bkz. get_database_products).
                ali_id_for_match = self.extract_aliexpress_id(listing['sku'])
                existing_matches = self._db_products_by_ali_id.get(ali_id_for_match) if ali_id_for_match else None

                if existing_matches:
                    target = existing_matches[0]
                    logger.info(f"🔗 Mevcut urun ile eslesti (ali_id={ali_id_for_match}, "
                                f"db_id={target['id']}) - ebay_item_id backfill: {ebay_id}")
                    try:
                        backfill_price = (target['ebay_price'] if listing.get('is_variation_group')
                                           else listing['ebay_price'])
                        cursor.execute('''
                            UPDATE products
                            SET ebay_item_id = ?, sku_id = ?, ebay_price = ?, currency = ?,
                                ebay_offer_id = ?, category_id = ?, status = 'AUTO_SYNCED',
                                updated_at = ?
                            WHERE id = ?
                        ''', (
                            ebay_id, listing['sku'], backfill_price, listing['currency'],
                            listing['offer_id'], listing['category_id'],
                            datetime.now().isoformat(), target['id']
                        ))
                        updated_count += 1
                        # In-memory gorunumu guncelle: ayni calismada ikinci bir listing AYNI
                        # ali_id ile tekrar eslesmeye calisirsa (olmamali ama savunma amacli)
                        # bu satiri tekrar backfill etmeye calismasin, ve delisting turunde
                        # yeni ebay_id artik db_products'ta "mevcut" gorunsun.
                        db_products[ebay_id] = dict(target, aliexpress_product_id=ali_id_for_match)
                        self._db_products_by_ali_id[ali_id_for_match] = existing_matches[1:]
                    except Exception as e:
                        logger.error(f"   ❌ Backfill hatası: {e}")
                    continue

                # YOK - Ekle!
                logger.info(f"➕ Yeni ürün ekleniyor: {ebay_id} - {listing['title'][:50]}...")
                
                # AliExpress ID'yi çıkar
                ali_id = ali_id_for_match
                
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
                
                # Hata 27: variation-group listing'ler icin burada temsili (EN DUSUK varyant)
                # fiyati products.ebay_price'a YAZMA - gercek per-varyant fiyat product_variants
                # tablosunda job_variation_sync tarafindan yonetiliyor (bkz. engine.py _has_variants()).
                # Bu alani burada ezersek her gece "fiyat degisti" gurultusu + price_optimize/dashboard
                # icin yanlis temsili deger birakiriz (ilgili urun zaten _has_variants() ile
                # price_optimize'da atlaniyor, ama degeri DB'de yanlis birakmak ayri bir sorun).
                if listing.get('is_variation_group'):
                    pass
                # Fiyat değişmiş mi?
                elif abs(float(db_product['ebay_price'] or 0) - listing['ebay_price']) > 0.01:
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
        logger.info(f"📊 Database'de: {self._db_total_rows + added_count - delisted_count} ürün")
        logger.info("=" * 70)
        logger.info("")
        
        return {
            'added': added_count,
            'updated': updated_count,
            'delisted': delisted_count,
            'ebay_total': len(ebay_listings),
            'db_total': self._db_total_rows + added_count
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
