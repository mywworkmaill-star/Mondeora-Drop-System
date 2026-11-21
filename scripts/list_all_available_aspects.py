#!/usr/bin/env python3
"""
List All Available Aspects for Our Listings
Shows what aspects we CAN use for each category.
"""

import sys
import sqlite3
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.listing_quality import categories


def get_our_categories():
    """Get unique categories from our published listings."""
    
    db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    db.row_factory = sqlite3.Row
    
    query = '''
        SELECT DISTINCT 
            category_id,
            COUNT(*) as product_count
        FROM products
        WHERE ebay_item_id IS NOT NULL
        AND category_id IS NOT NULL
        GROUP BY category_id
        ORDER BY product_count DESC
    '''
    
    rows = db.execute(query).fetchall()
    db.close()
    
    return [{'category_id': row['category_id'], 'count': row['product_count']} for row in rows]


def main():
    """List all available aspects for each category."""
    
    ebay = eBayRESTClient()
    
    print(f"\n{'='*80}")
    print("TÜM KATEGORİLER İÇİN KULLANILABİLİR ASPECT'LER")
    print(f"{'='*80}\n")
    
    # Get our categories
    our_categories = get_our_categories()
    
    print(f"📦 Toplam {len(our_categories)} kategori analiz ediliyor...\n")
    
    all_aspects = {}
    
    for idx, cat_info in enumerate(our_categories, 1):
        category_id = cat_info['category_id']
        count = cat_info['count']
        
        print(f"[{idx}/{len(our_categories)}] Category: {category_id} ({count} ürün)")
        
        try:
            # Get aspect metadata
            meta = categories.aspects_for(ebay, category_id)
            
            # Group by required vs optional
            required = [a for a in meta if a.get('required')]
            optional = [a for a in meta if not a.get('required')]
            
            print(f"  ✅ {len(meta)} aspect bulundu ({len(required)} zorunlu, {len(optional)} opsiyonel)")
            
            # Store for later
            all_aspects[category_id] = {
                'category_id': category_id,
                'product_count': count,
                'total_aspects': len(meta),
                'required_count': len(required),
                'optional_count': len(optional),
                'required_aspects': [
                    {
                        'name': a['name'],
                        'mode': a['mode'],
                        'value_count': len(a.get('values', []))
                    }
                    for a in required
                ],
                'optional_aspects': [
                    {
                        'name': a['name'],
                        'mode': a['mode'],
                        'value_count': len(a.get('values', []))
                    }
                    for a in optional[:20]  # First 20 optional
                ],
                'all_aspect_names': [a['name'] for a in meta]
            }
            
        except Exception as e:
            print(f"  ❌ Hata: {e}")
            continue
    
    # Save detailed report
    report_path = ROOT / 'data' / 'audit' / 'available_aspects_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_aspects, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print("ÖZET RAPOR")
    print(f"{'='*80}\n")
    
    # Summary by category
    print("📊 KATEGORİ BAŞINA ASPECT SAYILARI:\n")
    
    for cat_id in sorted(all_aspects.keys(), key=lambda x: all_aspects[x]['product_count'], reverse=True):
        info = all_aspects[cat_id]
        print(f"Category {cat_id} ({info['product_count']} ürün):")
        print(f"  Toplam: {info['total_aspects']} aspects")
        print(f"  Zorunlu: {info['required_count']}")
        print(f"  Opsiyonel: {info['optional_count']}")
        
        # Show required aspects
        if info['required_aspects']:
            print(f"  ✅ ZORUNLU:")
            for asp in info['required_aspects']:
                print(f"     - {asp['name']} ({asp['mode']}, {asp['value_count']} değer)")
        
        # Show top optional aspects
        if info['optional_aspects']:
            print(f"  📋 POPÜLER OPSİYONEL (ilk 10):")
            for asp in info['optional_aspects'][:10]:
                print(f"     - {asp['name']} ({asp['mode']}, {asp['value_count']} değer)")
        
        print()
    
    # Common aspects across categories
    print("\n📌 TÜM KATEGORİLERDE ORTAK ASPECT'LER:\n")
    
    aspect_frequency = defaultdict(int)
    for cat_info in all_aspects.values():
        for name in cat_info['all_aspect_names']:
            aspect_frequency[name] += 1
    
    # Show aspects appearing in 3+ categories
    common = [(name, count) for name, count in aspect_frequency.items() if count >= 3]
    common.sort(key=lambda x: x[1], reverse=True)
    
    for name, count in common[:20]:
        print(f"  {name}: {count} kategoride")
    
    print(f"\n📄 Detaylı rapor kaydedildi: {report_path}")
    print()


if __name__ == '__main__':
    main()
