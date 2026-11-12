#!/usr/bin/env python
"""
AUTONOMOUS SCHEDULER
Runs self-improving system automatically every day
"""

import sys
import os
sys.path.insert(0, '.')

import time
import schedule
from datetime import datetime
import subprocess

# Import sales tracker
try:
    from sales_tracker import SalesTracker
    SALES_TRACKER_AVAILABLE = True
except ImportError:
    SALES_TRACKER_AVAILABLE = False
    print("⚠️  Sales tracker not available")

class AutonomousScheduler:
    """
    Scheduler that runs improvement cycles automatically
    """
    
    def __init__(self):
        self.python_path = "C:/Program Files/Python311/python.exe"
        self.project_dir = "C:/Users/Administrator/Desktop/Mondeora-Drop-System"
        
        # Initialize sales tracker
        if SALES_TRACKER_AVAILABLE:
            try:
                self.sales_tracker = SalesTracker()
                print("✅ Sales tracker initialized!")
            except Exception as e:
                print(f"⚠️  Sales tracker init error: {e}")
                self.sales_tracker = None
        else:
            self.sales_tracker = None
    
    def run_improvement_cycle(self):
        """Run improvement cycle"""
        print()
        print("=" * 70)
        print(f"🤖 AUTONOMOUS RUN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        try:
            result = subprocess.run(
                [self.python_path, "self_improving_system.py"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            print(result.stdout)
            
            if result.returncode == 0:
                print("✅ Improvement cycle completed successfully!")
            else:
                print(f"⚠️  Improvement cycle finished with warnings")
                print(result.stderr)
                
        except Exception as e:
            print(f"❌ Error running improvement cycle: {e}")
    
    def run_social_media_automation(self):
        """Run social media posting if needed"""
        print()
        print("📱 Checking social media automation...")
        print()
        
        # Check if it's time to post
        hour = datetime.now().hour
        
        # Post at 10 AM, 3 PM, 9 PM
        if hour in [10, 15, 21]:
            print(f"✅ Optimal posting time ({hour}:00) - Ready for social media!")
            print("   (Manual trigger or API integration needed)")
        else:
            print(f"⏭️  Not optimal time (current: {hour}:00)")
    
    def run_auto_product_listing(self):
        """Automatically find and list new products"""
        print()
        print("=" * 70)
        print(f"🛍️  AUTO PRODUCT LISTING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        # Rotate keywords for variety
        keywords = [
            "cat toy", "dog toy", "pet accessories",
            "pet grooming", "pet bed", "pet bowl",
            "pet carrier", "pet collar", "pet leash"
        ]
        
        # Select keyword based on hour (different keywords at different times)
        hour = datetime.now().hour
        keyword = keywords[hour % len(keywords)]
        
        print(f"🔍 Using keyword: '{keyword}'")
        print()
        
        try:
            # Run bulletproof listing creator
            result = subprocess.run(
                [self.python_path, "create_listings_bulletproof_full.py", 
                 "--keyword", keyword, "--count", "5"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes
            )
            
            print(result.stdout)
            
            if result.returncode == 0:
                print("✅ Auto product listing completed!")
            else:
                print("⚠️  Product listing finished with warnings")
                if result.stderr:
                    print(result.stderr)
                    
        except subprocess.TimeoutExpired:
            print("⏰ Product listing timeout - will retry next cycle")
        except Exception as e:
            print(f"❌ Error running product listing: {e}")
    
    def run_sales_check(self):
        """Check for new eBay sales"""
        print()
        print("=" * 70)
        print(f"💰 SALES CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        if not self.sales_tracker:
            print("⚠️  Sales tracker not available")
            return
        
        try:
            # Run sales check cycle
            new_sales = self.sales_tracker.run_check_cycle()
            
            if new_sales:
                print(f"🎉 {len(new_sales)} NEW SALE(S) DETECTED!")
                
                # Send notifications for each sale
                for sale in new_sales:
                    self.sales_tracker.send_notification(sale)
                    
            else:
                print("📭 No new sales this cycle")
                
        except Exception as e:
            print(f"❌ Error checking sales: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_schedule(self):
        """Setup automatic schedule"""
        print("=" * 70)
        print("⏰ AUTONOMOUS SCHEDULER SETUP")
        print("=" * 70)
        print()
        
        # Run improvement cycle every 6 hours
        schedule.every(6).hours.do(self.run_improvement_cycle)
        
        # Check social media times every hour
        schedule.every(1).hours.do(self.run_social_media_automation)
        
        # Check for new sales every 5 minutes
        if self.sales_tracker:
            schedule.every(5).minutes.do(self.run_sales_check)
            print("✅ Sales tracking enabled (every 5 minutes)")
        
        # Auto product listing twice daily (9 AM and 8 PM)
        schedule.every().day.at("09:00").do(self.run_auto_product_listing)
        schedule.every().day.at("20:00").do(self.run_auto_product_listing)
        
        # Run initial cycle immediately
        print("🚀 Running initial improvement cycle...")
        self.run_improvement_cycle()
        
        print()
        print("=" * 70)
        print("✅ SCHEDULER ACTIVE!")
        print("=" * 70)
        print()
        print("📋 Schedule:")
        print("   • Improvement cycle: Every 6 hours")
        print("   • Social media check: Every hour")
        print("   • Sales tracking: Every 5 minutes 💰")
        print("   • Optimal post times: 10:00, 15:00, 21:00")
        print("   • Auto product listing: 09:00 & 20:00 daily")
        print()
        print("🤖 System will now run autonomously...")
        print("   Press Ctrl+C to stop")
        print()
    
    def run(self):
        """Start autonomous operation"""
        self.setup_schedule()
        
        # Run forever
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        scheduler = AutonomousScheduler()
        scheduler.run()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Autonomous scheduler stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
