# 🔗 AliExpress API Entegrasyon Haritası

**Son güncelleme:** 2026-11-10  
**Durum:** ✅ 17 API metodu aktif, tümü `src/jobs.py` hub'ından çağrılıyor

---

## 📊 API → Job Mapping

| AliExpress API | Job | Kullanım | Sıklık | Durum |
|---|---|---|---|---|
| **aliexpress.ds.text.search** | `research` | Keyword araması → product discovery | Günlük 02:00 | ✅ |
| **aliexpress.ds.product.get** | `research`, `product_sync`, `freight_sync`, `inventory_sync` | Ürün detayları (price, stock, SKUs, images) | Her 4 saat | ✅ |
| **aliexpress.ds.freight.query** | `freight_sync` | Kargo maliyeti DE'ye | Günlük 05:00 | ✅ |
| **aliexpress.ds.category.get** | `supplier_probe` | Token validation + kategori listesi | Günlük 06:00 | ✅ |
| **aliexpress.ds.member.benefit.get** | `supplier_probe` | Hesap yetkileri (auto-pay, wholesale) | Günlük 06:00 | ✅ |
| **aliexpress.ds.product.specialinfo.get** | `supplier_probe` | CE/compliance iddiaları (unverified) | Günlük 06:00 | ⚠️ |
| **aliexpress.trade.ds.order.get** | `orders_sync` | AliExpress sipariş durumu | Her 30 dk | ✅ |
| **aliexpress.ds.order.tracking.get** | `tracking_sync` | Kargo takip no | Her saat | ✅ |
| **aliexpress.ds.order.create** | `orders_sync` (SAFE) | Sipariş oluşturma (ödeme yok) | Manual | ⚠️ |
| **aliexpress.ds.order.afterpay** | - | Ödeme (API desteklenmiyor) | - | ❌ |
| **aliexpress.logistics.buyer.freight.calculate** | - | Legacy freight (DS yerine .ds.freight.query) | - | 🔶 |
| **aliexpress.affiliate.product.query** | - | Affiliate (DS olmayan ürünler için) | - | 🔶 |
| **aliexpress.affiliate.productdetail.get** | - | Affiliate detay | - | 🔶 |
| **aliexpress.ds.category.tree.get** | - | Tam kategori ağacı | - | 🔶 |
| **aliexpress.ds.feed.itemids.get** | - | Feed-based discovery | - | 🔶 |
| **aliexpress.ds.image.searchV2** | - | Görsel arama | - | 🔶 |
| **aliexpress.photobank.redefining.uploadimageforsdk** | - | Resim yükleme (listing için) | - | 🔶 |
| **aliexpress.ds.search.event.report** | - | Analytics reporting | - | 🔶 |

**Lejant:**
- ✅ Aktif kullanımda
- ⚠️ Kod var, kısmi/manuel
- ❌ API desteklemiyor
- 🔶 Client'ta var, job yok (orphan)

---

## 🎯 Job Bazlı Breakdown

### 1. `research` (Günlük 02:00)
**AliExpress API'leri:**
- `aliexpress.ds.text.search` → 50 aday/sayfa, 3 sayfa = 150 ürün
- `aliexpress.ds.product.get` → her aday için detay (price, image, SKU, stock)

**Akış:**
```
Keyword rotation (pet toy, dog toy...) 
  → text.search (SALES_DESC)
  → Her ürün: product.get
  → VeRO filter (150 brand)
  → Fiyat hesapla (min €25 profit, 25% margin)
  → Category select (smart_category_selector)
  → data/research_candidates.json
```

**Çıktı:** `READY_TO_LIST` ürünler → `listing_pipeline` job'a gider.

---

### 2. `product_sync` (Her 4 saat, 03:00/07:00/11:00/15:00)
**AliExpress API'leri:**
- `aliexpress.ds.product.get` → listelenen ürünlerin güncel fiyat/stok

**Akış:**
```
DB'den is_listed=1 ürünler
  → Her biri: product.get (aliexpress_product_id)
  → Fiyat değişti mi? → price_optimize job'a log
  → Stok 0 mı? → eBay'e quantity=0 yaz
  → DB sync
```

---

### 3. `inventory_sync` (Her 4 saat, offset +20 dk)
**AliExpress API'leri:**
- `aliexpress.ds.product.get` → stock (`warehouse_count`)

**eBay:**
- `PUT /sell/inventory/v1/inventory_item/{sku}` → `quantity` güncelle

**Akış:**
```
is_listed=1 ürünler
  → product.get
  → Stock farklıysa:
    - eBay inventory update
    - DB: current_stock, aliexpress_stock, status=(sold_out|active)
```

