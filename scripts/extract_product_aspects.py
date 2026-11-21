#!/usr/bin/env python3
"""
Mevcut Competitor Analysis'den Ürüne Özel Aspects
==================================================

Her ürün için:
1. Kendi analysis_{product_id}.json dosyasını bul
2. O dosyadaki aspects'i çıkar
3. AYRI dosyaya kaydet (product_{id}_aspects.json)
4. Database'e uygula

HER ÜRÜN AYRI - BİRBİRİNE KARIŞTIRMA!
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.audit_logger import get_logger


class ProductSpecificAspects:
    """Extract product-specific aspects from existing analysis."""
    
    def __init__(self):
        """Initialize."""
        self.logger = get_logger()
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.analysis_dir = ROOT / 'data' / 'audit' / 'competitor_analysis'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
        self.aspects_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_from_analysis(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Extract aspects from product's own analysis file.
        
        Args:
            product_id: Product ID
        
        Returns:
            dict: Product-specific aspects
        """
        # Find analysis file for this product
        analysis_file = self.analysis_dir / f'analysis_{product_id}.json'
        
        if not analysis_file.exists():
            print(f"  ⚠️  Analysis dosyası yok: {analysis_file.name}")
            return None
        
        print(f"  📂 Analysis bulundu: {analysis_file.name}")
        
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract aspects from the file
            aspects = {}
            
            # Check if aspects already in file
            if 'aspects' in data and isinstance(data['aspects'], dict):
                if 'merged_aspects' in data['aspects']:
                    aspects = data['aspects']['merged_aspects']
            
            # Also check for competitor-specific aspects
            # (Some files might have richer data)
            
            return {
                'product_id': product_id,
                'title': data.get('title', {}).get('original_title', 'Unknown'),
                'aspects': aspects,
                'aspect_count': len(aspects),
                'source': 'competitor_analysis',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"  ❌ Dosya okuma hatası: {e}")
            return None
    
    def save_product_aspects(self, data: Dict[str, Any]):
        """Save to product-specific file."""
        product_id = data['product_id']
        
        # AYRI dosya
        aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
        
        with open(aspect_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  💾 Kaydedildi: {aspect_file.name}")
        
        try:
            self.logger.log(
                action='product_aspects_extracted',
                message=f'Extracted aspects for {product_id}',
                category='aspect_extraction',
                level='info',
                product_id=product_id,
                success=True,
                data={
                    'aspect_count': data['aspect_count'],
                    'source': data['source'],
                    'file': str(aspect_file)
                }
            )
        except:
            pass
    
    def apply_to_database(self, product_id: str, aspects: Dict[str, str]):
        """Apply to database."""
        if not aspects:
            print(f"  ⚠️  Aspect yok, database güncellenmedi")
            return
        
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
    
    def process_product(self, product_id: str) -> bool:
        """Process one product."""
        print(f"\n{'='*70}")
        print(f"📦 ÜRÜN: {product_id}")
        print(f"{'='*70}")
        
        # Extract from analysis
        result = self.extract_from_analysis(product_id)
        
        if not result:
            return False
        
        print(f"  Title: {result['title'][:60]}...")
        print(f"  Aspects: {result['aspect_count']}")
        
        # Show aspects
        if result['aspects']:
            print(f"\n  📋 Aspects:")
            for i, (name, value) in enumerate(list(result['aspects'].items())[:10], 1):
                print(f"    {i}. {name}: {value}")
            if result['aspect_count'] > 10:
                print(f"    ... +{result['aspect_count'] - 10} daha")
        
        print(f"\n  {'='*70}")
        
        # Save to product-specific file
        self.save_product_aspects(result)
        
        # Apply to database
        self.apply_to_database(product_id, result['aspects'])
        
        return True


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ürüne Özel Aspect Extraction')
    parser.add_argument('--product-id', help='Single product ID')
    parser.add_argument('--all', action='store_true', help='All products with analysis files')
    
    args = parser.parse_args()
    
    extractor = ProductSpecificAspects()
    
    if args.product_id:
        # Tek ürün
        success = extractor.process_product(args.product_id)
        return 0 if success else 1
    
    elif args.all:
        # Tüm ürünler - analysis dosyası olanlar
        analysis_files = list(extractor.analysis_dir.glob('analysis_*.json'))
        
        print(f"\n{'='*70}")
        print(f"ÜRÜNE ÖZEL ASPECT EXTRACTION - BATCH")
        print(f"{'='*70}")
        print(f"  Analysis dosyası: {len(analysis_files)}")
        print()
        
        stats = {'success': 0, 'failed': 0, 'total_aspects': 0}
        
        for i, analysis_file in enumerate(analysis_files, 1):
            # Extract product ID from filename
            product_id = analysis_file.stem.replace('analysis_', '')
            
            print(f"\n[{i}/{len(analysis_files)}]")
            
            try:
                if extractor.process_product(product_id):
                    stats['success'] += 1
                    
                    # Count aspects
                    aspect_file = extractor.aspects_dir / f'product_{product_id}_aspects.json'
                    if aspect_file.exists():
                        with open(aspect_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            stats['total_aspects'] += data.get('aspect_count', 0)
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
        print("  python scripts/extract_product_aspects.py --product-id 1005009030953454")
        print("  python scripts/extract_product_aspects.py --all")
        return 1


if __name__ == '__main__':
    sys.exit(main())
