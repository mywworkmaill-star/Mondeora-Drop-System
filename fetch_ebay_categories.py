"""
eBay GERÇEK KATEGORİ ÇEKİCİ
===========================
eBay Taxonomy API'den tüm kategorileri çeker ve kaydeder
"""

import json
import sqlite3
import logging
from pathlib import Path
from dotenv import load_dotenv
import sys
import requests
import os

sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class eBayCategoryFetcher:
    """eBay kategori ağacını çeker ve kaydeder"""
    
    def __init__(self):
        self.categories = []
        self.db_path = Path('data/ebay_categories.db')
        self.json_path = Path('data/ebay_categories.json')
        self.access_token = None
        
    def get_access_token(self):
        """eBay OAuth token al"""
        logger.info("🔑 eBay access token alınıyor...")
        
        # .env'den credentials
        client_id = os.getenv('EBAY_APP_ID')
        client_secret = os.getenv('EBAY_CERT_ID')
        
        if not client_id or not client_secret:
            logger.error("❌ EBAY_APP_ID veya EBAY_CERT_ID bulunamadı!")
            return False
        
        # OAuth endpoint
        url = 'https://api.ebay.com/identity/v1/oauth2/token'
        
        # Basic Auth
        import base64
        auth_str = f"{client_id}:{client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        }
        
        data = {
            'grant_type': 'client_credentials',
            'scope': 'https://api.ebay.com/oauth/api_scope'
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                logger.info("✅ Access token alındı")
                return True
            else:
                logger.error(f"❌ Token alınamadı: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Token alma hatası: {e}")
            return False
        
    def fetch_categories(self):
        """eBay Taxonomy API'den kategorileri çek"""
        logger.info("=" * 70)
        logger.info("🔍 eBay KATEGORİLERİ ÇEKİLİYOR")
        logger.info("=" * 70)
        logger.info("")
        
        # Önce token al
        if not self.get_access_token():
            return False
        
        # eBay Germany category tree ID: 77
        category_tree_id = '77'
        
        try:
            # Taxonomy API - tüm kategorileri al
            logger.info(f"📡 eBay Taxonomy API çağrılıyor (Tree ID: {category_tree_id})...")
            
            url = f'https://api.ebay.com/commerce/taxonomy/v1/category_tree/{category_tree_id}'
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ API hatası: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text[:200]}")
                return False
            
            data = response.json()
            logger.info(f"✅ API yanıt aldı")
            logger.info("")
            
            # Root kategorilerden başla
            root_category = data.get('rootCategoryNode', {})
            
            if not root_category:
                logger.error("❌ Root category bulunamadı!")
                return False
            
            # Tüm kategorileri düzleştir
            self._flatten_categories(root_category, parent_path="")
            
            logger.info(f"✅ Toplam {len(self.categories)} kategori bulundu!")
            logger.info("")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Hata: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _flatten_categories(self, node, parent_path="", level=0):
        """Kategori ağacını düzleştir (recursive)"""
        
        category = node.get('category', {})
        category_id = category.get('categoryId')
        category_name = category.get('categoryName', 'Unknown')
        
        if category_id:
            # Tam yol oluştur
            full_path = f"{parent_path} > {category_name}" if parent_path else category_name
            
            # Listeye ekle
            self.categories.append({
                'id': str(category_id),
                'name': category_name,
                'path': full_path,
                'level': level,
                'leaf': node.get('leafCategoryTreeNode', False)
            })
            
            # Alt kategoriler varsa recursive çağır
            child_nodes = node.get('childCategoryTreeNodes', [])
            for child in child_nodes:
                self._flatten_categories(child, full_path, level + 1)
    
    def save_to_database(self):
        """Kategorileri SQLite veritabanına kaydet"""
        logger.info("💾 Kategoriler veritabanına kaydediliyor...")
        
        # Data klasörü yoksa oluştur
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Database oluştur
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Eski tabloyu sil
        cursor.execute('DROP TABLE IF EXISTS categories')
        
        # Tablo oluştur
        cursor.execute('''
            CREATE TABLE categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                full_path TEXT NOT NULL,
                level INTEGER,
                is_leaf BOOLEAN,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index oluştur
        cursor.execute('CREATE INDEX idx_name ON categories(name)')
        cursor.execute('CREATE INDEX idx_keywords ON categories(keywords)')
        cursor.execute('CREATE INDEX idx_leaf ON categories(is_leaf)')
        
        # Kategorileri ekle
        for cat in self.categories:
            # Anahtar kelimeler oluştur (path'deki tüm kelimeler)
            keywords = ' '.join(cat['path'].lower().split(' > '))
            
            cursor.execute('''
                INSERT INTO categories 
                (category_id, name, full_path, level, is_leaf, keywords)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                cat['id'],
                cat['name'],
                cat['path'],
                cat['level'],
                1 if cat['leaf'] else 0,
                keywords
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ {len(self.categories)} kategori veritabanına kaydedildi")
        logger.info(f"📂 Dosya: {self.db_path}")
        logger.info("")
    
    def save_to_json(self):
        """Kategorileri JSON dosyasına kaydet"""
        logger.info("📄 Kategoriler JSON'a kaydediliyor...")
        
        self.json_path.write_text(
            json.dumps(self.categories, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        logger.info(f"✅ JSON kaydedildi: {self.json_path}")
        logger.info("")
    
    def show_stats(self):
        """İstatistikleri göster"""
        logger.info("=" * 70)
        logger.info("📊 KATEGORİ İSTATİSTİKLERİ")
        logger.info("=" * 70)
        logger.info("")
        
        # Seviyeye göre dağılım
        from collections import Counter
        level_counts = Counter(cat['level'] for cat in self.categories)
        
        logger.info("📊 Seviye Dağılımı:")
        for level in sorted(level_counts.keys()):
            logger.info(f"   Level {level}: {level_counts[level]} kategori")
        logger.info("")
        
        # Leaf kategoriler
        leaf_count = sum(1 for cat in self.categories if cat['leaf'])
        logger.info(f"🍃 Leaf Kategoriler: {leaf_count}")
        logger.info(f"📁 Parent Kategoriler: {len(self.categories) - leaf_count}")
        logger.info("")
        
        # Örnek kategoriler
        logger.info("📋 Örnek Kategoriler (İlk 15):")
        for cat in self.categories[:15]:
            leaf_icon = "🍃" if cat['leaf'] else "📁"
            logger.info(f"   {leaf_icon} [{cat['id']:6}] {cat['path'][:55]}")
        logger.info("")
        
        # Pet kategorileri
        pet_cats = [cat for cat in self.categories 
                   if 'pet' in cat['name'].lower() or 'tier' in cat['name'].lower() 
                   or 'hund' in cat['name'].lower() or 'katz' in cat['name'].lower()]
        logger.info(f"🐾 Pet/Tier Kategorileri: {len(pet_cats)}")
        for cat in pet_cats[:10]:
            leaf_icon = "🍃" if cat['leaf'] else "📁"
            logger.info(f"   {leaf_icon} [{cat['id']:6}] {cat['name']}")
        logger.info("")
        
        # Phone kategorileri
        phone_cats = [cat for cat in self.categories 
                     if 'phone' in cat['name'].lower() or 'handy' in cat['name'].lower()
                     or 'iphone' in cat['name'].lower()]
        logger.info(f"📱 Phone/Handy Kategorileri: {len(phone_cats)}")
        for cat in phone_cats[:10]:
            leaf_icon = "🍃" if cat['leaf'] else "📁"
            logger.info(f"   {leaf_icon} [{cat['id']:6}] {cat['name']}")
        logger.info("")


def main():
    fetcher = eBayCategoryFetcher()
    
    # 1. Kategorileri çek
    if not fetcher.fetch_categories():
        logger.error("=" * 70)
        logger.error("❌ KATEGORİLER ÇEKİLEMEDİ!")
        logger.error("=" * 70)
        return
    
    # 2. Veritabanına kaydet
    fetcher.save_to_database()
    
    # 3. JSON'a kaydet
    fetcher.save_to_json()
    
    # 4. İstatistikleri göster
    fetcher.show_stats()
    
    logger.info("=" * 70)
    logger.info("✅ İŞLEM TAMAMLANDI!")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📂 Dosyalar:")
    logger.info(f"   Database: {fetcher.db_path}")
    logger.info(f"   JSON: {fetcher.json_path}")
    logger.info("")


if __name__ == "__main__":
    main()
