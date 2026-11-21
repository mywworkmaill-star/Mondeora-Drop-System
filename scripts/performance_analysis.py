#!/usr/bin/env python3
"""Performance Analysis for Mondeora Optimization Cron"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

def analyze_performance():
    conn = sqlite3.connect('data/dropshipping.db')
    c = conn.cursor()
    
    results = {}
    
    print('━' * 80)
    print('📊 PERFORMANS ANALIZI - Gerçek Veri')
    print('━' * 80)
    
    # 1. Aktif listings
    c.execute('SELECT COUNT(DISTINCT ebay_item_id) FROM products WHERE ebay_item_id IS NOT NULL')
    unique_listings = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM products WHERE is_listed=1')
    db_listed = c.fetchone()[0]
    
    results['unique_listings'] = unique_listings
    results['db_listed'] = db_listed
    
    print(f'\n🏪 Aktif İlanlar:')
    print(f'   eBay unique listings: {unique_listings}')
    print(f'   DB is_listed=1: {db_listed}')
    
    # 2. Düşük performanslı ilanlar (>30 gün, 0 satış)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    c.execute('''
        SELECT COUNT(*) FROM products 
        WHERE is_listed=1 
        AND created_at < ?
        AND ebay_item_id NOT IN (SELECT DISTINCT ebay_item_id FROM sales WHERE ebay_item_id IS NOT NULL)
    ''', (thirty_days_ago,))
    dead_listings = c.fetchone()[0]
    
    results['dead_listings_count'] = dead_listings
    
    print(f'\n💀 Düşük Performans (>30 gün, 0 satış):')
    print(f'   Kaldırılabilir: {dead_listings} ilan')
    
    # 3. Fiyat optimizasyonu adayları
    c.execute('''
        SELECT COUNT(*) FROM products 
        WHERE is_listed=1 
        AND aliexpress_price IS NOT NULL
        AND (
            updated_at < date('now', '-14 days')
            OR ebay_price IS NULL
        )
    ''')
    price_candidates = c.fetchone()[0]
    
    results['price_candidates'] = price_candidates
    
    print(f'\n💰 Fiyat Optimizasyonu:')
    print(f'   Güncellenebilir: {price_candidates} ilan')
    
    # 4. Traffic ve conversion stats
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN views > 0 THEN 1 ELSE 0 END) as has_views,
            SUM(CASE WHEN sales > 0 THEN 1 ELSE 0 END) as has_sales,
            AVG(CASE WHEN views > 0 THEN views ELSE NULL END) as avg_views,
            AVG(CASE WHEN sales > 0 THEN sales ELSE NULL END) as avg_sales
        FROM products WHERE is_listed=1
    ''')
    row = c.fetchone()
    total, has_views, has_sales, avg_views, avg_sales = row
    
    results['traffic'] = {
        'total': total,
        'has_views': has_views or 0,
        'has_sales': has_sales or 0,
        'avg_views': avg_views or 0,
        'avg_sales': avg_sales or 0
    }
    
    print(f'\n📈 Trafik İstatistikleri:')
    print(f'   Görüntüleme alan: {has_views}/{total} ilan ({has_views/total*100 if total else 0:.1f}%)')
    print(f'   Satış olan: {has_sales}/{total} ilan ({has_sales/total*100 if total else 0:.1f}%)')
    print(f'   Ort. görüntüleme: {avg_views:.1f}' if avg_views else '   Ort. görüntüleme: 0')
    print(f'   Ort. satış: {avg_sales:.1f}' if avg_sales else '   Ort. satış: 0')
    
    # 5. Sales stats
    c.execute('''
        SELECT 
            COUNT(*) as total_sales,
            SUM(sale_price) as revenue,
            SUM(profit) as profit,
            COUNT(DISTINCT ebay_item_id) as products_sold
        FROM sales
        WHERE sale_date >= date('now', '-30 days')
    ''')
    sales_row = c.fetchone()
    if sales_row and sales_row[0]:
        sales, rev, prof, prod_sold = sales_row
        results['sales_30d'] = {
            'count': sales,
            'revenue': float(rev or 0),
            'profit': float(prof or 0),
            'products': prod_sold
        }
        print(f'\n💵 Son 30 Gün Satışlar:')
        print(f'   Toplam: {sales} satış')
        print(f'   Ciro: EUR {rev:.2f}')
        print(f'   Kar: EUR {prof:.2f}')
        print(f'   Satılan ürün çeşidi: {prod_sold}')
    else:
        results['sales_30d'] = {'count': 0}
        print(f'\n💵 Son 30 Gün Satışlar: 0')
    
    # 6. En düşük performanslı 10 ilan
    print(f'\n⚠️  En Düşük Performanslı İlanlar:')
    c.execute('''
        SELECT 
            id,
            ebay_item_id,
            title,
            created_at,
            views,
            sales,
            ebay_price
        FROM products 
        WHERE is_listed=1
        ORDER BY 
            CASE WHEN views IS NULL THEN 1 ELSE 0 END DESC,
            views ASC,
            sales ASC,
            created_at ASC
        LIMIT 10
    ''')
    
    worst_performers = []
    for row in c.fetchall():
        pid, item_id, title, created, views, sales, price = row
        age = (datetime.now() - datetime.fromisoformat(created)).days if created else 0
        worst_performers.append({
            'id': pid,
            'item_id': item_id,
            'age_days': age,
            'views': views or 0,
            'sales': sales or 0,
            'price': float(price or 0),
            'title': title
        })
        print(f'   [{pid}] {age}gün | {views or 0} görün. | {sales or 0} satış | EUR{price:.2f} | {(title or "")[:35]}')
    
    results['worst_performers'] = worst_performers
    
    conn.close()
    print('\n' + '━' * 80)
    
    # Save results
    output_file = Path('data/performance_analysis.json')
    output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f'\n✅ Sonuçlar kaydedildi: {output_file}')
    
    return results

if __name__ == '__main__':
    analyze_performance()
