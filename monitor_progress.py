#!/usr/bin/env python
"""
Real-time Progress Monitor for Bulletproof Listing Creation
"""

import sqlite3
import time
import os
from datetime import datetime

def monitor_progress():
    """
    Monitor database for new listings and show real-time progress
    """
    print("=" * 70)
    print("📊 MONDEORA ULTRA - REAL-TIME PROGRESS MONITOR")
    print("=" * 70)
    print()
    print("⏳ Bulletproof listing creation is running in background...")
    print("   This will take ~15 minutes for 10 products")
    print()
    print("📈 Monitoring database for new listings...")
    print()
    
    db_path = "data/dropshipping.db"
    
    # Get initial count
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku_id LIKE 'AUTO-PET-%'")
        initial_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✅ Initial AUTO products: {initial_count}")
        print()
        print("Waiting for new listings...")
        print("-" * 70)
        print()
        
        last_count = initial_count
        checks = 0
        max_checks = 60  # 60 checks x 15 sec = 15 minutes
        
        while checks < max_checks:
            time.sleep(15)  # Check every 15 seconds
            checks += 1
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get current count
                cursor.execute("SELECT COUNT(*) FROM products WHERE sku_id LIKE 'AUTO-PET-%'")
                current_count = cursor.fetchone()[0]
                
                if current_count > last_count:
                    # New products added!
                    new_products = current_count - last_count
                    
                    # Get details of new products
                    cursor.execute("""
                        SELECT sku_id, title, ebay_price, ebay_item_id, created_at
                        FROM products 
                        WHERE sku_id LIKE 'AUTO-PET-%'
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (new_products,))
                    
                    products = cursor.fetchall()
                    
                    for sku, title, price, listing_id, created in products:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}] ✅ NEW LISTING CREATED!")
                        print(f"   SKU: {sku}")
                        print(f"   Title: {title[:60]}...")
                        print(f"   Price: €{price:.2f}")
                        print(f"   eBay ID: {listing_id}")
                        print()
                    
                    last_count = current_count
                    
                    # Progress bar
                    progress = (current_count - initial_count)
                    target = 10
                    percentage = min(100, int((progress / target) * 100))
                    bar = "█" * (percentage // 5) + "░" * (20 - (percentage // 5))
                    print(f"📊 Progress: [{bar}] {percentage}% ({progress}/{target})")
                    print()
                
                conn.close()
                
                # Check if we reached target
                if current_count - initial_count >= 10:
                    print("=" * 70)
                    print("🎉 TARGET REACHED! 10 listings created!")
                    print("=" * 70)
                    break
                    
            except Exception as e:
                print(f"⚠️  Error checking database: {e}")
                continue
        
        # Final summary
        print()
        print("=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku_id LIKE 'AUTO-PET-%'")
        final_count = cursor.fetchone()[0]
        
        new_listings = final_count - initial_count
        
        print(f"✅ Total AUTO products: {final_count}")
        print(f"🆕 New listings created: {new_listings}")
        print()
        
        if new_listings > 0:
            # Get all new listings
            cursor.execute("""
                SELECT sku_id, title, ebay_price, margin_percent, ebay_item_id
                FROM products 
                WHERE sku_id LIKE 'AUTO-PET-%'
                ORDER BY created_at DESC
                LIMIT ?
            """, (new_listings,))
            
            listings = cursor.fetchall()
            
            print("📝 NEW LISTINGS:")
            print("-" * 70)
            total_value = 0
            for i, (sku_id, title, price, margin, ebay_id) in enumerate(listings, 1):
                profit = (price * (margin / 100)) if margin and price else 0
                print(f"{i}. {title[:50]}...")
                print(f"   Price: €{price:.2f} | Margin: {margin:.1f}% | eBay: {ebay_id}")
                total_value += price if price else 0
            
            print("-" * 70)
            print(f"💰 Total Listing Value: €{total_value:.2f}")
            print()
        
        conn.close()
        
        print("🚀 Next Steps:")
        print("   1. Check eBay.de - listings should be live")
        print("   2. Launch dashboard: python launch_dashboard.py")
        print("   3. Create more listings or start automation")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("   Check that data/dropshipping.db exists")

if __name__ == "__main__":
    try:
        monitor_progress()
    except KeyboardInterrupt:
        print("\n\n⏸️  Monitoring stopped (listings still creating in background)")
