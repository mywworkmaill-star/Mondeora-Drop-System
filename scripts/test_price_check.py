
"""Test rakip fiyat kontrolü"""
from check_product_price import check_competitor_prices

# Test ürünleri
tests = [
    ("Haustierbürste Katze Hund", 34.99),  # Çok yüksek
    ("Haustierbürste Katze Hund", 9.04),   # Rekabetçi
    ("Katzenspielzeug Katzenminze", 6.60), # Rekabetçi
]

for title, price in tests:
    print(f"\nTest: {title} @ {price} EUR")
    result = check_competitor_prices(title, price)
    print(f"  → {result.get('status')}: {result.get('recommendation')}")
    if result.get('suggested_price') != price:
        print(f"  → Öneri: {result.get('suggested_price')} EUR")
