"""
Master Description Generator
Uses all components to generate professional eBay descriptions
"""

import sys
sys.path.insert(0, 'src')

from description_generator.base_template import BaseTemplate
from description_generator.category_templates import CategoryTemplates
from description_generator.dynamic_injection import DynamicInjector
from description_generator.length_optimizer import LengthOptimizer


class DescriptionGenerator:
    """Main generator class"""
    
    @staticmethod
    def generate_for_product(product_dict):
        """
        Generate complete professional description for a product
        
        Args:
            product_dict: Dict with all product fields from database
            
        Returns:
            dict: {
                'html': generated description,
                'length': character count,
                'valid': within eBay limits,
                'category': detected category,
                'stats': length stats
            }
        """
        
        # Step 1: Prepare product data
        product_data = DynamicInjector.prepare_product_data(product_dict)
        
        # Step 2: Detect category
        category = CategoryTemplates.detect_category(
            product_dict.get('title', ''),
            product_dict.get('aspects')
        )
        
        # Step 3: Generate category-specific content
        category_html = CategoryTemplates.generate_category_content(category, product_data)
        
        # Step 4: Generate full HTML
        html = BaseTemplate.generate(product_data, category_html)
        
        # Step 5: Optimize length
        html = LengthOptimizer.optimize(html, target=3500)
        
        # Step 6: Measure and validate
        stats = LengthOptimizer.measure(html)
        
        return {
            'html': html,
            'length': stats['length'],
            'valid': stats['valid'],
            'category': category,
            'stats': stats
        }


if __name__ == '__main__':
    # Test with product ID from command line
    import sqlite3
    import json
    
    if len(sys.argv) < 2:
        print('Usage: python generate_description.py <product_id>')
        sys.exit(1)
    
    product_id = int(sys.argv[1])
    
    # Load product from database
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    
    cursor2 = conn.cursor()
    cursor2.execute('PRAGMA table_info(products)')
    columns = [col[1] for col in cursor2.fetchall()]
    
    row = cursor.fetchone()
    if not row:
        print(f'Product ID {product_id} not found!')
        sys.exit(1)
    
    product = dict(zip(columns, row))
    conn.close()
    
    # Generate description
    print(f'Generating description for ID {product_id}...')
    print()
    
    result = DescriptionGenerator.generate_for_product(product)
    
    category = result['category']
    length = result['length']
    valid_text = 'YES' if result['valid'] else 'NO'
    percentage = result['stats']['percentage']
    
    print('Category:', category)
    print('Length:', length, 'chars')
    print('Valid:', valid_text)
    print('Percentage:', str(percentage) + '%')
    print()
    
    if length > 4000:
        over = length - 4000
        print('WARNING: Over limit by', over, 'chars!')
    elif length > 3500:
        margin = 4000 - length
        print('NOTICE: Close to target (' + str(margin) + ' chars margin)')
    else:
        under = 3500 - length
        print('GOOD: Under target (' + str(under) + ' chars under)')
    
    print()
    print('=' * 80)
    print('GENERATED HTML:')
    print('=' * 80)
    print(result['html'])
    print()
    print('=' * 80)
