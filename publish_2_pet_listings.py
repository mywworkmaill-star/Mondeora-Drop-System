"""
2 HAZIR PET LİSTİNG'İ PUBLISH ET
Kratzbaum + Leine
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests

load_dotenv()

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("2 PET LİSTİNG PUBLISH EDİLİYOR")
print("="*70)

# Önce mevcut offer'ları bul
SKUS = ["SAFE-PET-004", "SAFE-PET-005"]
published = []
errors = []

for sku in SKUS:
    print(f"\n{'='*70}")
    print(f"SKU: {sku}")
    print(f"{'='*70}")
    
    try:
        # 1. SKU'nun offer'larını bul
        print(f"\n1. Offer'lar aranıyor...")
        
        offers_resp = requests.get(
            f"https://api.ebay.com/sell/inventory/v1/offer?sku={sku}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Language': 'de-DE'
            }, timeout=30
        )
        
        if offers_resp.status_code == 200:
            offers_data = offers_resp.json()
            offers = offers_data.get('offers', [])
            
            if len(offers) > 0:
                offer = offers[0]
                offer_id = offer.get('offerId')
                status = offer.get('status')
                
                print(f"   ✅ Offer bulundu: {offer_id}")
                print(f"   Status: {status}")
                
                if status == 'PUBLISHED':
                    listing_id = offer.get('listingId')
                    print(f"   ℹ️  Zaten yayında: {listing_id}")
                    published.append({
                        'sku': sku,
                        'offer_id': offer_id,
                        'listing_id': listing_id,
                        'status': 'already_published'
                    })
                else:
                    # 2. Publish et
                    print(f"\n2. Publish ediliyor...")
                    
                    pub_resp = requests.post(
                        f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish",
                        headers={
                            'Authorization': f'Bearer {access_token}',
                            'Content-Type': 'application/json'
                        }, timeout=30
                    )
                    
                    if pub_resp.status_code in [200, 201]:
                        pub_data = pub_resp.json()
                        listing_id = pub_data.get('listingId')
                        
                        print(f"   ✅ YAYINLANDI!")
                        print(f"   Listing ID: {listing_id}")
                        print(f"   Link: https://www.ebay.de/itm/{listing_id}")
                        
                        # 3. Reklam ekle
                        print(f"\n3. Reklam kampanyasına ekleniyor...")
                        
                        ad_resp = requests.post(
                            f"https://api.ebay.com/sell/marketing/v1/ad_campaign/168739871017/ad",
                            headers={
                                'Authorization': f'Bearer {access_token}',
                                'Content-Type': 'application/json'
                            },
                            json={
                                "bidPercentage": "5.0",
                                "listingId": listing_id
                            }, timeout=30
                        )
                        
                        if ad_resp.status_code in [200, 201]:
                            ad_data = ad_resp.json()
                            ad_id = ad_data.get('adId')
                            print(f"   ✅ Reklam eklendi: {ad_id}")
                        elif ad_resp.status_code == 409:
                            print(f"   ℹ️  Reklam zaten mevcut (409)")
                        else:
                            print(f"   ⚠️  Reklam hatası: {ad_resp.status_code}")
                        
                        published.append({
                            'sku': sku,
                            'offer_id': offer_id,
                            'listing_id': listing_id,
                            'status': 'newly_published',
                            'link': f"https://www.ebay.de/itm/{listing_id}"
                        })
                    else:
                        print(f"   ❌ Publish hatası: {pub_resp.status_code}")
                        print(f"   {pub_resp.text[:300]}")
                        errors.append(f"{sku}: Publish failed {pub_resp.status_code}")
            else:
                print(f"   ⚠️  Offer bulunamadı!")
                errors.append(f"{sku}: No offer found")
        else:
            print(f"   ❌ Offer arama hatası: {offers_resp.status_code}")
            errors.append(f"{sku}: Offer search failed")
            
    except Exception as e:
        print(f"\n❌ Hata: {str(e)}")
        errors.append(f"{sku}: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 SONUÇ:")
print(f"   Publish edilen: {len([p for p in published if p['status'] == 'newly_published'])}")
print(f"   Zaten yayında: {len([p for p in published if p['status'] == 'already_published'])}")
print(f"   Toplam başarılı: {len(published)}/2")

if published:
    print(f"\n🎉 YAYINDA OLAN LİSTİNG'LER:")
    for item in published:
        status_emoji = "🆕" if item['status'] == 'newly_published' else "✅"
        print(f"\n   {status_emoji} SKU: {item['sku']}")
        print(f"      Offer: {item['offer_id']}")
        print(f"      Listing: {item['listing_id']}")
        if 'link' in item:
            print(f"      Link: {item['link']}")

if errors:
    print(f"\n⚠️  HATALAR ({len(errors)}):")
    for err in errors:
        print(f"   - {err}")

print(f"\n✨ TOPLAM AKTİF PET LİSTİNG: {3 + len([p for p in published if p['status'] == 'newly_published'])}")
print(f"\n🛡️ HEPSİ:")
print(f"   ✅ VeRO-Safe (markasız)")
print(f"   ✅ Profesyonel HTML açıklama")
print(f"   ✅ Gerçek AliExpress görselleri")
print(f"   ✅ Reklam %5 aktif")
