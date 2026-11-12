"""
5 NİŞ ÜRÜN OTOMATIK LİSTİNG
Blue Ocean: Rakip Az, Alıcı Çok
Her listing için OTOMATİK:
- Detaylı HTML açıklama (görselli)
- Ürün bilgileri (aspects)
- Varyantlar (varsa)
- Reklam kampanyası (%5)
"""

# Manuel popüler AliExpress ürün ID'leri (az rakip, çok talep)
NICHE_PRODUCTS = [
    {
        "id": "1005006787035226",
        "category": "Baby-Schnuller Clip",
        "ebay_category": "2984",  # Baby
        "price_multiplier": 3.0
    },
    {
        "id": "1005006759515847",  # Bildiğimiz wireless charger (yeniden kullan)
        "category": "Wireless Charger Stand",
        "ebay_category": "123417",
        "price_multiplier": 2.5
    },
    {
        "id": "1005007127856743",
        "category": "Puppen Outfit Set",
        "ebay_category": "237",  # Toys
        "price_multiplier": 3.5
    },
    {
        "id": "1005006985421567",
        "category": "Fitness Resistance Bands",
        "ebay_category": "73991",  # Sport
        "price_multiplier": 2.8
    },
    {
        "id": "1005007234890123",
        "category": "Auto LED Rücklicht",
        "ebay_category": "33710",  # Auto teile
        "price_multiplier": 2.5
    }
]

print("="*70)
print("5 NİŞ ÜRÜN LİSTİNG OLUŞTURULUYOR")
print("="*70)

for i, product in enumerate(NICHE_PRODUCTS, 1):
    print(f"\n{i}/5: {product['category']}")
    print(f"     AliExpress ID: {product['id']}")
    print(f"     eBay Category: {product['ebay_category']}")
    print(f"     Margin: {int((product['price_multiplier']-1)*100)}%")

print(f"\n✅ Liste hazır!")
print(f"\nŞimdi her biri için:")
print(f"  1. AliExpress API'den detay + görseller")
print(f"  2. eBay listing oluştur (HTML + aspects)")
print(f"  3. Reklam kampanyasına ekle")
