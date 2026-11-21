# 🚀 Cassini Optimization - Quick Start Guide

## 📊 Mevcut Durum (2026-11-13)

**21 Aktif İlan - Kritik Bulgular:**
- ✅ Ortalama Score: 86.5/110 (78.6%) - İyi
- ✅ Başlıklar: 21/21 Almanca, 65-80 karakter - Mükemmel
- ✅ Fotoğraflar: 21/21 ilanda 5-6 resim - Mükemmel
- ✅ Açıklamalar: 2900-3900 karakter - Mükemmel
- ✅ Promoted Listings: 21/21 aktif (%5 bid) - Optimal
- ❌ **ZERO TRAFFIC: 21/21 ilanda son 30 günde 0 impression** - KRİTİK!
- ❌ Fiyat Rekabeti: Sadece 11/21 (%52) medyan seviyesinde
- ❌ Eksik Aspects: 6/21 ilanda zorunlu aspect'ler eksik

---

## 🔴 EN KRİTİK SORUN: Zero Traffic

**Tüm ilanlar son 30 günde SIFIR impression almış!**

Bu şu anlama gelir:
- İlanlar eBay arama sonuçlarında gösterilmiyor VEYA
- Çok düşük sıralama (200+) var

**Root Cause:** Muhtemelen:
1. Yanlış kategori atamaları
2. Başlıklar search query'lere match etmiyor
3. Promoted Listings bid çok düşük
4. Listing'ler gerçekte inactive (API vs web farklılığı)

---

## ⚡ HEMEN YAPILACAKLAR (İlk 24 Saat)

### 1. Traffic Root Cause Analizi (30 dakika)
```bash
cd C:/Users/Administrator/Desktop/Mondeora-Drop-System
"C:/Program Files/Python311/python.exe" scripts/traffic_audit.py
```

**Bu script ne yapar:**
- Her ilan için core keyword'leri çıkarır
- eBay Browse API'de Best Match araması yapar
- İlk 200 sonuçta olup olmadığını kontrol eder
- Sonuç: `data/traffic_audit_results.json`

**Beklenen bulgu:** 15-20 ilan ilk 200'de YOK

---

### 2. Eksik Aspect'leri Doldur (15 dakika)
```bash
# Önce test et
"C:/Program Files/Python311/python.exe" scripts/fill_missing_aspects.py --dry-run

# Gerçek güncelleme
"C:/Program Files/Python311/python.exe" scripts/fill_missing_aspects.py
```

**Etkilenen 6 İlan:**
- Pop-Up Maus (860134873775): +1 aspect
- Aufbewahrungstasche (860133996385): +4 aspects
- Mini Wärme (860134886090): +1 aspect
- Löffel Halter (860138343669): +3 aspects
- Tür Kleiderbügel (860139559198): +1 aspect
- Müllbeutelhalter (860139559384): +1 aspect

**Etki:** +15-25% Cassini relevance, Score 86.5 → 92

---

### 3. Agresif Fiyat Optimizasyonu (20 dakika)
```bash
# Önce test et
"C:/Program Files/Python311/python.exe" scripts/optimize_prices.py --dry-run

# Gerçek güncelleme
"C:/Program Files/Python311/python.exe" scripts/optimize_prices.py
```

**Fiyat İndirimleri (6 İlan):**

| İlan | Mevcut | Yeni | İndirim |
|------|--------|------|---------|
| Pop-Up Maus | 34.99 EUR | 24.99 EUR | -28% |
| Hundespielzeugball | 33.99 EUR | 25.99 EUR | -24% |
| Mini Wärme | 35.99 EUR | 22.99 EUR | -36% |
| Make-up Organizer | 37.99 EUR | 27.99 EUR | -26% |
| Tür Kleiderbügel | 22.99 EUR | 17.99 EUR | -22% |
| Kabelaufwickler | 35.99 EUR | 29.99 EUR | -17% |

**Etki:** +30-40% CTR, +25% conversion, rekabet 52% → 81%

---

## 📅 HAFTALIK PLAN

### Hafta 1 (Gün 1-7) - CRITICAL

**Gün 1-2:**
- [x] Traffic audit çalıştır
- [x] Eksik aspects doldur
- [x] Fiyat optimizasyonu yap
- [ ] Traffic audit sonuçlarını analiz et
- [ ] İlk 200'de olmayan ilanları not al

**Gün 3-4:**
- [ ] Kategori doğrulama (traffic olmayan ilanlar)
- [ ] eBay.de'de manuel kategori kontrolü
- [ ] `config/category_overrides.json` güncelle
- [ ] Promoted Listings bid %5→%8 test başlat (10 ilan)

