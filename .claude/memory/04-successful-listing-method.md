# eBay Listing Method - Skeleton (Nov 2026)

## Core Workflow (Skeleton Only):

### 1. **Multi-Image Fetching**
```python
def get_aliexpress_images(ali, aliexpress_product_id):
    """Get images from AliExpress"""
    product = ali.get_product_details(aliexpress_product_id)
    image_urls_str = product.get('image_urls', '')  # STRING with semicolon!
    
    if isinstance(image_urls_str, str) and image_urls_str:
        images = [img.strip() for img in image_urls_str.split(';') if img.strip()]
        https_images = [img for img in images if img.startswith('https://')]
        return https_images[:7]  # eBay limit
    
    return []
```

### 2. **Aspects Building (Product-Specific)**
```python
# ⚠️ CRITICAL: Extract aspects from PRODUCT TITLE - NOT generic template!

from extract_product_aspects import build_product_specific_aspects

# Load template as base structure only
template_aspects = load_template('43504')

# Extract product-specific aspects from title
aspects = build_product_specific_aspects(product['title'], template_aspects)

# What it extracts:
# - Produktart: from title keywords (Angelbox, Kabelorganizer, Werkzeugbox, etc.)
# - Dimensions: from title patterns (30x20x10 cm)
# - Farbe: from color words in title (Weiß, Schwarz, Grau, etc.)
# - Material: inferred from product type (Kunststoff, Metall, Holz)
# - Kapazität: from compartment count (14 Fächern → "14 Fächer")
# - Besonderheiten: from feature words (Mit Griff, Faltbar, Wandmontage)
# - Zimmer: inferred from product type (Küche, Garage, Wohnzimmer)
```

**Extraction Functions (in extract_product_aspects.py):**
```python
def extract_produktart(title: str) -> str:
    """
    Extract specific product type from title
    - 'Angelgerät' → 'Angelbox'
    - 'Kabelorganizer' → 'Kabelorganizer'
    - 'Fernbedienungs' → 'Fernbedienungshalter'
    - 'Müll Halter' → 'Müllbeutelhalter'
    - 'Werkzeug Box' → 'Werkzeugbox'
    """
    # Pattern matching on title keywords

def extract_dimensions(title: str) -> Dict[str, str]:
    """
    Extract real dimensions if mentioned
    Pattern: '30x20x10 cm' or '30 x 20 x 10cm'
    Returns: {"Breite": "30 cm", "Höhe": "20 cm", "Länge": "10 cm"}
    """
    # Regex extraction

def extract_farbe(title: str) -> str:
    """Extract color: Weiß, Schwarz, Grau, Blau, etc."""
    # Keyword matching

def extract_material(title: str, produktart: str) -> str:
    """
    Extract or infer material
    - Explicit: 'Kunststoff' in title
    - Inferred: Storage boxes usually Kunststoff
    """

def extract_kapazitaet(title: str) -> str:
    """
    Extract capacity from title
    Pattern: '14 Fächern' → '14 Fächer'
    Pattern: 'extra große' → 'Extra groß'
    """

def extract_besonderheiten(title: str) -> List[str]:
    """
    Extract features:
    - 'mit griff' → 'Mit Griff'
    - 'faltbar' → 'Faltbar'
    - 'wand montiert' → 'Wandmontage'
    - 'wasserdicht' → 'Wasserdicht'
    - 'doppelseitig' → 'Doppelseitig'
    """

def extract_zimmer(produktart: str, title: str) -> str:
    """
    Infer room from product type or title
    - 'Küchen' in title → 'Küche'
    - Kabelorganizer → 'Wohnzimmer'
    - Angelbox → 'Garage'
    - Müllbeutelhalter → 'Küche'
    """
```

