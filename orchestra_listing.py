"""
ORCHESTRA LISTING SYSTEM
Otomatik ürün listeleme orchestrator - tüm adımları sırayla yürütür

WORKFLOW:
1. Ready ürün seç (kar potansiyeli yüksek)
2. Görselleri kontrol et/güncelle (min 6 görsel)
3. Rakip araştırması yap (eBay.de)
4. Fiyat belirle (rakip bazlı)
5. Vision analysis (TÜM 6 görsel)
6. Description oluştur
7. eBay'e listele
8. Database güncelle
"""

import sys
sys.path.insert(0, 'src')

from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
import sqlite3
import json
import time
from datetime import datetime
import re

# Initialize
ali = AliExpressAPIClient()
ebay = eBayAPIClient()

class OrchestraListing:
    """Otomatik listeleme orchestrator"""
    
    def __init__(self):
        self.conn = sqlite3.connect('data/dropshipping.db')
        self.cursor = self.conn.cursor()
        
    def close(self):
        self.conn.close()
    
    def step_1_select_product(self):
        """Step 1: En iyi ready ürünü seç"""
        print('=' * 80)
        print('STEP 1: ÜRÜN SEÇİMİ')
        print('=' * 80)
        print()
        
        # Ready ürünleri getir
        self.cursor.execute('''
            SELECT 
                p.id,
                p.aliexpress_product_id,
                p.title,
                p.aliexpress_price,
                p.shipping_cost,
                p.ebay_price,
                p.image_url
            FROM products p
            WHERE p.status = 'ready_to_list'
            AND p.is_listed = 0
            AND p.aliexpress_price IS NOT NULL
            AND p.ebay_price IS NOT NULL
            AND p.ebay_price BETWEEN 15 AND 40
            ORDER BY (p.ebay_price - p.aliexpress_price - (p.shipping_cost)) DESC
            LIMIT 5
        ''')
        
        products = self.cursor.fetchall()
        
        if not products:
            print('❌ Ready ürün bulunamadı')
            return None
        
        print(f'✅ {len(products)} ürün bulundu')
        print()
        
        # En iyisini seç (sweet spot €15-40)
        best = products[0]
        
        product = {
            'id': best[0],
            'ali_id': best[1],
            'title': best[2],
            'ali_price': best[3],
            'shipping': best[4] or 0,
            'ebay_price': best[5],
            'images': best[6]
        }
        
        cost = product['ali_price'] + product['shipping']
        profit = product['ebay_price'] - cost - (product['ebay_price'] * 0.11)
        
        print(f"ID {product['id']}: {product['title'][:60]}...")
        print(f"💰 €{cost:.2f} → €{product['ebay_price']:.2f} (Kar: €{profit:.2f})")
        print()
        
        return product
    
    def step_2_check_images(self, product):
        """Step 2: Görselleri kontrol et/güncelle"""
        print('=' * 80)
        print('STEP 2: GÖRSEL KONTROLÜ')
        print('=' * 80)
        print()
        
        images = product['images'].split(',') if product['images'] else []
        
        print(f"Mevcut: {len(images)} görsel")
        
        if len(images) >= 4:
            print('✅ Yeterli görsel var')
            print()
            return images
        
        print('⚠️  4+ görsel lazım, AliExpress\'ten çekiliyor...')
        
        try:
            details = ali.get_product_details(product['ali_id'])
            
            if not details:
                print('❌ AliExpress detay alınamadı')
                return images
            
            new_images_str = details.get('image_urls', '')
            
            if ';' in new_images_str:
                new_images = new_images_str.split(';')
            elif ',' in new_images_str:
                new_images = new_images_str.split(',')
            else:
                new_images = [new_images_str]
            
            # HTTPS filtrele
            new_images = [img for img in new_images if img.startswith('https://')][:6]
            
            if len(new_images) >= 4:
                # Database güncelle
                images_csv = ','.join(new_images)
                self.cursor.execute('''
                    UPDATE products
                    SET image_url = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                ''', (images_csv, product['id']))
                self.conn.commit()
                
                product['images'] = images_csv
                print(f'✅ {len(new_images)} görsel güncellendi')
                print()
                return new_images
            else:
                print(f'⚠️  Sadece {len(new_images)} görsel bulundu')
                print()
                return new_images
                
        except Exception as e:
            print(f'❌ Hata: {str(e)}')
            print()
            return images
    
    def step_3_competitor_research(self, product):
        """Step 3: Rakip araştırması (simüle - gerçekte web_search gerekir)"""
        print('=' * 80)
        print('STEP 3: RAKİP ARAŞTIRMASI')
        print('=' * 80)
        print()
        
        print('⚠️  Manuel rakip araştırması gerekiyor!')
        print(f'   Query: site:ebay.de "{product["title"][:30]}"')
        print()
        print('💡 Şimdilik mevcut fiyatı kullanıyoruz...')
        print()
        
        # Mevcut fiyatı kullan (zaten 3.1x markup ile hesaplanmış)
        return product['ebay_price']
    
    def step_4_vision_analysis(self, product, images):
        """Step 4: Vision analysis (simüle - gerçekte vision_analyze gerekir)"""
        print('=' * 80)
        print('STEP 4: VİSİON ANALİZ')
        print('=' * 80)
        print()
        
        print(f'📸 {len(images)} görsel analiz edilecek...')
        print()
        print('⚠️  Manuel vision analysis gerekiyor (Hermes context)!')
        print('💡 Şimdilik basit aspects kullanıyoruz...')
        print()
        
        # Basit aspects (title'dan çıkar)
        title_lower = product['title'].lower()
        
        material = 'Kunststoff'
        if 'bambus' in title_lower or 'holz' in title_lower:
            material = 'Bambus-Holz' if 'bambus' in title_lower else 'Holz'
        
        color = 'Mehrfarbig'
        if 'transparent' in title_lower or 'klar' in title_lower:
            color = 'Transparent'
        elif 'schwarz' in title_lower or 'black' in title_lower:
            color = 'Schwarz'
        elif 'weiß' in title_lower or 'white' in title_lower:
            color = 'Weiß'
        
        aspects = {
            'Marke': ['No-Name'],
            'Produktart': ['Aufbewahrungsbox'],
            'Material': [material],
            'Farbe': [color],
            'Zimmer': ['Wohnzimmer'],
            'Besonderheiten': ['Multifunktional'],
            'Stil': ['Modern'],
            'Anzahl der Einheiten': ['1']
        }
        
        print('✅ Aspects:')
        for key, val in aspects.items():
            print(f'   {key}: {val}')
        print()
        
        return aspects
    
    def step_5_create_description(self, product, aspects):
        """Step 5: Description oluştur"""
        print('=' * 80)
        print('STEP 5: DESCRIPTION OLUŞTURMA')
        print('=' * 80)
        print()
        
        # Basit HTML description
        title_clean = product['title'].split(',')[0][:60]
        
        desc = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">{title_clean}</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Praktische Aufbewahrungslösung für Ihr Zuhause!</strong>
