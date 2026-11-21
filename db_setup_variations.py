"""
Database Schema for Product Variations
Creates table for storing manual variation input

Schema Design:
- product_variations table: stores all SKUs for a variation product
- Each SKU = one combination (e.g., "Schwarz, 1m")
- Links to products table via product_id
"""

import sqlite3


def create_variations_table(db_path='data/dropshipping.db'):
    """
    Create product_variations table if not exists
    """
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_variations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            
            -- Variation properties
            sku VARCHAR(100) UNIQUE NOT NULL,
            variation_name VARCHAR(200),  -- Human-readable: "Schwarz, 1m"
            
            -- Variation dimensions (flexible)
            color VARCHAR(50),
            size VARCHAR(50),
            length VARCHAR(50),
            material VARCHAR(50),
            style VARCHAR(50),
            
            -- Pricing & stock
            cost_price FLOAT,  -- AliExpress cost
            sell_price FLOAT,  -- eBay price
            stock INTEGER DEFAULT 999,
            
            -- Media
            image_url TEXT,
            additional_images TEXT,  -- JSON array of extra images
            
            -- eBay specific
            ebay_sku VARCHAR(100),  -- eBay inventory SKU
            ebay_offer_id VARCHAR(100),  -- eBay offer ID
            
            -- Metadata
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            
            -- Foreign key
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_variations_product_id 
        ON product_variations(product_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_variations_sku 
        ON product_variations(sku)
    ''')
    
    conn.commit()
    
    # Verify table structure
    cursor.execute('PRAGMA table_info(product_variations)')
    columns = cursor.fetchall()
    
    conn.close()
    
    return {
        'success': True,
        'table': 'product_variations',
        'columns': len(columns),
        'column_names': [col[1] for col in columns]
    }


def add_variation_flag_to_products(db_path='data/dropshipping.db'):
    """
    Add is_variation_product flag to products table
    """
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute('PRAGMA table_info(products)')
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_variation_product' not in columns:
        cursor.execute('''
            ALTER TABLE products 
            ADD COLUMN is_variation_product BOOLEAN DEFAULT 0
        ''')
        
        conn.commit()
        result = {'added': True, 'column': 'is_variation_product'}
    else:
        result = {'added': False, 'message': 'Column already exists'}
    
    if 'variation_group_id' not in columns:
        cursor.execute('''
            ALTER TABLE products 
            ADD COLUMN variation_group_id VARCHAR(100)
        ''')
        
        conn.commit()
        result['variation_group_id'] = 'added'
    
    conn.close()
    
    return result


# Run setup
if __name__ == "__main__":
    print("📊 CREATING VARIATION DATABASE SCHEMA")
    print("=" * 70)
    print()
    
    # Create variations table
    result1 = create_variations_table()
    
    print(f"✅ Table: {result1['table']}")
    print(f"   Columns: {result1['columns']}")
    print(f"   Names: {', '.join(result1['column_names'][:8])}...")
    print()
    
    # Add flags to products table
    result2 = add_variation_flag_to_products()
    
    print(f"✅ Products table updated:")
    if result2.get('added'):
        print(f"   Added: is_variation_product")
    else:
        print(f"   Skipped: {result2.get('message', 'Already exists')}")
    
    if result2.get('variation_group_id'):
        print(f"   Added: variation_group_id")
    
    print()
    print("🎉 Database schema ready for variations!")