---

### 4. `freight_sync` (Günlük 05:00) ✨ YENİ
**AliExpress API'leri:**
- `aliexpress.ds.product.get` → SKU listesi
- `aliexpress.ds.freight.query` → DE'ye kargo maliyeti

**Akış:**
```
is_listed=1 ürünler
  → product.get (SKU matching)
  → freight.query (product_id, sku_id, ship_to=DE, quantity=1)
  → DB: shipping_cost güncelle (€ olarak)
```

**Sonuç:** `price_optimize` job kargo maliyetini okuyor, fiyat hesaplıyor.

---

### 5. `orders_sync` (Her 30 dk)
**AliExpress API'leri:**
- `aliexpress.ds.order.create` → sipariş oluştur (SAFE mode: pending only)
- `aliexpress.trade.ds.order.get` → sipariş durumu

**eBay:**
- `GET /sell/fulfillment/v1/order` → paid orders

**Akış:**
```
eBay polling → paid orders
  → Parse address (DE, PLZ, telefon)
  → DB: orders + order_lines
  → ds.order.create (SAFE: pending notification)
  → Desktop HTML: MONDEORA_SIPARIS_{timestamp}.html
  → data/pending_aliexpress_orders.jsonl
  → Manuel ödeme (browser)
  
Sipariş durumu:
  → trade.ds.order.get (her pending order için)
  → Status: PLACE_ORDER_SUCCESS → WAIT_SELLER_SEND_GOODS → ...
  → DB order_lines.status güncelle
```

**CRITICAL:** Ödeme otomatik DEĞİL! `aliexpress.ds.order.afterpay` API desteklemiyor, browser gerekli.

---

### 6. `tracking_sync` (Her saat) ✨ YENİ
**AliExpress API'leri:**
- `aliexpress.ds.order.tracking.get` → tracking number, logistics service

**eBay:**
- `POST /sell/fulfillment/v1/order/{id}/shipping_fulfillment`

**Akış:**
```
DB: order_lines (status=shipped_by_supplier)
  → order.tracking.get (ae_order_id)
  → Carrier map: CAINIAO → "Cainiao", YANWEN → "Yanwen"
  → eBay'e yükle (lineItemId, trackingNumber, carrier)
  → DB: tracking_uploaded=1
  → Buyer'a otomatik mesaj (eBay sends)
```

---

### 7. `supplier_probe` (Günlük 06:00) ✨ YENİ
**AliExpress API'leri:**
- `aliexpress.ds.member.benefit.get` → hesap yetenekleri
- `aliexpress.ds.category.get` → root categories (validation)
- `aliexpress.ds.product.specialinfo.get` → CE compliance (1 sample product)

**Akış:**
```
member.benefit.get → {canApply, canBenefit} auto-pay, wholesale
  → data/supplier_capabilities.json

category.get → kategori sayısı (2 = root ok)

specialinfo.get → 1 listed product için compliance iddiası
  → item_qualification_list (UNVERIFIED - only supplier claims)
```

**Amaç:** Orphan API'leri test et, account capability'leri kaydet.

---

### 8. `health_check` (Her 5 dk) ✨ YENİ
**AliExpress API'leri:**
- `aliexpress.ds.category.get` → token validity (read probe)

**eBay:**
- `GET /sell/inventory/v1/inventory_item?limit=1` → token validity

**Akış:**
```
5 probe:
  1. ebay_inventory_read → inventory API
  2. aliexpress_signed_read → category.get (HMAC signature valid?)
  3. database_write → health_checks table INSERT test
  4. ebay_token_ttl → metadata expires_at (> 5 min?)
  5. aliexpress_token_ttl → metadata expires_at

→ health_checks table
→ status: ok | degraded (unhealthy list)
```

---

### 9. `link_verify` (Günlük 04:00) ✨ YENİ
**Script:** `verify_aliexpress_links_readonly.py`

**AliExpress API'leri:**
- `aliexpress.ds.product.get` → her DB ürün için detay

**eBay:**
- `GET /sell/inventory/v1/inventory_item` (per SKU)

**Akış:**
```
DB'den tüm ürünler
  → product.get (AliExpress)
  → eBay inventory read
  → Image dHash compare
  → Fee calculation
  → data/link_verification_latest.json
    - ebay_listing_status: ACTIVE | INACTIVE | NOT_FOUND
    - supplier_available: true | false
    - images_match: true | false
    - drift_detected: is_listed DB vs eBay actual
```

**Read-only** — DB veya eBay'e yazma yok.

---

## 🔄 Token Management

