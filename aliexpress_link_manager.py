"""
AliExpress Link Manager
Tüm AliExpress linklerini yönetir, yedekler ve doğrular
"""

import json
import sqlite3
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional

class AliExpressLinkManager:
    """AliExpress link yönetimi: backup, verification, recovery"""
    
    def __init__(self, db_path="data/dropshipping.db", backup_path="data/aliexpress_links_backup.json"):
        self.db_path = db_path
        self.backup_path = backup_path
        
    def get_all_links_from_db(self) -> List[Dict]:
        """Database'den tüm AliExpress linklerini çek"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                ebay_item_id,
                title,
                aliexpress_product_id,
                ebay_price,
                status,
                created_at
            FROM products
            WHERE aliexpress_product_id IS NOT NULL
            ORDER BY created_at DESC
        """)
        
        products = []
        for row in cursor.fetchall():
            id, ebay_id, title, ali_id, price, status, created = row
            
            products.append({
                'db_id': id,
                'ebay_item_id': ebay_id,
                'title': title,
                'aliexpress_product_id': ali_id,
                'aliexpress_link': f'https://www.aliexpress.com/item/{ali_id}.html',
                'ebay_link': f'https://www.ebay.de/itm/{ebay_id}',
                'ebay_price': price,
                'status': status,
                'created_at': created,
                'last_verified': None,
                'link_status': 'unknown'
            })
        
        conn.close()
        return products
    
    def verify_link(self, ali_product_id: str) -> Dict:
        """AliExpress linkini doğrula (404 kontrolü)"""
        # Try multiple domain formats
        urls_to_try = [
            f'https://www.aliexpress.com/item/{ali_product_id}.html',
            f'https://aliexpress.com/item/{ali_product_id}.html',
            f'https://www.aliexpress.us/item/{ali_product_id}.html'
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for url in urls_to_try:
            try:
                response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    return {
                        'status': 'valid',
                        'working_url': url,
                        'status_code': 200,
                        'verified_at': datetime.now().isoformat()
                    }
                elif response.status_code == 404:
                    continue  # Try next URL
                else:
                    # Might be CAPTCHA or other block
                    return {
                        'status': 'blocked',
                        'working_url': url,
                        'status_code': response.status_code,
                        'verified_at': datetime.now().isoformat()
                    }
            
            except requests.exceptions.RequestException as e:
                continue
        
        # All URLs failed
        return {
            'status': 'invalid',
            'working_url': None,
            'status_code': 404,
            'verified_at': datetime.now().isoformat()
        }
    
    def verify_all_links(self, products: List[Dict]) -> List[Dict]:
        """Tüm linkleri doğrula"""
        print("=" * 80)
        print("🔍 ALİEXPRESS LİNK DOĞRULAMA")
        print("=" * 80)
        print()
        
        verified_products = []
        
        for i, product in enumerate(products, 1):
            ali_id = product['aliexpress_product_id']
            title_short = product['title'][:40] if product['title'] else 'N/A'
            
            print(f"{i}/{len(products)} Kontrol: {title_short}...")
            print(f"   AliExpress ID: {ali_id}")
            
            verification = self.verify_link(ali_id)
            
            product['last_verified'] = verification['verified_at']
            product['link_status'] = verification['status']
            
            if verification['status'] == 'valid':
                product['working_url'] = verification['working_url']
                print(f"   ✅ ÇALIŞIYOR: {verification['working_url']}")
            elif verification['status'] == 'blocked':
                product['working_url'] = verification['working_url']
                print(f"   ⚠️  BLOCKED (CAPTCHA?): {verification['status_code']}")
            else:
                product['working_url'] = None
                print(f"   ❌ 404 NOT FOUND - Link çalışmıyor!")
            
            verified_products.append(product)
            
            # Rate limiting
            time.sleep(1)
            print()
        
        return verified_products
    
    def save_backup(self, products: List[Dict]):
        """Linkleri JSON backup dosyasına kaydet"""
        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'total_products': len(products),
            'products': products
        }
        
        with open(self.backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        
        print("=" * 80)
        print("💾 BACKUP KAYDEDILDI")
        print("=" * 80)
        print(f"📁 Dosya: {self.backup_path}")
        print(f"📊 Toplam: {len(products)} ürün")
        print(f"⏰ Tarih: {backup_data['backup_date']}")
        print()
    
    def load_backup(self) -> Optional[Dict]:
        """Backup dosyasından yükle"""
        try:
            with open(self.backup_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    def add_link_to_backup(self, ebay_item_id: str, ali_product_id: str, title: str, price: float):
        """Yeni bir link ekle (yeni ürün oluşturulduğunda)"""
        # Load existing backup
        backup = self.load_backup()
        
        if backup is None:
            backup = {
                'backup_date': datetime.now().isoformat(),
                'total_products': 0,
                'products': []
            }
        
        # Add new product
        new_product = {
            'ebay_item_id': ebay_item_id,
            'title': title,
            'aliexpress_product_id': ali_product_id,
            'aliexpress_link': f'https://www.aliexpress.com/item/{ali_product_id}.html',
            'ebay_link': f'https://www.ebay.de/itm/{ebay_item_id}',
            'ebay_price': price,
            'created_at': datetime.now().isoformat(),
            'last_verified': None,
            'link_status': 'unknown'
        }
        
        backup['products'].append(new_product)
        backup['total_products'] = len(backup['products'])
        backup['backup_date'] = datetime.now().isoformat()
        
        # Save
        with open(self.backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Backup'a eklendi: {title[:40]}... → {ali_product_id}")
    
    def restore_missing_links(self):
        """Database'de eksik linkleri backup'tan geri yükle"""
        backup = self.load_backup()
        
        if not backup:
            print("❌ Backup dosyası bulunamadı!")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        restored_count = 0
        
        for product in backup['products']:
            ebay_id = product['ebay_item_id']
            ali_id = product['aliexpress_product_id']
            
            # Check if link missing in DB
            cursor.execute("""
                SELECT aliexpress_product_id FROM products 
                WHERE ebay_item_id = ?
            """, (ebay_id,))
            
            result = cursor.fetchone()
            
            if result and result[0] is None:
                # Missing link - restore!
                cursor.execute("""
                    UPDATE products 
                    SET aliexpress_product_id = ?
                    WHERE ebay_item_id = ?
                """, (ali_id, ebay_id))
                
                restored_count += 1
                print(f"✅ Restored: {ebay_id} → {ali_id}")
        
        conn.commit()
        conn.close()
        
        print()
        print(f"📊 Toplam {restored_count} link geri yüklendi!")
    
    def generate_report(self, products: List[Dict]) -> Dict:
        """Özet rapor oluştur"""
        total = len(products)
        valid = sum(1 for p in products if p.get('link_status') == 'valid')
        invalid = sum(1 for p in products if p.get('link_status') == 'invalid')
        blocked = sum(1 for p in products if p.get('link_status') == 'blocked')
        unknown = sum(1 for p in products if p.get('link_status') == 'unknown')
        
        return {
            'total': total,
            'valid': valid,
            'invalid': invalid,
            'blocked': blocked,
            'unknown': unknown,
            'valid_percent': (valid / total * 100) if total > 0 else 0
        }


def main():
    """Ana script - tüm linkleri yedekle ve doğrula"""
    manager = AliExpressLinkManager()
    
    print("=" * 80)
    print("🔗 ALİEXPRESS LİNK YÖNETİM SİSTEMİ")
    print("=" * 80)
    print()
    
    # 1. Get all links from database
    print("📦 Database'den linkler çekiliyor...")
    products = manager.get_all_links_from_db()
    print(f"✅ {len(products)} ürün bulundu")
    print()
    
    # 2. Verify links (optional - can be slow)
    verify = input("🔍 Linkleri doğrulamak ister misin? (y/n): ").lower()
    
    if verify == 'y':
        products = manager.verify_all_links(products)
        
        # Show report
        report = manager.generate_report(products)
        print("=" * 80)
        print("📊 DOĞRULAMA RAPORU")
        print("=" * 80)
        print(f"✅ Çalışan linkler:  {report['valid']}/{report['total']} ({report['valid_percent']:.1f}%)")
        print(f"❌ Kırık linkler:    {report['invalid']}/{report['total']}")
        print(f"⚠️  Blocked linkler:  {report['blocked']}/{report['total']}")
        print(f"❓ Bilinmeyen:       {report['unknown']}/{report['total']}")
        print()
    
    # 3. Save backup
    manager.save_backup(products)
    
    print("=" * 80)
    print("✅ İŞLEM TAMAMLANDI!")
    print("=" * 80)
    print(f"📁 Backup: {manager.backup_path}")
    print(f"💾 {len(products)} ürün kaydedildi")
    print()
    print("💡 Bu backup dosyası:")
    print("   • Tüm AliExpress linklerini içerir")
    print("   • Database silinse bile linkleri korur")
    print("   • Gelecekte restore edilebilir")
    print()


if __name__ == '__main__':
    main()
