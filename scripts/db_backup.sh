#!/bin/bash
# Test workflow script - Phase 3: Database Backup

echo "==================================================================="
echo "💾 DATABASE BACKUP"
echo "==================================================================="

DB_FILE="data/dropshipping.db"
BACKUP_DIR="data/backups"
BACKUP_FILE="$BACKUP_DIR/dropshipping_$(date +%Y%m%d_%H%M%S).db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Copy database
if [ -f "$DB_FILE" ]; then
    cp "$DB_FILE" "$BACKUP_FILE"
    echo "✅ Database backed up: $BACKUP_FILE"
else
    echo "❌ Database not found"
    exit 1
fi

echo ""
echo "✅ Backup complete!"
echo ""

exit 0
