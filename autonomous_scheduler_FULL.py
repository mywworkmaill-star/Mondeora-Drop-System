#!/usr/bin/env python
"""
100% AUTONOMOUS DROPSHIPPING SCHEDULER
Complete hands-free automation (except payment methods)
"""

import sys
import os
sys.path.insert(0, '.')

import time
import schedule
from datetime import datetime
import subprocess

# Import all automation modules
try:
    from sales_tracker import SalesTracker
    SALES_TRACKER_AVAILABLE = True
except ImportError:
    SALES_TRACKER_AVAILABLE = False
    print("⚠️  Sales tracker not available")

try:
    from auto_order_fulfillment import AutoOrderFulfillment
    ORDER_FULFILLMENT_AVAILABLE = True
except ImportError:
    ORDER_FULFILLMENT_AVAILABLE = False
    print("⚠️  Order fulfillment not available")

try:
    from auto_tracking_management import AutoTrackingManagement
    TRACKING_MANAGEMENT_AVAILABLE = True
except ImportError:
    TRACKING_MANAGEMENT_AVAILABLE = False
    print("⚠️  Tracking management not available")

try:
    from auto_inventory_sync import AutoInventorySync
    INVENTORY_SYNC_AVAILABLE = True
except ImportError:
    INVENTORY_SYNC_AVAILABLE = False
    print("⚠️  Inventory sync not available")

try:
    from auto_customer_communication import AutoCustomerCommunication
    CUSTOMER_COMM_AVAILABLE = True
except ImportError:
    CUSTOMER_COMM_AVAILABLE = False
    print("⚠️  Customer communication not available")

try:
    from auto_performance_optimization import AutoPerformanceOptimization
    PERFORMANCE_OPT_AVAILABLE = True
except ImportError:
    PERFORMANCE_OPT_AVAILABLE = False
    print("⚠️  Performance optimization not available")

try:
    from auto_database_sync import AutoDatabaseSync
    DATABASE_SYNC_AVAILABLE = True
except ImportError:
    DATABASE_SYNC_AVAILABLE = False
    print("⚠️  Database sync not available")

try:
    from self_improving_system import SelfImprovingSystem
    SELF_IMPROVEMENT_AVAILABLE = True
except ImportError:
    SELF_IMPROVEMENT_AVAILABLE = False
    print("⚠️  Self-improvement not available")

try:
    from self_expanding_ai import SelfExpandingAI
    SELF_EXPANDING_AVAILABLE = True
except ImportError:
    SELF_EXPANDING_AVAILABLE = False
    print("⚠️  Self-expanding AI not available")


# Token refresh timing (eBay access token lifetime is ~7200s)
TOKEN_CHECK_INTERVAL_MINUTES = 30
TOKEN_REFRESH_THRESHOLD_SECONDS = 30 * 60


def _env_flag(name):
    from src.runtime import read_config
    return str(read_config().get(name, '')).lower() == 'true'


def _live_writes_ok():
    from src.runtime import writes_allowed
    return writes_allowed()


def _ready_for_live():
    """Legacy jobs may only create listings/orders when the readiness gate passed."""
    import json
    from pathlib import Path
    try:
        report = json.loads((Path(__file__).resolve().parent / 'data/readiness_report.json').read_text(encoding='utf-8'))
        return bool(report.get('ready_for_live')) and _live_writes_ok()
    except Exception:
        return False


# job name -> predicate that must be true, else the job is skipped (fail-closed)
JOB_GATES = {
    'run_auto_product_listing': ('live listing creation needs readiness gate', _ready_for_live),
    'run_order_fulfillment': ('order processing needs readiness gate', _ready_for_live),
    'run_tracking_update': ('tracking upload needs readiness gate', _ready_for_live),
    'run_customer_communication': ('buyer messages need live-write switches', _live_writes_ok),
    'run_social_media_automation': ('public posts need live-write switches', _live_writes_ok),
    'run_improvement_cycle': ('self-modifying code needs ALLOW_SELF_MODIFICATION=true', lambda: _env_flag('ALLOW_SELF_MODIFICATION')),
    'run_expansion_cycle': ('self-modifying code needs ALLOW_SELF_MODIFICATION=true', lambda: _env_flag('ALLOW_SELF_MODIFICATION')),
}