### eBay OAuth2
**Job:** `token_refresh` (Her saat :08)  
**Metadata:** `data/ebay_oauth_metadata.json`  
**Renewal:** < 30 min kalan ise `POST /identity/v1/oauth2/token`  
**Scopes:** sell.inventory, sell.fulfillment, sell.account, sell.marketing

### AliExpress Dropshipping
**Job:** `token_refresh` (Her saat :08)  
**Metadata:** `data/aliexpress_oauth_metadata.json`  
**Renewal:** `POST /rest/auth/token/refresh` (HMAC-SHA256 sign)  
**Ömür:** 30 gün (refresh_token: ~6 ay)

---

## 📈 Kullanım İstatistikleri (Günlük)

| API | Günlük Çağrı | Kota | Kullanım |
|---|---|---|---|
| ds.text.search | ~5 (research) | 100/gün | %5 |
| ds.product.get | ~180 (research: 150 + sync: 16×6) | Sınırsız | ✅ |
| ds.freight.query | ~16 (freight_sync) | Sınırsız | ✅ |
| ds.category.get | ~290 (health: 288 + probe: 1) | Sınırsız | ✅ |
| trade.ds.order.get | ~48 (sipariş başına, her 30 dk) | Sınırsız | ✅ |
| ds.order.tracking.get | ~24 (sipariş başına, her saat) | Sınırsız | ✅ |

**Kota Exhaustion:** `text.search` tek sınırlı API; günlük 100, midnight UTC reset. Error: `business error (code)` → cycle skip → ertesi gün.

---

## 🚫 Kullanılmayan API'ler (Orphan)

Client'ta var ama job yok:

1. **aliexpress.logistics.buyer.freight.calculate**  
   → Legacy; yerine `ds.freight.query` kullanılıyor

2. **aliexpress.affiliate.product.query / .productdetail.get**  
   → Affiliate (dropshipping DS API ile çelişiyor)

3. **aliexpress.ds.category.tree.get**  
   → Full tree (gereksiz; smart_category_selector eBay taxonomy kullanıyor)

4. **aliexpress.ds.feed.itemids.get**  
   → Feed-based discovery (text.search yeterli)

5. **aliexpress.ds.image.searchV2**  
   → Görsel arama (kullanılmıyor)

6. **aliexpress.photobank.* (upload, delete, list)**  
   → AliExpress seller için (biz buyer/dropshipper)

7. **aliexpress.ds.search.event.report**  
   → Analytics reporting (optional)

8. **aliexpress.ds.wholesale.get**  
   → Wholesale pricing (şu an retail kullanılıyor)

**Tavsiye:** Orphan API'leri sil VEYA yeni job'lar ekle (örn. `image_search` job).

---

## ✅ Entegrasyon Durumu

| Kategori | Durum |
|---|---|
| **Token yenileme** | ✅ Otomatik (her saat, 5 dk threshold) |
| **Ürün araştırma** | ✅ text.search + product.get |
| **Fiyat/stok senkronu** | ✅ product.get → eBay sync |
| **Kargo maliyeti** | ✅ freight.query → DB |
| **Sipariş oluşturma** | ⚠️ SAFE mode (pending only, ödeme manuel) |
| **Sipariş tracking** | ✅ tracking.get → eBay fulfillment |
| **Health monitoring** | ✅ 5 check → health_checks table |
| **Link verification** | ✅ Read-only drift detection |
| **Capability probing** | ✅ member.benefit, specialinfo |
| **Ödeme** | ❌ API desteklemiyor (browser gerekli) |

---

## 🔮 Eksikler & Roadmap

### Kısa Vadede (1 hafta)
1. **Orphan cleanup** – Kullanılmayan client metodlarını sil
2. **Wholesale entegrasyonu** – `ds.wholesale.get` için `price_optimize` job
3. **Image search** – `ds.image.searchV2` için competitor monitoring

### Orta Vadede (1 ay)
1. **Otomatik ödeme** – Browser automation (CAPTCHA risk)
2. **Feed discovery** – `ds.feed.itemids.get` → trending products
3. **Analytics** – `ds.search.event.report` → click tracking

### Uzun Vadede (3 ay)
1. **Multi-supplier** – 1688.com, Banggood entegrasyonu
2. **Bulk ordering** – Toplu sipariş API
3. **Returns management** – AliExpress dispute API

---

## 📞 API Documentation

**Official:** https://openservice.aliexpress.com/doc/doc.htm  
**Client:** `src/api/aliexpress_client.py` (1900+ satır)  
**Test:** `"C:/Program Files/Python311/python.exe" -m src.jobs supplier_probe`

**Support:** api-support@aliexpress.com
