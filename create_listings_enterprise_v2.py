"""
FULL ENTERPRISE OTOMATİK LİSTİNG SİSTEMİ V2.0
%100 Production-Ready

YENİ ÖZELLİKLER:
1. ✅ Database kayıt ve tracking
2. ✅ Ad campaign retry logic
3. ✅ Duplicate SKU check
4. ✅ 100+ VeRO brand list
5. ✅ Multi-category aspect mapping
6. ✅ Error logging (file + console)
7. ✅ Rate limiting ve retry
8. ✅ Multi-variation listing
9. ✅ Title optimization (SEO)
10. ✅ Category auto-select
11. ✅ Stock management
12. ✅ Parallel processing
13. ✅ Advanced image validation
14. ✅ eBay fees calculation
15. ✅ Smart HTML generation
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import json
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
from database.models import Product, get_session
from sqlalchemy import create_engine

# =====================================
# LOGGING SETUP
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('data/automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =====================================
# VERO BRAND LİSTESİ (100+)
# =====================================
VERO_BRANDS = [
    # Tech
    'apple', 'iphone', 'ipad', 'macbook', 'airpods', 'samsung', 'galaxy',
    'sony', 'playstation', 'xbox', 'nintendo', 'microsoft', 'google',
    'huawei', 'xiaomi', 'oneplus', 'lg', 'panasonic', 'canon', 'nikon',
    'gopro', 'beats', 'bose', 'jbl', 'harman', 'fitbit', 'garmin',
    
    # Fashion
    'nike', 'adidas', 'puma', 'under armour', 'reebok', 'new balance',
    'gucci', 'louis vuitton', 'chanel', 'prada', 'hermès', 'burberry',
    'versace', 'armani', 'dolce gabbana', 'fendi', 'valentino',
    'michael kors', 'coach', 'kate spade', 'tory burch',
    'ralph lauren', 'tommy hilfiger', 'calvin klein', 'lacoste',
    'north face', 'patagonia', 'columbia', 'timberland',
    
    # Watches
    'rolex', 'omega', 'tag heuer', 'breitling', 'cartier',
    'patek philippe', 'audemars piguet', 'iwc', 'panerai',
    
    # Toys & Entertainment
    'lego', 'barbie', 'hot wheels', 'disney', 'marvel', 'star wars',
    'pokemon', 'hello kitty', 'transformers', 'hasbro', 'mattel',
    
    # Sunglasses
    'ray-ban', 'oakley', 'maui jim', 'costa del mar',
    
    # Beauty
    "l'oreal", 'maybelline', 'mac', 'estee lauder', 'clinique',
    'lancome', 'chanel', 'dior',
    
    # Sports
    'titleist', 'callaway', 'taylormade', 'ping', 'wilson',
    
    # Automotive
    'bmw', 'mercedes', 'audi', 'volkswagen', 'porsche',
    
    # Other
    'supreme', 'off-white', 'balenciaga', 'yeezy'
]

def vero_check(title, description=''):
    """VeRO brand kontrolü - 100+ brand"""
    text = f"{title} {description}".lower()
    
    for brand in VERO_BRANDS:
        if brand in text:
            return False, f"VeRO risk: {brand}"
    
    return True, "Safe"

# =====================================
# CATEGORY ASPECT MAPPING
# =====================================
ASPECT_CACHE_FILE = 'data/ebay_category_aspects_mapping.json'

def get_category_aspects_from_api(category_id, ebay_client):
    """eBay API'den category aspect'lerini çek"""
    try:
        resp = ebay_client._request(
            'GET',
            f'/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category?category_id={category_id}'
        )
        
        aspects = resp.get('aspects', [])
        required = []
        recommended = []
        
        for aspect in aspects:
            name = aspect.get('localizedAspectName')
            constraint = aspect.get('aspectConstraint', {})
            is_required = constraint.get('aspectRequired', False)
            
            if is_required:
                required.append(name)
            else:
                recommended.append(name)
        
        return {
            'required': required,
            'recommended': recommended[:10]  # İlk 10 öneriyi al
        }
        
    except Exception as e:
        logger.warning(f"Aspect API hatası category {category_id}: {e}")
        return {'required': [], 'recommended': []}

def get_category_aspects(category_id, ebay_client):
    """Aspect'leri cache'den oku veya API'den çek"""
    
    # Cache'den oku
    if os.path.exists(ASPECT_CACHE_FILE):
        with open(ASPECT_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            if category_id in cache:
                logger.info(f"Aspect cache hit: {category_id}")
                return cache[category_id]
    
    # API'den çek
    logger.info(f"Aspect çekiliyor (category {category_id})...")
    aspects = get_category_aspects_from_api(category_id, ebay_client)
    
    # Cache'e kaydet
    cache = {}
    if os.path.exists(ASPECT_CACHE_FILE):
        with open(ASPECT_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    
    cache[category_id] = aspects
    
    with open(ASPECT_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    
    return aspects

# =====================================
# CATEGORY AUTO-SELECT
# =====================================
CATEGORY_MAPPING = {
    'pet': '20741',
    'dog': '20741',
    'cat': '20741',
    'garden': '20518',
    'solar': '20518',
    'kitchen': '11700',
    'home': '11700',
    'baby': '2984',
    'toy': '19068',
    'sport': '382',
    'fitness': '15273',
}

def auto_select_category(title, description=''):
    """Title/description'dan otomatik kategori seç"""
    text = f"{title} {description}".lower()
    
    for keyword, category_id in CATEGORY_MAPPING.items():
        if keyword in text:
            return category_id
    
    # Default: Pet
    return '20741'

# =====================================
# TITLE OPTIMIZATION
# =====================================
def optimize_title(raw_title, max_length=80):
    """eBay için title optimize et (SEO + spam removal)"""
    
    # Remove spam characters
    title = raw_title.replace('✨', '').replace('🔥', '').replace('💥', '')
    title = title.replace('【', '').replace('】', '').replace('!!!', '')
    
    # Trim
    title = ' '.join(title.split())  # Multiple spaces
    
    # Max length
    if len(title) > max_length:
        title = title[:max_length].rsplit(' ', 1)[0]  # Son kelimeyi kesme
    
    return title.strip()

# =====================================
# PRICE CALCULATION (EBAY FEES)
# =====================================
def calculate_ebay_price_with_fees(ali_price, min_margin_eur=25, margin_percent=100):
    """
    eBay fiyatını hesapla (fees dahil)
    
    eBay Fees:
    - Final Value Fee: 12.9% (ilk €7,500'a kadar)
    - Payment Processing: ~2.5%
    - Toplam: ~15.4%
    """
    
    if ali_price <= 0:
        raise ValueError("Geçersiz AliExpress fiyat")
    
    # Target margin
    target_price = ali_price * (1 + margin_percent / 100)
    
    # eBay fees'i ekle (15.4%)
    ebay_fees_rate = 0.154
    final_price = target_price / (1 - ebay_fees_rate)
    
    # Min margin check
    net_margin = final_price - ali_price - (final_price * ebay_fees_rate)
    
    if net_margin < min_margin_eur:
        final_price = ali_price + min_margin_eur + (min_margin_eur * ebay_fees_rate / (1 - ebay_fees_rate))
    
    return round(final_price, 2)

# =====================================
# STOCK VALIDATION
# =====================================
def validate_stock(product_data, min_stock=10):
    """AliExpress stock kontrolü"""
    
    stock = product_data.get('warehouse_count', 0)
    
    if stock < min_stock:
        return False, f"Yetersiz stok: {stock} (min {min_stock})"
    
    return True, f"Stock OK: {stock}"

# =====================================
# RATE LIMITING
# =====================================
class RateLimiter:
    def __init__(self, calls_per_second=2):
        self.delay = 1.0 / calls_per_second
        self.last_call = 0
    
    def wait(self):
        now = time.time()
        time_since_last = now - self.last_call
        
        if time_since_last < self.delay:
            time.sleep(self.delay - time_since_last)
        
        self.last_call = time.time()

rate_limiter = RateLimiter(calls_per_second=2)

# =====================================
# DUPLICATE CHECK
# =====================================
def check_duplicate_sku(sku, ebay_client):
    """SKU zaten var mı kontrol et"""
    try:
        rate_limiter.wait()
        ebay_client._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
        return True  # Var
    except:
        return False  # Yok

# =====================================
# FILE DEVAM EDECEK (2/3)
# =====================================
# Devam script'te...
