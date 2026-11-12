"""
ALIEXPRESS API FIX - KEYWORD DIVERSITY IMPROVER
Farklı keyword'lerin farklı ürünler getirmesini sağlar
"""

import random

# AliExpress kategorileri
ALIEXPRESS_CATEGORIES = {
    'pet': 200003482,           # Pet Products
    'pet_grooming': 200214000,  # Pet Grooming
    'pet_toys': 200214001,      # Pet Toys
    'pet_feeding': 200214002,   # Pet Feeding
    'pet_beds': 200214003,      # Pet Beds & Mats
}

def get_diverse_search_params(keyword, attempt=1):
    """
    Keyword'e göre çeşitli search parametreleri döndür
    Her denemede farklı parametre kombinasyonu kullan
    
    Args:
        keyword: Arama kelimesi
        attempt: Kaçıncı deneme (1, 2, 3, ...)
    
    Returns:
        dict: search_product_page için parametreler
    """
    
    # Category ID'yi KULLANMA - schema hatası veriyor!
    # Sadece farklı sort ve page kullan
    
    # Farklı sort seçenekleri (attempt'e göre döngü)
    sort_options = [
        'orders,desc',      # En çok sipariş alan
        'min_price,asc',    # En ucuz
        'comments,desc',    # En çok yorum alan
        'orders,asc',       # En az sipariş alan (yeni ürünler)
    ]
    
    # Attempt'e göre farklı kombinasyonlar
    page_num = ((attempt - 1) % 3) + 1  # 1, 2, 3, 1, 2, 3...
    sort_by = sort_options[(attempt - 1) % len(sort_options)]
    
    params = {
        'keyword': keyword,
        'category_id': None,  # KULLANMA!
        'sort_by': sort_by,
        'page_num': page_num,
        'page_size': 50  # Daha fazla ürün çek
    }
    
    print(f"🔍 Search params for '{keyword}' (attempt {attempt}):")
    print(f"   Sort: {sort_by}")
    print(f"   Page: {page_num}")
    
    return params


def search_with_diversity(ali_client, keyword, target_count=10, max_attempts=3):
    """
    Çeşitli parametrelerle arama yap, yeterli ürün bulunana kadar
    
    Args:
        ali_client: AliExpressAPIClient instance
        keyword: Arama kelimesi
        target_count: Hedef ürün sayısı
        max_attempts: Maksimum deneme sayısı
    
    Returns:
        list: Bulunan ürünler (unique)
    """
    all_products = {}  # itemId -> product dict
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 Attempt {attempt}/{max_attempts} for '{keyword}'")
        
        try:
            params = get_diverse_search_params(keyword, attempt)
            
            result = ali_client.search_product_page(
                keyword=params['keyword'],
                category_id=params['category_id'],
                sort_by=params['sort_by'],
                page_num=params['page_num'],
                page_size=params['page_size']
            )
            
            products = result.get('products', [])
            print(f"   ✅ Found {len(products)} products")
            
            # Unique ürünleri ekle
            for p in products:
                item_id = p.get('itemId')
                if item_id and item_id not in all_products:
                    all_products[item_id] = p
            
            print(f"   📊 Total unique: {len(all_products)}")
            
            # Yeterli ürün bulunduysa dur
            if len(all_products) >= target_count:
                print(f"   ✅ Target reached: {len(all_products)} >= {target_count}")
                break
                
        except Exception as e:
            print(f"   ❌ Attempt {attempt} failed: {e}")
            continue
    
    products_list = list(all_products.values())
    print(f"\n🎯 Final: {len(products_list)} unique products found")
    
    return products_list


# Test fonksiyonu
if __name__ == '__main__':
    from src.api.aliexpress_client import AliExpressAPIClient
    from dotenv import load_dotenv
    
    load_dotenv()
    
    ali = AliExpressAPIClient()
    
    print("=" * 70)
    print("🧪 ALIEXPRESS DIVERSITY TEST")
    print("=" * 70)
    
    keywords = ['pet grooming', 'pet bed', 'pet bowl']
    
    for keyword in keywords:
        print(f"\n\n{'=' * 70}")
        print(f"Testing: {keyword}")
        print("=" * 70)
        
        products = search_with_diversity(ali, keyword, target_count=15, max_attempts=3)
        
        print(f"\n📦 Results for '{keyword}':")
        for i, p in enumerate(products[:5], 1):
            print(f"   {i}. {p.get('itemId')} - {p.get('title', '')[:50]}")
