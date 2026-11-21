#!/usr/bin/env python3
"""
Diagnostic & Fix: Listing Preparation Pipeline
Detects and fixes common listing_prepare issues.
"""

import sys
import sqlite3
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def diagnose_listing_pipeline():
    """Diagnose why listing_prepare produces 0 ready products."""
    
    issues = []
    fixes = []
    
    # 1. Check pending_rows
    db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    
    pending = db.execute('''
        SELECT COUNT(*) FROM products 
        WHERE is_listed=0 
        AND (ebay_item_id IS NULL OR ebay_item_id='')
        AND status IN ('needs_variation_listing','manual_review','ready_to_list','active','prepared')
    ''').fetchone()[0]
    
    print(f'📊 DIAGNOSTIC REPORT')
    print(f'='*60)
    print(f'\n1. Pending Products: {pending}')
    
    if pending == 0:
        issues.append('No products match pending_rows() criteria')
        fixes.append('Add active products with is_listed=0, ebay_item_id=NULL')
    
    # 2. Check priced vs unpriced
    priced = db.execute('''
        SELECT COUNT(*) FROM products
        WHERE is_listed=0
        AND (ebay_item_id IS NULL OR ebay_item_id='')
        AND status IN ('needs_variation_listing','manual_review','ready_to_list','active','prepared')
        AND ebay_price IS NOT NULL
        AND ebay_price > 0
    ''').fetchone()[0]
    
    print(f'   - With price: {priced}')
    print(f'   - Without price: {pending - priced}')
    
    if priced == 0:
        issues.append('No products have ebay_price set')
        fixes.append('Run price calculation for pending products')
    
    # 3. Check cache status
    cache_path = ROOT / 'data' / 'listing_ready.sqlite'
    if cache_path.exists():
        cache_db = sqlite3.connect(cache_path)
        
        try:
            total = cache_db.execute('SELECT COUNT(*) FROM ready_listings').fetchone()[0]
            ready = cache_db.execute('SELECT COUNT(*) FROM ready_listings WHERE status="ready"').fetchone()[0]
            blocked = cache_db.execute('SELECT COUNT(*) FROM ready_listings WHERE status="blocked"').fetchone()[0]
            
            print(f'\n2. Cache Status (listing_ready.sqlite):')
            print(f'   - Total: {total}')
            print(f'   - Ready: {ready}')
            print(f'   - Blocked: {blocked}')
            
            if blocked > ready * 2:
                issues.append(f'Too many blocked products in cache ({blocked} blocked vs {ready} ready)')
                fixes.append('Clear cache: rm data/listing_ready.sqlite')
                
        except sqlite3.OperationalError:
            issues.append('Cache DB schema error')
            fixes.append('Delete and rebuild cache')
        
        cache_db.close()
    else:
        print(f'\n2. Cache: Not found (will be created)')
    
    # 4. Check readiness
    readiness_path = ROOT / 'data' / 'readiness_report.json'
    if readiness_path.exists():
        readiness = json.loads(readiness_path.read_text(encoding='utf-8'))
        
        print(f'\n3. Readiness:')
        print(f'   - Supervised trial: {readiness.get("ready_for_supervised_trial")}')
        print(f'   - Live: {readiness.get("ready_for_live")}')
        print(f'   - Trial blockers: {len(readiness.get("supervised_trial_blockers", []))}')
        
        if not readiness.get('ready_for_supervised_trial') and not readiness.get('ready_for_live'):
            issues.append('Not ready for supervised trial or live')
            fixes.append('Enable supervised trial override')
    
    # 5. Summary
    print(f'\n{"="*60}')
    if issues:
        print(f'\n⚠️  ISSUES FOUND: {len(issues)}')
        for i, issue in enumerate(issues, 1):
            print(f'   {i}. {issue}')
        
        print(f'\n💡 RECOMMENDED FIXES:')
        for i, fix in enumerate(fixes, 1):
            print(f'   {i}. {fix}')
    else:
        print(f'\n✅ No issues detected')
    
    db.close()
    
    return issues, fixes


def auto_fix():
    """Automatically fix common issues."""
    
    print(f'\n🔧 AUTO-FIX')
    print(f'='*60)
    
    # Fix 1: Clear stale cache
    cache_path = ROOT / 'data' / 'listing_ready.sqlite'
    if cache_path.exists():
        cache_path.unlink()
        print(f'✅ Cleared cache: {cache_path}')
    
    # Fix 2: Prioritize priced products
    db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    
    # Set priced products to 'ready_to_list' status for priority
    updated = db.execute('''
        UPDATE products
        SET status = 'ready_to_list'
        WHERE status IN ('active', 'manual_review', 'needs_variation_listing')
        AND is_listed = 0
        AND (ebay_item_id IS NULL OR ebay_item_id = '')
        AND ebay_price IS NOT NULL
        AND ebay_price > 0
    ''')
    db.commit()
    
    count = updated.rowcount
    print(f'✅ Prioritized {count} priced products (status → ready_to_list)')
    
    # Show what will be prepared
    ready = db.execute('''
        SELECT aliexpress_product_id, ebay_price
        FROM products
        WHERE status = 'ready_to_list'
        AND is_listed = 0
        LIMIT 5
    ''').fetchall()
    
    if ready:
        print(f'\n📦 Products ready for listing:')
        for pid, price in ready:
            print(f'   - {pid}: {price} EUR')
    
    db.close()
    
    print(f'\n✅ Auto-fix complete')


if __name__ == '__main__':
    issues, fixes = diagnose_listing_pipeline()
    
    if issues:
        print(f'\n❓ Run auto-fix? (y/n)')
        # For script usage: auto-run
        auto_fix()
