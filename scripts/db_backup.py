#!/usr/bin/env python3
"""Database Backup - Phase 3"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

print("=" * 67)
print("DATABASE BACKUP")
print("=" * 67)

db_file = ROOT / 'data' / 'dropshipping.db'
backup_dir = ROOT / 'data' / 'backups'
backup_file = backup_dir / f'dropshipping_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'

# Create backup directory
backup_dir.mkdir(parents=True, exist_ok=True)

# Copy database
if db_file.exists():
    shutil.copy2(db_file, backup_file)
    print(f"Database backed up: {backup_file}")
else:
    print("Database not found")
    sys.exit(1)

print()
print("Backup complete!")
print()

sys.exit(0)
