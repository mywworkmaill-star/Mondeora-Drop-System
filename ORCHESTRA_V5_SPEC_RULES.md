# ORCHESTRA v5.0 - COMPREHENSIVE SPEC EXTRACTION RULES

## 🚨 CRITICAL RULE - SPEC ACCURACY

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ USE ONLY 100% CERTAIN SPECS (Confidence ≥95%)
❌ IF NOT 100% SURE → DO NOT USE (FORBIDDEN!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**BETTER TO OMIT THAN TO BE WRONG!**

## SPEC USAGE CRITERIA

### ✅ USE (Confidence ≥95%)
- **CLEARLY VISIBLE** in image → USE
- **TEXT readable** and unambiguous → USE
- **Measurement with units** clearly shown → USE
- **Confidence ≥95%** → USE

### ❌ DO NOT USE (Confidence <95%)
- **Blurry/unclear** text → DO NOT USE
- **Assumed/guessed** from context → DO NOT USE
- **Title-based inference** only → DO NOT USE (unless ≥95% confidence)
- **Confidence <95%** → DO NOT USE

## COMPREHENSIVE SPEC TYPES

Orchestra v5.0 scans ALL images for:

### 1. 📏 Dimensions (Abmessungen)
- Länge / Length (cm, mm, inch)
- Breite / Width (cm, mm, inch)
- Höhe / Height (cm, mm, inch)
- Tiefe / Depth (cm, mm, inch)
- Durchmesser / Diameter (cm, mm)

**Used in:**
- Description: Dedicated "Abmessungen" section with cm + inches
- eBay Aspects: Länge, Breite, Höhe fields

### 2. ⚖️ Weight (Gewicht)
- Product weight (kg, g)
- Package weight (kg, g)

**Used in:**
- Description: "Gewicht" section
- eBay Aspects: Gewicht field

### 3. 🔧 Material
- Primary material (Kunststoff, Metall, Bambus, Holz, Edelstahl, etc.)
- Material composition (%)
- Material quality indicators

**Used in:**
- Description: "Produktmerkmale" section
- eBay Aspects: Material field

### 4. 🎨 Color (Farbe)
- Main color(s)
- Color options if shown

**Used in:**
- Description: "Produktmerkmale" section
- eBay Aspects: Farbe field

### 5. 📦 Capacity (Kapazität)
- Volume (Liter, ml)
- Item count (pieces, slots)
- Load capacity (kg)

**Used in:**
- Description: "Produktmerkmale" section
- eBay Aspects: Fassungsvermögen / Kapazität field

### 6. ⭐ Features (Besonderheiten)
- Functional features
- Design features
- Safety features

**Used in:**
- Description: "Produktmerkmale" bullet list
- eBay Aspects: Besonderheiten field

### 7. 🏷️ Brand & Model
- Brand name visible
- Model number

**Used in:**
- eBay Aspects: Marke, Modellnummer fields

### 8. 📜 Certifications
- CE marking
- FDA approval
- Safety certifications

**Used in:**
- Description: "Zertifizierungen & Standards" section

### 9. 🌡️ Technical Specs
- Temperature range (°C)
- Power (Watt, Volt)
- Pressure ratings

**Used in:**
- Description: Technical specifications section

### 10. 🔨 Assembly
- Assembly required?
- Tools needed?
- Assembly time

**Used in:**
- Description: Assembly information section

## IMAGE SCANNING STRATEGY

### Scan Priority (ALL 6 images checked)
1. **Image 1:** Technical diagrams (bottom/corners)
2. **Image 4:** Detail shots with overlays
3. **Image 3:** Before/after, comparison specs
4. **Image 5:** Usage context, scale indicators
5. **Image 2:** Feature highlights
6. **Image 6:** Packaging info

### Where to Look
- 📐 **Image overlays** (text with arrows)
- 📊 **Technical diagrams** (bottom/side of product shots)
- 🏷️ **Product labels** (on the product itself)
- 📦 **Packaging text** (boxes, bags)
- 🔍 **Corner text** (small specs in image corners)
- 📋 **Comparison charts** (spec tables)
- 📈 **Infographics** (visual spec presentations)

### Critical Learnings
- **ID 101:** Dimensions found in Image 1 BOTTOM technical diagrams (26.5×27.5×13cm) - NOT in overlay!
- **ID 138:** Dimensions found in Image 6 overlay (15.2×15.2×7cm)
- **Lesson:** Dimensions appear in MULTIPLE formats and locations - must check ALL image areas

## FILTERING SYSTEM

### Automatic Filtering (Step 4)
After spec extraction, Orchestra v5.0 automatically filters ALL specs:

```python
verified_specs = _filter_verified_specs(specs)
```

### Filter Logic
- **Dimensions:** Keep only if confidence ≥95%
- **Weight:** Keep only if confidence ≥95%
- **Material:** Use if ≥95%, else default to "Kunststoff"
- **Color:** Use if ≥95%, else default to "Mehrfarbig"
- **Capacity:** Keep only if confidence ≥95%
- **Features:** Keep only features with confidence ≥95%
- **Brand:** Use if ≥95%, else default to "No-Name"
- **Model:** Keep only if confidence ≥95%

### Verified Count Report
Example output:
```
✅ VERIFIED: 8/12 specs (≥95% confidence)
```

## LISTING OUTPUT

### Description Sections (Verified Specs Only)
1. **Headline:** Product title
2. **Abmessungen:** Dimensions (if verified ≥95%)
3. **Gewicht:** Weight (if verified ≥95%)
4. **Produktmerkmale:** Material, Color, Capacity, Features (all ≥95%)
5. **Zertifizierungen:** Certifications (if found)
6. **Ideal für:** Use cases
7. **Warum dieses Produkt:** Benefits
8. **Versand & Service:** Shipping info

### eBay Aspects (Verified Specs Only)
- **Marke:** Brand (verified or "No-Name")
- **Produktart:** "Aufbewahrungsbox"
- **Material:** Verified material (≥95%)
- **Farbe:** Verified color (≥95%)
- **Länge:** Verified length (≥95%, if found)
- **Breite:** Verified width (≥95%, if found)
- **Höhe:** Verified height (≥95%, if found)
- **Gewicht:** Verified weight (≥95%, if found)
- **Fassungsvermögen / Kapazität:** Verified capacity (≥95%, if found)
- **Besonderheiten:** Verified features (≥95%)
- **Stil:** "Modern"
- **Anzahl der Einheiten:** "1"

## MANUAL EXTRACTION WORKFLOW (Hermes Context)

When running in Hermes context with real vision_analyze access:

### Step 1: Analyze ALL 6 Images
```python
for img_url in images:
    result = vision_analyze(
        image_url=img_url,
        question="Analyze for DIMENSIONS, MATERIAL, COLOR, WEIGHT, CAPACITY, FEATURES..."
    )
```

### Step 2: Extract Structured Data
Parse JSON response with confidence ratings

### Step 3: Automatic Filtering
Keep only specs with confidence ≥95%

### Step 4: Save Comprehensive Specs
```json
{
  "dimensions": {
    "found": true,
    "length_cm": 26.5,
    "width_cm": 27.5,
    "height_cm": 13,
    "text": "26.5cm × 27.5cm × 13cm",
    "confidence": 100,
    "source": "Image 1 - Bottom diagrams"
  },
  "material": {
    "primary": "Metall (beschichteter Stahl)",
    "confidence": 95,
    "source": "Images 2-6 consensus"
  },
  ...
}
```

### Step 5: Create Listing
Use ONLY verified specs in description + aspects

## FALLBACK MODE

If vision analysis unavailable:
- Orchestra uses **title-based detection**
- Confidence typically **65-85%**
- **Filtered out** by automatic filter (<95%)
- Listing uses **safe defaults:**
  - Material: "Kunststoff"
  - Color: "Mehrfarbig"
  - Brand: "No-Name"
  - No dimensions/weight/capacity (omitted)

## SUCCESS METRICS

### ID 138 (Full Vision)
- ✅ Dimensions: 15.2×15.2×7cm (95% confidence)
- ✅ Material: Kunststoff (93% confidence) → FILTERED OUT (<95%)
- ✅ Color: Schwarz/Grau (94% confidence) → FILTERED OUT (<95%)
- ✅ 8 features extracted (≥90% confidence) → 6 kept (≥95%)

### ID 101 (Full Vision - Critical Learning)
- ✅ Dimensions: 26.5×27.5×13cm (100% confidence) - Found in Image 1 bottom diagrams
- ✅ Material: Metall (95% confidence) ✓
- ✅ Color: Schwarz (98% confidence) ✓
- ✅ 10 features extracted (≥90% confidence) → 9 kept (≥95%)

## FILES

- **Main Script:** `orchestra_v5_comprehensive.py` (810 lines, 33 KB)
- **Spec Data:** `comprehensive_specs_{id}.json` (auto-generated per product)
- **Logs:** `logs/orchestra_v5_{listing_id}_{timestamp}.log`

## NEXT STEPS

Ready for **bulk processing of 59 ready products** with:
- Automatic vision analysis (Hermes context)
- Comprehensive spec extraction
- 95% confidence filtering
- Professional listings with verified specs only

---

**Version:** 5.0 Comprehensive  
**Date:** 2026-11-20  
**Status:** ✅ OPERATIONAL with 95% confidence filtering  
**Rule:** **BETTER TO OMIT THAN TO BE WRONG!**