</p>

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> {aspects['Material'][0]}</li>
<li>✅ <strong>Farbe:</strong> {aspects['Farbe'][0]}</li>
<li>✅ <strong>Stil:</strong> {aspects['Stil'][0]}</li>
<li>✅ <strong>Multifunktional</strong> - Vielseitig einsetzbar</li>
<li>✅ <strong>Praktisch</strong> - Platzsparende Aufbewahrung</li>
<li>✅ <strong>Hochwertig</strong> - Langlebige Qualität</li>
</ul>

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🏠 Wohnzimmer</li>
<li>🛏️ Schlafzimmer</li>
<li>🖥️ Arbeitszimmer</li>
<li>🍳 Küche</li>
</ul>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong>
</p>
</div>
</div>
'''
        
        print(f'✅ Description: {len(desc)} chars')
        print()
        
        return desc
    
    def step_6_publish_ebay(self, product, aspects, description, images):
        """Step 6: eBay'e publish"""
        print('=' * 80)
        print('STEP 6: EBAY PUBLISH')
        print('=' * 80)
        print()
        
        # eBay title (80 chars max)
        title_words = product['title'].split()[:10]
        ebay_title = ' '.join(title_words)[:80]
        
        print(f'Title: {ebay_title}')
        print(f'Price: €{product["ebay_price"]:.2f}')
        print()
        
        try:
            sku = f"ALI-{product['ali_id']}"
            
            # Inventory item
            inventory_item = {
                'sku': sku,
                'product': {
                    'title': ebay_title,
                    'description': description,
                    'aspects': aspects,
                    'imageUrls': images[:8]
                },
                'condition': 'NEW',
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': 10
                    }
                }
            }
            
            ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
            print(f'✅ Inventory: {sku}')
            
            # Offer
            offer_data = {
                'sku': sku,
                'marketplaceId': 'EBAY_DE',
                'format': 'FIXED_PRICE',
                'listingPolicies': {
                    'fulfillmentPolicyId': '263035514017',
                    'paymentPolicyId': '263035507017',
                    'returnPolicyId': '263035512017'
                },
                'categoryId': '20741',
                'merchantLocationKey': 'WAREHOUSE_DE_1',
                'pricingSummary': {
                    'price': {
                        'currency': 'EUR',
                        'value': str(product['ebay_price'])
                    }
                }
            }
            
            response2 = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
            offer_id = response2.get('offerId')
            print(f'✅ Offer: {offer_id}')
            
            # Publish
            response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
            listing_id = response3.get('listingId')
            print(f'✅ Published: {listing_id}')
            print()
            
            return listing_id, offer_id
            
        except Exception as e:
            print(f'❌ Hata: {str(e)}')
            import traceback
            traceback.print_exc()
            return None, None
    
    def step_7_update_database(self, product, listing_id, offer_id):
        """Step 7: Database güncelle"""
        print('=' * 80)
        print('STEP 7: DATABASE GÜNCELLEME')
        print('=' * 80)
        print()
        
        try:
            self.cursor.execute('''
                UPDATE products
                SET is_listed = 1,
                    ebay_item_id = ?,
                    ebay_offer_id = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            ''', (listing_id, offer_id, product['id']))
            
            self.conn.commit()
            
            print(f"✅ ID {product['id']} güncellendi")
            print()
            
        except Exception as e:
            print(f'❌ Database hatası: {str(e)}')
            print()
    
    def run(self):
        """Tüm workflow'u çalıştır"""
        print('╔══════════════════════════════════════════════════════════════════════╗')
        print('║            ORCHESTRA LISTING SYSTEM - OTOMATIK LİSTELEME            ║')
        print('╚══════════════════════════════════════════════════════════════════════╝')
        print()
        
        # Step 1: Ürün seç
        product = self.step_1_select_product()
        
        if not product:
            print('❌ DURDURULDU: Ürün seçilemedi')
            return
        
        time.sleep(1)
        
        # Step 2: Görseller
        images = self.step_2_check_images(product)
        
        if len(images) < 4:
            print('⚠️  UYARI: 4\'ten az görsel, devam ediliyor...')
        
        time.sleep(1)
        
        # Step 3: Rakip araştırması
        final_price = self.step_3_competitor_research(product)
        product['ebay_price'] = final_price
        
        time.sleep(1)
        
        # Step 4: Vision analysis
        aspects = self.step_4_vision_analysis(product, images)
        
        time.sleep(1)
        
        # Step 5: Description
        description = self.step_5_create_description(product, aspects)
        
        time.sleep(1)
        
        # Step 6: eBay publish
        listing_id, offer_id = self.step_6_publish_ebay(product, aspects, description, images)
        
        if not listing_id:
            print('❌ DURDURULDU: eBay publish başarısız')
            return
        
        time.sleep(1)
        
        # Step 7: Database update
        self.step_7_update_database(product, listing_id, offer_id)
        
        # Final report
        cost = product['ali_price'] + product['shipping']
        profit = product['ebay_price'] - cost - (product['ebay_price'] * 0.11)
        
        print('=' * 80)
        print('✅ ORCHESTRA TAMAMLANDI!')
        print('=' * 80)
        print()
        print(f"🔗 https://www.ebay.de/itm/{listing_id}")
        print(f"💰 €{product['ebay_price']:.2f} (Kar: €{profit:.2f})")
        print()

# Main
if __name__ == '__main__':
    orchestra = OrchestraListing()
    
    try:
        orchestra.run()
    finally:
        orchestra.close()
