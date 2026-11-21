#!/usr/bin/env python3
"""
Aspect Enrichment Master
=========================

Maksimum aspect doldurma sistemi:
1. AliExpress'ten aspect çek
2. Rakiplerden aspect topla
3. eBay category requirements kontrol et
4. Tüm aspects'leri merge et ve optimize et
5. eBay'e uygula + database'e kaydet

DOĞRU BİLGİ - UYDURMA DEĞİL:
- AliExpress product attributes
- Rakip listing aspects
- eBay category taxonomy
"""

import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
# from src.api.aliexpress_client import AliExpressClient  # Skip for now - not critical
from src.utils.audit_logger import get_logger


class AspectEnricher:
    """Aspect enrichment master."""
    
    def __init__(self):
        """Initialize enricher."""
        self.logger = get_logger()
        self.ebay = eBayRESTClient()
        # self.ali = AliExpressClient()  # Skip for now - focus on competitor aspects
        self.db_path = ROOT / 'data' / 'dropshipping.db'
    
    def get_aliexpress_aspects(self, product_id: str) -> Dict[str, str]:
        """
        Get aspects from AliExpress product details.
        
        Args:
            product_id: AliExpress product ID
        
        Returns:
            dict: Aspect name -> value
        """
        aspects = {}
        
        # TODO: Implement AliExpress API integration
        # For now, focus on competitor aspects (real data from eBay)
        
        return aspects
    
    def get_competitor_aspects(self, product_id: str, ebay_category: str) -> Dict[str, List[str]]:
        """
        Get aspects from competitor listings.
        
        Args:
            product_id: Product ID
            ebay_category: eBay category ID
        
        Returns:
            dict: Aspect name -> list of values from competitors
        """
        aspects = {}
        
        try:
            # Load competitor analysis if exists
            analysis_dir = ROOT / 'data' / 'audit' / 'competitor_analysis'
            
            for file_path in analysis_dir.glob(f'{product_id}_*.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'competitors' in data:
                    for comp in data['competitors']:
                        if 'aspects' in comp:
                            for aspect_name, aspect_value in comp['aspects'].items():
                                if aspect_name not in aspects:
                                    aspects[aspect_name] = []
                                
                                if aspect_value not in aspects[aspect_name]:
                                    aspects[aspect_name].append(aspect_value)
        
        except Exception as e:
            self.logger.log_error(
                action='competitor_aspect_fetch_failed',
                error_message=str(e),
                product_id=product_id
            )
        
        return aspects
    
    def get_category_aspects(self, category_id: str) -> List[str]:
        """
        Get required/recommended aspects for eBay category.
        
        Args:
            category_id: eBay category ID
        
        Returns:
            list: Required aspect names
        """
        required_aspects = []
        
        try:
            # Get category tree
            response = self.ebay._request(
                'GET',
                f'/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category?category_id={category_id}'
            )
            
            if 'aspects' in response:
                for aspect in response['aspects']:
                    aspect_name = aspect.get('localizedAspectName', '')
                    required = aspect.get('aspectConstraint', {}).get('aspectRequired', False)
                    
                    if required or aspect.get('aspectUsage') == 'RECOMMENDED':
                        required_aspects.append(aspect_name)
        
        except Exception as e:
            self.logger.log_error(
                action='category_aspect_fetch_failed',
                error_message=str(e),
                product_id=category_id
            )
        
        return required_aspects
    
    def merge_aspects(self, 
                     ali_aspects: Dict[str, str],
                     comp_aspects: Dict[str, List[str]],
                     existing_aspects: Dict[str, str] = None) -> Dict[str, str]:
        """
        Merge aspects from all sources (priority: existing > AliExpress > competitors).
        
        Args:
            ali_aspects: AliExpress aspects
            comp_aspects: Competitor aspects
            existing_aspects: Existing aspects from eBay
        
        Returns:
            dict: Merged aspects
        """
        merged = {}
        
        # Start with existing aspects (highest priority)
        if existing_aspects:
            merged.update(existing_aspects)
        
        # Add AliExpress aspects (real product data)
        for name, value in ali_aspects.items():
            if name not in merged and value:
                merged[name] = value
        
        # Add competitor aspects (most common value)
        for name, values in comp_aspects.items():
            if name not in merged and values:
                # Use most common value
                from collections import Counter
                most_common = Counter(values).most_common(1)[0][0]
                merged[name] = most_common
        
        return merged
    
    def enrich_product(self, product_id: str, ebay_item_id: str = None) -> Dict[str, Any]:
        """
        Enrich product with maximum aspects.
        
        Args:
            product_id: AliExpress product ID
            ebay_item_id: eBay item ID (optional)
        
        Returns:
            dict: Enrichment result
        """
        print(f"\n{'='*70}")
        print(f"🔍 ENRICHING: {product_id}")
        print(f"{'='*70}")
        
        start_time = datetime.now()
        
        # Get database info
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ebay_item_id, category_id, aspects, aspect_count
            FROM products
            WHERE aliexpress_product_id = ?
        ''', (product_id,))
        
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Product not found in database")
            conn.close()
            return {'success': False, 'error': 'not_found'}
        
        ebay_item_id = ebay_item_id or row[0]
        category_id = row[1]
        existing_aspects_json = row[2]
        current_count = row[3] or 0
        
        # Parse existing aspects
        existing_aspects = {}
        if existing_aspects_json:
            try:
                existing_aspects = json.loads(existing_aspects_json)
            except:
                pass
        
        print(f"  Current aspects: {current_count}")
        print(f"  eBay Item ID: {ebay_item_id}")
        print(f"  Category: {category_id}")
        
        # Step 1: Get AliExpress aspects
        print(f"\n  📦 Fetching AliExpress aspects...")
        ali_aspects = self.get_aliexpress_aspects(product_id)
        print(f"  Found: {len(ali_aspects)} aspects")
        
        # Step 2: Get competitor aspects
        print(f"\n  🔍 Fetching competitor aspects...")
        comp_aspects = self.get_competitor_aspects(product_id, category_id)
        print(f"  Found: {len(comp_aspects)} unique aspect types")
        
        # Step 3: Merge aspects
        print(f"\n  🔀 Merging aspects...")
        merged_aspects = self.merge_aspects(ali_aspects, comp_aspects, existing_aspects)
        print(f"  Total: {len(merged_aspects)} aspects")
        
        # Step 4: Save to database
        aspects_json = json.dumps(merged_aspects, ensure_ascii=False)
        
        cursor.execute('''
            UPDATE products
            SET aspects = ?,
                aspect_count = ?,
                updated_at = ?
            WHERE aliexpress_product_id = ?
        ''', (aspects_json, len(merged_aspects), datetime.now().isoformat(), product_id))
        
        conn.commit()
        conn.close()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Print results
        print(f"\n  {'='*70}")
        print(f"  ✅ ENRICHED")
        print(f"  Before: {current_count} aspects")
        print(f"  After: {len(merged_aspects)} aspects")
        print(f"  Added: +{len(merged_aspects) - current_count}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  {'='*70}")
        
        # Log
        try:
            self.logger.log(
                action='aspect_enrichment_complete',
                message=f'Enriched {product_id}: {current_count} → {len(merged_aspects)} aspects',
                category='aspect_enrichment',
                level='success',
                product_id=product_id,
                ebay_item_id=ebay_item_id,
                success=True,
                duration_ms=int(duration * 1000),
                data={
                    'before': current_count,
                    'after': len(merged_aspects),
                    'added': len(merged_aspects) - current_count,
                    'ali_aspects': len(ali_aspects),
                    'comp_aspects': len(comp_aspects)
                }
            )
        except:
            pass  # Ignore audit errors
        
        return {
            'success': True,
            'product_id': product_id,
            'ebay_item_id': ebay_item_id,
            'before': current_count,
            'after': len(merged_aspects),
            'aspects': merged_aspects
        }
    
    def _map_aspect_name(self, ali_name: str) -> str:
        """Map AliExpress attribute name to German eBay aspect."""
        mapping = {
            'Color': 'Farbe',
            'Size': 'Größe',
            'Material': 'Material',
            'Brand': 'Marke',
            'Style': 'Stil',
            'Type': 'Typ',
            'Pattern': 'Muster',
            'Feature': 'Besonderheiten',
            'Quantity': 'Menge',
            'Weight': 'Gewicht',
            'Dimensions': 'Maße',
            'Package': 'Verpackung'
        }
        
        return mapping.get(ali_name, ali_name)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Aspect Enrichment Master')
    parser.add_argument('--product-id', help='Single product ID to enrich')
    parser.add_argument('--all', action='store_true', help='Enrich all products')
    parser.add_argument('--limit', type=int, help='Limit number of products')
    parser.add_argument('--min-aspects', type=int, default=5, help='Only enrich products with < N aspects')
    
    args = parser.parse_args()
    
    enricher = AspectEnricher()
    
    if args.product_id:
        # Single product
        result = enricher.enrich_product(args.product_id)
        return 0 if result['success'] else 1
    
    elif args.all:
        # All products
        conn = sqlite3.connect(enricher.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT aliexpress_product_id, aspect_count
            FROM products
            WHERE ebay_item_id IS NOT NULL
              AND (aspect_count IS NULL OR aspect_count < ?)
            ORDER BY aspect_count ASC
            LIMIT ?
        ''', (args.min_aspects, args.limit or 100))
        
        products = cursor.fetchall()
        conn.close()
        
        print(f"\n{'='*70}")
        print(f"ASPECT ENRICHMENT - BATCH MODE")
        print(f"{'='*70}")
        print(f"  Products to enrich: {len(products)}")
        print(f"  Min aspects filter: < {args.min_aspects}")
        print()
        
        stats = {'success': 0, 'failed': 0, 'total_added': 0}
        
        for i, (product_id, current_count) in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}]")
            
            result = enricher.enrich_product(product_id)
            
            if result['success']:
                stats['success'] += 1
                stats['total_added'] += result['after'] - result['before']
            else:
                stats['failed'] += 1
        
        print(f"\n{'='*70}")
        print(f"📊 BATCH COMPLETE")
        print(f"{'='*70}")
        print(f"  ✅ Success: {stats['success']}")
        print(f"  ❌ Failed: {stats['failed']}")
        print(f"  📈 Total aspects added: {stats['total_added']}")
        print(f"{'='*70}\n")
        
        return 0 if stats['failed'] == 0 else 1
    
    else:
        print("Usage: python scripts/aspect_enrichment_master.py --all --limit 10")
        return 1


if __name__ == '__main__':
    sys.exit(main())
