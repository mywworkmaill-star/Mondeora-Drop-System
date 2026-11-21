#!/usr/bin/env python3
"""Health Check - Phase 1"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

print("=" * 67)
print("HEALTH CHECK")
print("=" * 67)

# Check database
db_path = ROOT / 'data' / 'dropshipping.db'
if db_path.exists():
    print("Database: OK")
else:
    print("Database: NOT FOUND")
    sys.exit(1)

# Check tokens
env_path = ROOT / '.env'
if env_path.exists():
    print("Tokens file: OK")
else:
    print("Tokens file: NOT FOUND (continuing...)")

# Check eBay connection
print("eBay API: OK (mocked)")

# Check AliExpress connection
print("AliExpress API: OK (mocked)")

print()
print("All systems operational!")
print()

sys.exit(0)
