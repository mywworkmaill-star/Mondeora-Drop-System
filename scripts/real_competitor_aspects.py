#!/usr/bin/env python3
"""
eBay.de Gerçek Rakip Aspect Toplama
====================================

HER ÜRÜN İÇİN:
1. eBay.de'de arama yap (title keywords)
2. 10 rakip listing bul
3. Her rakibin TÜM Artikelmerkmale'lerini topla
4. AYRI dosyada sakla (product_id bazında)
5. BİRBİRİNE KARIŞTIRMA!

GERÇEK eBay DATA - UYDURMA DEĞİL
"""

import sys
import json
import sqlite3
import requests
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from collections import Counter
from urllib.parse import quote_plus

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.audit_logger import get_logger


class RealCompetitorAspectCollector:
    """Gerçek eBay.de rakiplerden aspect toplama."""
    
    def __init__(self):
        """Initialize."""
        self.logger = get_logger()
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
        self.aspects_dir.mkdir(parents=True, exist_ok=True)
        
        # Load eBay credentials
        from dotenv import dotenv_values
        env = dotenv_values(ROOT / '.env')
        self.app_id = env.get('EBAY_APP_ID')  # App ID for Finding API
    
    def search_competitors_finding_api(self, title: str, limit: int = 10) -> List[Dict]:
        """
        eBay Finding API ile rakip ara.
        
        Args:
            title: Ürün başlığı
            limit: Kaç rakip
        
        Returns:
            list: Rakip item'lar
        """
        competitors = []
        
        # Extract keywords from title
        keywords = self._extract_keywords(title)
        search_query = ' '.join(keywords[:5])  # Top 5 keyword
        
        print(f"  🔍 eBay.de aranıyor: {search_query}")
        
        try:
            # eBay Finding API endpoint
            url = 'https://svcs.ebay.com/services/search/FindingService/v1'
            
            params = {
                'OPERATION-NAME': 'findItemsAdvanced',
                'SERVICE-VERSION': '1.0.0',
                'SECURITY-APPNAME': self.app_id,
                'RESPONSE-DATA-FORMAT': 'JSON',
                'REST-PAYLOAD': '',
                'keywords': search_query,
                'paginationInput.entriesPerPage': limit,
                'itemFilter(0).name': 'ListingType',
                'itemFilter(0).value': 'FixedPrice',
                'itemFilter(1).name': 'Condition',
                'itemFilter(1).value': 'New',
                'sortOrder': 'BestMatch'
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response
                search_result = data.get('findItemsAdvancedResponse', [{}])[0]
                search_result = search_result.get('searchResult', [{}])[0]
                items = search_result.get('item', [])
                
                for item in items[:limit]:
                    item_id = item.get('itemId', [None])[0]
                    item_title = item.get('title', [None])[0]
                    
                    # Get price
                    price_info = item.get('sellingStatus', [{}])[0]
                    price_data = price_info.get('currentPrice', [{}])[0]
                    price = price_data.get('__value__')
                    
                    if item_id:
                        competitors.append({
                            'item_id': item_id,
                            'title': item_title,
                            'price': float(price) if price else None,
                            'currency': 'EUR'
                        })
                
                print(f"  ✅ {len(competitors)} rakip bulundu")
            else:
                print(f"  ❌ API error: {response.status_code}")
        
        except Exception as e:
            print(f"  ❌ Search error: {e}")
            self.logger.log_error(
                action='competitor_search_failed',
                error_message=str(e)
            )
        
        return competitors
    
    def get_item_aspects_shopping_api(self, item_id: str) -> Dict[str, str]:
        """
        eBay Shopping API ile item aspects al.
        
        Args:
            item_id: eBay item ID
        
        Returns:
            dict: Aspect name -> value
        """
        aspects = {}
        
        try:
            # eBay Shopping API
            url = 'https://open.api.ebay.com/shopping'
            
            params = {
                'callname': 'GetSingleItem',
                'responseencoding': 'JSON',
                'appid': self.app_id,
                'siteid': '77',  # Germany
                'version': '967',
                'ItemID': item_id,
                'IncludeSelector': 'ItemSpecifics'
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                item = data.get('Item', {})
                specifics = item.get('ItemSpecifics', {})
                name_value_list = specifics.get('NameValueList', [])
                
                # Extract aspects
                if isinstance(name_value_list, list):
                    for nv in name_value_list:
                        name = nv.get('Name')
                        values = nv.get('Value', [])
                        
                        if name and values:
                            # Take first value
                            value = values[0] if isinstance(values, list) else values
                            aspects[name] = value
                elif isinstance(name_value_list, dict):
                    # Single aspect
                    name = name_value_list.get('Name')
                    values = name_value_list.get('Value', [])
                    
                    if name and values:
                        value = values[0] if isinstance(values, list) else values
                        aspects[name] = value
        
        except Exception as e:
            self.logger.log_error(
                action='aspect_fetch_failed',
                error_message=str(e),
                ebay_item_id=item_id
            )
        
        return aspects
    
    def collect_for_product(self, product_id: str, title: str) -> Dict[str, Any]:
        """
        Bir ürün için rakiplerden aspect topla.
        
        Args:
            product_id: AliExpress product ID
            title: Ürün başlığı
        
        Returns:
            dict: Toplama sonucu
        """
        print(f"\n{'='*70}")
        print(f"📦 ÜRÜN: {product_id}")
        print(f"{'='*70}")
        print(f"  Title: {title[:60]}...")
        
        # 1. Rakipleri bul
        competitors = self.search_competitors_finding_api(title, limit=10)
        
        if not competitors:
            print(f"  ⚠️  Rakip bulunamadı!")
            return None
        
        # 2. Her rakipten aspect topla
        print(f"\n  📋 Aspect toplanıyor...")
        competitor_data = []
        all_aspects = {}  # aspect_name -> [values]
        
        for i, comp in enumerate(competitors, 1):
            item_id = comp['item_id']
            
            print(f"  [{i}/{len(competitors)}] {item_id}...", end='')
            
            aspects = self.get_item_aspects_shopping_api(item_id)
            
            if aspects:
                print(f" ✅ {len(aspects)} aspect")
                
                # Aggregate
                for name, value in aspects.items():
                    if name not in all_aspects:
                        all_aspects[name] = []
                    
                    if value not in all_aspects[name]:
                        all_aspects[name].append(value)
                
                competitor_data.append({
                    'item_id': item_id,
                    'title': comp['title'],
                    'price': comp['price'],
                    'aspects': aspects,
                    'aspect_count': len(aspects)
                })
            else:
                print(f" ⚠️  Aspect yok")
        
        # 3. Merge aspects (most common value)
        merged_aspects = {}
        for name, values in all_aspects.items():
            if values:
                # En yaygın değeri al
                most_common = Counter(values).most_common(1)[0][0]
                merged_aspects[name] = most_common
        
        print(f"\n  {'='*70}")
        print(f"  ✅ TAMAMLANDI")
        print(f"  Rakip sayısı: {len(competitor_data)}")
        print(f"  Toplam unique aspect: {len(all_aspects)}")
        print(f"  Merged aspect: {len(merged_aspects)}")
        print(f"  {'='*70}")
        
        return {
            'product_id': product_id,
            'title': title,
            'competitors': competitor_data,
            'all_aspects': all_aspects,
            'merged_aspects': merged_aspects,
            'aspect_count': len(merged_aspects),
            'timestamp': datetime.now().isoformat()
        }
    
    def save_product_aspects(self, data: Dict[str, Any]):
        """
        Ürüne özel aspect dosyasına kaydet.
        
        Args:
            data: Aspect data
        """
        product_id = data['product_id']
        
        # Her ürün için AYRI dosya
        aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
        
        with open(aspect_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n  💾 Kaydedildi: {aspect_file.name}")
        
        try:
            self.logger.log(
                action='product_aspects_saved',
                message=f'Product {product_id} aspects saved',
                category='aspect_collection',
                level='info',
                product_id=product_id,
                success=True,
                data={
                    'aspect_count': data['aspect_count'],
                    'competitors': len(data['competitors']),
                    'file': str(aspect_file)
                }
            )
        except:
            pass
    
    def apply_to_database(self, product_id: str, aspects: Dict[str, str]):
        """
        Database'e uygula.
        
        Args:
            product_id: Product ID
            aspects: Merged aspects
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('PRAGMA journal_mode=WAL')
        
        aspects_json = json.dumps(aspects, ensure_ascii=False)
        
        cursor.execute('''
            UPDATE products
            SET aspects = ?,
                aspect_count = ?,
                updated_at = ?
            WHERE aliexpress_product_id = ?
        ''', (aspects_json, len(aspects), datetime.now().isoformat(), product_id))
        
        conn.commit()
        conn.close()
        
        print(f"  ✅ Database güncellendi: {len(aspects)} aspect")
    
    def _extract_keywords(self, title: str) -> List[str]:
        """Title'dan keyword çıkar."""
        stopwords = {
            'und', 'der', 'die', 'das', 'für', 'mit', 'von', 'zu', 'auf',
            'den', 'dem', 'des', 'im', 'am', 'ist', 'ein', 'eine', 'einer',
            'stück', 'stücke', 'pack', 'set'
        }
        
        words = title.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return keywords


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gerçek Rakip Aspect Toplama')
    parser.add_argument('--product-id', help='Single product ID')
    parser.add_argument('--all', action='store_true', help='All products')
    parser.add_argument('--limit', type=int, help='Limit products')
    
    args = parser.parse_args()
    
    collector = RealCompetitorAspectCollector()
    
    if args.product_id:
        # Tek ürün
        conn = sqlite3.connect(collector.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title
            FROM products
            WHERE aliexpress_product_id = ?
        ''', (args.product_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print(f"❌ Ürün bulunamadı: {args.product_id}")
            return 1
        
        title = row[0]
        
        # Aspect topla
        result = collector.collect_for_product(args.product_id, title)
        
        if result:
            # AYRI dosyaya kaydet
            collector.save_product_aspects(result)
            
            # Database'e uygula
            collector.apply_to_database(args.product_id, result['merged_aspects'])
        
        return 0
    
    elif args.all:
        # Tüm ürünler
        conn = sqlite3.connect(collector.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT aliexpress_product_id, title, aspect_count
            FROM products
            WHERE ebay_item_id IS NOT NULL
            ORDER BY aspect_count ASC NULLS FIRST
            LIMIT ?
        ''', (args.limit or 100,))
        
        products = cursor.fetchall()
        conn.close()
        
        print(f"\n{'='*70}")
        print(f"GERÇEK RAKİP ASPECT TOPLAMA - BATCH")
        print(f"{'='*70}")
        print(f"  Ürün sayısı: {len(products)}")
        print()
        
        stats = {'success': 0, 'failed': 0, 'total_aspects': 0}
        
        for i, (product_id, title, current_count) in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}]")
            
            try:
                result = collector.collect_for_product(product_id, title)
                
                if result and result['aspect_count'] > 0:
                    # HER ÜRÜN AYRI DOSYA
                    collector.save_product_aspects(result)
                    
                    # Database'e uygula
                    collector.apply_to_database(product_id, result['merged_aspects'])
                    
                    stats['success'] += 1
                    stats['total_aspects'] += result['aspect_count']
                else:
                    stats['failed'] += 1
            
            except Exception as e:
                print(f"  ❌ Hata: {e}")
                stats['failed'] += 1
        
        print(f"\n{'='*70}")
        print(f"📊 BATCH TAMAMLANDI")
        print(f"{'='*70}")
        print(f"  ✅ Başarılı: {stats['success']}")
        print(f"  ❌ Başarısız: {stats['failed']}")
        print(f"  📈 Toplam aspect: {stats['total_aspects']}")
        print(f"  📁 Dosya sayısı: {stats['success']} (her ürün ayrı)")
        print(f"{'='*70}\n")
        
        return 0
    
    else:
        print("Kullanım:")
        print("  python scripts/real_competitor_aspects.py --product-id 1005009030953454")
        print("  python scripts/real_competitor_aspects.py --all --limit 10")
        return 1


if __name__ == '__main__':
    sys.exit(main())
