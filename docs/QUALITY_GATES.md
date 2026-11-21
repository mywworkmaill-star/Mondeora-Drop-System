# Kalite Kontrol Pipeline Dokümantasyonu

**Oluşturulma Tarihi:** 2026-11-13  
**Amaç:** ready-listing-buffer'a eklenen her ürün için otomatik kalite kontrol gate sistemi

## Genel Bakış

Her ürün ready-listing-buffer'a eklenmeden önce 5 otomatik kalite gate'inden geçer:
1. **Başlık Kalitesi** - 60-80 karakter, 8+ kelime, doğal Almanca
2. **Fotoğraf Sayısı** - Min 6, ideal 8-12, tümü ≥500px
3. **Açıklama Zenginliği** - Min 500 karakter, HTML bullet points, özellik tablosu
4. **Item Specifics** - Min 10 aspect (Marke, Material, Farbe vb)
5. **Kategori Güveni** - Confidence ≥ 0.6, needs_review kontrolü
6. **Fiyat Rekabeti** - Mevcut rakip median kontrolü (değişiklik yok, zaten vardı)

## Gate Fonksiyonları

### 1. check_title_quality(title, rules=None)

**Kaynak:** `src/listing_quality/gates.py:109`

**Kontroller:**
- 60-80 karakter aralığı (optimal)
- En az 8 kelime (Almanca anahtar kelimeler için)
- Almanca olmayan karakterler (Kiril, Çince vb)

**Döndürür:** `list[str]` - Sorunlar listesi, sorun yoksa boş liste

**Örnekler:**
```python
from src.listing_quality import gates

# ✅ İyi başlık
probs = gates.check_title_quality("Hundespielzeugball Bissfest Ungiftig Gummi für Hunde Katzen 3er-Set")
assert probs == []

# ❌ Çok kısa
probs = gates.check_title_quality("Hundespielzeug")  
# ['title too short (14 < 60 chars)', 'too few keywords (1 < 8 words)']

# ❌ Yabancı dil
probs = gates.check_title_quality("Hundespielzeug для собак")
# ['non-German characters: {...}']
```

### 2. check_image_count(image_urls, rules=None)

**Kaynak:** `src/listing_quality/gates.py:132`

**Kontroller:**
- Min 6 fotoğraf (eBay minimum + kalite)
- İdeal 8-12 fotoğraf
- Her fotoğraf ≥500px (images.filter_urls() kullanarak)

**Döndürür:** `(list[str], dict)` - (Sorunlar, Info dict)

**Info Dict Yapısı:**
```python
{
    'total': 10,        # Toplam gönderilen URL
    'valid': 8,         # ≥500px olan
    'dropped': 2,       # <500px veya invalid
    'ideal': 8          # İdeal hedef
}
```

**Örnekler:**
```python
# ✅ Yeterli ve kaliteli
probs, info = gates.check_image_count([f'url{i}' for i in range(10)])
# probs = [], info['valid'] = 10

# ❌ Yetersiz
probs, info = gates.check_image_count(['url1', 'url2', 'url3'])
# probs = ['insufficient images (3 < 6 min)']
```

### 3. check_description_quality(description, rules=None)

**Kaynak:** `src/listing_quality/gates.py:160`

