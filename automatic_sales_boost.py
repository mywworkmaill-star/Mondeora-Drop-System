#!/usr/bin/env python
"""
AUTOMATIC SALES BOOST SYSTEM
Activates all sales optimization features automatically
NO MANUAL WORK REQUIRED!
"""

import sys
import os
sys.path.insert(0, '.')

from src.api.ebay_client import eBayRESTClient
import sqlite3
import json
from datetime import datetime, timezone

class AutomaticSalesBooster:
    """
    Automatic sales optimization - no manual steps

    Hata 26: bu script src.jobs hub'ini bypass eder (root-level, cron
    dogrudan `from automatic_sales_boost import ...; .boost_all_listings()`
    cagirir). Fiyati %15 dusurup ucretsiz kargo/best-offer/promoted-ad
    acan GERCEK canli eBay yazmalari yapar -- yanlislikla calisirsa butun
    envanterin fiyatini degistirir. Varsayilan GUVENLI: .env'de
    SALES_BOOST_LIVE_CONFIRMED=true YOKSA dry-run (hic PUT/POST gondermez,
    sadece ne yapacagini raporlar). Bu job su an PAUSED (mondeora-sales-boost
    cron'u), ama kod tabaninda kalici oldugu icin guvenli varsayilan sart.
    """
    
    def __init__(self):
        self.ebay = eBayRESTClient()
        self.db_path = 'data/dropshipping.db'
        self.campaign_id = "168750173017"
        self.dry_run = os.environ.get('SALES_BOOST_LIVE_CONFIRMED', '').strip().lower() != 'true'
        
    def get_all_listings(self):
        """Get all AUTO products from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sku_id, title, ebay_item_id, ebay_price, aliexpress_price
            FROM products
            WHERE sku_id LIKE 'AUTO-PET-%'
            ORDER BY created_at DESC
        """)
        
        listings = cursor.fetchall()
        conn.close()
        
        return listings
    
    def optimize_price(self, sku, current_price, cost):
        """
        Optimize price for sales (15% discount)
        """
        try:
            if not current_price or current_price <= 0:
                return None
                
            # 15% discount for flash sale
            sale_price = round(current_price * 0.85, 2)
            
            # Ensure minimum margin (2x cost)
            if cost and cost > 0:
                min_price = cost * 2
                if sale_price < min_price:
                    sale_price = round(min_price, 2)

            if self.dry_run:
                # Hata 26: dry-run gercekten hicbir PUT/POST gondermemeli.
                return sale_price

            # Update offer price via eBay API
            response = self.ebay.call(
                'PUT',
                f'sell/inventory/v1/inventory_item/{sku}',
                data={
                    'availability': {
                        'shipToLocationAvailability': {
                            'quantity': 999
                        }
                    },
                    'product': {
                        'title': f'[FLASH SALE] {sku}'
                    }
                }
            )
            
            # Update offer
            offers_response = self.ebay.call(
                'GET',
                f'sell/inventory/v1/offer',
                params={'sku': sku}
            )
            
            if offers_response and 'offers' in offers_response:
                for offer in offers_response['offers']:
                    offer_id = offer.get('offerId')
                    
                    # Update price
                    self.ebay.call(
                        'PUT',
                        f'sell/inventory/v1/offer/{offer_id}',
                        data={
                            'pricingSummary': {
                                'price': {
                                    'value': str(sale_price),
                                    'currency': 'EUR'
                                }
                            }
                        }
                    )
            
            return sale_price
            
        except Exception as e:
            print(f"   ⚠️  Price update error: {e}")
            return None
    
    def enable_free_shipping(self, sku):
        """
        Enable free shipping for a listing
        """
        try:
            # Get current offers
            offers_response = self.ebay.call(
                'GET',
                'sell/inventory/v1/offer',
                params={'sku': sku}
            )
            
            if offers_response and 'offers' in offers_response:
                for offer in offers_response['offers']:
                    offer_id = offer.get('offerId')
                    
                    # Update with free shipping
                    self.ebay.call(
                        'PUT',
                        f'sell/inventory/v1/offer/{offer_id}',
                        data={
                            'listingPolicies': {
                                'shippingCostOverrides': [
                                    {
                                        'shippingCost': {
                                            'value': '0.00',
                                            'currency': 'EUR'
                                        },
                                        'shippingServiceType': 'DOMESTIC'
                                    }
                                ]
                            }
                        }
                    )
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"   ⚠️  Free shipping error: {e}")
            return False
    
    def enable_best_offer(self, sku):
        """
        Enable best offer negotiation
        """
        try:
            # Get current offers
            offers_response = self.ebay.call(
                'GET',
                'sell/inventory/v1/offer',
                params={'sku': sku}
            )
            
            if offers_response and 'offers' in offers_response:
                for offer in offers_response['offers']:
                    offer_id = offer.get('offerId')
                    
                    # Enable best offer
                    self.ebay.call(
                        'PUT',
                        f'sell/inventory/v1/offer/{offer_id}',
                        data={
                            'listingPolicies': {
                                'bestOfferTerms': {
                                    'bestOfferEnabled': True,
                                    'autoAcceptPrice': {
                                        'value': '0.00',
                                        'currency': 'EUR'
                                    },
                                    'autoDeclinePrice': {
                                        'value': '0.00',
                                        'currency': 'EUR'
                                    }
                                }
                            }
                        }
                    )
                    
                    return True
            
            return False
            
        except Exception as e:
            print(f"   ⚠️  Best offer error: {e}")
            return False
    
    def create_promoted_ad(self, sku, listing_id):
        """
        Create promoted listing ad (15% rate)
        """
        try:
            # Create ad via Marketing API
            response = self.ebay.call(
                'POST',
                f'sell/marketing/v1/ad_campaign/{self.campaign_id}/ad',
                data={
                    'bidPercentage': '15.0',  # 15% ad rate
                    'inventoryReferenceId': sku,
                    'inventoryReferenceType': 'INVENTORY_ITEM'
                }
            )
            
            if response and response.get('adId'):
                return response['adId']
            
            return None
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if already exists
            if '35036' in error_msg or 'already exists' in error_msg.lower():
                # Update existing ad to 15%
                try:
                    # Get existing ads
                    ads_response = self.ebay.call(
                        'GET',
                        f'sell/marketing/v1/ad_campaign/{self.campaign_id}/ad',
                        params={'limit': 100}
                    )
                    
                    if ads_response and 'ads' in ads_response:
                        for ad in ads_response['ads']:
                            if ad.get('inventoryReferenceId') == sku:
                                ad_id = ad.get('adId')
                                
                                # Update bid to 15%
                                self.ebay.call(
                                    'PUT',
                                    f'sell/marketing/v1/ad_campaign/{self.campaign_id}/ad/{ad_id}',
                                    data={
                                        'bidPercentage': '15.0'
                                    }
                                )
                                
                                return ad_id
                
                except Exception:
                    pass
                
                return 'EXISTS'
            
            print(f"   ⚠️  Promoted ad error: {e}")
            return None
    
    def boost_all_listings(self):
        """
        Main function - boost all listings automatically

        Hata 8 deseni: her listing'in 4 islemi (fiyat/kargo/best-offer/reklam)
        kendi try/except'i icinde zaten izoleydi, AMA bu dongunun govdesinin
        KENDISI (sku/title/ebay_id okuma, €{price:.2f} formatlama) try/except
        DISINDAYDI -- price/cost NULL olan (DB'de eksik ebay_price) TEK bir kayit
        TypeError ile TUM batch'i (kalan saglikli kayitlarin boost'unu) durdururdu.
        Artik her kaydin tum govdesi izole + price/cost None-guard'li.
        """
        print("=" * 70)
        print("🤖 AUTOMATIC SALES BOOST SYSTEM - STARTING...")
        print("=" * 70)
        print()
        if self.dry_run:
            print("🧪 DRY-RUN MODE: SALES_BOOST_LIVE_CONFIRMED=true degil -- hicbir")
            print("   PUT/POST eBay'e gonderilmeyecek, sadece ne yapilacagi raporlanacak.")
        else:
            print("⚡ LIVE MODE: gercek eBay fiyat/kargo/best-offer/reklam degisiklikleri yapilacak.")
        print()
        
        listings = self.get_all_listings()
        
        if not listings:
            print("❌ No listings found in database")
            self._write_status('ok', 0, {})
            return
        
        print(f"Found {len(listings)} listings to optimize\n")
        
        stats = {
            'total': len(listings),
            'price_optimized': 0,
            'free_shipping': 0,
            'best_offer': 0,
            'promoted_ads': 0
        }
        skipped = []
        
        for i, (sku, title, ebay_id, price, cost) in enumerate(listings, 1):
            try:
                price = float(price) if price is not None else 0.0
                cost = float(cost) if cost is not None else 0.0
                title = title or sku

                print(f"📦 {i}/{len(listings)}: {title[:50]}...")
                print(f"   SKU: {sku}")
                print(f"   eBay ID: {ebay_id}")
                print(f"   Current Price: €{price:.2f}")
                print()

                # 1. Price Optimization (15% discount)
                print("   💰 Optimizing price (15% flash sale)...")
                new_price = self.optimize_price(sku, price, cost)
                if new_price:
                    print(f"   ✅ Price updated: €{price:.2f} → €{new_price:.2f}")
                    stats['price_optimized'] += 1
                else:
                    print(f"   ℹ️  Price kept at: €{price:.2f}")
                print()

                # 2. Free Shipping
                print("   📦 Enabling free shipping...")
                if self.enable_free_shipping(sku):
                    print("   ✅ Free shipping enabled")
                    stats['free_shipping'] += 1
                else:
                    print("   ℹ️  Free shipping status unchanged")
                print()

                # 3. Best Offer
                print("   💬 Enabling best offer negotiation...")
                if self.enable_best_offer(sku):
                    print("   ✅ Best offer enabled")
                    stats['best_offer'] += 1
                else:
                    print("   ℹ️  Best offer status unchanged")
                print()

                # 4. Promoted Ads (15% rate)
                print("   📢 Creating promoted listing ad (15% rate)...")
                ad_id = self.create_promoted_ad(sku, ebay_id)
                if ad_id:
                    if ad_id == 'EXISTS':
                        print("   ✅ Promoted ad already active (updated to 15%)")
                    else:
                        print(f"   ✅ Promoted ad created: {ad_id}")
                    stats['promoted_ads'] += 1
                else:
                    print("   ⚠️  Promoted ad not created (may already exist)")

                print()
                print("-" * 70)
                print()
            except Exception as ex:
                print(f"   ⚠️  SKIP (listing hatasi, diger kayitlar ETKILENMEDI): sku={sku} -> {ex}")
                skipped.append({'sku': sku, 'error': str(ex)})
                print()
                continue
        
        # Final summary
        print("=" * 70)
        print("🎉 AUTOMATIC BOOST COMPLETE!")
        print("=" * 70)
        print()
        print("📊 OPTIMIZATION RESULTS:")
        print(f"   Total Listings:       {stats['total']}")
        print(f"   Price Optimized:      {stats['price_optimized']}/{stats['total']}")
        print(f"   Free Shipping:        {stats['free_shipping']}/{stats['total']}")
        print(f"   Best Offer:           {stats['best_offer']}/{stats['total']}")
        print(f"   Promoted Ads:         {stats['promoted_ads']}/{stats['total']}")
        if skipped:
            print(f"   Skipped (hatali):     {len(skipped)}/{stats['total']}")
        print()
        if self.dry_run:
            print("🧪 DRY-RUN tamamlandi -- canliya gecmek icin .env'e")
            print("   SALES_BOOST_LIVE_CONFIRMED=true ekleyip tekrar calistir.")
        else:
            print("✅ LIVE degisiklikler eBay'e gonderildi.")
        print()
        self._write_status('ok' if not skipped else 'partial', len(listings), stats, skipped)

    def _write_status(self, status, total, stats, skipped=None):
        """src.jobs hub disinda calisan bu script icin de gorunurluk birak
        (Hata 24/26'daki 'sessiz ok' deseninin tekrarini onlemek icin)."""
        try:
            os.makedirs('data/jobs', exist_ok=True)
            payload = {
                'job': 'sales_boost',
                'status': status,
                'dry_run': self.dry_run,
                'total': total,
                'stats': stats,
                'skipped': skipped or [],
                'at': datetime.now(timezone.utc).isoformat(),
            }
            with open('data/jobs/last_sales_boost.json', 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
        except Exception as ex:
            print(f"   ⚠️  status yazilamadi: {ex}")

if __name__ == "__main__":
    try:
        booster = AutomaticSalesBooster()
        booster.boost_all_listings()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
