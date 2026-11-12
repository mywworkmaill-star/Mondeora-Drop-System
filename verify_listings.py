#!/usr/bin/env python
"""
Verify existing eBay listings are live
"""

import sys
sys.path.insert(0, '.')

from src.api.ebay_client import eBayRESTClient

def verify_listings():
    print("=" * 70)
    print("🔍 VERIFYING eBay LISTINGS")
    print("=" * 70)
    print()
    
    ebay = eBayRESTClient()
    
    # Get our listings from database
    import sqlite3
    conn = sqlite3.connect('data/dropshipping.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sku_id, title, ebay_item_id, ebay_price
        FROM products
        WHERE sku_id LIKE 'AUTO-PET-%'
        ORDER BY created_at DESC
    """)
    
    listings = cursor.fetchall()
    conn.close()
    
    print(f"Checking {len(listings)} listings...\n")
    
    live_count = 0
    total_value = 0
    
    for sku, title, ebay_id, price in listings:
        try:
            # Try to get the listing from eBay
            result = ebay.get_inventory_item(sku)
            
            if result and result.get('sku') == sku:
                status = "✅ LIVE"
                live_count += 1
                total_value += price
            else:
                status = "⚠️  UNKNOWN"
                
            print(f"{status} | {title[:50]}...")
            print(f"      eBay ID: {ebay_id} | Price: €{price:.2f}")
            print(f"      URL: https://www.ebay.de/itm/{ebay_id}")
            print()
            
        except Exception as e:
            print(f"❌ ERROR | {title[:50]}...")
            print(f"      Error: {str(e)}")
            print()
    
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"Total Listings:    {len(listings)}")
    print(f"Live on eBay:      {live_count}")
    print(f"Total Value:       €{total_value:.2f}")
    print()
    
    if live_count == len(listings):
        print("✅ ALL LISTINGS ARE LIVE! System working perfectly!")
    elif live_count > 0:
        print(f"⚠️  {len(listings) - live_count} listings may need attention")
    else:
        print("❌ No listings verified - check eBay API connection")
    
    print()
    print("🚀 Next Steps:")
    if live_count > 0:
        print("   1. ✅ Existing listings are working")
        print("   2. 🎯 Create more with different keywords:")
        print("      python create_listings_bulletproof_full.py --keyword 'cat toy' --count 10")
        print("   3. 📊 Launch dashboard to monitor:")
        print("      python launch_dashboard.py")
    else:
        print("   1. Check eBay API token is valid")
        print("   2. Manually verify listings on eBay.de")
        print("   3. Run: python refresh_ebay_token.py")

if __name__ == "__main__":
    try:
        verify_listings()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
