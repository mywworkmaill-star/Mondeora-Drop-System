#!/usr/bin/env python3
"""
ASPECT COLLECTOR: Rakiplerden otomatik aspect toplama
Başarılı listinglerimizden (ID 72, 73) template oluştur
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

class AspectCollector:
    """Rakip listinglerden aspect toplama ve template oluşturma"""
    
    def __init__(self):
        self.ebay = eBayAPIClient()
        self.db_path = 'data/dropshipping.db'
        self.templates_dir = Path('data/aspect_templates')
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def collect_from_successful_listings(self, product_ids: list) -> dict:
        """
        Başarılı listinglerden aspect topla
        
        Args:
            product_ids: Database product IDs (örn: [72, 73])
        
        Returns:
            dict: {aspect_name: {values: [...], count: n, percentage: %}}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(product_ids))
        cursor.execute(f'SELECT id, sku_id, ebay_item_id FROM products WHERE id IN ({placeholders})', product_ids)
        products = cursor.fetchall()
        conn.close()
        
        all_aspects = {}
        
        for prod_id, sku, item_id in products:
            if not sku:
                continue
            
            try:
                inventory = self.ebay._request('GET', self.ebay.inventory_path + '/inventory_item/' + sku)
                
                if 'product' in inventory and 'aspects' in inventory['product']:
                    aspects = inventory['product']['aspects']
                    
                    for name, values in aspects.items():
                        if name not in all_aspects:
                            all_aspects[name] = {
                                'values': [],
                                'count': 0,
                                'product_ids': []
                            }
                        
                        all_aspects[name]['values'].extend(values)
                        all_aspects[name]['count'] += 1
                        all_aspects[name]['product_ids'].append(prod_id)
            
            except Exception as e:
                print(f'⚠️ Error collecting from ID {prod_id}: {e}')
        
        # Calculate percentages
        total_products = len(products)
        for name, data in all_aspects.items():
            data['percentage'] = (data['count'] / total_products) * 100
        
        return all_aspects
    
    def create_category_template(self, category_id: str, aspect_data: dict) -> dict:
        """
        Category için aspect template oluştur
        
        Args:
            category_id: eBay category ID
            aspect_data: collect_from_successful_listings() output
        
        Returns:
            dict: Template data
        """
        # Zorunlu aspects (50%+ yaygın olanlar)
        mandatory_aspects = {}
        optional_aspects = {}
        
        for name, data in aspect_data.items():
            if data['percentage'] >= 50:
                mandatory_aspects[name] = {
                    'required': True,
                    'example_values': list(set(data['values']))[:3],
                    'usage_rate': f"{data['percentage']:.0f}%"
                }
            else:
                optional_aspects[name] = {
                    'required': False,
                    'example_values': list(set(data['values']))[:3],
                    'usage_rate': f"{data['percentage']:.0f}%"
                }
        
        template = {
            'category_id': category_id,
            'mandatory_aspects': mandatory_aspects,
            'optional_aspects': optional_aspects,
            'created_at': datetime.now().isoformat(),
            'source': 'successful_listings',
            'sample_count': len(set([pid for data in aspect_data.values() for pid in data['product_ids']]))
        }
        
        return template
    
    def save_template(self, category_id: str, template: dict):
        """Template'i kaydet"""
        template_file = self.templates_dir / f'category_{category_id}_template.json'
        
        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f'💾 Template saved: {template_file}')
        return template_file
    
    def apply_template_to_product(self, product_id: int, category_id: str, custom_values: dict = None) -> dict:
        """
        Template'i bir ürüne uygula
        
        Args:
            product_id: Database product ID
            category_id: eBay category ID
            custom_values: Ürüne özel değerler {aspect_name: value}
        
        Returns:
            dict: Ready aspects for eBay API
        """
        template_file = self.templates_dir / f'category_{category_id}_template.json'
        
        if not template_file.exists():
            raise FileNotFoundError(f'Template not found: {template_file}')
        
        with open(template_file, 'r', encoding='utf-8') as f:
            template = json.load(f)
        
        aspects = {}
        
        # Mandatory aspects
        for name, data in template['mandatory_aspects'].items():
            if custom_values and name in custom_values:
                aspects[name] = [custom_values[name]]
            else:
                # Use first example value
                aspects[name] = [data['example_values'][0]]
        
        # Optional aspects (sadece custom values varsa)
        if custom_values:
            for name, data in template['optional_aspects'].items():
                if name in custom_values:
                    aspects[name] = [custom_values[name]]
        
        return aspects


def main():
    """Test run"""
    collector = AspectCollector()
    
    print('🔍 ASPECT COLLECTOR')
    print('=' * 70)
    
    # 1. Başarılı listinglerden aspect topla
    print('\n📦 Collecting from successful listings (ID 72, 73)...')
    aspect_data = collector.collect_from_successful_listings([72, 73])
    
    print(f'\n✅ Collected {len(aspect_data)} unique aspects')
    print(f'\n📊 Top 10 aspects:')
    sorted_aspects = sorted(aspect_data.items(), key=lambda x: x[1]['percentage'], reverse=True)
    for i, (name, data) in enumerate(sorted_aspects[:10], 1):
        print(f'   {i}. {name}: {data["percentage"]:.0f}% ({data["count"]} listings)')
    
    # 2. Category 43504 template oluştur
    print(f'\n🎯 Creating template for Category 43504...')
    template = collector.create_category_template('43504', aspect_data)
    
    print(f'\n✅ Template created:')
    print(f'   Mandatory: {len(template["mandatory_aspects"])} aspects')
    print(f'   Optional: {len(template["optional_aspects"])} aspects')
    
    for name in list(template['mandatory_aspects'].keys())[:5]:
        print(f'      ✓ {name}')
    
    # 3. Kaydet
    template_file = collector.save_template('43504', template)
    
    # 4. Test: ID 44'e uygula
    print(f'\n🧪 Testing template on product ID 44...')
    custom = {
        'Produktart': 'Kabelorganizer',
        'Breite': '10 cm',
        'Höhe': '5 cm',
        'Länge': '10 cm',
        'Hauptmaterial': 'Kunststoff'
    }
    
    aspects = collector.apply_template_to_product(44, '43504', custom)
    
    print(f'✅ Generated aspects for ID 44:')
    for name, values in list(aspects.items())[:7]:
        print(f'   {name}: {values[0]}')
    
    print(f'\n🎉 ASPECT COLLECTOR HAZIR!')
    print(f'📁 Template: {template_file}')


if __name__ == '__main__':
    main()
