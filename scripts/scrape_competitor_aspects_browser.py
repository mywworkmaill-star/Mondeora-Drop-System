#!/usr/bin/env python3
"""
BROWSER-BASED COMPETITOR ASPECT SCRAPER
Her ürün için eBay.de'de rakip ara ve aspects çek
"""

import sys
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.insert(0, 'src')


class BrowserCompetitorScraper:
    """
    Browser automation ile eBay.de rakiplerinden aspect scraping
    """
    
    def __init__(self):
        self.db_path = 'data/dropshipping.db'
        self.output_dir = Path('data/product_aspects')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_keyword_from_title(self, title: str, max_words: int = 2) -> str:
        """
        Title'dan arama keyword'ü çıkar
        
        Örnek:
            "Robuste, extra große, faltbare Aufbewahrungstasche mit Reißverschluss"
            → "aufbewahrungstasche reißverschluss"
        
        Args:
            title: Product title
            max_words: Max keyword count (default 2)
        
        Returns:
            str: Search keyword
        """
        # Lowercase
        title = title.lower()
        
        # Remove noise
        noise_words = [
            'premium', 'hochwertig', 'neu', 'extra', 'robuste', 'große',
            'multifunktion', 'praktisch', 'ideal', 'perfekt', 'für',
            'mit', 'und', 'oder', 'aus', 'zum', 'zur', 'im', 'am'
        ]
        
        # Split into words
        words = re.findall(r'\b\w+\b', title)
        
        # Filter
        keywords = []
        for word in words:
            if len(word) <= 3:  # Too short
                continue
            if word in noise_words:
                continue
            if word.isdigit():  # Numbers
                continue
            
            keywords.append(word)
        
        # Take last N words (product type usually at end)
        keywords = keywords[-max_words:]
        
        return ' '.join(keywords)
    
    def scrape_competitors_via_browser(self, keyword: str, limit: int = 5) -> list:
        """
        Browser ile eBay.de'de arama yap ve rakip Item ID'leri al
        
        HERMES browser_exec kullanacak
        
        Args:
            keyword: Search keyword
            limit: Max competitors
        
        Returns:
            list: [{'item_id': '...', 'title': '...', 'price': '...'}, ...]
        """
        # Bu fonksiyon Hermes browser_exec tool ile çağrılacak
        # Şimdilik placeholder
        return []
    
    def extract_aspects_from_ebay_page(self, item_id: str) -> dict:
        """
        eBay listing sayfasından aspects çıkar (browser)
        
        Args:
            item_id: eBay item ID
        
        Returns:
            dict: {aspect_name: aspect_value}
        """
        # Bu da browser_exec ile çalışacak
        # Placeholder
        return {}
    
    def merge_competitor_aspects(self, competitors_aspects: list, threshold: float = 0.5) -> dict:
        """
        Birden fazla rakipten aspects'leri merge et
        
        Args:
            competitors_aspects: [{aspect_name: value}, ...]
            threshold: Minimum percentage to include (0.5 = 50%)
        
        Returns:
            dict: Merged aspects
        """
        all_aspects = {}
        
        for aspects in competitors_aspects:
            for name, value in aspects.items():
                if name not in all_aspects:
                    all_aspects[name] = []
                all_aspects[name].append(value)
        
        # Merge: use most common value if 50%+ agreement
        merged = {}
        total_competitors = len(competitors_aspects)
        
        for name, values in all_aspects.items():
            value_counts = Counter(values)
            most_common_value, count = value_counts.most_common(1)[0]
            
            percentage = count / total_competitors
            
            if percentage >= threshold:
                merged[name] = most_common_value
        
        return merged
    
    def save_product_aspects(self, product_id: int, aspects: dict, metadata: dict = None):
        """
        Ürüne özel aspects'i kaydet
        
        Args:
            product_id: Database product ID
            aspects: {aspect_name: value}
            metadata: Extra info (keyword, competitor_count, etc.)
        """
        output_file = self.output_dir / f'product_{product_id}_aspects.json'
        
        data = {
            'product_id': product_id,
            'aspects': aspects,
            'aspect_count': len(aspects),
            'metadata': metadata or {},
            'timestamp': datetime.now().isoformat(),
            'source': 'competitor_scraping_browser'
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f'💾 Saved: {output_file}')
        return output_file
    
    def process_product(self, product_id: int):
        """
        Bir ürün için tam workflow
        
        1. Title'dan keyword çıkar
        2. eBay.de'de ara (browser)
        3. Top 5 rakip bul
        4. Her rakipten aspects çek
        5. Merge et
        6. Kaydet
        """
        # Get product
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT title, ebay_price FROM products WHERE id = ?', (product_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f'❌ Product {product_id} not found')
            return None
        
        title, price = result
        
        print(f'\n📦 Product ID {product_id}')
        print(f'   Title: {title[:60]}')
        
        # Extract keyword
        keyword = self.extract_keyword_from_title(title)
        print(f'   Keyword: "{keyword}"')
        
        # NOTE: Browser scraping kısmı ayrı implement edilecek
        # Şimdilik keyword extraction ve save structure'ı hazır
        
        return keyword


def main():
    """Test run"""
    scraper = BrowserCompetitorScraper()
    
    print('🔍 BROWSER COMPETITOR ASPECT SCRAPER')
    print('=' * 70)
    
    # Test: ID 23 için keyword extraction
    keyword_23 = scraper.process_product(23)
    
    # Test: ID 44 için keyword extraction
    keyword_44 = scraper.process_product(44)
    
    print(f'\n✅ Keywords extracted!')
    print(f'\nℹ️  Next step: Browser scraping implementation')
    print(f'   Will use: mcp__browser_exec tool')
    print(f'   Search: eBay.de sold listings')
    print(f'   Extract: Item specifics from each competitor')


if __name__ == '__main__':
    main()
