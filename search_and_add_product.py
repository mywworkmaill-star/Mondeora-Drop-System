"""
Simple AliExpress product search and add to database
"""

import sys
sys.path.insert(0, 'src')

from api.aliexpress_client import AliExpressAPIClient
import sqlite3
import json

def search_new_product():
    print('🔍 YENİ ÜRÜN ARAŞTIRMA')
    print('=' * 80)
    print()
    
    # Get existing products
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    cursor.execute('SELECT aliexpress_product_id FROM products')
    existing = set(row[0] for row in cursor.fetchall())
    
    print(f'Database: {len(existing)} mevcut ürün')
    print()
    
    # Search AliExpress
    ali = AliExpressAPIClient()
    
    keywords = ['kitchen drawer organizer', 'desk organizer box']
    
    for keyword in keywords:
        print(f'🔎 Searching: "{keyword}"...')
        
        try:
            # Use search_product_page method
            result = ali.search_product_page(
                keyword=keyword,
                page_num=1,
                page_size=20,
                sort_by='SALES_DESC'
            )
            
            if 'products' in result:
                products = result['products']
                
                print(f'✅ {len(products)} ürün bulundu')
                print()
                
                for p in products:
                    prod_id = str(p.get('itemId', ''))
                    
                    if not prod_id or prod_id in existing:
                        continue
                    
                    price_str = p.get('targetSalePrice', '0')
                    try:
                        price = float(price_str)
                    except:
                        price = 0
                    
                    if 2 <= price <= 15:
                        title = p.get('title', '')
                        image = p.get('imageUrl', '')
                        
                        print(f'✅ BULUNDU!')
                        print(f'   ID: {prod_id}')
                        print(f'   Title: {title[:70]}')
                        print(f'   Price: €{price}')
                        print(f'   Image: {image[:60]}...')
                        print()
                        
                        # Add to database
                        cursor.execute('''
                            INSERT INTO products (
                                aliexpress_product_id,
                                title,
                                aliexpress_price,
                                ebay_price,
                                image_url,
                                status,
                                is_listed,
                                created_at,
                                updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ''', (prod_id, title[:500], price, price * 2.5, image, 'ready', 0))
                        
                        conn.commit()
                        
                        new_id = cursor.lastrowid
                        
                        print('=' * 80)
                        print('✅ DATABASE\'E EKLENDİ!')
                        print('=' * 80)
                        print(f'Database ID: {new_id}')
                        print(f'AliExpress ID: {prod_id}')
                        print(f'Title: {title[:70]}')
                        print(f'Price: €{price} → €{price * 2.5} (2.5x markup)')
                        print()
                        
                        conn.close()
                        return new_id, prod_id
                        
        except Exception as e:
            print(f'❌ Hata: {e}')
            import traceback
            traceback.print_exc()
    
    conn.close()
    print('❌ Uygun ürün bulunamadı')
    return None, None

if __name__ == '__main__':
    new_id, ali_id = search_new_product()
    
    if new_id:
        print('=' * 80)
        print('SONRAKİ ADIM: ENRICHMENT')
        print('=' * 80)
        print()
        print(f'python quick_list_product.py {new_id}')
