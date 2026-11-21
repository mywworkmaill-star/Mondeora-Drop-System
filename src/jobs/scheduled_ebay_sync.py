"""
Scheduled eBay Sync Job Configuration
Runs daily at 00:00 to verify database ← → eBay consistency
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.jobs.ebay_verification_job import run_verification

def main():
    """Main entry point for scheduled job"""
    print("🔄 Starting scheduled eBay verification job...")
    
    try:
        # Run verification (not dry-run, will update database)
        stats = run_verification(dry_run=False, limit=None)
        
        # Check if any critical issues
        if stats['verified_inactive'] > 10:
            print(f"\n⚠️  WARNING: {stats['verified_inactive']} listings are inactive!")
            print("   This may indicate a sync problem.")
        
        if stats['errors'] > 5:
            print(f"\n⚠️  WARNING: {stats['errors']} verification errors!")
            print("   Check eBay API access.")
        
        print("\n✅ Scheduled job completed successfully")
        return 0
        
    except Exception as e:
        print(f"\n❌ Scheduled job failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
