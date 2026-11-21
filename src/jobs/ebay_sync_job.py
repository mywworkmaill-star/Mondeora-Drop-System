"""
eBay → Database Sync Job
Fetches all active eBay listings and syncs to database
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.ebay_client import eBayAPIClient


def fetch_all_ebay_offers(ebay_client, limit=100):
    """
    Fetch all active eBay offers using Inventory API
    
    Returns:
        List of dicts with offer details
    """
    all_offers = []
    
    print(f"🔍 Fetching eBay offers (using _pages generator)...")
    
    try:
        # Use existing _pages method from eBayAPIClient
        # GET /sell/inventory/v1/offer with pagination
        for offer in ebay_client._pages('/sell/inventory/v1/offer', 'offers', params={}, limit=limit):
            all_offers.append(offer)
            if len(all_offers) % 10 == 0:
                print(f"   Fetched {len(all_offers)} offers...")
                
    except Exception as e:
        print(f"❌ Error fetching offers: {e}")
        import traceback
        traceback.print_exc()
    
    return all_offers


def parse_offer_to_product(offer):
    """
    Parse eBay offer to product data
    
    Returns:
        dict with product fields
    """
    sku = offer.get('sku', '')
    listing_id = offer.get('listingId', '')
    
    # Try to extract product_id from SKU
    # SKU format: MULTI-{timestamp} or ALI-{product_id}
    product_id = None
    if 'ALI-' in sku:
        try:
            product_id = int(sku.split('ALI-')[1].split('-')[0])
        except:
            pass
    
    # Get price
    price_data = offer.get('pricingSummary', {})
    price = price_data.get('price', {}).get('value', 0)
    
    # Get quantity
    quantity = offer.get('availableQuantity', 0)
    
    # Get title
    title = ''
    if 'listing' in offer:
        title = offer['listing'].get('title', '')
    
    return {
        'sku': sku,
        'ebay_item_id': listing_id,
        'ebay_offer_id': offer.get('offerId', ''),
        'title': title,
        'price': float(price) if price else 0,
        'quantity': quantity,
        'status': offer.get('status', ''),
        'product_id': product_id,
        'format': offer.get('format', ''),
        'marketplace': offer.get('marketplaceId', 'EBAY_DE')
    }


def sync_to_database(offers_data, db_path='data/dropshipping.db'):
    """
    Sync eBay offers to database
    
    Returns:
        dict with sync statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        'total_offers': len(offers_data),
        'matched': 0,
        'updated': 0,
        'new_unmatched': 0,
        'skipped': 0
    }
    
    for offer in offers_data:
        ebay_item_id = offer['ebay_item_id']
        sku = offer['sku']
        product_id = offer['product_id']
        
        # Try to find existing product
        matched = False
        
        # Strategy 1: Match by product_id (if extracted from SKU)
        if product_id:
            cursor.execute('SELECT id, ebay_item_id FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            if row:
                db_id, db_ebay_id = row
                if db_ebay_id != ebay_item_id:
                    # Update ebay_item_id
                    cursor.execute('''
                        UPDATE products
                        SET ebay_item_id = ?, 
                            ebay_offer_id = ?,
                            is_listed = 1,
                            status = 'active'
                        WHERE id = ?
                    ''', (ebay_item_id, offer['ebay_offer_id'], product_id))
                    stats['updated'] += 1
                    print(f"   ✅ Updated ID {product_id} → {ebay_item_id}")
                else:
                    stats['skipped'] += 1
                matched = True
                stats['matched'] += 1
        
        # Strategy 2: Match by ebay_item_id (already in DB)
        if not matched:
            cursor.execute('SELECT id FROM products WHERE ebay_item_id = ?', (ebay_item_id,))
            row = cursor.fetchone()
            if row:
                matched = True
                stats['matched'] += 1
                stats['skipped'] += 1
        
        # Strategy 3: Unmatched (create placeholder or log)
        if not matched:
            stats['new_unmatched'] += 1
            print(f"   ⚠️  Unmatched: {ebay_item_id} (SKU: {sku}, Title: {offer['title'][:40]}...)")
    
    conn.commit()
    conn.close()
    
    return stats


def generate_sync_report(stats, offers_data, db_path='data/dropshipping.db'):
    """Generate sync report"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get DB stats
    cursor.execute('SELECT COUNT(*) FROM products WHERE ebay_item_id IS NOT NULL AND is_listed = 1')
    db_count = cursor.fetchone()[0]
    
    conn.close()
    
    report = f"""
{'='*80}
EBAY → DATABASE SYNC REPORT
{'='*80}

eBay Active Offers:        {stats['total_offers']}
Database Active Products:  {db_count}

Sync Results:
  ✅ Matched:              {stats['matched']}
  🔄 Updated:              {stats['updated']}
  ⚠️  New Unmatched:        {stats['new_unmatched']}
  ⏭️  Skipped (no change): {stats['skipped']}

Sync Gap: {stats['total_offers'] - db_count} listings not in database

{'='*80}
"""
    
    return report


def run_sync(dry_run=False):
    """
    Main sync function
    
    Args:
        dry_run: If True, fetch but don't update database
    """
    print(f"\n{'='*80}")
    print(f"EBAY → DATABASE SYNC JOB")
    print(f"{'='*80}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Dry run: {dry_run}\n")
    
    # Initialize eBay client
    ebay = eBayAPIClient()
    
    # Fetch all offers
    print("📥 STEP 1: Fetch eBay Offers")
    offers = fetch_all_ebay_offers(ebay, limit=100)
    print(f"   Total offers fetched: {len(offers)}\n")
    
    if not offers:
        print("❌ No offers fetched. Check eBay API access.")
        return
    
    # Parse offers
    print("🔄 STEP 2: Parse Offers")
    parsed_offers = []
    for offer in offers:
        try:
            parsed = parse_offer_to_product(offer)
            parsed_offers.append(parsed)
        except Exception as e:
            print(f"   ⚠️  Parse error: {e}")
    
    print(f"   Parsed: {len(parsed_offers)} offers\n")
    
    # Sync to database
    if not dry_run:
        print("💾 STEP 3: Sync to Database")
        stats = sync_to_database(parsed_offers)
    else:
        print("🔍 STEP 3: Dry Run (no database updates)")
        stats = {
            'total_offers': len(parsed_offers),
            'matched': 0,
            'updated': 0,
            'new_unmatched': 0,
            'skipped': 0
        }
    
    # Generate report
    print("\n📊 STEP 4: Generate Report")
    report = generate_sync_report(stats, parsed_offers)
    print(report)
    
    # Save report
    report_path = PROJECT_ROOT / 'data' / 'ebay_sync_report.txt'
    report_path.write_text(report, encoding='utf-8')
    print(f"Report saved: {report_path}")
    
    return stats


if __name__ == '__main__':
    import sys
    
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv
    
    try:
        run_sync(dry_run=dry_run)
    except Exception as e:
        print(f"\n❌ SYNC FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
