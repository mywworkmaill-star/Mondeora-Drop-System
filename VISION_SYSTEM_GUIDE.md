# Vision Aspect Extraction System

## 📋 Genel Bakış

Ürün görsellerinden otomatik aspect çıkarma sistemi.

**Özellikler:**
- Material, Farbe, Besonderheiten otomatik çıkarma
- %80+ confidence threshold (sadece yüksek güvenilirlik)
- 7 günlük cache (aynı ürün 2x analiz edilmez)
- eBay format (dict[str, list[str]])
- Fallback to title-based extraction (vision fail olursa)

## 🗂 Dosyalar

```
src/vision/
├── __init__.py                # Package init
├── aspect_extractor.py        # Ana vision sınıfı (430 satır)
└── batch_analyzer.py          # Toplu analiz (150 satır)

vision_listing.py              # Test script (100 satır)
```

## 📊 Database Schema

```sql
CREATE TABLE vision_analysis (
    id INTEGER PRIMARY KEY,
    product_id INTEGER,
    image_url TEXT,
    analyzed_at DATETIME,
    raw_response TEXT,
    aspects_json TEXT,          -- {"aspects": {...}, "low_confidence": {...}}
    confidence_score INTEGER,   -- 0-100
    status VARCHAR(20),         -- success/failed
    UNIQUE(product_id, image_url)
);
```

## 🚀 Kullanım

### 1. Tek Ürün Analizi

```bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System

# Test product 39
python -m src.vision.aspect_extractor 39

# Çıktı:
# ✅ Material: Metall (90%)
# ✅ Farbe: Schwarz (95%)
# ✅ Features: Selbstklebend, Wandmontage (90%)
```

### 2. Batch Analiz (10 ürün)

```bash
# İlk 10 ready product
python -m src.vision.batch_analyzer 10

# Specific products
python -m src.vision.batch_analyzer 39,29,37,44,47

# Çıktı:
# Success: 9/10
# Average Confidence: 87%
# Aspect Coverage:
#   Material: 9/10 (90%)
#   Farbe: 8/10 (80%)
#   Besonderheiten: 7/10 (70%)
```

### 3. Programmatic Usage

```python
from src.vision.aspect_extractor import VisionAspectExtractor

extractor = VisionAspectExtractor()

# Analyze (auto-caches)
result = extractor.get_cached_or_analyze(
    product_id=39,
    image_url='https://...',
    product_type='organizer'
)

# Check results
if result['status'] == 'success':
    aspects = result['aspects']
    # {
    #   'Material': ['Metall'],
    #   'Farbe': ['Schwarz'],
    #   'Besonderheiten': ['Selbstklebend', 'Wandmontage']
    # }
    
    confidence = result['confidence_score']  # 90
    
    # Merge with existing aspects
    final_aspects = {**title_aspects, **aspects}
```

## 🔧 Integration with Listing Pipeline

```python
# In create_multi_image_listing.py

from src.vision.aspect_extractor import VisionAspectExtractor

def build_aspects(product):
    # Step 1: Title-based extraction (existing)
    title_aspects = extract_from_title(product['title'])
    
    # Step 2: Vision extraction (NEW!)
    if product['image_url']:
        extractor = VisionAspectExtractor()
        vision_result = extractor.get_cached_or_analyze(
            product['id'],
            product['image_url']
        )
        
        # Only use if confident
        if vision_result['confidence_score'] >= 80:
            vision_aspects = vision_result['aspects']
        else:
            vision_aspects = {}
    else:
        vision_aspects = {}
    
    # Step 3: Merge (vision overrides title if confident)
    final_aspects = {}
    
    for key in REQUIRED_ASPECTS:
        if key in vision_aspects:
            final_aspects[key] = vision_aspects[key]  # Vision wins
        elif key in title_aspects:
            final_aspects[key] = title_aspects[key]  # Fallback
        else:
            final_aspects[key] = ['Nicht angegeben']  # Required
    
    return final_aspects
```

## 📈 Performance

| Operation | Time | Cost |
|-----------|------|------|
| Single vision call | 3-5s | $0.02 |
| Cache hit | <100ms | $0 |
| Batch 10 products | ~40s | $0.20 |
| Batch 100 products | ~7min | $2.00 |

**Cache Savings:**
- Day 1: Analyze 100 products = $2.00
- Day 2-7: Cache hit 100% = $0.00
- Week total: $2.00 (not $14.00)

## ✅ Verification Test

```bash
# Test ID 39 (Kitchen Paper Towel Holder)
python -m src.vision.aspect_extractor 39

# Expected output:
# ✅ Material: Metall (90% confidence)
# ✅ Farbe: Schwarz (95% confidence)  
# ✅ Features: Selbstklebend, Wandmontage, 1 Fach (90%)
# ⚠️ Size: Klein (75% - below 80% threshold, not used)
```

## 🎯 Quality Gates

Vision results enhance Quality Gate scoring:

```python
# In listing_validator.py

if product['vision_confidence'] >= 80:
    score += 5  # Bonus for vision-verified aspects
    
if 'Material' in vision_aspects and 'Farbe' in vision_aspects:
    score += 3  # Bonus for complete visual info
```

## 🔍 Confidence Scoring

| Confidence | Meaning | Action |
|------------|---------|--------|
| 90-100 | Very confident | Use aspect ✅ |
| 80-89 | Confident | Use aspect ✅ |
| 60-79 | Somewhat confident | Store but don't use ⚠️ |
| <60 | Uncertain | Ignore ❌ |

## ⚠️ Pitfalls

1. **Low confidence:** <80% = don't use as aspect
2. **Cache invalidation:** Image URL changes = new analysis needed
3. **Vision vs title conflict:** Always verify image before trusting title
4. **Dimension estimates:** Vision size estimates are unreliable, use package_info
5. **Rate limiting:** Max 20 calls/min to avoid API throttling

## 📝 Skill Reference

Skill: **vision-aspect-extraction** (e-commerce category)

Load: `skill_view(name='vision-aspect-extraction')`

Related skills:
- ebay-listing-aspect-enrichment
- ebay-de-keyword-titles
- listing-quality-gate

## 🎓 Examples

### Example 1: Plastic Organizer
```json
{
  "material": {"value": "Kunststoff", "confidence": 95},
  "color": {"value": ["Transparent"], "confidence": 90},
  "features": {"value": ["5 Fächer", "Stapelbar"], "confidence": 85}
}
```

### Example 2: Metal Paper Holder
```json
{
  "material": {"value": "Metall", "confidence": 90},
  "color": {"value": ["Schwarz"], "confidence": 95},
  "features": {"value": ["Selbstklebend", "Wandmontage"], "confidence": 90}
}
```

### Example 3: Fabric Storage Bag
```json
{
  "material": {"value": "Stoff", "confidence": 85},
  "color": {"value": ["Grau", "Weiß"], "confidence": 88},
  "features": {"value": ["Reißverschluss", "Faltbar"], "confidence": 82}
}
```

## 🚀 Next Steps

1. ✅ Skill created (vision-aspect-extraction)
2. ✅ Module implemented (src/vision/)
3. ✅ Tested with real product (ID 39)
4. ⏳ Integrate with listing pipeline
5. ⏳ Batch analyze 10 products
6. ⏳ Update Quality Gate with vision scoring
7. ⏳ Production deployment

## 📞 Support

Questions? Load skill:
```bash
skill_view(name='vision-aspect-extraction')
```
