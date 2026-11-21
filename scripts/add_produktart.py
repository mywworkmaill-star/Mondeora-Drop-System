#!/usr/bin/env python3
"""
Produktart Aspect Enrichment
=============================

HTTP 400 hatası alan ürünlere "Produktart" aspect'i ekle.

Strateji:
1. Title'dan product type çıkar
2. Genel kategoriler kullan (Spielzeug, Haushalt, etc.)
3. Mevcut aspects'lere ekle
4. Tekrar eBay'e import et
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class ProduktartEnricher:
    """Add Produktart to products missing it."""
    
    def __init__(self):
        """Initialize."""
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
        
        # Common Produktart values by keywords
        self.produktart_mapping = {
            # Haushalt (Household)
            'organizer': 'Organizer',
            'aufbewahrung': 'Aufbewahrungsbox',
            'tasche': 'Aufbewahrungstasche',
            'halter': 'Halter',
            'ständer': 'Ständer',
            'behälter': 'Behälter',
            'box': 'Aufbewahrungsbox',
            'kabel': 'Kabelorganizer',
            
            # Spielzeug (Toys)
            'spielzeug': 'Spielzeug',
            'spiel': 'Spielzeug',
            'maus': 'Spielzeug',
            'katze': 'Spielzeug',
            
            # Küche (Kitchen)
            'küche': 'Küchenhelfer',
            'müll': 'Mülleimer-Zubehör',
            
            # Kleidung (Clothing)
            'kleiderbügel': 'Kleiderbügel',
            'haken': 'Haken',
            
            # Elektronik
            'hülle': 'Schutzhülle',
            'case': 'Schutzhülle',
            'kamera': 'Kamera-Zubehör',
            
            # Allgemein
            'zubehör': 'Zubehör',
            'tool': 'Werkzeug',
            'set': 'Set'
        }
    
    def detect_produktart(self, title: str) -> Optional[str]:
        """
        Detect Produktart from title.
        
        Args:
            title: Product title
        
        Returns:
            str: Produktart value or None
        """
        title_lower = title.lower()
        
        # Check each mapping
        for keyword, produktart in self.produktart_mapping.items():
            if keyword in title_lower:
                return produktart
        
        # Default fallback
        return 'Artikel'
    
    def enrich_product(self, product_id: str) -> bool:
        """
        Add Produktart to product aspects.
        
        Args:
            product_id: Product ID
        
        Returns:
            bool: Success
        """
        print(f"\n{'='*70}")
        print(f"📦 ÜRÜN: {product_id}")
        print(f"{'='*70}")
        
        # Get aspect file
        aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
        
        if not aspect_file.exists():
            print(f"  ⚠️  Aspect dosyası yok")
            return False
        
        # Load aspects
        with open(aspect_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        aspects = data.get('aspects', {})
        title = data.get('title', '')
        
        print(f"  Title: {title[:60]}...")
        print(f"  Mevcut aspects: {len(aspects)}")
        
        # Check if Produktart already exists
        if 'Produktart' in aspects:
            print(f"  ✅ Produktart zaten var: {aspects['Produktart']}")
            return True
        
        # Detect Produktart
        produktart = self.detect_produktart(title)
        
        if not produktart:
            print(f"  ⚠️  Produktart belirlenemedi")
            return False
        
        print(f"  🔍 Tespit edilen Produktart: {produktart}")
        
        # Add to aspects
        aspects['Produktart'] = produktart
        data['aspects'] = aspects
        data['aspect_count'] = len(aspects)
        data['updated_at'] = datetime.now().isoformat()
        
        # Save
        with open(aspect_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ Produktart eklendi: {produktart}")
        print(f"  💾 Dosya güncellendi: {len(aspects)} aspect")
        
        # Update database
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
        
        print(f"  ✅ Database güncellendi")
        print(f"  {'='*70}")
        
        return True


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Produktart Aspect Enrichment')
    parser.add_argument('--product-id', help='Single product ID')
    parser.add_argument('--all', action='store_true', help='All products')
    parser.add_argument('--failed-only', action='store_true', help='Only products that failed import')
    
    args = parser.parse_args()
    
    enricher = ProduktartEnricher()
    
    if args.product_id:
        # Tek ürün
        success = enricher.enrich_product(args.product_id)
        return 0 if success else 1
    
    elif args.all or args.failed_only:
        # Tüm ürünler
        aspect_files = list(enricher.aspects_dir.glob('product_*_aspects.json'))
        
        print(f"\n{'='*70}")
        print(f"PRODUKTART ENRICHMENT - BATCH")
        print(f"{'='*70}")
        print(f"  Aspect dosyası: {len(aspect_files)}")
        print()
        
        stats = {'success': 0, 'failed': 0, 'already_has': 0, 'added': 0}
        
        for i, aspect_file in enumerate(aspect_files, 1):
            # Extract product ID
            product_id = aspect_file.stem.replace('product_', '').replace('_aspects', '')
            
            print(f"\n[{i}/{len(aspect_files)}]")
            
            try:
                # Check if already has Produktart
                with open(aspect_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                aspects = data.get('aspects', {})
                
                if 'Produktart' in aspects:
                    stats['already_has'] += 1
                    continue
                
                # Enrich
                if enricher.enrich_product(product_id):
                    stats['success'] += 1
                    stats['added'] += 1
                else:
                    stats['failed'] += 1
            
            except Exception as e:
                print(f"  ❌ Hata: {e}")
                stats['failed'] += 1
        
        print(f"\n{'='*70}")
        print(f"📊 BATCH TAMAMLANDI")
        print(f"{'='*70}")
        print(f"  ✅ Produktart eklendi: {stats['added']}")
        print(f"  ✓ Zaten vardı: {stats['already_has']}")
        print(f"  ❌ Başarısız: {stats['failed']}")
        print(f"  📊 Toplam: {len(aspect_files)}")
        print(f"{'='*70}\n")
        
        return 0 if stats['failed'] == 0 else 1
    
    else:
        print("Kullanım:")
        print("  python scripts/add_produktart.py --product-id 1005009030953454")
        print("  python scripts/add_produktart.py --all")
        print("  python scripts/add_produktart.py --failed-only")
        return 1


if __name__ == '__main__':
    sys.exit(main())
