"""
TAM SİSTEM KONTROLÜ
Tüm listing'leri, hataları ve eksiklikleri kontrol et
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import json

load_dotenv()

from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient

ebay = eBayAPIClient()
ali = AliExpressAPIClient()

print("="*70)
print("🔍 TAM SİSTEM KONTROLÜ")
print("="*70)

issues = []
warnings = []
success = []

# =====================================
# 1. EBAY LİSTİNG KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("1. EBAY LİSTİNG KONTROLÜ")
print(f"{'='*70}")

try:
    # Tüm offers
    offers_resp = ebay._request('GET', '/sell/inventory/v1/offer?limit=200')
    offers = offers_resp.get('offers', [])
    
    print(f"\n📊 Toplam Offer: {len(offers)}")
    
    auto_offers = [o for o in offers if o.get('sku', '').startswith('AUTO-')]
    print(f"   AUTO- prefix: {len(auto_offers)}")
    
    # Her offer detayı
    print(f"\n📦 AUTO LİSTİNGLER:")
    for offer in auto_offers:
        sku = offer.get('sku')
        offer_id = offer.get('offerId')
        listing_id = offer.get('listingId')
        price = offer.get('pricingSummary', {}).get('price', {}).get('value')
        status = offer.get('status')
        
        print(f"\n   SKU: {sku}")
        print(f"      Offer ID: {offer_id}")
        print(f"      Listing ID: {listing_id}")
        print(f"      Fiyat: €{price}")
        print(f"      Status: {status}")
        
        if status != 'PUBLISHED':
            issues.append({
                'type': 'listing_status',
                'sku': sku,
                'issue': f'Status {status}, PUBLISHED olmalı'
            })
        else:
            success.append(f"Listing {listing_id} başarılı")
    
except Exception as e:
    issues.append({
        'type': 'ebay_api',
        'issue': f'eBay API hatası: {str(e)[:200]}'
    })
    print(f"   ❌ Hata: {e}")

# =====================================
# 2. DUPLICATE SKU KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("2. DUPLICATE SKU KONTROLÜ")
print(f"{'='*70}")

try:
    all_skus = [o.get('sku') for o in offers]
    sku_counts = {}
    for sku in all_skus:
        sku_counts[sku] = sku_counts.get(sku, 0) + 1
    
    duplicates = {k: v for k, v in sku_counts.items() if v > 1}
    
    if duplicates:
        print(f"\n⚠️  DUPLICATE SKU'LAR BULUNDU:")
        for sku, count in duplicates.items():
            print(f"   {sku}: {count} kez")
            issues.append({
                'type': 'duplicate_sku',
                'sku': sku,
                'count': count
            })
    else:
        print(f"\n✅ Duplicate SKU yok")
        success.append("Duplicate SKU kontrolü başarılı")
        
except Exception as e:
    warnings.append(f"Duplicate check hatası: {e}")

# =====================================
# 3. AD CAMPAIGN KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("3. AD CAMPAIGN KONTROLÜ")
print(f"{'='*70}")

try:
    campaign_id = "168739871017"
    
    # Campaign detay
    campaign_resp = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{campaign_id}')
    
    print(f"\n📢 Campaign: {campaign_resp.get('campaignName')}")
    print(f"   Status: {campaign_resp.get('campaignStatus')}")
    print(f"   Funding: {campaign_resp.get('fundingStrategy', {}).get('fundingModel')}")
    
    # Campaign ads
    try:
        ads_resp = ebay._request('GET', f'/sell/marketing/v1/ad_campaign/{campaign_id}/ad?limit=200')
        ads = ads_resp.get('ads', [])
        
        print(f"   Toplam Ad: {len(ads)}")
        
        # AUTO listing'lerin kaçı ad'de
        auto_listing_ids = [o.get('listingId') for o in auto_offers]
        ads_listing_ids = [a.get('listingId') for a in ads]
        
        missing_ads = [lid for lid in auto_listing_ids if lid and lid not in ads_listing_ids]
        
        if missing_ads:
            print(f"\n⚠️  REKLAMSIZ LİSTİNGLER ({len(missing_ads)}):")
            for lid in missing_ads:
                print(f"   {lid}")
                warnings.append(f"Listing {lid} reklamda yok")
        else:
            print(f"\n✅ Tüm listing'ler reklamda")
            success.append("Ad campaign kontrolü başarılı")
            
    except Exception as e:
        warnings.append(f"Ad list hatası: {str(e)[:100]}")
        print(f"   ⚠️  Ad listesi alınamadı: {e}")
        
except Exception as e:
    issues.append({
        'type': 'ad_campaign',
        'issue': f'Campaign API hatası: {str(e)[:200]}'
    })
    print(f"   ❌ Hata: {e}")

# =====================================
# 4. IMAGE VALIDATION KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("4. IMAGE VALIDATION KONTROLÜ")
print(f"{'='*70}")

try:
    for offer in auto_offers[:3]:  # İlk 3 test
        sku = offer.get('sku')
        
        # SKU'dan product ID çıkar: AUTO-PET-1005009425311548
        if 'AUTO-PET-' in sku:
            product_id = sku.replace('AUTO-PET-', '')
            
            print(f"\n   Kontrol: {sku}")
            
            # Inventory item'dan görseller
            try:
                inv_resp = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
                ebay_images = inv_resp.get('product', {}).get('imageUrls', [])
                
                print(f"      eBay görseller: {len(ebay_images)}")
                
                # AliExpress'ten fresh görseller
                try:
                    ali_product = ali.get_product_details(product_id)
                    ali_images = ali_product.get('image_urls', '').split(';')
                    
                    print(f"      AliExpress görseller: {len(ali_images)}")
                    
                    # İlk görsel eşleşiyor mu?
                    if ebay_images and ali_images:
                        if ebay_images[0] == ali_images[0]:
                            print(f"      ✅ İlk görsel eşleşiyor")
                            success.append(f"{sku} image validation OK")
                        else:
                            print(f"      ⚠️  İlk görsel FARKLI!")
                            warnings.append(f"{sku} image mismatch")
                            
                except Exception as e:
                    warnings.append(f"{sku} AliExpress check hatası: {str(e)[:50]}")
                    
            except Exception as e:
                warnings.append(f"{sku} inventory item hatası: {str(e)[:50]}")
        
except Exception as e:
    warnings.append(f"Image validation hatası: {e}")

# =====================================
# 5. PRICE VALIDATION KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("5. PRICE VALIDATION KONTROLÜ")
print(f"{'='*70}")

try:
    for offer in auto_offers[:5]:  # İlk 5
        sku = offer.get('sku')
        ebay_price = float(offer.get('pricingSummary', {}).get('price', {}).get('value', 0))
        
        if 'AUTO-PET-' in sku:
            product_id = sku.replace('AUTO-PET-', '')
            
            try:
                ali_product = ali.get_product_details(product_id)
                ali_price = float(ali_product.get('sale_price') or 0)
                
                if ali_price <= 0:
                    skus = ali_product.get('skus', [])
                    if skus:
                        ali_price = float(skus[0].get('sale_price') or 0)
                
                if ali_price > 0:
                    margin = ebay_price - ali_price
                    margin_percent = (margin / ali_price) * 100
                    
                    print(f"\n   {sku}:")
                    print(f"      AliExpress: €{ali_price}")
                    print(f"      eBay: €{ebay_price}")
                    print(f"      Margin: €{margin:.2f} ({margin_percent:.0f}%)")
                    
                    if margin < 25:
                        issues.append({
                            'type': 'low_margin',
                            'sku': sku,
                            'margin': margin
                        })
                        print(f"      ❌ Margin €25'in altında!")
                    else:
                        success.append(f"{sku} margin OK (€{margin:.2f})")
                        print(f"      ✅ Margin OK")
                        
            except Exception as e:
                warnings.append(f"{sku} price check hatası: {str(e)[:50]}")
                
except Exception as e:
    warnings.append(f"Price validation hatası: {e}")

# =====================================
# 6. ASPECT KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("6. ASPECT KONTROLÜ")
print(f"{'='*70}")

try:
    required_aspects = ['Marke', 'Material', 'Farbe']
    
    for offer in auto_offers[:3]:
        sku = offer.get('sku')
        
        try:
            inv_resp = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            aspects = inv_resp.get('product', {}).get('aspects', {})
            
            print(f"\n   {sku}:")
            print(f"      Aspect'ler: {list(aspects.keys())}")
            
            missing = [a for a in required_aspects if a not in aspects]
            
            if missing:
                print(f"      ⚠️  Eksik: {missing}")
                warnings.append(f"{sku} eksik aspect'ler: {missing}")
            else:
                print(f"      ✅ Tüm zorunlu aspect'ler var")
                success.append(f"{sku} aspects OK")
                
        except Exception as e:
            warnings.append(f"{sku} aspect check hatası: {str(e)[:50]}")
            
except Exception as e:
    warnings.append(f"Aspect kontrolü hatası: {e}")

# =====================================
# 7. HTML QUALITY KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("7. HTML QUALITY KONTROLÜ")
print(f"{'='*70}")

try:
    for offer in auto_offers[:3]:
        sku = offer.get('sku')
        
        try:
            inv_resp = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            html = inv_resp.get('product', {}).get('description', '')
            
            html_len = len(html)
            
            print(f"\n   {sku}:")
            print(f"      HTML uzunluk: {html_len} karakter")
            
            # Kontroller
            checks = {
                'table': '<table' in html.lower(),
                'img': '<img' in html.lower(),
                'gradient': 'gradient' in html.lower(),
                'emoji': any(ord(c) > 127 for c in html),
            }
            
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"      {status} {check}")
                
            if html_len < 1000:
                warnings.append(f"{sku} HTML çok kısa ({html_len} char)")
            elif html_len > 4000:
                warnings.append(f"{sku} HTML çok uzun ({html_len} char)")
            else:
                success.append(f"{sku} HTML quality OK")
                
        except Exception as e:
            warnings.append(f"{sku} HTML check hatası: {str(e)[:50]}")
            
except Exception as e:
    warnings.append(f"HTML kontrolü hatası: {e}")

# =====================================
# 8. DATABASE KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("8. DATABASE KONTROLÜ")
print(f"{'='*70}")

try:
    import sqlite3
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    # AUTO listing'ler database'de mi?
    cursor.execute("SELECT COUNT(*) FROM products WHERE sku_id LIKE 'AUTO-%'")
    auto_count = cursor.fetchone()[0]
    
    print(f"\n   Database'deki AUTO listing'ler: {auto_count}")
    print(f"   eBay'deki AUTO listing'ler: {len(auto_offers)}")
    
    if auto_count < len(auto_offers):
        issues.append({
            'type': 'database_missing',
            'ebay_count': len(auto_offers),
            'db_count': auto_count,
            'issue': f'{len(auto_offers) - auto_count} listing database\'de yok'
        })
        print(f"   ❌ {len(auto_offers) - auto_count} listing database'de kayıtlı değil!")
    else:
        success.append("Database sync OK")
        print(f"   ✅ Tüm listing'ler database'de")
    
    conn.close()
    
except Exception as e:
    issues.append({
        'type': 'database',
        'issue': f'Database hatası: {str(e)[:200]}'
    })
    print(f"   ❌ Hata: {e}")

# =====================================
# 9. VERO KONTROLÜ
# =====================================
print(f"\n{'='*70}")
print("9. VERO BRAND KONTROLÜ")
print(f"{'='*70}")

VERO_BRANDS = [
    'apple', 'iphone', 'ipad', 'samsung', 'nike', 'adidas', 
    'disney', 'lego', 'gucci', 'louis vuitton'
]

try:
    for offer in auto_offers[:5]:
        sku = offer.get('sku')
        
        try:
            inv_resp = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            title = inv_resp.get('product', {}).get('title', '').lower()
            desc = inv_resp.get('product', {}).get('description', '').lower()
            
            found_brands = []
            for brand in VERO_BRANDS:
                if brand in title or brand in desc:
                    found_brands.append(brand)
            
            if found_brands:
                print(f"\n   ⚠️  {sku}:")
                print(f"      VeRO riski: {', '.join(found_brands)}")
                issues.append({
                    'type': 'vero_risk',
                    'sku': sku,
                    'brands': found_brands
                })
            else:
                success.append(f"{sku} VeRO safe")
                
        except Exception as e:
            warnings.append(f"{sku} VeRO check hatası: {str(e)[:50]}")
    
    if not any(i['type'] == 'vero_risk' for i in issues):
        print(f"\n   ✅ Tüm listing'ler VeRO safe")
        
except Exception as e:
    warnings.append(f"VeRO kontrolü hatası: {e}")

# =====================================
# ÖZET
# =====================================
print(f"\n{'='*70}")
print("📊 ÖZET RAPOR")
print(f"{'='*70}")

print(f"\n✅ BAŞARILAR ({len(success)}):")
for s in success[:10]:
    print(f"   - {s}")
if len(success) > 10:
    print(f"   ... ve {len(success) - 10} tane daha")

print(f"\n⚠️  UYARILAR ({len(warnings)}):")
for w in warnings[:10]:
    print(f"   - {w}")
if len(warnings) > 10:
    print(f"   ... ve {len(warnings) - 10} tane daha")

print(f"\n❌ KRİTİK SORUNLAR ({len(issues)}):")
for issue in issues:
    print(f"   - [{issue['type']}] {issue.get('issue', issue)}")

# JSON'a kaydet
report = {
    'success': success,
    'warnings': warnings,
    'issues': issues,
    'summary': {
        'success_count': len(success),
        'warning_count': len(warnings),
        'issue_count': len(issues)
    }
}

with open('data/system_check_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n{'='*70}")
print(f"✅ Rapor kaydedildi: data/system_check_report.json")
print(f"{'='*70}")
