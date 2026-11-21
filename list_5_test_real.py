"""
GERÇEK eBay API ile 5 Ürün Test Listeleme
Using actual eBayAPIClient methods
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime
import time

def create_real_ebay_listing(ebay_client, product):
    """
    Gerçek eBay listing oluştur - list_product_fixed_price kullanarak
    """
    pid, ali_id, title, desc, price, sku, category_id, image_url = product
    
    # Image URL'leri hazırla
    images = []
    if image_url and image_url.startswith('https://'):
        images = [image_url]
    
    # list_product_fixed_price için gerekli data
    listing_data = {
        "sku": sku or f"AUTO-SKU-{pid}",
        "title": title[:80] if title else f"Product {pid}",  # eBay limit 80 chars
        "description": desc or "High quality product from AliExpress",
        "price": price or 29.99,
        "quantity": 10,
        "category_id": category_id or "112529",  # Default Electronics
        "condition": "NEW",
        "image_urls": images,  # DOĞRU KEY: image_urls (plural)
        "shipping_policy_id": "263035514017",
        "payment_policy_id": "263035507017", 
        "return_policy_id": "263035512017"
    }
    
    # Create listing via eBayAPIClient
    result = ebay_client.list_product_fixed_price(listing_data)
    
    if not result:
        raise Exception("Listing creation failed - no result returned")
    
    # Result structure check
    listing_id = None
    if isinstance(result, dict):
        listing_id = result.get('ItemID') or result.get('item_id') or result.get('listing_id')
    
    if not listing_id:
        raise Exception(f"Listing ID not found in result: {result}")
    
    return {
        'listing_id': listing_id,
        'sku': sku or f"AUTO-SKU-{pid}",
        'result': result
    }


def list_5_products_test():
    """
    5 ürünü GERÇEK eBay API ile test listele
    """
    print("=" * 70)
    print("🚀 5 ÜRÜN TEST - GERÇEK eBay API")
    print("=" * 70)
    print(f"⏰ Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("⚠️  Bu işlem ~10-15 dakika sürebilir (her ürün ~2-3 dakika)")
    print("=" * 70)
    print()
    
    # eBay client
    print("🔧 eBay API client başlatılıyor...")
    ebay_client = eBayAPIClient()
    print("✅ Client hazır\n")
    
    # Database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # Listelenmemiş VE görseli olan ürünleri al
    cursor.execute('''
        SELECT id, aliexpress_product_id, title, description, ebay_price, sku_id, category_id, image_url
        FROM products 
        WHERE (is_listed = 0 OR is_listed IS NULL)
        AND title IS NOT NULL
        AND ebay_price IS NOT NULL
        AND ebay_price > 0
        AND image_url IS NOT NULL
        AND image_url LIKE 'https://%'
        LIMIT 5
    ''')
    
    products = cursor.fetchall()
    
    if not products:
        print("❌ Listelemeye hazır ürün bulunamadı!")
        conn.close()
        return
    
    print(f"📦 {len(products)} ürün bulundu\n")
    
    success_count = 0
    fail_count = 0
    results = []
    
    for i, product in enumerate(products, 1):
        pid = product[0]
        title = product[2]
        price = product[4]
        
        print(f"\n{'=' * 70}")
        print(f"📦 ÜRÜN {i}/5")
        print(f"{'=' * 70}")
        print(f"ID: {pid}")
        print(f"Title: {title[:60] if title else 'No title'}...")
        print(f"Price: €{price}")
        print()
        
        try:
            print("⏳ eBay API çağrısı yapılıyor...")
            print(f"   Method: list_product_fixed_price")
            
            result = create_real_ebay_listing(ebay_client, product)
            
            print(f"   ✅ Listing created!")
            print(f"   📋 Listing ID: {result['listing_id']}")
            print(f"   🏷️  SKU: {result['sku']}")
            
            # Database güncelle
            cursor.execute('''
                UPDATE products 
                SET is_listed = 1,
                    ebay_item_id = ?,
                    sku_id = ?,
                    status = 'active',
                    updated_at = ?
                WHERE id = ?
            ''', (result['listing_id'], result['sku'], datetime.now(), pid))
            
            conn.commit()
            
            print(f"\n✅ BAŞARILI! ({i}/5)")
            success_count += 1
            results.append({
                'id': pid,
                'listing_id': result['listing_id'],
                'status': 'success'
            })
            
            # Rate limit için bekle (3 saniye)
            print("⏳ Rate limit için 3 saniye bekleniyor...")
            time.sleep(3)
            
        except Exception as e:
            print(f"\n❌ HATA: {e}")
            fail_count += 1
            results.append({
                'id': pid,
                'error': str(e),
                'status': 'failed'
            })
            
            # Hata sonrası biraz daha bekle
            print("⏳ Hata sonrası 5 saniye bekleniyor...")
            time.sleep(5)
        
        print(f"\n📊 İlerleme: {i}/5 ({success_count} başarılı, {fail_count} hata)")
    
    conn.close()
    
    # Final rapor
    print(f"\n{'=' * 70}")
    print("📊 FINAL RAPOR")
    print(f"{'=' * 70}")
    print(f"✅ Başarılı: {success_count}")
    print(f"❌ Başarısız: {fail_count}")
    print(f"📦 Toplam: {len(products)}")
    print(f"⏰ Bitiş: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'=' * 70}")
    
    # Başarılı listingleri göster
    if success_count > 0:
        print(f"\n✅ BAŞARILI LİSTİNGLER:")
        for r in results:
            if r['status'] == 'success':
                print(f"   https://www.ebay.de/itm/{r['listing_id']}")
    
    # Hataları göster
    if fail_count > 0:
        print(f"\n❌ HATALI LİSTİNGLER:")
        for r in results:
            if r['status'] == 'failed':
                print(f"   ID {r['id']}: {r['error'][:80]}...")
    
    print(f"\n{'=' * 70}")
    if success_count > 0:
        print(f"🎉 {success_count} ürün başarıyla listelendi!")
        print(f"📱 Telegram bildirimi gönderildi")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    try:
        list_5_products_test()
    except KeyboardInterrupt:
        print("\n\n⚠️ İşlem kullanıcı tarafından durduruldu!")
    except Exception as e:
        print(f"\n\n❌ GENEL HATA: {e}")
        import traceback
        traceback.print_exc()