**Kontroller:**
- Min 500 karakter gerçek metin (HTML strip'lendikten sonra)
- HTML formatı var mı
- Bullet points (`<ol>`, `<ul>`, `<li>`)
- Özellik tablosu (`<table>`, `<tr>`)

**Döndürür:** `(list[str], dict)`

**Info Dict Yapısı:**
```python
{
    'length': 650,
    'has_html': True,
    'has_lists': True,
    'has_table': True
}
```

**Örnekler:**
```python
# ✅ Tam açıklama
desc = """
<h2>Beschreibung</h2>
<ul>
    <li>Hochwertiges Material</li>
    <li>Bissfest und ungiftig</li>
</ul>
<table>
    <tr><td>Material</td><td>Gummi</td></tr>
</table>
""" + "x" * 400
probs, info = gates.check_description_quality(desc)
# probs = []

# ❌ Düz metin
probs, info = gates.check_description_quality("Kurze Beschreibung.")
# probs = ['description too short', 'no HTML formatting', ...]
```

### 4. check_item_specifics_count(aspects, rules=None)

**Kaynak:** `src/listing_quality/gates.py:193`

**Kontroller:**
- Min 10 aspect (eBay ranking + kalite için)

**Aspects Format:** Dict veya list of tuples kabul eder

**Döndürür:** `(list[str], dict)`

**Örnekler:**
```python
# ✅ Yeterli aspects (dict)
aspects = {
    'Marke': 'Unbranded', 'Material': 'Gummi', 'Farbe': 'Blau',
    'Größe': 'M', 'Gewicht': '100g', 'Herstellungsland': 'China',
    'Altersgruppe': 'Erwachsene', 'Besonderheiten': 'Bissfest',
    'Produktart': 'Spielzeug', 'Tierart': 'Hund', 'Paketinhalt': '3 Stück'
}
probs, info = gates.check_item_specifics_count(aspects)
# probs = [], info['count'] = 11

# ❌ Az aspects
aspects = {'Marke': 'Unbranded', 'Material': 'Gummi'}
probs, info = gates.check_item_specifics_count(aspects)
# probs = ['insufficient item specifics (2 < 10 min)']
```

### 5. check_category_confidence(category_result, rules=None)

**Kaynak:** `src/listing_quality/gates.py:212`

**Kontroller:**
- Confidence ≥ 0.6 (eBay Taxonomy API güveni)
- needs_review flag = False olmalı
- category_id var mı

**Category Result Dict Yapısı:**
```python
{
    'confidence': 0.85,
    'needs_review': False,
    'category_id': '12345'
}
```

**Döndürür:** `(list[str], dict)`

**Örnekler:**
```python
# ✅ İyi kategori
cat_result = {'confidence': 0.85, 'needs_review': False, 'category_id': '12345'}
probs, info = gates.check_category_confidence(cat_result)
# probs = []

# ❌ Düşük confidence
cat_result = {'confidence': 0.4, 'needs_review': False, 'category_id': '12345'}
probs, info = gates.check_category_confidence(cat_result)
# probs = ['low category confidence (0.40 < 0.6)']

# ❌ Manuel review gerekli
cat_result = {'confidence': 0.8, 'needs_review': True, 'category_id': '12345'}
probs, info = gates.check_category_confidence(cat_result)
# probs = ['category flagged for manual review']
```

## Entegrasyon: ready_plan.py

**Kaynak:** `src/listing_quality/ready_plan.py:307-356`

`build_prepared()` fonksiyonuna eklenen yeni kontroller:

```python
# NEW QUALITY GATES: Title, Images, Description, Item Specifics, Category
try:
    # 1. Title quality check
    final_title = st['plan'].get('title', '')
    title_probs = gates.check_title_quality(final_title)
    if title_probs:
        for prob in title_probs:
            blockers.append('quality_title:' + prob.replace(' ', '_').replace(':', '-'))
    
    # 2. Image count check
    image_urls = st['res'].get('ae_multimedia_info_dto', {}).get('image_urls', '')
    if image_urls:
        imgs = [u.strip() for u in image_urls.split(';') if u.strip()]
        img_probs, img_info = gates.check_image_count(imgs)
        st['gates']['images'] = img_info  # Info kaydedilir
        if img_probs:
            for prob in img_probs:
                blockers.append('quality_images:' + ...)
    else:
        blockers.append('quality_images:no_images')
    
    # 3. Description quality check
    desc = st['plan'].get('description', '')
    desc_probs, desc_info = gates.check_description_quality(desc)
    st['gates']['description'] = desc_info
    ...
    
    # 4. Item specifics count check
    aspects = st['plan'].get('product', {}).get('aspects', {})
    aspect_probs, aspect_info = gates.check_item_specifics_count(aspects)
    st['gates']['aspects'] = aspect_info
    ...
    
    # 5. Category confidence check
    category_result = {
        'confidence': st.get('category_confidence', 0.0),
        'needs_review': st.get('needs_review', True),
        'category_id': st['plan'].get('product', {}).get('categoryId')
    }
    cat_probs, cat_info = gates.check_category_confidence(category_result)
    st['gates']['category'] = cat_info
    ...
except Exception as error:
    blockers.append('quality_gates_failed:' + type(error).__name__)
```

## Blocker Adlandırma Formatı

Tüm kalite gate blokerleri `quality_<gate>:<reason>` formatını kullanır:

**Başlık:**
- `quality_title:too_short`
- `quality_title:too_long`
- `quality_title:too_few_keywords`
- `quality_title:non-German_characters`

**Fotoğraflar:**
- `quality_images:no_images`
- `quality_images:insufficient_images`
- `quality_images:below_ideal_image_count`
- `quality_images:N_images_dropped`

**Açıklama:**
- `quality_description:description_too_short`
- `quality_description:no_HTML_formatting`
- `quality_description:no_bullet_points_or_numbered_lists`
- `quality_description:no_specification_table`

**Item Specifics:**
- `quality_aspects:no_item_specifics_provided`
- `quality_aspects:insufficient_item_specifics`

**Kategori:**
- `quality_category:low_category_confidence`
- `quality_category:category_flagged_for_manual_review`
- `quality_category:no_category_ID_assigned`

**Genel:**
- `quality_gates_failed:<ExceptionType>`

## Config Dosyası: risk_rules.json

**Kaynak:** `config/risk_rules.json:192-212`

Yeni eklenmiş kurallar:

```json
{
  "images": {
    "min_count": 6,
    "ideal_count": 8,
    "max_count": 12,
    "min_resolution": 500,
    "note": "eBay requires ≥500px on longest side (error 25002). Min 6, ideal 8-12 for good presentation."
  },
  "description": {
    "min_length": 500,
    "note": "German HTML description with bullets, specs table, and package info. Min 500 chars of actual text."
  },
  "aspects": {
    "min_count": 10,
    "note": "Item Specifics (eBay attributes): min 10 for quality ranking. Includes Marke, Material, Farbe, Größe, etc."
  },
  "category": {
    "min_confidence": 0.6,
    "note": "eBay Taxonomy confidence. Below 0.6 or needs_review=true requires manual verification."
  }
}
```

## Test Coverage

**Kaynak:** `tests/test_quality_gates.py`

**Test Sınıfları:**
- `TestTitleQualityGate` - 6 test (optimal, too short, too long, few words, foreign chars, edge case)
- `TestImageCountGate` - 4 test (no images, insufficient, below ideal, ideal count)
- `TestDescriptionQualityGate` - 6 test (empty, short, no HTML, no lists, no table, complete)
- `TestItemSpecificsGate` - 4 test (no aspects, too few, sufficient, list format)
- `TestCategoryConfidenceGate` - 5 test (low confidence, needs review, no ID, good, edge case)
- `TestIntegrationWithReadyPlan` - 1 test (blocker format)

**Toplam:** 26 test, tümü geçiyor ✅

**Çalıştırma:**
```bash
cd C:/Users/Administrator/Desktop/Mondeora-Drop-System
"C:/Program Files/Python311/python.exe" -m pytest tests/test_quality_gates.py -v
```

## Kullanım Örnekleri

### Manuel Gate Kontrolü

```python
from src.listing_quality import gates

# Başlık kontrolü
title = "Hundespielzeugball Bissfest Ungiftig Gummi für Hunde Katzen 3er-Set"
problems = gates.check_title_quality(title)
if problems:
    print("Başlık sorunları:", problems)

# Fotoğraf kontrolü
image_urls = ['https://img1.jpg', 'https://img2.jpg', ...]
probs, info = gates.check_image_count(image_urls)
print(f"Geçerli fotoğraf: {info['valid']}, Sorunlar: {probs}")

# Açıklama kontrolü
desc = "<p>...</p><ul><li>...</li></ul><table>...</table>"
probs, info = gates.check_description_quality(desc)
print(f"Uzunluk: {info['length']}, HTML: {info['has_html']}")

# Aspects kontrolü
aspects = {'Marke': 'X', 'Material': 'Y', ...}
probs, info = gates.check_item_specifics_count(aspects)
print(f"Aspect sayısı: {info['count']}, Min gerekli: {info['min_required']}")

# Kategori kontrolü
cat_result = {'confidence': 0.85, 'needs_review': False, 'category_id': '12345'}
probs, info = gates.check_category_confidence(cat_result)
print(f"Confidence: {info['confidence']}, Sorunlar: {probs}")
```

### Readiness Report'tan Blocker Okuma

```python
from src.listing_quality import ready_plan

# readiness dict'i hazırlanmış bir ürün için
readiness = {
    'ready_for_live': False,
    'generated_at': '2026-11-13T10:00:00Z',
    'checks': [...],
    'blockers': [
        'quality_title:too_short',
        'quality_images:insufficient_images',
        'quality_description:no_HTML_formatting'
    ]
}

blockers = ready_plan.readiness_blockers(readiness)
print("Toplam blocker:", len(blockers))

# Kalite blocker'ları filtrele
quality_blockers = [b for b in blockers if b.startswith('quality_')]
print("Kalite sorunları:", quality_blockers)
```

## Gate'leri Geçemeyen Ürünler İçin Workflow

1. **Blocker'ı Tanımlayın:**
   - `build_prepared()` sonucundaki `blockers` listesini okuyun
   - `quality_*` prefix'li blocker'ları ayırın

2. **Sorunu Düzeltin:**
   - **Title:** `ebay-de-keyword-titles` skill'ini kullanarak yeniden yazın
   - **Images:** AliExpress'ten daha yüksek çözünürlüklü URL'ler alın
   - **Description:** `description.build()` çıktısını kontrol edin, gerekirse detail HTML'i iyileştirin
   - **Aspects:** `categories.fill_aspects()` çıktısını kontrol edin, eksik olanları `extra_aspects` ile ekleyin
   - **Category:** `categories.resolve_for_product()` confidence düşükse `config/category_overrides.json`'a ekleyin

3. **Tekrar Test Edin:**
   - Düzeltilmiş verilerle `build_prepared()` tekrar çağırın
   - `blockers` listesi boş mu kontrol edin

4. **Ready Buffer'a Ekleyin:**
   - Blocker yoksa ürün ready-listing-buffer'a eklenmeye hazır

## Bilinen Kısıtlamalar

1. **Görsel Doğrulama:** `check_image_count()` sadece çözünürlük kontrol eder, içerik kontrolü yapmaz
2. **Başlık Semantiği:** `check_title_quality()` karakter/kelime sayar, anlamsal doğruluğu kontrol etmez (bkz: `ebay-de-keyword-titles` skill)
3. **Açıklama Kalitesi:** HTML varlığını kontrol eder, metni doğrulamaz
4. **Aspects İçeriği:** Sayı kontrol eder, değerlerin doğruluğunu kontrol etmez
5. **Kategori Override:** Manuel override olsa bile confidence düşükse blocker ekler

## İlgili Dosyalar

| Dosya | Değişiklik | Satır Aralığı |
|-------|-----------|---------------|
| `src/listing_quality/gates.py` | 5 yeni fonksiyon eklendi | 109-244 |
| `src/listing_quality/ready_plan.py` | `build_prepared()` gate entegrasyonu | 307-356 |
| `config/risk_rules.json` | 4 yeni kural eklendi | 192-212 |
| `tests/test_quality_gates.py` | 26 yeni test (YENİ DOSYA) | 1-268 |

## İlgili Skills

- **listing-quality-gate** - Genel kalite kapısı prosedürü
- **ready-listing-buffer** - 10 hazır ilan standardı
- **ebay-de-keyword-titles** - Başlık kalitesi kuralları
- **ebay-listing-optimizer** - Ranking faktörleri

## Değişiklik Geçmişi

**2026-11-13**
- İlk versiyon
- 5 yeni gate fonksiyonu eklendi
- `ready_plan.py` entegrasyonu tamamlandı
- 26 test yazıldı (tümü geçiyor)
- Dokümantasyon oluşturuldu