def _gated(fn, reason, predicate):
    import functools
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            allowed = predicate()
        except Exception:
            allowed = False
        if not allowed:
            print(f"🔒 {fn.__name__} skipped: {reason}")
            return None
        return fn(*args, **kwargs)
    return wrapper


class FullAutonomousScheduler:
    """
    100% Autonomous Dropshipping Scheduler
    Handles everything from product sourcing to customer feedback
    """
    
    def __init__(self):
        self.python_path = "C:/Program Files/Python311/python.exe"
        self.project_dir = "C:/Users/Administrator/Desktop/Mondeora-Drop-System"
        
        # Initialize all automation modules
        self.sales_tracker = SalesTracker() if SALES_TRACKER_AVAILABLE else None
        self.order_fulfillment = AutoOrderFulfillment() if ORDER_FULFILLMENT_AVAILABLE else None
        self.tracking_management = AutoTrackingManagement() if TRACKING_MANAGEMENT_AVAILABLE else None
        self.inventory_sync = AutoInventorySync() if INVENTORY_SYNC_AVAILABLE else None
        self.customer_comm = AutoCustomerCommunication() if CUSTOMER_COMM_AVAILABLE else None
        self.performance_opt = AutoPerformanceOptimization() if PERFORMANCE_OPT_AVAILABLE else None
        self.database_sync = AutoDatabaseSync() if DATABASE_SYNC_AVAILABLE else None
        self.ai_improvement = SelfImprovingSystem() if SELF_IMPROVEMENT_AVAILABLE else None
        self.ai_expansion = SelfExpandingAI() if SELF_EXPANDING_AVAILABLE else None
        
        print()
        print("=" * 70)
        print("🤖 100% AUTONOMOUS DROPSHIPPING SYSTEM")
        print("=" * 70)
        print()
        print("✅ Modules loaded:")
        print(f"   Sales Tracking:          {'✅' if self.sales_tracker else '❌'}")
        print(f"   Order Fulfillment:       {'✅' if self.order_fulfillment else '❌'}")
        print(f"   Tracking Management:     {'✅' if self.tracking_management else '❌'}")
        print(f"   Inventory Sync:          {'✅' if self.inventory_sync else '❌'}")
        print(f"   Customer Communication:  {'✅' if self.customer_comm else '❌'}")
        print(f"   Performance Optimization:{'✅' if self.performance_opt else '❌'}")
        print(f"   Database Sync:           {'✅' if self.database_sync else '❌'}")
        print(f"   AI Improvement:          {'✅' if self.ai_improvement else '❌'}")
        print(f"   AI Self-Expansion:       {'✅' if self.ai_expansion else '❌'} 🚀 NEW!")
        print()
    
    # ===== CORE AUTOMATION METHODS =====
    
    def run_improvement_cycle(self):
        """Run AI learning and improvement cycle"""
        print()
        print("=" * 70)
        print(f"🤖 AI IMPROVEMENT CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        try:
            # Run self-improvement (learns from data)
            if self.ai_improvement:
                self.ai_improvement.run_improvement_cycle()
            else:
                result = subprocess.run(
                    [self.python_path, "self_improving_system.py"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print(result.stdout)
            
            print("✅ Improvement cycle completed!")
            
        except Exception as e:
            print(f"❌ Improvement error: {e}")
    
    def run_expansion_cycle(self):
        """Run AI self-expansion cycle (adds new features)"""
        print()
        print("=" * 70)
        print(f"🚀 AI EXPANSION CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        try:
            # Run self-expansion (identifies and queues new features)
            if self.ai_expansion:
                self.ai_expansion.run_expansion_cycle()
            else:
                result = subprocess.run(
                    [self.python_path, "self_expanding_ai.py"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                print(result.stdout)
            
            print("✅ Expansion cycle completed!")
            
        except Exception as e:
            print(f"❌ Expansion error: {e}")
    
    def run_social_media_automation(self):
        """Check social media optimal posting times"""
        print()
        print("=" * 70)
        print(f"📱 SOCIAL MEDIA CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        hour = datetime.now().hour
        
        if hour in [10, 15, 21]:
            print(f"⏰ OPTIMAL POSTING TIME! ({hour}:00)")
            print("   💡 Tip: This is a great time to post on social media!")
        else:
            print(f"⏳ Next optimal time: ", end="")
            next_times = [10, 15, 21]
            next_hour = min([t for t in next_times if t > hour], default=next_times[0])
            print(f"{next_hour}:00")
    
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
        
        # Select keyword based on hour
        hour = datetime.now().hour
        keyword = keywords[hour % len(keywords)]
        
        print(f"🔍 Using keyword: '{keyword}'")
        print()
        
        try:
            result = subprocess.run(
                [self.python_path, "create_listings_bulletproof_full.py", 
                 "--keyword", keyword, "--count", "5"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            print(result.stdout)
            
            if result.returncode == 0:
                print("✅ Auto product listing completed!")
            else:
                print("⚠️  Product listing finished with warnings")
                    
        except subprocess.TimeoutExpired:
            print("⏰ Product listing timeout - will retry next cycle")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def run_sales_check(self):
        """Check for new eBay sales"""
        if not self.sales_tracker:
            return
        
        try:
            new_sales = self.sales_tracker.run_check_cycle()
            
            if new_sales:
                print(f"🎉 {len(new_sales)} NEW SALE(S) DETECTED!")
                
                for sale in new_sales:
                    self.sales_tracker.send_notification(sale)
                    
        except Exception as e:
            print(f"❌ Sales check error: {e}")
    
    def run_order_fulfillment(self):
        """Process unfulfilled orders - place AliExpress orders"""
        if not self.order_fulfillment:
            return
        
        try:
            self.order_fulfillment.process_pending_orders()
        except Exception as e:
            print(f"❌ Order fulfillment error: {e}")
    
    def run_tracking_update(self):
        """Get tracking numbers and update eBay"""
        if not self.tracking_management:
            return
        
        try:
            self.tracking_management.process_pending_tracking()
        except Exception as e:
            print(f"❌ Tracking management error: {e}")
    
    def run_inventory_sync(self):
        """Daily inventory synchronization"""
        if not self.inventory_sync:
            return
        
        try:
            self.inventory_sync.run_daily_sync()
        except Exception as e:
            print(f"❌ Inventory sync error: {e}")
    
    def run_customer_communication(self):
        """Send customer emails/messages"""
        if not self.customer_comm:
            return
        
        try:
            self.customer_comm.process_communications()
        except Exception as e:
            print(f"❌ Customer communication error: {e}")
    
    def run_performance_optimization(self):
        """Optimize listings for better performance"""
        if not self.performance_opt:
            return
        
    def refresh_ebay_token(self):
        """Auto-refresh eBay OAuth token before expiry"""
        try:
            from src.api.ebay_client import eBayAPIClient
            from datetime import datetime
            import time
            import json
            from pathlib import Path
            
            ebay = eBayAPIClient()
            metadata_path = Path('data/ebay_oauth_metadata.json')
            
            # Check if token needs refresh (refresh 5 minutes before expiry)
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                
                expires_at = metadata.get('expires_at', 0)
                now = time.time()
                time_until_expiry = expires_at - now
                
                # Refresh if less than 30 minutes remaining (check interval is 30 min)
                if time_until_expiry < TOKEN_REFRESH_THRESHOLD_SECONDS:
                    print(f"🔄 eBay token expiring in {time_until_expiry/60:.1f} minutes - refreshing...")
                    result = ebay.refresh_access_token(force=True)
                    
                    if result.get('success'):
                        print(f"✅ eBay token refreshed successfully")
                        print(f"   Expires: {datetime.fromtimestamp(result['expires_at']).strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        print(f"❌ eBay token refresh failed")
                else:
                    print(f"✅ eBay token valid for {time_until_expiry/3600:.1f} hours")
            else:
                # No metadata, try to refresh anyway
                print("⚠️  No eBay token metadata - attempting refresh...")
                result = ebay.refresh_access_token(force=True)
                print(f"   Result: {result.get('success', False)}")
                
        except Exception as e:
            print(f"❌ eBay token refresh error: {e}")
    
    def refresh_aliexpress_token(self):
        """Auto-refresh AliExpress OAuth token"""
        try:
            from pathlib import Path
            import json
            import time
            from datetime import datetime
            
            metadata_path = Path('data/aliexpress_token_refresh_metadata.json')
            
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                
                expires_at = datetime.fromisoformat(metadata['expires_at']).timestamp()
                now = time.time()
                time_until_expiry = expires_at - now
                
                # Refresh if less than 30 minutes remaining (check interval is 30 min)
                if time_until_expiry < TOKEN_REFRESH_THRESHOLD_SECONDS:
                    print(f"🔄 AliExpress token expiring in {time_until_expiry/60:.1f} minutes - refreshing...")
                    
                    # Import and run refresh
                    import sys
                    sys.path.insert(0, '.')
                    from token_auto_refresh_complete import AliExpressRefreshTokenToAccessToken
                    
                    refresher = AliExpressRefreshTokenToAccessToken()
                    result = refresher.refresh_access_token_via_refresh_token()
                    
                    if result:
                        print(f"✅ AliExpress token refreshed successfully")
                    else:
                        print(f"❌ AliExpress token refresh failed")
                else:
                    print(f"✅ AliExpress token valid for {time_until_expiry/3600:.1f} hours")
            else:
                print("⚠️  No AliExpress token metadata found")
                
        except Exception as e:
            print(f"❌ AliExpress token refresh error: {e}")
        
        try:
            self.performance_opt.run_optimization()
        except Exception as e:
            print(f"❌ Performance optimization error: {e}")
    
    def run_database_sync(self):
        """Sync eBay active listings to database"""
        if not self.database_sync:
            return
        
        try:
            print()
            print("=" * 70)
            print("🔄 AUTO DATABASE SYNC STARTING...")
            print("=" * 70)
            result = self.database_sync.sync_ebay_to_database()
            if result:
                print(f"✅ Sync complete: +{result['added']}, ~{result['updated']}, -{result['delisted']}")
        except Exception as e:
            print(f"❌ Database sync error: {e}")
            import traceback
            traceback.print_exc()
    
    # ===== SCHEDULER SETUP =====
    
    def setup_schedule(self):
        """Setup complete automation schedule"""
        print("=" * 70)
        print("⏰ 100% AUTONOMOUS SCHEDULER SETUP")
        print("=" * 70)
        print()
        
        # === REAL-TIME MONITORING (Every 5 minutes) ===
        if self.sales_tracker:
            schedule.every(5).minutes.do(self.run_sales_check)
            print("✅ Sales monitoring: Every 5 minutes")
        
        # === ORDER PROCESSING (Every 10 minutes) ===
        if self.order_fulfillment:
            schedule.every(10).minutes.do(self.run_order_fulfillment)
            print("✅ Order fulfillment: Every 10 minutes")
        
        # === TRACKING UPDATES (Every 30 minutes) ===
        if self.tracking_management:
            schedule.every(30).minutes.do(self.run_tracking_update)
            print("✅ Tracking updates: Every 30 minutes")
        
        # === HOURLY TASKS ===
        schedule.every(1).hours.do(self.run_social_media_automation)
        print("✅ Social media check: Every hour")
        
        if self.customer_comm:
            schedule.every(1).hours.do(self.run_customer_communication)
            print("✅ Customer communication: Every hour")
        
        if self.database_sync:
            schedule.every(1).hours.do(self.run_database_sync)
            print("✅ Database sync: Every hour")
        
        # Token refresh. eBay access tokens last ~2h, so the check interval must be
        # shorter than (lifetime - threshold) or the token expires between checks.
        schedule.every(TOKEN_CHECK_INTERVAL_MINUTES).minutes.do(self.refresh_ebay_token)
        schedule.every(TOKEN_CHECK_INTERVAL_MINUTES).minutes.do(self.refresh_aliexpress_token)
        print(f"✅ Token auto-refresh: Every {TOKEN_CHECK_INTERVAL_MINUTES} min (eBay + AliExpress)")
        
        # === DAILY TASKS ===
        
        # Product listing (SAFE GROWTH - every 6 hours to avoid eBay limits)
        # 4 times per day = 12-20 products/day (safe for seller limits)
        # Gradually increases without triggering spam detection
        schedule.every(6).hours.do(self.run_auto_product_listing)
        print("✅ Auto product listing: Every 6 hours (SAFE mode - 4x/day)")
        
        # Inventory sync (1x daily)
        if self.inventory_sync:
            schedule.every().day.at("03:00").do(self.run_inventory_sync)
            print("✅ Inventory sync: 03:00 daily")
        
        # Performance optimization (1x daily)
        if self.performance_opt:
            schedule.every().day.at("04:00").do(self.run_performance_optimization)
            print("✅ Performance optimization: 04:00 daily")
        
        # AI improvement (every 6 hours)
        schedule.every(6).hours.do(self.run_improvement_cycle)
        print("✅ AI improvement: Every 6 hours")
        
        # AI self-expansion (every 24 hours - adds new features!)
        schedule.every(24).hours.do(self.run_expansion_cycle)
        print("✅ AI self-expansion: Every 24 hours 🚀 NEW!")
        
        # === INITIAL RUN ===
        print()
        print("🚀 Running initial checks...")
        self.run_improvement_cycle()
        
        # Run expansion on first start
        print()
        print("🚀 Checking for new features to add...")
        self.run_expansion_cycle()
        
        print()
        print("=" * 70)
        print("✅ 100% AUTONOMOUS SYSTEM ACTIVE!")
        print("=" * 70)
        print()
        print("📋 Complete Schedule:")
        print("   • Sales monitoring:          Every 5 minutes 💰")
        print("   • Order fulfillment:         Every 10 minutes 📦")
        print("   • Tracking updates:          Every 30 minutes 🚚")
        print("   • Customer communication:    Every hour 📧")
        print("   • Social media check:        Every hour 📱")
        print("   • AI improvement:            Every 6 hours 🤖")
        print("   • AI self-expansion:         Every 24 hours 🚀 NEW!")
        print("   • Product listing:           Every 6 hours (SAFE mode) 🛍️")
        print("   • Inventory sync:            03:00 daily 📦")
        print("   • Performance optimization:  04:00 daily ⚡")
        print()
        print("🤖 System is now 100% autonomous AND self-expanding!")
        print("   → Learns from data (every 6h)")
        print("   → Adds new features automatically (every 24h)")
        print("   (Except payment methods - manual setup required)")
        print("   Press Ctrl+C to stop")
        print()
    
    def run(self):
        """Start autonomous operation"""
        self.setup_schedule()
        
        # Run forever
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


for _name, (_reason, _pred) in JOB_GATES.items():
    setattr(FullAutonomousScheduler, _name, _gated(getattr(FullAutonomousScheduler, _name), _reason, _pred))


if __name__ == "__main__":
    try:
        scheduler = FullAutonomousScheduler()
        scheduler.run()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Autonomous scheduler stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
