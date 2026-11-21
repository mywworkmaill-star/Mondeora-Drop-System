#!/usr/bin/env python3
"""
eBay'e Aspects Import
=====================

Her ürün için:
1. product_{id}_aspects.json dosyasını oku
2. O ürünün eBay listing'ini bul
3. Aspects'leri eBay Inventory API ile uygula
4. Sonuçları kaydet

HER ÜRÜN KENDİ ASPECTS - BİRBİRİNE KARIŞTIRMA!
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
from src.utils.audit_logger import get_logger


class EbayAspectsImporter:
    """Import aspects to eBay listings."""
    
    def __init__(self):
        """Initialize."""
        self.logger = get_logger()
        self.ebay = eBayRESTClient()
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.aspects_dir = ROOT / 'data' / 'product_aspects'
    
    def get_product_aspects(self, product_id: str) -> Optional[Dict[str, str]]:
        """
        Get aspects from product file.
        
        Args:
            product_id: Product ID
        
        Returns:
            dict: Aspects or None
        """
        aspect_file = self.aspects_dir / f'product_{product_id}_aspects.json'
        
        if not aspect_file.exists():
            print(f"  ⚠️  Aspect dosyası yok")
            return None
        
        try:
            with open(aspect_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            aspects = data.get('aspects', {})
            
            if not aspects:
                print(f"  ⚠️  Dosyada aspect yok")
                return None
            
            return aspects
        
        except Exception as e:
            print(f"  ❌ Dosya okuma hatası: {e}")
            return None
    
    def get_product_sku(self, product_id: str) -> Optional[str]:
        """Get product SKU from database."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sku_id, ebay_item_id
            FROM products
            WHERE aliexpress_product_id = ?
        ''', (product_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return None
        
        return row[0]
    
    def update_inventory_item_aspects(self, sku: str, aspects: Dict[str, str]) -> bool:
        """
        Update eBay inventory item with aspects.
        
        Args:
            sku: Product SKU
            aspects: Aspects to apply
        
        Returns:
            bool: Success
        """
        try:
            # Get current inventory item
            from urllib.parse import quote
            encoded_sku = quote(sku, safe='')
            
            # Try to get existing item
            try:
                current_item = self.ebay._request('GET', f'/sell/inventory/v1/inventory_item/{encoded_sku}')
            except:
                current_item = None
            
            # Prepare aspects for eBay format
            # eBay expects: {"aspects": {"Name": ["Value"], ...}}
            ebay_aspects = {}
            for name, value in aspects.items():
                # Convert to list format
                if isinstance(value, str):
                    ebay_aspects[name] = [value]
                elif isinstance(value, list):
                    ebay_aspects[name] = value
                else:
                    ebay_aspects[name] = [str(value)]
            
            # Update payload
            if current_item:
                # Update existing item
                payload = current_item.copy()
                
                # Update product aspect
                if 'product' not in payload:
                    payload['product'] = {}
                
                payload['product']['aspects'] = ebay_aspects
            else:
                # Create minimal payload (shouldn't happen, but handle it)
                payload = {
                    'product': {
                        'aspects': ebay_aspects
                    }
                }
            
            # Send to eBay
            self.ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{encoded_sku}', json=payload)
            
            print(f"  ✅ eBay güncellendi: {len(aspects)} aspect")
            
            return True
        
        except Exception as e:
            print(f"  ❌ eBay update hatası: {e}")
            
            self.logger.log_error(
                action='ebay_aspect_update_failed',
                error_message=str(e),
                product_id=sku
            )
            
            return False
    
    def import_for_product(self, product_id: str) -> bool:
        """
        Import aspects for one product.
        
        Args:
            product_id: Product ID
        
        Returns:
            bool: Success
        """
        print(f"\n{'='*70}")
        print(f"📦 ÜRÜN: {product_id}")
        print(f"{'='*70}")
        
        # 1. Get aspects from file
        aspects = self.get_product_aspects(product_id)
        
        if not aspects:
            return False
        
        print(f"  Aspects: {len(aspects)}")
        
        # Show aspects
        for i, (name, value) in enumerate(list(aspects.items())[:5], 1):
            print(f"    {i}. {name}: {value}")
        if len(aspects) > 5:
            print(f"    ... +{len(aspects) - 5} daha")
        
        # 2. Get SKU
        sku = self.get_product_sku(product_id)
        
        if not sku:
            print(f"  ❌ SKU bulunamadı")
            return False
        
        print(f"  SKU: {sku}")
        
        # 3. Update eBay
        success = self.update_inventory_item_aspects(sku, aspects)
        
        if success:
            # Log success
            try:
                self.logger.log(
                    action='aspects_imported_to_ebay',
                    message=f'Imported {len(aspects)} aspects to eBay',
                    category='aspect_import',
                    level='success',
                    product_id=product_id,
                    success=True,
                    data={
                        'aspect_count': len(aspects),
                        'sku': sku
                    }
                )
            except:
                pass
        
        print(f"  {'='*70}")
        
        return success


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description='eBay Aspects Import')
    parser.add_argument('--product-id', help='Single product ID')
    parser.add_argument('--all', action='store_true', help='All products with aspect files')
    parser.add_argument('--limit', type=int, help='Limit products')
    
    args = parser.parse_args()
    
    importer = EbayAspectsImporter()
    
    if args.product_id:
        # Tek ürün
        success = importer.import_for_product(args.product_id)
        return 0 if success else 1
    
    elif args.all:
        # Tüm ürünler
        aspect_files = list(importer.aspects_dir.glob('product_*_aspects.json'))
        
        # Limit
        if args.limit:
            aspect_files = aspect_files[:args.limit]
        
        print(f"\n{'='*70}")
        print(f"EBAY ASPECTS IMPORT - BATCH")
        print(f"{'='*70}")
        print(f"  Aspect dosyası: {len(aspect_files)}")
        print()
        
        stats = {'success': 0, 'failed': 0, 'total_aspects': 0}
        
        for i, aspect_file in enumerate(aspect_files, 1):
            # Extract product ID
            product_id = aspect_file.stem.replace('product_', '').replace('_aspects', '')
            
            print(f"\n[{i}/{len(aspect_files)}]")
            
            try:
                if importer.import_for_product(product_id):
                    stats['success'] += 1
                    
                    # Count aspects
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
        print(f"{'='*70}\n")
        
        return 0 if stats['failed'] == 0 else 1
    
    else:
        print("Kullanım:")
        print("  python scripts/import_aspects_to_ebay.py --product-id 1005009030953454")
        print("  python scripts/import_aspects_to_ebay.py --all")
        print("  python scripts/import_aspects_to_ebay.py --all --limit 5")
        return 1


if __name__ == '__main__':
    sys.exit(main())
