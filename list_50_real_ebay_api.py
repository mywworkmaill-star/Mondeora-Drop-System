"""
GERÇEK eBay API ile 50 Ürün Listeleme
Real API calls, no simulation
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
import sqlite3
from datetime import datetime
import time

def create_real_ebay_listing(ebay_client, product):
    """
    Gerçek eBay listing oluştur
    """
    pid, ali_id, title, desc, price, sku, category_id = product
    
    # Inventory item oluştur
    inventory_data = {
        "sku": sku or f"AUTO-{pid}",
        "product": {
            "title": title[:80],  # eBay limit 80 chars
            "description": desc or "High quality product",
            "aspects": {
                "Brand": ["Unbranded"],
                "Type": ["Standard"],
                "MPN": ["Does Not Apply"]
            },
            "imageUrls": []  # Şimdilik boş, gerçekte AliExpress'ten çekilmeli
        },
        "condition": "NEW",
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 10
            }
        }
    }
    
    # Create inventory item
    inv_result = ebay_client.create_inventory_item(inventory_data)
    
    if not inv_result:
        raise Exception("Inventory item creation failed")
    
    # Create offer
    offer_data = {
        "sku": sku or f"AUTO-{pid}",
        "marketplaceId": "EBAY_DE",
        "format": "FIXED_PRICE",
        "listingDescription": desc or "High quality product",
        "availableQuantity": 10,
        "categoryId": category_id or "112529",  # Default Electronics
        "listingPolicies": {
            "paymentPolicyId": "263035507017",
            "returnPolicyId": "263035512017",
            "fulfillmentPolicyId": "263035514017"
        },
        "pricingSummary": {
            "price": {
                "value": str(price or 29.99),
                "currency": "EUR"
            }
        }
    }
    
    offer_result = ebay_client.create_offer(offer_data)
    
    if not offer_result or 'offerId' not in offer_result:
        raise Exception("Offer creation failed")
    
    offer_id = offer_result['offerId']
    
    # Publish offer
    publish_result = ebay_client.publish_offer(offer_id)
    
    if not publish_result or 'listingId' not in publish_result:
        raise Exception("Offer publish failed")
    
    listing_id = publish_result['listingId']
    
    return {
        'listing_id': listing_id,
        'offer_id': offer_id,
        'sku': sku or f"AUTO-{pid}"
    }


def list_50_products_real():
    """
    50 ürünü GERÇEK eBay API ile listele
    """
    print("=" * 70)
    print("🚀 5 ÜRÜN TEST - GERÇEK eBay API")
    print("=" * 70)
    print(f"⏰ Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("⚠️  Bu işlem ~10-15 dakika sürebilir (her ürün ~2-3 dakika)")
    print("=" * 70)
    print()
    
    # eBay client
    ebay_client = eBayAPIClient()
    
    # Database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # Listelenmemiş ürünleri al
    cursor.execute('''
        SELECT id, aliexpress_product_id, title, description, ebay_price, sku_id, category_id
        FROM products 
        WHERE (is_listed = 0 OR is_listed IS NULL)
        AND title IS NOT NULL
        AND ebay_price IS NOT NULL
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
        print(f"Title: {title[:60]}...")
        print(f"Price: €{price}")
        print()
        
        try:
            print("⏳ eBay API çağrıları yapılıyor...")
            print("   1/3 Creating inventory item...")
            
            result = create_real_ebay_listing(ebay_client, product)
            
            print(f"   ✅ Inventory item created")
            print(f"   2/3 Creating offer...")
            print(f"   ✅ Offer created: {result['offer_id']}")
            print(f"   3/3 Publishing offer...")
            print(f"   ✅ Published! Listing ID: {result['listing_id']}")
            
            # Database güncelle
            cursor.execute('''
                UPDATE products 
                SET is_listed = 1,
                    ebay_item_id = ?,
                    ebay_offer_id = ?,
                    status = 'active',
                    updated_at = ?
                WHERE id = ?
            ''', (result['listing_id'], result['offer_id'], datetime.now(), pid))
            
            conn.commit()
            
            print(f"\n✅ BAŞARILI! ({i}/50)")
            success_count += 1
            results.append({
                'id': pid,
                'listing_id': result['listing_id'],
                'status': 'success'
            })
            
            # Rate limit için bekle (2 saniye)
            time.sleep(2)
            
        except Exception as e:
            print(f"\n❌ HATA: {e}")
            fail_count += 1
            results.append({
                'id': pid,
                'error': str(e),
                'status': 'failed'
            })
            
            # Hata sonrası biraz daha bekle
            time.sleep(5)
        
        print(f"\n📊 İlerleme: {i}/50 ({success_count} başarılı, {fail_count} hata)")
        
        # Her 10 üründe bir ara rapor
        if i % 10 == 0:
            print(f"\n{'─' * 70}")
            print(f"📊 ARA RAPOR ({i}/50)")
            print(f"{'─' * 70}")
            print(f"✅ Başarılı: {success_count}")
            print(f"❌ Başarısız: {fail_count}")
            print(f"⏰ Geçen süre: ~{i * 2} dakika")
            print(f"⏱️  Tahmini kalan: ~{(50 - i) * 2} dakika")
            print(f"{'─' * 70}\n")
    
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
                print(f"   ID {r['id']}: {r['listing_id']}")
    
    # Hataları göster
    if fail_count > 0:
        print(f"\n❌ HATALI LİSTİNGLER:")
        for r in results:
            if r['status'] == 'failed':
                print(f"   ID {r['id']}: {r['error'][:60]}...")

if __name__ == "__main__":
    try:
        list_50_products_real()
    except KeyboardInterrupt:
        print("\n\n⚠️ İşlem kullanıcı tarafından durduruldu!")
    except Exception as e:
        print(f"\n\n❌ GENEL HATA: {e}")
        import traceback
        traceback.print_exc()
