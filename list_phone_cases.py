import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Product
import requests

load_dotenv()

engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)
session = Session()
ebay = eBayAPIClient()

print("="*70)
print("TELEFON KILIFLARINI LISTELIYORUM (COKLU FOTOGRAF)")
print("="*70)

# Multiple images per product
products_to_list = [
    {
        'sku': 'PHONE-CASE-IPHONE15-BLACK-001',
        'title': 'Silikon Huelle iPhone 15 Pro Max Schutzhuelle Schwarz',
        'description': '<p>Hochwertige Silikon-Schutzhuelle fuer iPhone 15 Pro Max</p><ul><li>Stossfest und kratzfest</li><li>Praezise Aussparungen fuer Kamera</li><li>Einfache Installation</li><li>Rutschfeste Oberflaeche</li><li>Premium Qualitaet</li></ul>',
        'price': 12.99,
        'quantity': 10,
        'images': [
            'https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=800',
            'https://images.unsplash.com/photo-1574944985070-8f3ebc6b79d2?w=800',
            'https://images.unsplash.com/photo-1556656793-08538906a9f8?w=800',
            'https://images.unsplash.com/photo-1603891219772-c39afc4c4cc9?w=800',
            'https://images.unsplash.com/photo-1592286927505-38b37258b7e0?w=800',
            'https://images.unsplash.com/photo-1585060544812-6b45742d762f?w=800'
        ],
        'aspects': {
            'Marke': ['Markenlos'],
            'Produktart': ['Aufprallschutzhuelle'],
            'Farbe': ['Schwarz'],
            'Kompatibles Modell': ['Fuer Apple iPhone 15 Pro Max'],
            'Material': ['Silikon'],
            'Design/Oberflaeche': ['Unifarben']
        }
    },
    {
        'sku': 'PHONE-CASE-SAMSUNG-S24-CLEAR-001',
        'title': 'Transparent Huelle Samsung Galaxy S24 Ultra TPU Klar',
        'description': '<p>Kristallklare TPU-Schutzhuelle fuer Samsung Galaxy S24 Ultra</p><ul><li>Ultra duenn nur 0.5mm</li><li>Stossfest und flexibel</li><li>Praezise Passform</li><li>Zeigt das Original-Design</li><li>Anti-Fingerabdruck</li></ul>',
        'price': 14.99,
        'quantity': 10,
        'images': [
            'https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800',
            'https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=800',
            'https://images.unsplash.com/photo-1585060544812-6b45742d762f?w=800',
            'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800',
            'https://images.unsplash.com/photo-1580910051074-3eb694886505?w=800',
            'https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?w=800'
        ],
        'aspects': {
            'Marke': ['Markenlos'],
            'Produktart': ['Aufprallschutzhuelle'],
            'Farbe': ['Transparent'],
            'Kompatibles Modell': ['Fuer Samsung Galaxy S24 Ultra'],
            'Material': ['TPU'],
            'Design/Oberflaeche': ['Transparent']
        }
    }
]

listed_count = 0
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

for i, prod in enumerate(products_to_list, 1):
    print(f"\n{'='*70}")
    print(f"URUN {i}/2: {prod['title'][:50]}")
    print(f"{'='*70}")
    
    sku = prod['sku']
    
    try:
        # Step 1: Create Inventory Item
        print(f"\n1. Inventory item ({len(prod['images'])} fotograf)...")
        
        inventory_item = {
            'product': {
                'title': prod['title'],
                'description': prod['description'],
                'aspects': prod['aspects'],
                'imageUrls': prod['images']
            },
            'condition': 'NEW',
            'packageWeightAndSize': {
                'dimensions': {
                    'height': 1,
                    'length': 16,
                    'width': 8,
                    'unit': 'CENTIMETER'
                },
                'weight': {
                    'value': 0.05,
                    'unit': 'KILOGRAM'
                }
            },
            'availability': {
                'shipToLocationAvailability': {
                    'quantity': prod['quantity']
                }
            }
        }
        
        inv_resp = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={
                'Authorization': f'Bearer {access_token}', 
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=inventory_item, timeout=30
        )
        
        if inv_resp.status_code not in [200, 204]:
            print(f"   HATA: {inv_resp.status_code} - {inv_resp.text[:200]}")
            continue
            
        print(f"   OK")
        
        # Step 2: Create Offer
        print(f"\n2. Offer olusturuluyor...")
        
        offer = {
            'sku': sku,
            'marketplaceId': 'EBAY_DE',
            'format': 'FIXED_PRICE',
            'availableQuantity': prod['quantity'],
            'categoryId': '20349',
            'listingDescription': prod['description'],
            'listingPolicies': {
                'paymentPolicyId': os.getenv('EBAY_PAYMENT_POLICY_ID'),
                'returnPolicyId': os.getenv('EBAY_RETURN_POLICY_ID'),
                'fulfillmentPolicyId': os.getenv('EBAY_FULFILLMENT_POLICY_ID')
            },
            'pricingSummary': {
                'price': {
                    'value': str(prod['price']),
                    'currency': 'EUR'
                }
            },
            'merchantLocationKey': os.getenv('EBAY_MERCHANT_LOCATION_KEY')
        }
        
        offer_resp = requests.post(
            'https://api.ebay.com/sell/inventory/v1/offer',
            headers={
                'Authorization': f'Bearer {access_token}', 
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=offer, timeout=30
        )
        
        if offer_resp.status_code not in [200, 201]:
            print(f"   HATA: {offer_resp.status_code} - {offer_resp.text[:300]}")
            continue
            
        offer_id = offer_resp.json().get('offerId')
        print(f"   OK: {offer_id}")
        
        # Step 3: Publish
        print(f"\n3. Yayinlaniyor...")
        
        pub_resp = requests.post(
            f'https://api.ebay.com/sell/inventory/v1/offer/{offer_id}/publish',
            headers={
                'Authorization': f'Bearer {access_token}', 
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            }, timeout=30
        )
        
        if pub_resp.status_code == 200:
            data = pub_resp.json()
            listing_id = data.get('listingId')
            
            print(f"\n   BASARILI!")
            print(f"   eBay ID: {listing_id}")
            print(f"   Link: https://www.ebay.de/itm/{listing_id}")
            
            # Database
            product = Product(
                aliexpress_product_id='MANUAL-PHONE-CASE',
                sku_id=sku,
                title=prod['title'],
                description=prod['description'],
                aliexpress_price=5.0,
                ebay_price=prod['price'],
                margin_percent=60,
                current_stock=prod['quantity'],
                aliexpress_stock=100,
                shipping_cost=0.0,
                currency='EUR',
                category_id='20349',
                fulfillment_verified=True,
                status='active',
                is_listed=True,
                ebay_item_id=listing_id,
                ebay_offer_id=offer_id
            )
            session.add(product)
            session.commit()
            
            listed_count += 1
            
        else:
            print(f"   HATA: {pub_resp.status_code}")
            print(f"   {pub_resp.text[:500]}")
    
    except Exception as e:
        print(f"\n   HATA: {str(e)[:300]}")
        import traceback
        traceback.print_exc()

session.close()

print(f"\n{'='*70}")
print(f"SONUC: {listed_count}/2 URUN LISTELENDI")
print(f"{'='*70}")

if listed_count == 2:
    print("\nTEBRIKLER! ILK 2 URUN EBAY'DE YAYINDA!")
    print("Yarin 4 urun daha ekle!")
