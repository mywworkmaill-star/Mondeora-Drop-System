"""
CSV Comparison Script
Compare eBay CSV export with database to find ghost listings
"""

import sys
import csv
import sqlite3
from pathlib import Path

def analyze_csv(csv_path):
    """Analyze eBay CSV and compare with database"""
    
    print('=' * 80)
    print('EBAY CSV ANALYSIS')
    print('=' * 80)
    print()
    
    # Read CSV
    print(f'📂 Reading CSV: {csv_path}')
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f'❌ File not found: {csv_path}')
        return
    
    ebay_items = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)
            
            # Common delimiters
            if ',' in sample:
                delimiter = ','
            elif ';' in sample:
                delimiter = ';'
            elif '\t' in sample:
                delimiter = '\t'
            else:
                delimiter = ','
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Print headers
            print(f'📋 CSV Columns: {reader.fieldnames}')
            print()
            
            # Find the column with Item ID
            item_id_col = None
            for col in reader.fieldnames or []:
                col_lower = col.lower()
                if 'item' in col_lower and ('id' in col_lower or 'number' in col_lower):
                    item_id_col = col
                    break
                elif 'artikelnummer' in col_lower:
                    item_id_col = col
                    break
            
            if not item_id_col:
                print('⚠️  Could not auto-detect Item ID column')
                print('Available columns:', reader.fieldnames)
                print()
                print('Please specify column name:')
                return
            
            print(f'✅ Using column: {item_id_col}')
            print()
            
            # Read all rows
            for row in reader:
                item_id = row.get(item_id_col, '').strip()
                
                if item_id and item_id.isdigit():
                    title = row.get('Title', row.get('Titel', ''))
                    ebay_items.append({
                        'item_id': item_id,
                        'title': title[:50] if title else 'N/A'
                    })
        
        print(f'📊 Found {len(ebay_items)} items in CSV')
        print()
        
    except Exception as e:
        print(f'❌ Error reading CSV: {e}')
        import traceback
        traceback.print_exc()
        return
    
    # Get database IDs
    print('📊 Reading database...')
    
    db_path = Path(__file__).parent / 'data' / 'dropshipping.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ebay_item_id, id, title 
        FROM products 
        WHERE ebay_item_id IS NOT NULL
        ORDER BY id
    ''')
    
    db_items = {}
    for ebay_id, prod_id, title in cursor.fetchall():
        db_items[ebay_id] = {'id': prod_id, 'title': title}
    
    conn.close()
    
    print(f'📊 Database has {len(db_items)} items')
    print()
    
    # Compare
    ebay_ids = set(item['item_id'] for item in ebay_items)
    db_ids = set(db_items.keys())
    
    ghost_ids = ebay_ids - db_ids  # On eBay but not in DB
    missing_ids = db_ids - ebay_ids  # In DB but not on eBay
    
    print('=' * 80)
    print('COMPARISON RESULTS')
    print('=' * 80)
    print()
    
    print(f'📊 eBay CSV:              {len(ebay_ids)} listings')
    print(f'📊 Database:              {len(db_ids)} listings')
    print(f'✅ Match:                 {len(ebay_ids & db_ids)} listings')
    print()
    
    print(f'👻 GHOST (on eBay, not in DB):  {len(ghost_ids)} listings')
    print(f'⚠️  MISSING (in DB, not on eBay): {len(missing_ids)} listings')
    print()
    
    if ghost_ids:
        print('=' * 80)
        print(f'👻 GHOST LISTINGS TO DELETE ({len(ghost_ids)}):')
        print('=' * 80)
        
        ghost_list = []
        for item in ebay_items:
            if item['item_id'] in ghost_ids:
                ghost_list.append(item)
        
        for i, item in enumerate(sorted(ghost_list, key=lambda x: x['item_id']), 1):
            print(f"{i:2d}. {item['item_id']} | {item['title']}")
        
        print()
        print('=' * 80)
        print('NEXT STEPS:')
        print('=' * 80)
        print()
        print('These listings are on eBay but NOT in your database.')
        print('They should be deleted from eBay to sync with database.')
        print()
        print('Options:')
        print('  A) Delete them manually from eBay Seller Hub')
        print('  B) Create a deletion script (I can help)')
        print('  C) Keep them (not recommended - sync issues)')
        print()
    
    if missing_ids:
        print('=' * 80)
        print(f'⚠️  MISSING ON EBAY ({len(missing_ids)}):')
        print('=' * 80)
        
        for item_id in sorted(list(missing_ids))[:10]:
            info = db_items[item_id]
            print(f"   ID {info['id']:3d} → {item_id} | {info['title'][:45]}")
        
        if len(missing_ids) > 10:
            print(f'   ... and {len(missing_ids) - 10} more')
        
        print()
        print('These are in database but not found in CSV.')
        print('Might be ended, sold, or inactive listings.')
        print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python compare_csv.py <path_to_csv>')
        print()
        print('Example:')
        print('  python compare_csv.py active_listings.csv')
        print('  python compare_csv.py Downloads/ebay_export.csv')
        sys.exit(1)
    
    csv_path = sys.argv[1]
    analyze_csv(csv_path)
