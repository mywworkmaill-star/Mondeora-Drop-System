#!/bin/bash
# MONDEORA CRON JOBS KURULUM
# Otomatik senkronizasyon ve monitoring job'larını kurar

echo "════════════════════════════════════════════════════════════════════════"
echo "🕐 MONDEORA CRON JOBS KURULUM"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Hermes cron directory
CRON_DIR="$HOME/.config/hermes/profiles/default/cron"
mkdir -p "$CRON_DIR"

echo "📁 Cron klasörü: $CRON_DIR"
echo ""

# Python path
PYTHON="/c/Program Files/Python311/python.exe"
PROJECT_DIR="/c/Users/Administrator/Desktop/Mondeora-Drop-System"

# ============================================================================
# 1. Token Auto Refresh (Her saat)
# ============================================================================
cat > "$CRON_DIR/mondeora_token_refresh.yaml" << 'EOF'
name: mondeora_token_refresh
schedule: "0 * * * *"  # Her saat başı
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  "/c/Program Files/Python311/python.exe" test_and_refresh_all_tokens.py
enabled: true
EOF
echo "✅ [1/7] Token refresh job oluşturuldu (hourly)"

# ============================================================================
# 2. Inventory Sync (Her 4 saatte)
# ============================================================================
cat > "$CRON_DIR/mondeora_inventory_sync.yaml" << 'EOF'
name: mondeora_inventory_sync
schedule: "0 */4 * * *"  # Her 4 saatte
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  "/c/Program Files/Python311/python.exe" auto_inventory_sync.py
enabled: true
EOF
echo "✅ [2/7] Inventory sync job oluşturuldu (4h)"

# ============================================================================
# 3. Order Check (Her 15 dakika)
# ============================================================================
cat > "$CRON_DIR/mondeora_order_check.yaml" << 'EOF'
name: mondeora_order_check
schedule: "*/15 * * * *"  # Her 15 dakika
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  "/c/Program Files/Python311/python.exe" order_notification_system.py
enabled: true
EOF
echo "✅ [3/7] Order check job oluşturuldu (15min)"

# ============================================================================
# 4. Price Update (Günlük 03:00)
# ============================================================================
cat > "$CRON_DIR/mondeora_price_update.yaml" << 'EOF'
name: mondeora_price_update
schedule: "0 3 * * *"  # Her gün saat 03:00
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  "/c/Program Files/Python311/python.exe" update_aliexpress_prices.py
enabled: true
EOF
echo "✅ [4/7] Price update job oluşturuldu (daily 03:00)"

# ============================================================================
# 5. Database Backup (Günlük 02:00)
# ============================================================================
cat > "$CRON_DIR/mondeora_db_backup.yaml" << 'EOF'
name: mondeora_db_backup
schedule: "0 2 * * *"  # Her gün saat 02:00
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  mkdir -p data/backups
  timestamp=$(date +%Y%m%d_%H%M%S)
  cp data/dropshipping.db "data/backups/dropshipping_${timestamp}.db"
  # Son 7 gün dışındaki yedekleri sil
  find data/backups -name "dropshipping_*.db" -mtime +7 -delete
enabled: true
EOF
echo "✅ [5/7] Database backup job oluşturuldu (daily 02:00)"

# ============================================================================
# 6. System Health Check (Her saat)
# ============================================================================
cat > "$CRON_DIR/mondeora_health_check.yaml" << 'EOF'
name: mondeora_health_check
schedule: "30 * * * *"  # Her saat 30. dakika
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  "/c/Program Files/Python311/python.exe" -m pytest tests -q --tb=no
enabled: true
EOF
echo "✅ [6/7] Health check job oluşturuldu (hourly)"

# ============================================================================
# 7. Log Cleanup (Haftalık Pazar 04:00)
# ============================================================================
cat > "$CRON_DIR/mondeora_log_cleanup.yaml" << 'EOF'
name: mondeora_log_cleanup
schedule: "0 4 * * 0"  # Her Pazar saat 04:00
command: |
  cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
  # 30 gün önceki logları sil
  find logs -name "*.log" -mtime +30 -delete
enabled: true
EOF
echo "✅ [7/7] Log cleanup job oluşturuldu (weekly Sunday 04:00)"

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "✅ CRON JOBS KURULUM TAMAMLANDI"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "📋 Oluşturulan Job'lar:"
echo "   1. mondeora_token_refresh      (Her saat - Token yenileme)"
echo "   2. mondeora_inventory_sync     (4 saatte - Stok senkronizasyonu)"
echo "   3. mondeora_order_check        (15 dakika - Sipariş kontrolü)"
echo "   4. mondeora_price_update       (Günlük - Fiyat güncelleme)"
echo "   5. mondeora_db_backup          (Günlük - Veritabanı yedek)"
echo "   6. mondeora_health_check       (Her saat - Sistem kontrolü)"
echo "   7. mondeora_log_cleanup        (Haftalık - Log temizliği)"
echo ""
echo "🔍 Job'ları kontrol et:"
echo "   ls -la $CRON_DIR"
echo ""
echo "⚠️  NOT: Hermes'i restart etmeniz gerekebilir"
echo "════════════════════════════════════════════════════════════════════════"
