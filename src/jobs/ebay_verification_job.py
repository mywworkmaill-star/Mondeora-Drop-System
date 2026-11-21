"""
Database → eBay Verification Job
Checks if products in database are still active on eBay
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.ebay_client import eBayAPIClient


def get_db_products(db_path='data/dropshipping.db'):
    """Get all products marked as listed in database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, ebay_item_id, ebay_offer_id, is_listed, status
        FROM products
        WHERE is_listed = 1 OR ebay_item_id IS NOT NULL
        ORDER BY id
    ''')
    
    products = []
    for row in cursor.fetchall():
        products.append({
            'id': row[0],
            'title': row[1],
            'ebay_item_id': row[2],
            'ebay_offer_id': row[3],
            'is_listed': row[4],
            'status': row[5]
        })
    
    conn.close()
    return products


def verify_ebay_listing(ebay_client, product):
    """
    Verify if a product is still active on eBay
    
    Returns:
        dict with verification result
    """
    result = {
        'product_id': product['id'],
        'ebay_item_id': product['ebay_item_id'],
        'exists': False,
        'active': False,
        'quantity': 0,
        'price': 0,
        'error': None
    }
    
    try:
        # Try to get offer by offer_id
        if product['ebay_offer_id']:
            try:
                path = f"/sell/inventory/v1/offer/{product['ebay_offer_id']}"
                response = ebay_client._request('GET', path)
                
                if response:
                    result['exists'] = True
                    result['active'] = response.get('status') == 'PUBLISHED'
                    result['quantity'] = response.get('availableQuantity', 0)
                    
                    price_data = response.get('pricingSummary', {})
                    result['price'] = float(price_data.get('price', {}).get('value', 0))
                    
                    return result
            except Exception as e:
                # If offer_id fails, try listing_id
                pass
        
        # Try to find by listing ID (item_id)
        # Note: eBay Inventory API doesn't have direct item_id lookup
        # We need to search by SKU or use Trading API
        
        # For now, mark as unknown if offer_id check failed
        result['error'] = 'Could not verify (no offer_id or API limitation)'
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def sync_verification_to_db(verifications, db_path='data/dropshipping.db'):
    """Update database based on verification results"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        'verified_active': 0,
        'verified_inactive': 0,
        'updated_inactive': 0,
        'errors': 0
    }
    
    for v in verifications:
        if v['error']:
            stats['errors'] += 1
            continue
        
        if v['active']:
            stats['verified_active'] += 1
        else:
            stats['verified_inactive'] += 1
            
            # Update database: mark as inactive
            cursor.execute('''
                UPDATE products
                SET is_listed = 0,
                    status = 'inactive'
                WHERE id = ?
            ''', (v['product_id'],))
            stats['updated_inactive'] += 1
            print(f"   ⚠️  ID {v['product_id']}: Marked inactive (not found on eBay)")
    
    conn.commit()
    conn.close()
    
    return stats


def generate_verification_report(products, verifications, stats):
    """Generate verification report"""
    
    report = f"""
{'='*80}
DATABASE → EBAY VERIFICATION REPORT
{'='*80}

Database Products Checked:  {len(products)}

Verification Results:
  ✅ Active on eBay:         {stats['verified_active']}
  ⚠️  Inactive/Not Found:    {stats['verified_inactive']}
  🔄 Updated to Inactive:    {stats['updated_inactive']}
  ❌ Errors:                 {stats['errors']}

{'='*80}

INACTIVE/NOT FOUND LISTINGS:
"""
    
    for v in verifications:
        if not v['active'] and not v['error']:
            product = next((p for p in products if p['id'] == v['product_id']), None)
            if product:
                report += f"\n  ID {v['product_id']}: {product['title'][:50]}..."
                report += f"\n    eBay Item ID: {v['ebay_item_id']}"
                report += f"\n    Status: {'Not Found' if not v['exists'] else 'Exists but Inactive'}"
    
    if stats['errors'] > 0:
        report += f"\n\nERRORS ({stats['errors']}):\n"
        for v in verifications:
            if v['error']:
                product = next((p for p in products if p['id'] == v['product_id']), None)
                if product:
                    report += f"\n  ID {v['product_id']}: {v['error']}"
    
    report += f"\n\n{'='*80}\n"
    
    return report


def run_verification(dry_run=False, limit=None):
    """
    Main verification function
    
    Args:
        dry_run: If True, check but don't update database
        limit: Max products to check (None = all)
    """
    print(f"\n{'='*80}")
    print(f"DATABASE → EBAY VERIFICATION JOB")
    print(f"{'='*80}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Dry run: {dry_run}\n")
    
    # Get database products
    print("📥 STEP 1: Get Database Products")
    products = get_db_products()
    
    if limit:
        products = products[:limit]
    
    print(f"   Total products to check: {len(products)}\n")
    
    if not products:
        print("❌ No products to verify.")
        return
    
    # Initialize eBay client
    ebay = eBayAPIClient()
    
    # Verify each product
    print("🔍 STEP 2: Verify on eBay")
    verifications = []
    
    for i, product in enumerate(products, 1):
        print(f"   [{i}/{len(products)}] Checking ID {product['id']}... ", end='')
        
        verification = verify_ebay_listing(ebay, product)
        verifications.append(verification)
        
        if verification['active']:
            print(f"✅ Active")
        elif verification['error']:
            print(f"⚠️  {verification['error']}")
        else:
            print(f"❌ Inactive/Not Found")
    
    # Sync to database
    if not dry_run:
        print("\n💾 STEP 3: Update Database")
        stats = sync_verification_to_db(verifications)
    else:
        print("\n🔍 STEP 3: Dry Run (no database updates)")
        stats = {
            'verified_active': sum(1 for v in verifications if v['active']),
            'verified_inactive': sum(1 for v in verifications if not v['active'] and not v['error']),
            'updated_inactive': 0,
            'errors': sum(1 for v in verifications if v['error'])
        }
    
    # Generate report
    print("\n📊 STEP 4: Generate Report")
    report = generate_verification_report(products, verifications, stats)
    print(report)
    
    # Save report
    report_path = PROJECT_ROOT / 'data' / 'ebay_verification_report.txt'
    report_path.write_text(report, encoding='utf-8')
    print(f"Report saved: {report_path}")
    
    return stats


if __name__ == '__main__':
    import sys
    
    # Check for flags
    dry_run = '--dry-run' in sys.argv
    limit = None
    
    # Parse limit
    for arg in sys.argv:
        if arg.startswith('--limit='):
            try:
                limit = int(arg.split('=')[1])
            except:
                pass
    
    try:
        run_verification(dry_run=dry_run, limit=limit)
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
