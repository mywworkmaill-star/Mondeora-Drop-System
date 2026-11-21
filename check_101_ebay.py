"""
Check if ID 101 listing exists on eBay and needs height correction
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.ebay_client import eBayAPIClient
import json

ebay = eBayAPIClient()

# User mentioned this eBay ID: 860160910067
ebay_item_id = '860160910067'

print(f"Checking eBay listing: {ebay_item_id}")
print("=" * 60)

try:
    # Try to get inventory item by SKU
    # ID 101 -> AliExpress ID 1005009723070135
    sku = 'ALI-1005009723070135'
    
    print(f"\nChecking SKU: {sku}")
    
    response = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
    
    print("\n✅ INVENTORY ITEM FOUND!")
    print(f"Title: {response.get('product', {}).get('title', 'N/A')[:60]}...")
    
    # Check current aspects
    aspects = response.get('product', {}).get('aspects', {})
    
    print(f"\nCURRENT DIMENSIONS in eBay:")
    print(f"  Länge: {aspects.get('Länge', ['Not set'])}")
    print(f"  Breite: {aspects.get('Breite', ['Not set'])}")
    print(f"  Höhe: {aspects.get('Höhe', ['Not set'])}")
    
    hohe = aspects.get('Höhe', [''])[0] if aspects.get('Höhe') else ''
    
    if '13' in hohe:
        print(f"\n❌ HATA BULUNDU: Höhe = {hohe}")
        print(f"   Doğru olmalı: 3 cm")
        print("\n🔧 eBay listing'i güncellenmeli!")
    elif '3' in hohe:
        print(f"\n✅ Doğru: Höhe = {hohe}")
    else:
        print(f"\n⚠️  Höhe bilgisi eksik: {hohe}")
        
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print(f"\nInventory item bulunamadı veya başka hata.")
    
print("\n" + "=" * 60)
print(f"eBay Link: https://www.ebay.de/itm/{ebay_item_id}")
