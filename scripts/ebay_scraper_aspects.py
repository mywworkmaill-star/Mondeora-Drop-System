#!/usr/bin/env python3
"""
eBay.de Web Scraping - Gerçek Rakip Aspects
============================================

HER ÜRÜN İÇİN:
1. eBay.de'de search (HTML scraping)
2. 10 rakip listing bul
3. Her rakip sayfasını scrape et
4. TÜM Artikelmerkmale'leri topla
5. AYRI dosyada sakla (product_id bazında)

GERÇEK eBay.de DATA - HER ÜRÜN AYRI!
"""

import sys
import json
import time
import sqlite3
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.audit_logger import get_logger


class EbayDeScraper:
    """eBay.de web scraper for competitor aspects."""
    
    def __init__(self):
        """Initialize scraper."""
        self.logger = get_logger()
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
        self.aspects_dir.mkdir(parents=True, exist_ok=True)
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.ua_index = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with rotating user agent."""
        self.ua_index = (self.ua_index + 1) % len(self.user_agents)
        
        return {
            'User-Agent': self.user_agents[self.ua_index],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def search_ebay_de(self, keywords: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search eBay.de and scrape competitor listings.
        
        Args:
            keywords: Search keywords
            limit: Max results
        
        Returns:
            list: Competitor items with item_id, title, price
        """
        competitors = []
        
        print(f"  🔍 eBay.de aranıyor: {keywords}")
        
        try:
            # eBay.de search URL
            url = f'https://www.ebay.de/sch/i.html?_nkw={quote_plus(keywords)}&_ipg=50&_sop=12'
            
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find listing items
                items = soup.find_all('li', class_='s-item')
                
                if not items:
                    # Try alternative class
                    items = soup.find_all('div', class_='s-item__wrapper')
                
                for item in items[:limit]:
                    try:
                        # Get item ID from data attribute or link
                        item_id = None
                        
                        # Try data-listingid
                        if item.has_attr('data-listingid'):
                            item_id = item['data-listingid']
                        
                        # Try from link
                        if not item_id:
                            link = item.find('a', class_='s-item__link')
                            if link and link.has_attr('href'):
                                href = link['href']
                                # Extract ID from URL: /itm/123456789
                                if '/itm/' in href:
                                    parts = href.split('/itm/')
                                    if len(parts) > 1:
                                        item_id = parts[1].split('?')[0].split('/')[0]
                        
                        if not item_id:
                            continue
                        
                        # Get title
                        title_elem = item.find('div', class_='s-item__title')
                        if not title_elem:
                            title_elem = item.find('h3', class_='s-item__title')
                        
                        title = title_elem.get_text(strip=True) if title_elem else None
                        
                        # Skip "Shop on eBay" entries
                        if title and 'Shop on eBay' in title:
                            continue
                        
                        # Get price
                        price_elem = item.find('span', class_='s-item__price')
                        price_text = price_elem.get_text(strip=True) if price_elem else None
                        
                        price = None
                        if price_text:
                            # Parse price: "EUR 12,99" or "12,99 EUR"
                            import re
                            match = re.search(r'(\d+[\.,]\d+)', price_text)
                            if match:
                                price_str = match.group(1).replace(',', '.')
                                try:
                                    price = float(price_str)
                                except:
                                    pass
                        
                        if item_id and title:
                            competitors.append({
                                'item_id': item_id,
                                'title': title,
                                'price': price,
                                'currency': 'EUR'
                            })
                    
                    except Exception as e:
                        continue
                
                print(f"  ✅ {len(competitors)} rakip bulundu")
            
            else:
                print(f"  ⚠️  HTTP {response.status_code}")
        
        except Exception as e:
            print(f"  ❌ Search error: {e}")
            self.logger.log_error(
                action='ebay_search_scrape_failed',
                error_message=str(e)
            )
        
        return competitors
    
    def scrape_item_aspects(self, item_id: str) -> Dict[str, str]:
        """
        Scrape Artikelmerkmale from eBay.de item page.
        
        Args:
            item_id: eBay item ID
        
        Returns:
            dict: Aspect name -> value
        """
        aspects = {}
        
        try:
            # eBay.de item URL
            url = f'https://www.ebay.de/itm/{item_id}'
            
            # Rate limiting
            time.sleep(1.5)  # 1.5s between requests
            
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Method 1: Find "Artikelmerkmale" section
                # Look for section with "Artikelmerkmale" or "Item specifics"
                
                # Try different selectors
                selectors = [
                    {'class': 'ux-layout-section-evo__item'},
                    {'class': 'ux-labels-values'},
                    {'class': 'itemAttr'},
                    {'id': 'viTabs_0_panel'}
                ]
                
                for selector in selectors:
                    sections = soup.find_all('div', selector)
                    
                    for section in sections:
                        # Look for dl (definition list) with dt/dd pairs
                        dls = section.find_all('dl')
                        
                        for dl in dls:
                            dts = dl.find_all('dt')
                            dds = dl.find_all('dd')
                            
                            # Match dt with dd
                            for dt, dd in zip(dts, dds):
                                name = dt.get_text(strip=True)
                                value = dd.get_text(strip=True)
                                
                                if name and value and name != value:
                                    aspects[name] = value
                
                # Method 2: Look for specific "Artikelmerkmale" table
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        
                        if len(cells) >= 2:
                            name = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            
                            # Filter out headers
                            if name and value and name != 'Artikelmerkmale' and name != value:
                                aspects[name] = value
                
                # Method 3: Look for ux-labels-values pairs
                label_value_pairs = soup.find_all('div', class_='ux-labels-values__values')
                
                for pair_container in label_value_pairs:
                    # Find parent to get label
                    parent = pair_container.find_parent('div', class_='ux-labels-values')
                    
                    if parent:
                        label = parent.find('div', class_='ux-labels-values__labels')
                        
                        if label:
                            name = label.get_text(strip=True)
                            value = pair_container.get_text(strip=True)
                            
                            if name and value:
                                aspects[name] = value
            
            else:
                print(f"    ⚠️  HTTP {response.status_code}")
        
        except Exception as e:
            self.logger.log_error(
                action='item_scrape_failed',
                error_message=str(e),
                ebay_item_id=item_id
            )
        
        return aspects
    
    def collect_for_product(self, product_id: str, title: str) -> Optional[Dict[str, Any]]:
        """
        Collect aspects for one product.
        
        Args:
            product_id: Product ID
            title: Product title
        
        Returns:
            dict: Collection result
        """
        print(f"\n{'='*70}")
        print(f"📦 ÜRÜN: {product_id}")
        print(f"{'='*70}")
        print(f"  Title: {title[:60]}...")
        
        # 1. Extract keywords
        keywords = self._extract_keywords(title)
        search_query = ' '.join(keywords[:5])  # Top 5 keywords
        
        # 2. Search eBay.de
        competitors = self.search_ebay_de(search_query, limit=10)
        
        if not competitors:
            print(f"  ⚠️  Rakip bulunamadı!")
            return None
        
        # 3. Scrape aspects from each competitor
        print(f"\n  📋 Aspects toplanıyor...")
        competitor_data = []
        all_aspects = {}  # aspect_name -> [values]
        
        for i, comp in enumerate(competitors, 1):
            item_id = comp['item_id']
            
            print(f"  [{i}/{len(competitors)}] {item_id}...", end='', flush=True)
            
            aspects = self.scrape_item_aspects(item_id)
            
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
        
        # 4. Merge aspects
        merged_aspects = {}
        for name, values in all_aspects.items():
            if values:
                # Most common value
                most_common = Counter(values).most_common(1)[0][0]
                merged_aspects[name] = most_common
        
        print(f"\n  {'='*70}")
        print(f"  ✅ TAMAMLANDI")
        print(f"  Rakip sayısı: {len(competitor_data)}")
        print(f"  Toplam unique aspect: {len(all_aspects)}")
        print(f"  Merged aspect: {len(merged_aspects)}")
        
        # Show top 10 aspects
        if merged_aspects:
            print(f"\n  📋 Toplanan Aspects (ilk 10):")
            for i, (name, value) in enumerate(list(merged_aspects.items())[:10], 1):
                print(f"    {i}. {name}: {value}")
        
        print(f"  {'='*70}")
        
        return {
            'product_id': product_id,
            'title': title,
            'search_query': search_query,
            'competitors': competitor_data,
            'all_aspects': all_aspects,
            'merged_aspects': merged_aspects,
            'aspect_count': len(merged_aspects),
            'timestamp': datetime.now().isoformat()
        }
    
    def save_product_aspects(self, data: Dict[str, Any]):
        """Save to product-specific file."""
        product_id = data['product_id']
        
        # AYRI dosya - her ürün kendi
        aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
        
        with open(aspect_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n  💾 Kaydedildi: {aspect_file.name}")
        
        try:
            self.logger.log(
                action='product_aspects_scraped',
                message=f'Scraped aspects for {product_id}',
                category='aspect_scraping',
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
        """Apply to database."""
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
        """Extract keywords from title."""
        stopwords = {
            'und', 'der', 'die', 'das', 'für', 'mit', 'von', 'zu', 'auf',
            'den', 'dem', 'des', 'im', 'am', 'ist', 'ein', 'eine', 'einer',
            'stück', 'stücke', 'pack', 'set', 'pcs', 'pc'
        }
        
        words = title.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        return keywords


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description='eBay.de Web Scraping - Rakip Aspects')
    parser.add_argument('--product-id', help='Single product ID')
    parser.add_argument('--all', action='store_true', help='All products')
    parser.add_argument('--limit', type=int, help='Limit products')
    
    args = parser.parse_args()
    
    scraper = EbayDeScraper()
    
    if args.product_id:
        # Tek ürün
        conn = sqlite3.connect(scraper.db_path, timeout=30.0)
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
        
        # Scrape
        result = scraper.collect_for_product(args.product_id, title)
        
        if result:
            # AYRI dosyaya kaydet
            scraper.save_product_aspects(result)
            
            # Database'e uygula
            scraper.apply_to_database(args.product_id, result['merged_aspects'])
        
        return 0
    
    elif args.all:
        # Batch
        conn = sqlite3.connect(scraper.db_path, timeout=30.0)
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
        print(f"EBAY.DE WEB SCRAPING - BATCH")
        print(f"{'='*70}")
        print(f"  Ürün sayısı: {len(products)}")
        print(f"  Rate limit: 1.5s per item")
        print(f"  Tahmini süre: {len(products) * 10 / 60:.1f} dakika")
        print()
        
        stats = {'success': 0, 'failed': 0, 'total_aspects': 0}
        
        for i, (product_id, title, current_count) in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}]")
            
            try:
                result = scraper.collect_for_product(product_id, title)
                
                if result and result['aspect_count'] > 0:
                    # AYRI dosya
                    scraper.save_product_aspects(result)
                    
                    # Database
                    scraper.apply_to_database(product_id, result['merged_aspects'])
                    
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
        print(f"  📁 Dosya: {stats['success']} (her ürün ayrı)")
        print(f"{'='*70}\n")
        
        return 0
    
    else:
        print("Kullanım:")
        print("  python scripts/ebay_scraper_aspects.py --product-id 1005009030953454")
        print("  python scripts/ebay_scraper_aspects.py --all --limit 5")
        return 1


if __name__ == '__main__':
    sys.exit(main())
