"""
AKILLI KATEGORİ SEÇİCİ
======================
Ürün başlığından otomatik en uygun eBay kategorisini bulur
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class SmartCategorySelector:
    """Ürün başlığından otomatik kategori seçer"""
    
    def __init__(self):
        self.db_path = Path('data/ebay_categories.db')
        
        # Manuel öncelikli kategoriler (GERÇEK eBay ID'ler!)
        self.priority_keywords = {
            # PET KATEGORİLERİ
            'hund': '20742',          # Hunde (Ana kategori)
            'katze': '20741',         # Katzen > Spielzeug
            'katz': '20741',
            'haustier': '1281',       # Haustierbedarf
            'pet': '1281',
            'dog': '20742',
            'cat': '20741',
            
            # Spesifik pet ürünleri
            'spielzeug': '20741',     # Katzen Spielzeug (en çok kullanılan)
            'futter': '100421',       # Futter
            'napf': '33079',          # Näpfe
            'halsband': '63057',      # Halsbänder
            
            # TELEFON KATEGORİLERİ
            'iphone': '9355',         # Handys & Smartphones
            'handy': '9355',
            'smartphone': '9355',
            'phone': '9355',
            
            # Telefon aksesuarları
            'hülle': '182064',        # Handy-Hüllen & -Folien
            'case': '182064',
            'ladegerät': '20357',     # Akkus
            'kabel': '20357',
            'charger': '20357'
        }
    
    def select_category(self, product_title: str, category_hint: str = None) -> str:
        """
        Ürün başlığından en uygun kategoriyi seç
        
        Args:
            product_title: Ürün başlığı
            category_hint: Kategori ipucu ('PET', 'PHONE', vb)
        
        Returns:
            Category ID (string)
        """
        
        logger.info(f"🔍 Kategori seçiliyor: {product_title[:50]}")
        
        # 1. Manuel hint varsa öncelikli kullan
        if category_hint:
            hint_upper = category_hint.upper()
            if hint_upper == 'PET':
                logger.info(f"   💡 Hint: PET → 20741 (Katzen Spielzeug)")
                return '20741'
            elif hint_upper in ('PHONE', 'HANDY', 'IPHONE'):
                logger.info(f"   💡 Hint: PHONE → 9355 (Handys & Smartphones)")
                return '9355'
        
        # 2. Başlık bazlı öncelikli anahtar kelime kontrolü
        title_lower = product_title.lower()
        
        # Kelimeleri böl
        words = title_lower.split()
        
        # Her kelimeyi kontrol et
        for word in words:
            for keyword, cat_id in self.priority_keywords.items():
                if keyword in word:
                    cat_info = self.get_category_info(cat_id)
                    if cat_info:
                        logger.info(f"   ✅ Anahtar: '{keyword}' → {cat_id} ({cat_info['name']})")
                        return cat_id
        
        # 3. Veritabanında ara
        category_id = self._search_in_database(product_title)
        if category_id:
            return category_id
        
        # 4. Default: Haustierbedarf (Pet Supplies)
        logger.warning(f"   ⚠️ Kategori bulunamadı, default: 1281 (Haustierbedarf)")
        return '1281'
    
    def _search_in_database(self, product_title: str) -> Optional[str]:
        """Veritabanında kategori ara"""
        
        if not self.db_path.exists():
            logger.warning(f"   ⚠️ Kategori DB yok: {self.db_path}")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Başlıktaki kelimeleri çıkar
            words = [w.lower() for w in product_title.split() if len(w) > 3]
            
            if not words:
                return None
            
            # En uzun kelimeden başla
            words.sort(key=len, reverse=True)
            
            for word in words[:5]:  # İlk 5 kelime
                cursor.execute('''
                    SELECT category_id, name, full_path, is_leaf
                    FROM categories
                    WHERE keywords LIKE ?
                    AND is_leaf = 1
                    ORDER BY level DESC
                    LIMIT 3
                ''', (f'%{word}%',))
                
                results = cursor.fetchall()
                if results:
                    cat_id, name, path, is_leaf = results[0]
                    logger.info(f"   🔎 DB Arama: '{word}' → {cat_id} ({name})")
                    conn.close()
                    return cat_id
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"   ❌ DB arama hatası: {e}")
            return None
    
    def get_category_info(self, category_id: str) -> Optional[Dict]:
        """Kategori bilgilerini al"""
        
        if not self.db_path.exists():
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT category_id, name, full_path, is_leaf
                FROM categories
                WHERE category_id = ?
            ''', (category_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'name': result[1],
                    'path': result[2],
                    'is_leaf': bool(result[3])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Kategori bilgisi alma hatası: {e}")
            return None
    
    def search_categories(self, query: str, limit: int = 10) -> List[Dict]:
        """Kategori ara"""
        
        if not self.db_path.exists():
            logger.warning(f"⚠️ Database bulunamadı: {self.db_path}")
            return []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT category_id, name, full_path, is_leaf
                FROM categories
                WHERE keywords LIKE ?
                ORDER BY level DESC, is_leaf DESC
                LIMIT ?
            ''', (f'%{query.lower()}%', limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'name': row[1],
                    'path': row[2],
                    'is_leaf': bool(row[3])
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"❌ Arama hatası: {e}")
            return []


# Test
if __name__ == "__main__":
    selector = SmartCategorySelector()
    
    # Test ürünler
    test_products = [
        ("Wireless Charging Pad 15W Fast Charger for iPhone", "PHONE"),
        ("Premium Haustier Wasserspender Automatisch 2L Katze Hund", "PET"),
        ("iPhone 15 Pro Max Hülle Kamera Schutz", None),
        ("Intelligentes Hunde Spielzeug Ball LED Licht USB", None),
        ("Katzen Kratzbaum Sisalseil Spielzeug Set", None),
        ("Silikon Hülle iPhone 14 Pro Max", None),
        ("Haustier Hund Pinsel Fellpflege", None),
        ("Pop-Up Lustige Maus Käse Block Katze Spielzeug", None)
    ]
    
    print("=" * 70)
    print("🧪 AKILLI KATEGORİ SEÇİCİ TEST")
    print("=" * 70)
    print()
    
    for title, hint in test_products:
        print(f"📦 {title}")
        print(f"   Hint: {hint or 'Yok'}")
        
        cat_id = selector.select_category(title, hint)
        cat_info = selector.get_category_info(cat_id)
        
        if cat_info:
            print(f"   → ✅ Category: {cat_id} - {cat_info['name']}")
            print(f"   → Path: {cat_info['path'][:60]}")
        else:
            print(f"   → Category ID: {cat_id}")
        
        print()
    
    # Kategori arama testi
    print("=" * 70)
    print("🔍 KATEGORİ ARAMA TESTİ")
    print("=" * 70)
    print()
    
    search_queries = ['hund', 'katze', 'iphone', 'handy']
    
    for query in search_queries:
        print(f"🔎 Arama: '{query}'")
        results = selector.search_categories(query, limit=5)
        for r in results:
            leaf = "🍃" if r['is_leaf'] else "📁"
            print(f"   {leaf} [{r['id']:6}] {r['name']:30} | {r['path'][:40]}")
        print()