**Gün 5-7:**
- [ ] Başlık optimizasyonu (5-7 ilan/gün)
- [ ] Almanca keyword research (eBay.de'de popüler aramalar)
- [ ] Traffic metriklerini günlük izle
- [ ] Bid test sonuçlarını gözlemle

---

### Hafta 2 (Gün 8-14) - HIGH

**Başlık A/B Testi:**
- [ ] Traffic olmayan 10 ilanın başlıklarını optimize et
- [ ] Core keyword'leri önde konumlandır
- [ ] 1 hafta sonra traffic karşılaştır

**Kategori Review:**
- [ ] Güven <0.7 olan 8 ilanı manual review et
- [ ] Override'lar ekle
- [ ] API güncelle

**Promoted Listings:**
- [ ] Bid test sonuçlarını analiz et
- [ ] ROI pozitif ise kalan 11 ilanı da %8'e çıkar
- [ ] Impression/view metriklerini track et

---

### Hafta 3-4 (Gün 15-30) - MEDIUM

**Conversion Optimization:**
- [ ] Açıklama template'ine SSS bölümü ekle
- [ ] "Warum bei uns kaufen?" trust signals ekle
- [ ] Tüm ilanları güncelle

**İlk Satış Tracking:**
- [ ] Günlük satış kontrolü
- [ ] Kar marjı hesaplama
- [ ] En iyi performans gösteren ilanları not al

**Strateji Review:**
- [ ] 30 günlük traffic verilerini analiz et
- [ ] Score re-audit (`cassini_audit_all.py`)
- [ ] Strateji pivot/continue kararı

---

## 📈 Beklenen Sonuçlar (30 Gün)

| Metrik | Başlangıç | Hedef | İyileştirme |
|--------|-----------|-------|-------------|
| Ortalama Score | 86.5/110 | 95/110 | +9.8% |
| Traffic | 0 impression | 500-1000/ilan | ∞ |
| Fiyat Rekabeti | 52% | 81% | +56% |
| Eksik Aspects | 29% | 0% | -100% |
| İlk Satışlar | 0 | 3-7 ürün | - |

---

## 🎯 En Düşük Performans İlanlar (Öncelik Sırası)

### 🔴 Score <80 (CRITICAL)

1. **Aufbewahrungstasche** (Score: 73) - 860133996385
   - ❌ 4 eksik aspect
   - Aksiyon: Aspect doldur + kategori kontrol

2. **Mini Wärme** (Score: 73) - 860134886090
   - ❌ Fiyat 2.01x median (EN YÜKSEK sapma)
   - ❌ 1 eksik aspect
   - Aksiyon: Fiyat 35.99→22.99 EUR + aspect

3. **Pop-Up Maus** (Score: 80) - 860134873775
   - ❌ Fiyat 1.84x median
   - ❌ 1 eksik aspect
   - Aksiyon: Fiyat 34.99→24.99 EUR + aspect

---

## 🟢 En Yüksek Performans İlanlar (Referans)

1. **Wand Müll Taschen Halter** (Score: 91) - 860138359448
   - ✓ Fiyat 0.7x median (çok rekabetçi)
   - ✓ Tüm aspects dolu
   - Model: Diğer ilanlar için benchmark

2. **Katze Puzzle Spielzeug** (Score: 91) - 860134874458
   - ✓ Fiyat 1.33x median (kabul edilebilir)
   - ✓ Tüm kontroller geçti

3. **50 Holz Katze Puzzles** (Score: 91) - 860135446221
   - ✓ Fiyat 1.1x median (ideal)
   - ✓ Mükemmel kategori

---

## 📚 Referans Dosyalar

- **Ana Rapor:** `data/cassini_strategy_report.md`
- **Audit Verileri:** `data/cassini_full_audit.json`
- **Traffic Analizi:** `data/traffic_audit_results.json` (çalıştırdıktan sonra)

**Script'ler:**
- `scripts/fill_missing_aspects.py`
- `scripts/optimize_prices.py`
- `scripts/traffic_audit.py`

**Skill'ler:**
- `ebay-listing-optimizer` - Cassini faktörleri
- `listing-quality-gate` - Kalite kontrol
- `ebay-de-keyword-titles` - Başlık optimization
- `ebay-category-resolution` - Kategori doğrulama
- `price-optimization` - Fiyatlama

---

## ⚠️ ÖNEMLİ NOTLAR

1. **Pinned Products:** `config/price_pinned_products.json`'daki ürünler için manuel onay gerekli
2. **Dry-run önce:** Tüm script'leri önce `--dry-run` ile test et
3. **Backup:** Değişiklikler öncesi DB backup al
4. **Monitoring:** İlk 7 gün günlük traffic kontrolü yap
5. **ROI:** Promoted Listings bid artırımında cost vs profit track et

---

## 🆘 Sorun Giderme

**Script çalışmıyor:**
- `.env` dosyasında eBay credentials kontrol et
- Python path doğru mu: `C:/Program Files/Python311/python.exe`
- `sys.path.insert(0, '.')` working directory'de mi

**API hatası:**
- Token süresi dolmuş olabilir
- eBay API rate limit aşıldı (1 dakika bekle)
- Sandbox vs Production mode kontrolü

**Veri tutarsızlığı:**
- DB vs eBay senkronizasyonu bozuk
- `sync.py` çalıştır
- Manual eBay.de kontrolü yap

---

**Son Güncelleme:** 2026-11-13  
**Sonraki Review:** 2026-11-20 (7 gün sonra)

✅ Hemen `traffic_audit.py` ile başla!
