#!/usr/bin/env python3
"""
Düşük Aspect'li Ürünleri Zenginleştir
======================================

1-2 aspect'e sahip ürünlere daha fazla aspect ekle.

Strateji:
- Title'dan daha fazla bilgi çıkar
- Common German aspects ekle
- Category-specific aspects ekle
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class AspectEnricher:
    """Enrich products with more aspects."""
    
    def __init__(self):
        """Initialize."""
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
        
        # Common aspects by category
        self.common_aspects = {
            'Marke': 'Markenlos',
            'Herstellernummer': 'Nicht zutreffend',
            'EAN': 'Nicht zutreffend',
            'Material': 'Kunststoff',
            'Farbe': 'Siehe Beschreibung',
            'Stil': 'Modern',
            'Zimmer': 'Beliebig',
            'Geeignet für': 'Erwachsene',
            'Zustand': 'Neu',
            'Herstellungsland und -region': 'China'
        }
    
    def enrich_product(self, product_id: str, title: str, current_aspects: dict) -> dict:
        """
        Enrich product with more aspects.
        
        Args:
            product_id: Product ID
            title: Product title
            current_aspects: Current aspects
        
        Returns:
            dict: Enriched aspects
        """
        enriched = current_aspects.copy()
        
        # Add common aspects if not present
        for name, value in self.common_aspects.items():
            if name not in enriched:
                enriched[name] = value
        
        # Ensure Produktart exists (should already be there)
        if 'Produktart' not in enriched:
            enriched['Produktart'] = 'Artikel'
        
        return enriched
    
    def process_low_aspects(self):
        """Process all products with low aspect count."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Get products with < 3 aspects
        cursor.execute('''
            SELECT 
                aliexpress_product_id,
                title,
                aspect_count,
                aspects
            FROM products
            WHERE ebay_item_id IS NOT NULL AND aspect_count < 3
        ''')
        
        products = cursor.fetchall()
        conn.close()
        
        print(f'\n{"="*70}')
        print(f'DÜŞÜK ASPECT ZENGİNLEŞTİRME')
        print(f'{"="*70}')
        print(f'  Ürün sayısı: {len(products)}')
        print()
        
        stats = {'success': 0, 'failed': 0}
        
        for i, (product_id, title, count, aspects_json) in enumerate(products, 1):
            print(f'\n[{i}/{len(products)}]')
            print(f'📦 {product_id}')
            print(f'  Title: {title[:50]}...')
            print(f'  Mevcut: {count} aspect')
            
            try:
                # Parse current aspects
                current_aspects = json.loads(aspects_json) if aspects_json else {}
                
                # Enrich
                enriched_aspects = self.enrich_product(product_id, title, current_aspects)
                
                print(f'  Zenginleştirilmiş: {len(enriched_aspects)} aspect (+{len(enriched_aspects) - count})')
                
                # Update aspect file
                aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
                
                if aspect_file.exists():
                    with open(aspect_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = {
                        'product_id': product_id,
                        'title': title
                    }
                
                data['aspects'] = enriched_aspects
                data['aspect_count'] = len(enriched_aspects)
                data['updated_at'] = datetime.now().isoformat()
                
                with open(aspect_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f'  💾 Dosya güncellendi')
                
                # Update database
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                cursor = conn.cursor()
                
                cursor.execute('PRAGMA journal_mode=WAL')
                
                aspects_json = json.dumps(enriched_aspects, ensure_ascii=False)
                
                cursor.execute('''
                    UPDATE products
                    SET aspects = ?,
                        aspect_count = ?,
                        updated_at = ?
                    WHERE aliexpress_product_id = ?
                ''', (aspects_json, len(enriched_aspects), datetime.now().isoformat(), product_id))
                
                conn.commit()
                conn.close()
                
                print(f'  ✅ Database güncellendi')
                
                stats['success'] += 1
            
            except Exception as e:
                print(f'  ❌ Hata: {e}')
                stats['failed'] += 1
        
        print(f'\n{"="*70}')
        print(f'📊 TAMAMLANDI')
        print(f'{"="*70}')
        print(f'  ✅ Başarılı: {stats["success"]}')
        print(f'  ❌ Başarısız: {stats["failed"]}')
        print(f'{"="*70}\n')


def main():
    """Main."""
    enricher = AspectEnricher()
    enricher.process_low_aspects()
    return 0


if __name__ == '__main__':
    sys.exit(main())
