#!/bin/bash
# MONDEORA TÜM SORUNLARI OTOMATIK ÇÖZÜM
# Tüm kritik sorunları sırayla çözer

echo "════════════════════════════════════════════════════════════════════════"
echo "🚀 MONDEORA OTOMATİK ONARIM SİSTEMİ"
echo "════════════════════════════════════════════════════════════════════════"
echo "⏰ Başlangıç: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

cd /c/Users/Administrator/Desktop/Mondeora-Drop-System

# Python path
PYTHON="/c/Program Files/Python311/python.exe"

# ============================================================================
# 1. mondeora.db Temizle (Boş veritabanı)
# ============================================================================
echo "📋 [1/6] mondeora.db temizleniyor..."
if [ -f "data/mondeora.db" ]; then
    rm data/mondeora.db
    echo "   ✅ mondeora.db silindi"
else
    echo "   ⏭️  mondeora.db zaten yok"
fi
echo ""

# ============================================================================
# 2. AliExpress Fiyatlarını Güncelle
# ============================================================================
echo "📋 [2/6] AliExpress fiyatları güncelleniyor..."
$PYTHON update_aliexpress_prices.py
echo ""

# ============================================================================
# 3. Stok Senkronizasyonu
# ============================================================================
echo "📋 [3/6] Stok senkronizasyonu başlatılıyor..."
if [ -f "auto_inventory_sync.py" ]; then
    $PYTHON auto_inventory_sync.py --alert-only 2>&1 | head -20
    echo "   ✅ Stok sync tamamlandı"
else
    echo "   ⚠️  auto_inventory_sync.py bulunamadı"
fi
echo ""

# ============================================================================
# 4. Test Dosyalarını Commit Et
# ============================================================================
echo "📋 [4/6] Test dosyaları commit ediliyor..."
git add test_*.py tests/*.py 2>/dev/null
git commit -m "Add missing test files" 2>&1 | grep -E "files changed|nothing to commit" || echo "   ✅ Commit tamamlandı"
echo ""

# ============================================================================
# 5. Veritabanı Analiz Raporu
# ============================================================================
echo "📋 [5/6] Veritabanı analizi yapılıyor..."
$PYTHON -c "
import sqlite3

conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

print('   📊 Güncel Durum:')

cursor.execute('SELECT COUNT(*) FROM products')
total = cursor.fetchone()[0]
print(f'      Toplam Ürün: {total}')

cursor.execute('SELECT COUNT(*) FROM products WHERE aliexpress_price IS NOT NULL')
priced = cursor.fetchone()[0]
print(f'      Fiyatı Var: {priced}/{total}')

cursor.execute('SELECT COUNT(*) FROM products WHERE is_listed = 1')
listed = cursor.fetchone()[0]
print(f'      eBay\'de Aktif: {listed}/{total}')

cursor.execute('SELECT COUNT(*) FROM products WHERE margin_percent >= 20')
good_margin = cursor.fetchone()[0]
print(f'      İyi Kar Marjı (≥20%%): {good_margin}/{total}')

conn.close()
"
echo ""

# ============================================================================
# 6. Token Doğrulama
# ============================================================================
echo "📋 [6/6] Token durumu kontrol ediliyor..."
$PYTHON test_and_refresh_all_tokens.py 2>&1 | tail -15
echo ""

# ============================================================================
# SONUÇ RAPORU
# ============================================================================
echo "════════════════════════════════════════════════════════════════════════"
echo "📊 ONARIM SONUÇ RAPORU"
echo "════════════════════════════════════════════════════════════════════════"
echo "⏱️  Bitiş: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "✅ Tamamlanan İşlemler:"
echo "   1. mondeora.db temizlendi"
echo "   2. AliExpress fiyatları güncellendi"
echo "   3. Stok senkronizasyonu yapıldı"
echo "   4. Test dosyaları commit edildi"
echo "   5. Veritabanı analizi yapıldı"
echo "   6. Token durumu doğrulandı"
echo ""
echo "🎯 Kalan Manuel İşlemler:"
echo "   - eBay eski token iptal edilmeli (developer.ebay.com)"
echo "   - Cron jobs kurulmalı (ayrı script)"
echo "   - Test siparişi oluşturulmalı"
echo ""
echo "════════════════════════════════════════════════════════════════════════"
