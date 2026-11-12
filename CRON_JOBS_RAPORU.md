# 🕐 MONDEORA CRON JOBS - TAM LİSTE

**Toplam:** 25 Job (24 Aktif + 1 Duraklatılmış)  
**Tarih:** 2026-11-10 13:27

---

## ⚡ YÜKSEK FREKANS (Dakikada/Saatte)

| # | Job | Sıklık | Son Çalışma | Durum | Görev |
|---|-----|--------|-------------|-------|-------|
| 1 | **token-refresh** | Her 30dk | 13:09 | ✅ OK | eBay + AliExpress token yenileme |
| 2 | **watchdog** | Her 15dk | 13:20 | ✅ OK | Sistem sağlık kontrolü |
| 3 | **orders-poll** | Her 10dk | 13:18 | ✅ OK | Sipariş durumu kontrolü |
| 4 | **orders-sync** | Her 15dk | 13:20 | ✅ OK | eBay → AliExpress sipariş sync |
| 5 | **sales-check** | Her 10dk | 13:20 | ✅ OK | Yeni satış bildirimi |
| 6 | **tracking-update** | Her 30dk | 12:57 | ✅ OK | Kargo takip numarası sync |
| 7 | **order-fulfillment** | Her 20dk | 13:25 | ✅ OK | Otomatik sipariş oluşturma |

---

## 🔄 ORTA FREKANS (Saatlik/3-6 Saatlik)

| # | Job | Sıklık | Son Çalışma | Durum | Görev |
|---|-----|--------|-------------|-------|-------|
| 8 | **product-sync** | Her 3 saat | 11:16 | ✅ OK | AliExpress ürün + stok sync |
| 9 | **research** | Her 6 saat | 11:14 | ✅ OK | Yeni ürün araştırması + trend |
| 10 | **memory-index** | Her 1 saat | 13:26 | ✅ OK | Vektör bellek indeksleme |
| 11 | **db-sync** ⭐ | Her 1 saat | 12:52 | ✅ OK | **eBay → DB sync (TEDARİKÇİ LİNK!)** |
| 12 | **customer-comm** | Her 1 saat | 13:11 | ✅ OK | Müşteri iletişimi otomatik yanıt |

---

## 📅 GÜNLÜK GÖREVLER

| # | Job | Zaman | Son Çalışma | Durum | Görev |
|---|-----|-------|-------------|-------|-------|
| 13 | **db-backup** | 02:00 | Bugün yok | ✅ OK | Veritabanı yedekleme |
| 14 | **inventory-sync** | 03:00 | 03:00 | ✅ OK | Envanter senkronizasyonu |
| 15 | **price-optimize** | 04:00 | 04:00 | ✅ OK | Rekabet analizi + fiyat optimize |
| 16 | **listing-pipeline** | 04:30 | Bugün yok | ✅ OK | Yeni ürün yayınlama |
| 17 | **performance-optimize** | 05:00 | Bugün yok | ✅ OK | Düşük performanslı ürün kaldırma |
| 18 | **diagnose** | 06:00 | 06:00 | ✅ OK | Hata analizi + kök neden tespiti |
| 19 | **link-verify** | 06:00 | 06:08 | ✅ OK | AliExpress link doğrulama |
| 20 | **health-check** | 08:00 | 08:11 | ✅ OK | Kapsamlı sistem sağlık kontrolü |
| 21 | **daily-report** | 22:00 | Bugün yok | ✅ OK | Günlük özet rapor |

---

## 🗓️ HAFTALIK GÖREVLER

| # | Job | Zaman | Son Çalışma | Durum | Görev |
|---|-----|-------|-------------|-------|-------|
| 22 | **log-cleanup** | Pazar 05:00 | Henüz yok | ✅ OK | Eski log temizleme (30 gün+) |
| 23 | **blue-ocean** | Pazartesi 07:00 | Henüz yok | ✅ OK | Düşük rekabet ürün analizi |
| 24 | **weekly-report** | Pazartesi 09:00 | Henüz yok | ✅ OK | Haftalık performans raporu |
| 25 | **sales-boost** | Pazar 10:00 | - | ⏸️ DURDURULDU | Promoted ads (maliyet nedeni) |

---

## 🎯 TEDARİKÇİ LİNK OTOMATİK KAYIT

### ⭐ Job #11: `mondeora-db-sync`

**Sıklık:** Her 1 saat  
**Script:** `mondeora_db_sync.sh`  
**Durum:** ✅ ÇALIŞIYOR (Son: 12:52, Sıradaki: 13:52)

**Ne Yapıyor:**
1. eBay'den tüm aktif ürünleri çeker
2. SKU'dan AliExpress ID'yi çıkarır
3. `products.aliexpress_product_id` kolonuna kaydeder
4. Fiyat değişikliklerini günceller
5. Silinen ürünleri DELISTED yapar

**Kod:**
```bash
#!/bin/bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
"/c/Program Files/Python311/python.exe" auto_database_sync.py
```

---

## 📊 İSTATİSTİKLER

### Sıklık Dağılımı:
```
⚡ Dakikalık (10-30dk):  7 job
🔄 Saatlik (1-6 saat):   5 job
📅 Günlük:               9 job
🗓️  Haftalık:            3 job
⏸️  Duraklatılmış:       1 job
```

### Sistem Durumu:
```
✅ Çalışan:           24/25 (96%)
⏸️  Duraklatılmış:     1/25 (4%)
🔄 Sıradaki 10dk:     sales-check, orders-poll
🔄 Sıradaki 1 saat:   db-sync (TEDARİKÇİ LİNK!)
```

---

## 🛠️ CRON JOBS'LARI GÖRMEK İÇİN

### Hermes CLI:
```bash
hermes cron list
```

### Python:
```python
# Job detaylarını görmek için
hermes cron list --json
```

### Script'lerin Yeri:
```
~/AppData/Local/hermes/scripts/mondeora_*.sh
```

---

## ✅ SONUÇ

🟢 **TEDARİKÇİ LİNK OTOMATİK KAYIT:** ZATEN ÇALIŞIYOR!  
🟢 **Job:** `mondeora-db-sync` (Her 1 saat)  
🟢 **Son Çalışma:** 12:52  
🟢 **Sıradaki Çalışma:** 13:52 (yaklaşık 25 dakika sonra)

Yeni ürün eklendiğinde:
1. SKU'ya AliExpress ID gömülüyor
2. eBay'e ekleniyor
3. 1 saat içinde `db-sync` job'ı otomatik kaydediyor

**Müdahale gerekmiyor!** ✅

---

**Rapor Tarihi:** 2026-11-10 13:27  
**Toplam Aktif Job:** 24  
**Sistem Durumu:** ✅ TAM OTOMATİK
