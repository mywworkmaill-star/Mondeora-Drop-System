"""
Variation Manager - Manual Input System
Allows user to manually define product variations

Usage:
    manager = VariationManager()
    
    # Define variations
    manager.add_variations(
        product_id=48,
        base_title="Toocki Kabel-Organizer",
        variations=[
            {'color': 'Schwarz', 'length': '1m', 'cost': 8.00, 'price': 19.99, 'stock': 50},
            {'color': 'Schwarz', 'length': '2m', 'cost': 10.00, 'price': 24.99, 'stock': 30},
            {'color': 'Weiß', 'length': '1m', 'cost': 8.00, 'price': 19.99, 'stock': 50}
        ]
    )
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import json


class VariationManager:
    """
    Manages product variations with manual input
    """
    
    def __init__(self, db_path='data/dropshipping.db'):
        self.db_path = db_path
    
    def add_variations(
        self,
        product_id: int,
        base_title: str,
        variations: List[Dict],
        base_image: str = None
    ) -> Dict:
        """
        Add variations for a product
        
        Args:
            product_id: Database product ID
            base_title: Base product title
            variations: List of variation dicts
                [
                    {
                        'color': 'Schwarz',
                        'length': '1m',
                        'cost': 8.00,
                        'price': 19.99,
                        'stock': 50,
                        'image': 'https://...'  # optional
                    },
                    ...
                ]
            base_image: Default image URL for variations without specific image
        
        Returns:
            {
                'success': bool,
                'product_id': int,
                'variations_added': int,
                'skus': [...]
            }
        """
        
        print(f"\n📦 ADDING VARIATIONS FOR PRODUCT {product_id}")
        print(f"   Base Title: {base_title[:60]}")
        print(f"   Variations: {len(variations)}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Mark product as variation product
        cursor.execute('''
            UPDATE products
            SET is_variation_product = 1
            WHERE id = ?
        ''', (product_id,))
        
        skus_created = []
        
        for i, var in enumerate(variations, 1):
            # Build SKU
            sku = f"VAR-{product_id}-{i:03d}"
            
            # Build variation name
            var_parts = []
            for key in ['color', 'size', 'length', 'material', 'style']:
                if key in var and var[key]:
                    var_parts.append(var[key])
            
            variation_name = ', '.join(var_parts)
            
            # Insert variation
            cursor.execute('''
                INSERT OR REPLACE INTO product_variations (
                    product_id,
                    sku,
                    variation_name,
                    color,
                    size,
                    length,
                    material,
                    style,
                    cost_price,
                    sell_price,
                    stock,
                    image_url,
                    is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product_id,
                sku,
                variation_name,
                var.get('color'),
                var.get('size'),
                var.get('length'),
                var.get('material'),
                var.get('style'),
                var.get('cost', 0.0),
                var.get('price', 0.0),
                var.get('stock', 999),
                var.get('image') or base_image,
                1
            ))
            
            skus_created.append(sku)
            
            print(f"   {i}. {variation_name} → {sku}")
            print(f"      Cost: €{var.get('cost', 0):.2f} | Price: €{var.get('price', 0):.2f} | Stock: {var.get('stock', 999)}")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ {len(skus_created)} variations added!")
        
        return {
            'success': True,
            'product_id': product_id,
            'variations_added': len(skus_created),
            'skus': skus_created
        }
    
    def get_variations(self, product_id: int) -> List[Dict]:
        """
        Get all variations for a product
        
        Returns:
            [
                {
                    'id': 1,
                    'sku': 'VAR-48-001',
                    'variation_name': 'Schwarz, 1m',
                    'color': 'Schwarz',
                    'length': '1m',
                    'cost_price': 8.00,
                    'sell_price': 19.99,
                    'stock': 50,
                    ...
                },
                ...
            ]
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM product_variations
            WHERE product_id = ?
            ORDER BY id
        ''', (product_id,))
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        conn.close()
        
        variations = []
        for row in rows:
            var = dict(zip(columns, row))
            variations.append(var)
        
        return variations
    
    def delete_variations(self, product_id: int) -> bool:
        """
        Delete all variations for a product
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM product_variations WHERE product_id = ?', (product_id,))
        
        cursor.execute('''
            UPDATE products
            SET is_variation_product = 0
            WHERE id = ?
        ''', (product_id,))
        
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ Deleted {deleted} variations for product {product_id}")
        
        return True
    
    def analyze_variation_dimensions(self, product_id: int) -> Dict:
        """
        Analyze variation dimensions (for eBay variation spec)
        
        Returns:
            {
                'dimensions': ['Color', 'Length'],
                'values': {
                    'Color': ['Schwarz', 'Weiß'],
                    'Length': ['1m', '2m', '3m']
                },
                'combinations': 6
            }
        """
        
        variations = self.get_variations(product_id)
        
        dimension_values = {}
        dimension_keys = ['color', 'size', 'length', 'material', 'style']
        
        for var in variations:
            for key in dimension_keys:
                if var.get(key):
                    # Capitalize for eBay
                    dim_name = key.capitalize()
                    
                    if dim_name not in dimension_values:
                        dimension_values[dim_name] = set()
                    
                    dimension_values[dim_name].add(var[key])
        
        # Convert to lists
        result = {
            'dimensions': list(dimension_values.keys()),
            'values': {k: sorted(list(v)) for k, v in dimension_values.items()},
            'combinations': len(variations)
        }
        
        return result


# Example usage
if __name__ == "__main__":
    print("🧪 TESTING VARIATION MANAGER")
    print("=" * 70)
    
    manager = VariationManager()
    
    # Test: Add variations for ID 48
    result = manager.add_variations(
        product_id=48,
        base_title="Toocki Kabel-Organizer",
        variations=[
            {'color': 'Schwarz', 'length': '1m', 'cost': 8.00, 'price': 19.99, 'stock': 50},
            {'color': 'Schwarz', 'length': '2m', 'cost': 10.00, 'price': 24.99, 'stock': 30},
            {'color': 'Schwarz', 'length': '3m', 'cost': 12.00, 'price': 29.99, 'stock': 20},
            {'color': 'Weiß', 'length': '1m', 'cost': 8.00, 'price': 19.99, 'stock': 50},
            {'color': 'Weiß', 'length': '2m', 'cost': 10.00, 'price': 24.99, 'stock': 30},
            {'color': 'Weiß', 'length': '3m', 'cost': 12.00, 'price': 29.99, 'stock': 20},
        ]
    )
    
    print()
    print(f"📊 RESULT:")
    print(f"   Success: {result['success']}")
    print(f"   Variations added: {result['variations_added']}")
    print(f"   SKUs: {result['skus'][:3]}...")
    
    # Test: Get variations
    print()
    print(f"🔍 RETRIEVING VARIATIONS:")
    variations = manager.get_variations(48)
    
    print(f"   Found: {len(variations)} variations")
    for var in variations[:3]:
        print(f"   - {var['variation_name']} (€{var['sell_price']})")
    
    # Test: Analyze dimensions
    print()
    print(f"📊 DIMENSION ANALYSIS:")
    analysis = manager.analyze_variation_dimensions(48)
    
    print(f"   Dimensions: {analysis['dimensions']}")
    for dim, values in analysis['values'].items():
        print(f"   {dim}: {values}")
    print(f"   Total combinations: {analysis['combinations']}")
    
    print()
    print("✅ Variation Manager working!")