**Example Results:**
```
Title: "Angelgerät-Box mit 14 Fächern, Angelzubehör"
→ Produktart: "Angelbox" (not generic "Organizer")
→ Kapazität: "14 Fächer" (extracted from title)
→ Zimmer: "Garage" (inferred from product type)

Title: "Küchen-Kabelaufwickler, Haushalts-Kabelorganizer"
→ Produktart: "Kabelorganizer" (from title)
→ Zimmer: "Küche" (from "Küchen" in title)
→ Besonderheiten: ["Standard"] (no special features)

Title: "2/6PCS Wand Montiert Müll Taschen Halter"
→ Produktart: "Müllbeutelhalter" (specific type)
→ Besonderheiten: ["Wandmontage"] (from "Wand Montiert")
→ Zimmer: "Küche" (inferred from product type)
```

### 3. **Description (Product-Specific)**
```html
<!-- DO NOT copy-paste generic template -->
<!-- Write UNIQUE description per product based on: -->
<!-- - Product features from AliExpress -->
<!-- - Product benefits for THIS item -->
<!-- - Specific use cases for THIS product -->

<div style="font-family:Arial,sans-serif;">
  <h2>{PRODUCT_SPECIFIC_TITLE}</h2>
  
  <!-- Produkthighlights: Extract from AliExpress description -->
  <div>
    <h3>✨ Produkthighlights</h3>
    <ul>
      <li>{FEATURE_1_FROM_ALIEXPRESS}</li>
      <li>{FEATURE_2_FROM_ALIEXPRESS}</li>
      <li>{FEATURE_3_FROM_ALIEXPRESS}</li>
    </ul>
  </div>
  
  <!-- Produktdetails: Real specs from product -->
  <div>
    <h3>📋 Produktdetails</h3>
    <table>
      <tr><td>Material:</td><td>{REAL_MATERIAL}</td></tr>
      <tr><td>Farbe:</td><td>{REAL_COLOR}</td></tr>
      <tr><td>Größe:</td><td>{REAL_SIZE}</td></tr>
    </table>
  </div>
  
  <!-- Vorteile: Product-specific benefits -->
  <div>
    <h3>✅ Vorteile</h3>
    <p>• {BENEFIT_1_FOR_THIS_PRODUCT}<br>
       • {BENEFIT_2_FOR_THIS_PRODUCT}</p>
  </div>
</div>
```

### 4. **eBay API Call**
```python
listing_data = {
    "sku": f"MULTI-{int(time.time())}",
    "title": product['title'][:80],
    "description": product_specific_html,  # Unique per product!
    "price": float(product['ebay_price']),
    "quantity": 10,
    "category_id": "43504",
    "condition": "NEW",
    "image_urls": images,          # 6-7 images
    "aspects": product_aspects     # Product-specific values!
}

result = ebay.list_product_fixed_price(listing_data)
```

## ⚠️ CRITICAL RULES:

### 1. **Variant Products - MANDATORY** ⚠️ NEW!
```python
# If product has variants (colors/sizes/lengths), create ONE listing with ALL variants

# ❌ WRONG: Each variant = separate listing
# ✅ CORRECT: All variants = ONE listing

# Example: Kabel-Organizer
# - Schwarz, 1m → €19.99
# - Schwarz, 2m → €24.99
# - Weiß, 1m → €19.99
# - Weiß, 2m → €24.99
# → 1 eBay listing with 4 variant options

# Check AliExpress SKUs:
product = ali.get_product_details(aliexpress_product_id)
skus = product.get('skus', [])

if len(skus) > 1:
    # Use eBay Inventory API variation listing
    # Script: apply_variation_listing.py
    # Skill: one-listing-all-variants, ebay-variation-listings
    pass
```

**User instruction:** "Variantli ürünleri varianlari ile bersber koymalisin"
(Products with variants must be listed together with all variants)

**CRITICAL:** Never create separate listings for each variant!

