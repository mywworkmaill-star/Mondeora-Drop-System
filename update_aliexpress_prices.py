"""
AliExpress fiyatlarını çekip veritabanını güncelle
"""
import sys
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.aliexpress_client import AliExpressAPIClient

def update_aliexpress_prices():
    print("\n" + "="*70)
    print("💰 ALIEXPRESS FİYATLARI GÜNCELLENİYOR")
    print("="*70)
    
    db_path = PROJECT_ROOT / 'data/dropshipping.db'
    
    if not db_path.exists():
        print(f"❌ Veritabanı bulunamadı: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # AliExpress product_id'si olan ürünleri al
    cursor.execute("""
        SELECT id, aliexpress_product_id, title, ebay_price 
        FROM products 
        WHERE aliexpress_product_id IS NOT NULL 
        AND aliexpress_product_id != ''
        ORDER BY id DESC
        LIMIT 20
    """)
    
    products = cursor.fetchall()
    
    if not products:
        print("⚠️  AliExpress product_id'si olan ürün bulunamadı")
        conn.close()
        return False
    
    print(f"📦 {len(products)} ürün bulundu\n")
    
    ali_client = AliExpressAPIClient()
    updated_count = 0
    
    for product_id, ali_product_id, title, ebay_price in products:
        print(f"🔍 Ürün #{product_id}: {title[:40]}...")
        print(f"   AliExpress ID: {ali_product_id}")
        print(f"   eBay Fiyat: €{ebay_price}")
        
        try:
            # AliExpress API'den fiyat çek
            product_details = ali_client.get_product_details(ali_product_id)
            
            if product_details:
                # Fiyat bilgisini çıkar (API response yapısına göre)
                ali_price = None
                
                # Farklı API yanıt yapıları dene
                if isinstance(product_details, dict):
                    # Fiyat alanları (API'ye göre değişir)
                    ali_price = (
                        product_details.get('target_sale_price') or
                        product_details.get('target_app_sale_price') or
                        product_details.get('target_original_price') or
                        product_details.get('price')
                    )
                
                if ali_price:
                    # String ise float'a çevir
                    if isinstance(ali_price, str):
                        ali_price = float(ali_price.replace(',', '.'))
                    
                    # Kar marjını hesapla
                    margin = ((float(ebay_price) - float(ali_price)) / float(ebay_price)) * 100 if ebay_price else 0
                    
                    # Veritabanını güncelle
                    cursor.execute("""
                        UPDATE products 
                        SET aliexpress_price = ?,
                            margin_percent = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (ali_price, margin, product_id))
                    
                    print(f"   ✅ AliExpress: €{ali_price} | Kar: {margin:.1f}%")
                    updated_count += 1
                else:
                    print(f"   ⚠️  Fiyat bilgisi alınamadı")
            else:
                print(f"   ❌ Ürün detayı alınamadı")
        
        except Exception as e:
            print(f"   ❌ Hata: {e}")
        
        print()
    
    conn.commit()
    conn.close()
    
    print("="*70)
    print(f"✅ {updated_count}/{len(products)} ürün güncellendi")
    print("="*70)
    
    return updated_count > 0


if __name__ == "__main__":
    success = update_aliexpress_prices()
    sys.exit(0 if success else 1)
