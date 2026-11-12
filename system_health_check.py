"""
COMPLETE SYSTEM HEALTH CHECK & DEBUG
Tüm sistemi test eder, hataları bulur ve raporlar
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')

print("=" * 80)
print("🔍 COMPLETE SYSTEM HEALTH CHECK")
print("=" * 80)
print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

# ============================================================================
# TEST 1: PROJECT STRUCTURE
# ============================================================================
print("\n" + "=" * 80)
print("TEST 1: PROJECT STRUCTURE")
print("=" * 80)

required_files = [
    'src/api/aliexpress_client.py',
    'src/api/ebay_client.py',
    'data/dropshipping.db',
    '.env',
    'autonomous_scheduler_FULL.py',
    'auto_database_sync.py',
    'create_listings_bulletproof_full.py',
]

for file_path in required_files:
    if Path(file_path).exists():
        print(f"✅ {file_path}")
        results['passed'].append(f"File exists: {file_path}")
    else:
        print(f"❌ {file_path} - MISSING!")
        results['failed'].append(f"Missing file: {file_path}")

# ============================================================================
# TEST 2: DATABASE CONNECTION & SCHEMA
# ============================================================================
print("\n" + "=" * 80)
print("TEST 2: DATABASE CONNECTION & SCHEMA")
print("=" * 80)

try:
    db_path = "data/dropshipping.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"✅ Database connection: {db_path}")
    results['passed'].append("Database connection successful")
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    required_tables = ['products', 'sales', 'order_fulfillment', 'tracking_updates', 
                      'customer_communications', 'strategy_performance', 'learning_insights']
    
    existing_tables = [t[0] for t in tables]
    
    for table in required_tables:
        if table in existing_tables:
            print(f"✅ Table: {table}")
            results['passed'].append(f"Table exists: {table}")
        else:
            print(f"⚠️  Table missing: {table}")
            results['warnings'].append(f"Table missing: {table}")
    
    # Check products count
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]
    print(f"📊 Total products in database: {product_count}")
    
    # Check active products
    cursor.execute("SELECT COUNT(*) FROM products WHERE status IN ('active', 'AUTO_SYNCED', 'MANUAL_IMPORT')")
    active_count = cursor.fetchone()[0]
    print(f"✅ Active products: {active_count}")
    
    if active_count > 0:
        results['passed'].append(f"Active products: {active_count}")
    else:
        results['warnings'].append("No active products found")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Database error: {e}")
    results['failed'].append(f"Database error: {e}")

# ============================================================================
# TEST 3: ENVIRONMENT VARIABLES
# ============================================================================
print("\n" + "=" * 80)
print("TEST 3: ENVIRONMENT VARIABLES")
print("=" * 80)

try:
    from dotenv import load_dotenv
    load_dotenv()
    
    required_env_vars = [
        'ALIEXPRESS_APP_KEY',
        'ALIEXPRESS_APP_SECRET',
        'EBAY_ACCESS_TOKEN',
        'EBAY_REFRESH_TOKEN',
    ]
    
    for var in required_env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * 20} (hidden)")
            results['passed'].append(f"Env var exists: {var}")
        else:
            print(f"❌ {var}: MISSING!")
            results['failed'].append(f"Missing env var: {var}")
            
except Exception as e:
    print(f"❌ Environment error: {e}")
    results['failed'].append(f"Environment error: {e}")

# ============================================================================
# TEST 4: ALIEXPRESS API CONNECTION
# ============================================================================
print("\n" + "=" * 80)
print("TEST 4: ALIEXPRESS API CONNECTION")
print("=" * 80)

try:
    from src.api.aliexpress_client import AliExpressAPIClient
    
    ali = AliExpressAPIClient()
    print("✅ AliExpress client initialized")
    results['passed'].append("AliExpress client initialized")
    
    # Test API call (might fail due to quota)
    try:
        test_result = ali.search_product_page('test', page_size=1)
        print("✅ AliExpress API call successful")
        results['passed'].append("AliExpress API working")
    except Exception as e:
        error_msg = str(e)
        if 'business error' in error_msg or 'quota' in error_msg.lower():
            print("⚠️  AliExpress API quota exceeded (expected)")
            results['warnings'].append("AliExpress API quota exceeded")
        else:
            print(f"❌ AliExpress API error: {e}")
            results['failed'].append(f"AliExpress API error: {e}")
            
except Exception as e:
    print(f"❌ AliExpress client error: {e}")
    results['failed'].append(f"AliExpress client error: {e}")

# ============================================================================
# TEST 5: EBAY API CONNECTION
# ============================================================================
print("\n" + "=" * 80)
print("TEST 5: EBAY API CONNECTION")
print("=" * 80)

try:
    from src.api.ebay_client import eBayAPIClient
    
    ebay = eBayAPIClient()
    print("✅ eBay client initialized")
    results['passed'].append("eBay client initialized")
    
    # Test token validity
    try:
        token_valid = ebay.check_token_validity()
        if token_valid:
            print("✅ eBay token valid")
            results['passed'].append("eBay token valid")
        else:
            print("⚠️  eBay token might be expired")
            results['warnings'].append("eBay token validation uncertain")
    except Exception as e:
        print(f"⚠️  eBay token check failed: {e}")
        results['warnings'].append(f"eBay token check failed: {e}")
        
except Exception as e:
    print(f"❌ eBay client error: {e}")
    results['failed'].append(f"eBay client error: {e}")

# ============================================================================
# TEST 6: AUTONOMOUS MODULES
# ============================================================================
print("\n" + "=" * 80)
print("TEST 6: AUTONOMOUS MODULES")
print("=" * 80)

modules = [
    'sales_tracker',
    'auto_order_fulfillment',
    'auto_tracking_management',
    'auto_inventory_sync',
    'auto_customer_communication',
    'auto_performance_optimization',
    'auto_database_sync',
]

for module in modules:
    module_path = f"{module}.py"
    if Path(module_path).exists():
        print(f"✅ {module_path}")
        results['passed'].append(f"Module exists: {module_path}")
        
        # Try to import
        try:
            __import__(module)
            print(f"   ✅ Import successful")
            results['passed'].append(f"Module imports: {module}")
        except Exception as e:
            print(f"   ⚠️  Import warning: {e}")
            results['warnings'].append(f"Module import issue: {module} - {e}")
    else:
        print(f"❌ {module_path} - MISSING!")
        results['failed'].append(f"Missing module: {module_path}")

# ============================================================================
# TEST 7: RUNNING PROCESSES
# ============================================================================
print("\n" + "=" * 80)
print("TEST 7: RUNNING PROCESSES")
print("=" * 80)

import subprocess

try:
    # Check for autonomous_scheduler_FULL.py
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'],
        capture_output=True,
        text=True
    )
    
    if 'python.exe' in result.stdout:
        print("✅ Python processes found")
        
        # Try to find autonomous scheduler
        result2 = subprocess.run(
            ['wmic', 'process', 'where', 'name="python.exe"', 'get', 'commandline'],
            capture_output=True,
            text=True
        )
        
        if 'autonomous_scheduler_FULL.py' in result2.stdout:
            print("✅ Autonomous scheduler is running")
            results['passed'].append("Autonomous scheduler running")
        else:
            print("⚠️  Autonomous scheduler not found")
            results['warnings'].append("Autonomous scheduler not running")
    else:
        print("⚠️  No Python processes found")
        results['warnings'].append("No Python processes running")
        
except Exception as e:
    print(f"⚠️  Process check failed: {e}")
    results['warnings'].append(f"Process check failed: {e}")

# ============================================================================
# TEST 8: LOG FILES
# ============================================================================
print("\n" + "=" * 80)
print("TEST 8: LOG FILES")
print("=" * 80)

log_dir = Path('logs')
if log_dir.exists():
    print(f"✅ Log directory exists")
    results['passed'].append("Log directory exists")
    
    log_files = list(log_dir.glob('*.log'))
    print(f"📊 Found {len(log_files)} log files")
    
    for log_file in log_files:
        print(f"   • {log_file.name}")
else:
    print("⚠️  Log directory missing")
    results['warnings'].append("Log directory missing")

# ============================================================================
# TEST 9: CRITICAL FIXES
# ============================================================================
print("\n" + "=" * 80)
print("TEST 9: CRITICAL FIXES")
print("=" * 80)

critical_files = [
    'aliexpress_diversity_fix.py',
    'auto_database_sync.py',
    'AUTO_DATABASE_SYNC_DOCUMENTATION.md',
    'ALIEXPRESS_FIX_DOCUMENTATION.md',
]

for file_path in critical_files:
    if Path(file_path).exists():
        print(f"✅ {file_path}")
        results['passed'].append(f"Fix file exists: {file_path}")
    else:
        print(f"⚠️  {file_path} - Missing")
        results['warnings'].append(f"Missing fix file: {file_path}")

# ============================================================================
# FINAL REPORT
# ============================================================================
print("\n" + "=" * 80)
print("🎯 FINAL HEALTH REPORT")
print("=" * 80)
print()

print(f"✅ PASSED:   {len(results['passed'])} tests")
print(f"⚠️  WARNINGS: {len(results['warnings'])} items")
print(f"❌ FAILED:   {len(results['failed'])} tests")
print()

if results['failed']:
    print("❌ CRITICAL FAILURES:")
    for fail in results['failed']:
        print(f"   • {fail}")
    print()

if results['warnings']:
    print("⚠️  WARNINGS:")
    for warn in results['warnings']:
        print(f"   • {warn}")
    print()

# Overall health score
total_tests = len(results['passed']) + len(results['warnings']) + len(results['failed'])
passed_tests = len(results['passed'])
health_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0

print("=" * 80)
print(f"🏥 OVERALL SYSTEM HEALTH: {health_score:.1f}%")
print("=" * 80)

if health_score >= 90:
    print("✅ EXCELLENT - System is healthy!")
elif health_score >= 70:
    print("⚠️  GOOD - Minor issues need attention")
elif health_score >= 50:
    print("⚠️  FAIR - Several issues need fixing")
else:
    print("❌ POOR - Critical issues require immediate attention")

print()
print("Test completed:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