### 2. **Already Listed Check - MANDATORY**
```python
# Check if product is already listed on eBay
if product.get('ebay_item_id'):
    print(f"❌ ALREADY LISTED: {product['ebay_item_id']}")
    return False  # Skip already-listed products
```

**User instruction:** "Ayni ürünleri listeleme" (Do not list the same products)

**CRITICAL:** Always check `ebay_item_id` field BEFORE listing!

### 3. **Niche Compliance - MANDATORY**
```python
niche_keywords = [
    'aufbewahrung', 'organizer', 'storage', 'kabel', 'küchen', 
    'kitchen', 'bathroom', 'bad', 'box', 'tasche', 'halter', 
    'holder', 'rack', 'stand', 'container', 'behälter'
]

is_niche = any(kw in product['title'].lower() for kw in niche_keywords)
if not is_niche:
    return False  # Skip non-niche products
```

**✅ ALLOWED:** Home Organization & Storage ONLY
**❌ NOT ALLOWED:** Toys, Electronics, Clothing, Appliances, Tools (unless organizers)

### 4. **Product-Specific Content - MANDATORY**

❌ **WRONG:** Copy-paste same description/aspects for all products
✅ **CORRECT:** Extract unique features/specs from EACH product

**How to get product-specific data:**
1. Read AliExpress product description
2. Extract real specifications (size, material, color)
3. Analyze images if needed (vision_analyze)
4. Write unique highlights and benefits per product
5. Update ALL aspect values with real data

### 6. **Dimension Extraction - IMPORTANT** ⚠️
```python
# Extract dimensions from title:
# - "30x20x10 cm" → Breite: 20cm, Höhe: 10cm, Länge: 30cm
# - "1m", "2m", "3m" → Länge: X Meter (for cables)

# Title: "Kabel-Organizer 2m"
dimensions = extract_dimensions(title)
# → Länge: "2 Meter"

# User feedback: "Bu listeledigkn üründe metreler cok önemli ama bos"
# (Meters are very important for this product but empty)

# CRITICAL: For cable organizers, length is MANDATORY information!
```

**Dimension patterns:**
- Box dimensions: `30x20x10 cm`, `30cm x 20cm`
- Cable length: `1m`, `2m`, `3m`, `5m` → Länge: "X Meter"
- If not in title: check AliExpress package_info_dto

### 7. **Quality Standards**

- ✅ 6+ images (from AliExpress image_urls split)
- ✅ 29 aspects (all with product-specific values)
- ✅ 2,500+ chars description (unique per product)
- ✅ Category 43504 (Home Organization & Storage)
- ✅ Niche keywords present in title

## Files:

- **Script:** `create_multi_image_listing.py` ✅ USES PRODUCT-SPECIFIC EXTRACTION
- **Extractor:** `extract_product_aspects.py` (9KB, 231 lines) ✅ NEW!
- **Template:** `data/aspect_templates/category_43504_template.json` (base structure only)
- **Collector:** `scripts/aspect_collector.py` (deprecated - use extractor)

## Critical Discovery:

**AliExpress `image_urls` format:**
- Type: `str` (not array!)
- Format: `"url1;url2;url3;url4;url5;url6"`
- Separator: Semicolon (`;`)
- Must: `.split(';')` before using

## User Instruction:

**"Her ürünün kendi aspect ve aciklamsini yap"**
(Each product must have its own aspects and description)

**DO NOT:**
- ❌ Use same description for all products
- ❌ Use generic template values
- ❌ Copy-paste aspects

**DO:**
- ✅ Extract unique features from EACH product
- ✅ Write custom description per product
- ✅ Update all aspect values with real specs
- ✅ Make every listing UNIQUE

## Verified Niche Listings:

1. **ID 31:** 860155270447 - Kabelorganizer ✅
2. **ID 41:** 860155317306 - Fernbedienungs-Organizer ✅
3. **ID 36:** 860155320241 - Müll Taschen Halter ✅

All live on eBay.de in Home Organization & Storage niche.
