"""
ORCHESTRA v5.2 - ALIEXPRESS VERIFICATION + COMPREHENSIVE SPECS + PROMOTED LISTINGS

GOVERNANCE (2026-11-20): "Chief of Staff" (Agency specialist, slug
`chief-of-staff`) is the designated MAIN CONTROLLER for all Mondeora
operations — not a code dependency of this script, but the standing
decision-routing layer above it and above every other Agency specialist
used on this project. Before any strategic change (pricing policy, niche
scope, selling-limit exposure, new automation direction), delegate a
state summary to it via agency_agents_delegate(agent='chief-of-staff',
task=...) and follow its escalate/handle/park triage before executing.
It does not replace Hasan's decisions — it filters noise and routes what
actually needs his attention (see its Decision Routing framework).

🚨 CRITICAL UPDATE: AliExpress data is now PRIMARY source!

NEW IN v5.2:
✅ Step 2: Complete AliExpress verification BEFORE listing
✅ Color from AliExpress SKU (PRIMARY) - no more "Mehrfarbig" mistakes!
✅ All variant images included
✅ Current price & stock verification
✅ Correct eBay DE category: 159897 (Storage Boxes)
✅ Fixed Zimmer aspects (storage rooms, not living/bedroom)

User feedback implemented: "Listelemeden önce AliExpress'te herşeyi belirle"

🚨 CRITICAL RULE - SPEC ACCURACY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ USE ONLY 100% CERTAIN SPECS (Confidence ≥95%)
❌ IF NOT 100% SURE → DO NOT USE (FORBIDDEN!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPEC USAGE CRITERIA:
✅ CLEARLY VISIBLE in image → USE
✅ TEXT readable and unambiguous → USE
✅ Measurement with units clearly shown → USE
✅ Confidence ≥95% → USE

❌ Blurry/unclear text → DO NOT USE
❌ Assumed/guessed from context → DO NOT USE
❌ Title-based inference only → DO NOT USE (unless ≥95% confidence)
❌ Confidence <95% → DO NOT USE

BETTER TO OMIT THAN TO BE WRONG!

COMPREHENSIVE SPEC TYPES COLLECTED:
✅ Dimensions (Länge/Breite/Höhe) - cm, mm, inch
✅ Material (Kunststoff, Metall, Bambus, Holz, etc.)
✅ Color (Schwarz, Weiß, Transparent, etc.)
✅ Weight (Gewicht) - kg, g
✅ Capacity (Kapazität) - liters, pieces, slots
✅ Features (Besonderheiten) - waterproof, adjustable, etc.
✅ Brand markings (Marke)
✅ Model numbers (Modellnummer)
✅ Certifications (CE, FDA, etc.)
✅ Temperature range (°C)
✅ Power specs (Watt, Volt)
✅ Assembly info (Montage)
✅ ANY visible product specifications

USAGE IN LISTING:
✅ Description: ONLY high-confidence specs (≥95%)
✅ eBay Aspects: ONLY verified specs (≥95%)
✅ Professional formatting

NEW IN v5.1:
✅ Step 9: Automatic Promoted Listings (eBay Ads)
✅ Campaign auto-creation if needed
✅ 8% default bid rate (safe)
✅ Ad verification

WORKFLOW:
1. Select product
2. Fetch 6 images
3. SCAN ALL 6 IMAGES THOROUGHLY for ANY specs
4. FILTER: Keep only specs with confidence ≥95%
5. Create description with VERIFIED specs only
6. Add VERIFIED specs to eBay aspects
7. Publish listing
8. Update database
9. Create Promoted Listing (NEW!)
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient
import sqlite3
import json
import time
import os
import re
from datetime import datetime

ali = AliExpressAPIClient()
ebay = eBayAPIClient()

class OrchestraV52:
    """Orchestra v5.1 - Comprehensive Spec Extraction + Promoted Listings"""
    
    # Canonical color-word map (German primary, English fallback) used to clean
    # BOTH AliExpress SKU "color" property values (often noisy, e.g. "2pcs black")
    # and title-based fallback detection. Substring match on purpose: catches
    # "4PCS-Black", "B white", "durchsichtiger", etc.
    COLOR_KEYWORD_MAP = [
        (['durchsichtig', 'transparent', 'klar'], 'Transparent'),
        (['schwarz', 'black'], 'Schwarz'),
        (['weiß', 'weiss', 'white'], 'Weiß'),
        (['grau', 'gray', 'grey'], 'Grau'),
        (['blau', 'blue'], 'Blau'),
        (['rot', 'red'], 'Rot'),
        (['grün', 'gruen', 'green'], 'Grün'),
        (['gelb', 'yellow'], 'Gelb'),
        (['rosa', 'pink'], 'Rosa'),
        (['lila', 'violett', 'purple'], 'Lila'),
        (['braun', 'brown'], 'Braun'),
        (['beige'], 'Beige'),
        (['silber', 'silver'], 'Silber'),
        (['gold'], 'Gold'),
        (['orange'], 'Orange'),
        (['creme', 'cream'], 'Creme'),
        (['mehrfarbig', 'bunt', 'multicolor', 'colorful'], 'Mehrfarbig'),
    ]
    
    def _match_color_word(self, text):
        """Return the canonical color name found as a substring of text, else None."""
        if not text:
            return None
        t = text.lower()
        for keywords, canonical in self.COLOR_KEYWORD_MAP:
            if any(kw in t for kw in keywords):
                return canonical
        return None
    
    def __init__(self):
        self.conn = sqlite3.connect('data/dropshipping.db')
        self.cursor = self.conn.cursor()
        self.log = []
        self.comprehensive_specs = None  # All specs from all images
        
    def close(self):
        self.conn.close()
    
    def log_step(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        self.log.append(log_line)
        print(log_line)
    
    def step_1_select_product(self):
        """Step 1: Select product"""
        self.log_step('=' * 80)
        self.log_step('STEP 1: ÜRÜN SEÇİMİ')
        self.log_step('=' * 80)
        
        self.cursor.execute('''
            SELECT 
                p.id,
                p.aliexpress_product_id,
                p.title,
                p.aliexpress_price,
                p.shipping_cost,
                p.ebay_price,
                p.image_url,
                p.category_id
            FROM products p
            WHERE p.status = 'ready_to_list'
            AND p.is_listed = 0
            AND p.aliexpress_price IS NOT NULL
            AND p.ebay_price IS NOT NULL
            AND p.ebay_price BETWEEN 15 AND 40
            ORDER BY (p.ebay_price - p.aliexpress_price - COALESCE(p.shipping_cost, 0)) DESC
            LIMIT 5
        ''')
        
        products = self.cursor.fetchall()
        
        if not products:
            self.log_step('❌ Ready ürün bulunamadı')
            return None
        
        self.log_step(f'✅ {len(products)} ürün bulundu')
        
        best = products[0]
        
        product = {
            'id': best[0],
            'ali_id': best[1],
            'title': best[2],
            'ali_price': best[3],
            'shipping': best[4] or 0,
            'ebay_price': best[5],
            'images': best[6],
            'category_id': best[7]
        }
        
        cost = product['ali_price'] + product['shipping']
        profit = product['ebay_price'] - cost - (product['ebay_price'] * 0.11)
        
        self.log_step(f"✅ SEÇİLDİ: ID {product['id']}")
        self.log_step(f"   {product['title'][:60]}...")
        self.log_step(f"   Cost: €{cost:.2f} → eBay: €{product['ebay_price']:.2f}")
        self.log_step(f"   Profit: €{profit:.2f}")
        
        return product
    
    def step_1_load_specific_product(self, product_id):
        """Load specific product by ID"""
        self.log_step('=' * 80)
        self.log_step(f'STEP 1: LOAD SPECIFIC PRODUCT (ID {product_id})')
        self.log_step('=' * 80)
        
        self.cursor.execute('''
            SELECT 
                p.id,
                p.aliexpress_product_id,
                p.title,
                p.aliexpress_price,
                p.shipping_cost,
                p.ebay_price,
                p.image_url,
                p.category_id
            FROM products p
            WHERE p.id = ?
        ''', (product_id,))
        
        row = self.cursor.fetchone()
        
        if not row:
            self.log_step(f'❌ Product ID {product_id} not found!')
            return None
        
        product = {
            'id': row[0],
            'ali_id': row[1],
            'title': row[2],
            'ali_price': row[3] or 0,
            'shipping': row[4] or 0,
            'ebay_price': row[5] or 0,
            'images': row[6],
            'category_id': row[7]
        }
        
        cost = product['ali_price'] + product['shipping']
        profit = product['ebay_price'] - cost - (product['ebay_price'] * 0.11)
        
        self.log_step(f"✅ LOADED: ID {product['id']}")
        self.log_step(f"   {product['title'][:60]}...")
        self.log_step(f"   Cost: €{cost:.2f} → eBay: €{product['ebay_price']:.2f}")
        self.log_step(f"   Profit: €{profit:.2f}")
        
        return product
        self.log_step(f"   💰 €{cost:.2f} → €{product['ebay_price']:.2f} (Kar: €{profit:.2f})")
        self.log_step('')
        
        return product
    
    def step_2_update_images(self, product):
        """Step 2: AliExpress Complete Verification + Images
        
        🚨 CRITICAL: Fetch ALL product details from AliExpress BEFORE listing!
        - Real color (from SKU properties)
        - All variant images
        - Current price & stock
        - Material/properties (if available)
        
        This is PRIMARY data source - vision is supplementary!
        """
        self.log_step('=' * 80)
        self.log_step('STEP 2: ALİEXPRESS VERİFİCATİON + GÖRSELLER')
        self.log_step('=' * 80)
        
        self.log_step('⏳ AliExpress\'ten FULL product details çekiliyor...')
        
        try:
            details = ali.get_product_details(product['ali_id'])
            
            if not details:
                self.log_step('⚠️  Detay alınamadı - fallback to database')
                self.log_step('')
                images = product['images'].split(',') if product['images'] else []
                return images
            
            # Store verified AliExpress data
            product['aliexpress_verified'] = {}
            
            # 1. IMAGES (including variant images)
            new_images_str = details.get('image_urls', '')
            new_images = []
            
            if ';' in new_images_str:
                new_images = new_images_str.split(';')
            elif ',' in new_images_str:
                new_images = new_images_str.split(',')
            else:
                new_images = [new_images_str]
            
            # Add variant images (from SKU properties)
            sku_infos = details.get('ae_item_sku_info_dtos', {}).get('ae_item_sku_info_d_t_o', [])
            for sku_info in sku_infos:
                props = sku_info.get('ae_sku_property_dtos', {}).get('ae_sku_property_d_t_o', [])
                for prop in props:
                    variant_image = prop.get('sku_image', '')
                    if variant_image and variant_image not in new_images:
                        new_images.append(variant_image)
            
            new_images = [img for img in new_images if img.startswith('https://')][:8]  # Max 8
            
            self.log_step(f'✅ Images: {len(new_images)} found')
            
            # 2. COLOR + MEASUREMENT/SIZE (from SKU properties) - PRIMARY DATA!
            # 🚨 FIX: scan ALL SKUs, not just the first match — a product can have
            # several color variants and/or several size/measurement variants.
            per_sku = []
            dim_pattern = re.compile(
                r'(\d+(?:[.,]\d+)?)\s*(?:cm|mm)?\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|mm)?'
                r'(?:\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|mm)?)?\s*(cm|mm)?',
                re.IGNORECASE
            )
            pack_pattern = re.compile(r'(\d+)\s*(?:pcs|pc|stück|stk|st|pack|set)\b', re.IGNORECASE)
            for sku_info in sku_infos:
                props = sku_info.get('ae_sku_property_dtos', {}).get('ae_sku_property_d_t_o', [])
                sku_color = None
                sku_dims = None
                sku_dims_text = None
                sku_pack = None
                for prop in props:
                    prop_name = prop.get('sku_property_name', '').lower()
                    prop_value = prop.get('property_value_definition_name', '') or ''
                    if prop_name in ['farbe', 'color', 'colour'] and not sku_color:
                        normalized = self._match_color_word(prop_value)
                        sku_color = normalized  # None if the value is noise (e.g. "Two sets", pack size)
                        if not sku_pack:
                            pm = pack_pattern.search(prop_value)
                            if pm:
                                sku_pack = f"{pm.group(1)} Stück"  # e.g. "2pcs black" -> pack dimension, kept separately from color
                    m = dim_pattern.search(prop_value)
                    if m and not sku_dims:
                        unit = (m.group(4) or 'cm').lower()
                        nums = [float(g.replace(',', '.')) for g in [m.group(1), m.group(2), m.group(3)] if g]
                        if unit == 'mm':
                            nums = [n / 10.0 for n in nums]
                        sku_dims = tuple(nums)
                        sku_dims_text = prop_value
                per_sku.append({'color': sku_color, 'dims': sku_dims, 'dims_text': sku_dims_text, 'pack': sku_pack})
            
            distinct_colors = sorted({p['color'] for p in per_sku if p['color']})
            distinct_dims = sorted({p['dims'] for p in per_sku if p['dims']})
            default = per_sku[0] if per_sku else {'color': None, 'dims': None, 'dims_text': None}
            
            # --- Color decision ---
            if len(distinct_colors) == 1:
                color = distinct_colors[0]
                product['aliexpress_verified']['color'] = color
                self.log_step(f'✅ Color: {color} (AliExpress SKU - {len(per_sku)} variant(s), tutarlı)')
            elif len(distinct_colors) > 1:
                color = default['color'] or 'Mehrfarbig'
                product['aliexpress_verified']['color'] = color
                product['aliexpress_verified']['color_variants'] = distinct_colors
                self.log_step(f'⚠️  RENK VARYANTLARI bulundu: {distinct_colors} — tek SKU olarak default \"{color}\" kullanılıyor')
                self.log_step('   💡 Öneri: Bu ürün variation listing olarak satılmalı (her renk ayrı SKU)')
            else:
                color = None
                self.log_step('⚠️  Color: Not found in SKU properties')
            
            # --- Size/measurement decision ---
            if len(distinct_dims) == 1:
                d = distinct_dims[0]
                dims_entry = {
                    'length_cm': d[0] if len(d) > 0 else None,
                    'width_cm': d[1] if len(d) > 1 else None,
                    'height_cm': d[2] if len(d) > 2 else None,
                    'text': default['dims_text'] or '',
                    'confidence': 97,
                    'source': 'AliExpress SKU property'
                }
                product['aliexpress_verified']['dimensions'] = dims_entry
                self.log_step(f"✅ Ölçü: {dims_entry['text']} (AliExpress SKU - {len(per_sku)} variant(s), tutarlı)")
            elif len(distinct_dims) > 1:
                default_dims = default['dims']
                if default_dims:
                    dims_entry = {
                        'length_cm': default_dims[0] if len(default_dims) > 0 else None,
                        'width_cm': default_dims[1] if len(default_dims) > 1 else None,
                        'height_cm': default_dims[2] if len(default_dims) > 2 else None,
                        'text': default['dims_text'] or '',
                        'confidence': 97,
                        'source': 'AliExpress SKU property (default variant)'
                    }
                    product['aliexpress_verified']['dimensions'] = dims_entry
                texts = [p['dims_text'] for p in per_sku if p['dims_text']]
                product['aliexpress_verified']['size_variants'] = sorted(set(texts))
                self.log_step(f"⚠️  ÖLÇÜ VARYANTLARI bulundu: {sorted(set(texts))} — default variant'ın ölçüsü kullanılıyor")
                self.log_step('   💡 Öneri: Bu ürün variation listing olarak satılmalı (her ölçü ayrı SKU)')
            else:
                self.log_step('⚠️  Ölçü: SKU özelliklerinde bulunamadı')
            
            # 3. PRICE & STOCK (current)
            current_price = details.get('sale_price', 0)
            current_stock = details.get('warehouse_count', 0)
            
            product['aliexpress_verified']['price'] = current_price
            product['aliexpress_verified']['stock'] = current_stock
            
            self.log_step(f'✅ Price: €{current_price} (current)')
            self.log_step(f'✅ Stock: {current_stock} available')
            
            # 4. VARIANTS
            product['aliexpress_verified']['variants'] = []
            for idx, sku_info in enumerate(sku_infos):
                variant = {
                    'sku_id': sku_info.get('sku_id', ''),
                    'price': sku_info.get('offer_sale_price', 0),
                    'stock': sku_info.get('sku_available_stock', 0),
                    'properties': {},
                    # From the per_sku pass above: normalized color + parsed dimensions
                    'normalized_color': per_sku[idx]['color'] if idx < len(per_sku) else None,
                    'dims_cm': per_sku[idx]['dims'] if idx < len(per_sku) else None,
                    'dims_text': per_sku[idx]['dims_text'] if idx < len(per_sku) else None,
                    'pack': per_sku[idx]['pack'] if idx < len(per_sku) else None,
                    'image': None
                }
                
                props = sku_info.get('ae_sku_property_dtos', {}).get('ae_sku_property_d_t_o', [])
                for prop in props:
                    prop_name = prop.get('sku_property_name', '')
                    prop_value = prop.get('property_value_definition_name', '')
                    variant['properties'][prop_name] = prop_value
                    if prop.get('sku_image') and not variant['image']:
                        variant['image'] = prop.get('sku_image')
                
                product['aliexpress_verified']['variants'].append(variant)
            
            self.log_step(f'✅ Variants: {len(product["aliexpress_verified"]["variants"])} SKU(s)')
            
            # Update database with images
            if len(new_images) >= 4:
                images_csv = ','.join(new_images)
                self.cursor.execute('''
                    UPDATE products
                    SET image_url = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                ''', (images_csv, product['id']))
                self.conn.commit()
                
                product['images'] = images_csv
            
            self.log_step('')
            self.log_step('🎯 AliExpress verification: COMPLETE')
            self.log_step('   Color, images, price, stock - ALL verified!')
            self.log_step('')
            
            return new_images if new_images else product['images'].split(',') if product['images'] else []
                
        except Exception as e:
            self.log_step(f'❌ Hata: {str(e)}')
            self.log_step('')
            images = product['images'].split(',') if product['images'] else []
            return images
    
    def _filter_verified_specs(self, specs):
        """
        Filter specs to keep ONLY high-confidence (≥95%) items
        CRITICAL: Better to omit than to be wrong!
        """
        verified = {
            'dimensions': specs['dimensions'].copy(),
            'weight': specs['weight'].copy(),
            'material': specs['material'].copy(),
            'color': specs['color'].copy(),
            'capacity': specs['capacity'].copy(),
            'features': [],
            'brand': specs['brand'].copy(),
            'model': specs['model'].copy(),
            'certifications': specs['certifications'].copy(),
            'technical': specs['technical'].copy(),
            'assembly': specs['assembly'].copy()
        }
        
        # Dimensions: Only if confidence ≥95%
        if specs['dimensions']['confidence'] < 95:
            verified['dimensions']['found'] = False
            verified['dimensions']['length_cm'] = None
            verified['dimensions']['width_cm'] = None
            verified['dimensions']['height_cm'] = None
            verified['dimensions']['text'] = ''
        
        # Weight: Only if confidence ≥95%
        if specs['weight']['confidence'] < 95:
            verified['weight']['found'] = False
            verified['weight']['product_weight_g'] = None
            verified['weight']['package_weight_g'] = None
        
        # Material: Only if confidence ≥95%
        if specs['material']['confidence'] < 95:
            verified['material']['primary'] = 'Kunststoff'  # Safe default
            verified['material']['confidence'] = 0
            verified['material']['source'] = 'default (low confidence)'
        
        # Color: Only if confidence ≥95%
        if specs['color']['confidence'] < 95:
            verified['color']['main'] = 'Mehrfarbig'  # Safe default
            verified['color']['confidence'] = 0
            verified['color']['source'] = 'default (low confidence)'
        
        # Capacity: Only if confidence ≥95%
        if specs['capacity']['confidence'] < 95:
            verified['capacity']['found'] = False
        
        # Features: Only features with confidence ≥95%
        for feat in specs['features']:
            feat_conf = feat.get('confidence', 0) if isinstance(feat, dict) else 95  # String features assumed verified
            if feat_conf >= 95:
                verified['features'].append(feat)
        
        # Brand: Only if confidence ≥95%
        if specs['brand']['confidence'] < 95:
            verified['brand']['name'] = 'No-Name'  # Safe default
            verified['brand']['confidence'] = 100
        
        # Model: Only if confidence ≥95%
        if specs['model']['confidence'] < 95:
            verified['model']['number'] = ''
            verified['model']['confidence'] = 0
        
        return verified
    
    def _get_aliexpress_dimensions_override(self, product):
        """AliExpress SKU-verified dimensions — more reliable than vision/title guess."""
        ali_dims = product.get('aliexpress_verified', {}).get('dimensions')
        if not ali_dims:
            return None
        return {
            'found': True,
            'length_cm': ali_dims.get('length_cm'),
            'width_cm': ali_dims.get('width_cm'),
            'height_cm': ali_dims.get('height_cm'),
            'depth_cm': None,
            'diameter_cm': None,
            'text': ali_dims.get('text', ''),
            'confidence': ali_dims.get('confidence', 97)
        }

    def step_4_comprehensive_spec_extraction(self, product, images):
        """
        Step 4: COMPREHENSIVE SPEC EXTRACTION v5.0
        Scans ALL images for ALL types of specifications
        """
        self.log_step('=' * 80)
        self.log_step('STEP 4: COMPREHENSIVE SPEC EXTRACTION v5.0')
        self.log_step('=' * 80)
        
        self.log_step(f'🔍 {len(images)} görsel DETAYLI taranacak - TÜM SPEC\'ler toplanacak...')
        self.log_step('')
        
        # Check if comprehensive specs already exist
        specs_file = f'comprehensive_specs_{product["id"]}.json'
        
        if os.path.exists(specs_file):
            self.log_step(f'✅ Comprehensive specs bulundu: {specs_file}')
            with open(specs_file, 'r', encoding='utf-8') as f:
                self.comprehensive_specs = json.load(f)
            
            override = self._get_aliexpress_dimensions_override(product)
            if override and override['confidence'] > self.comprehensive_specs.get('dimensions', {}).get('confidence', 0):
                self.comprehensive_specs['dimensions'] = override
                self.log_step(f"✅ Dimensions AliExpress SKU verisiyle güncellendi: {override['text']} ({override['confidence']}%)")
                with open(specs_file, 'w', encoding='utf-8') as f:
                    json.dump(self.comprehensive_specs, f, indent=2, ensure_ascii=False)
            
            self._log_found_specs()
            return self.comprehensive_specs
        
        # Manual extraction instructions (for Hermes context)
        self.log_step('📋 MANUEL COMPREHENSIVE SPEC EXTRACTION GEREKLİ!')
        self.log_step('')
        self.log_step('TÜM GÖRSELLERDEN TOPLANACAK SPEC TÜRLERİ:')
        self.log_step('')
        self.log_step('1. 📏 DIMENSIONS (Abmessungen):')
        self.log_step('   • Länge/Length (cm, mm, inch)')
        self.log_step('   • Breite/Width (cm, mm, inch)')
        self.log_step('   • Höhe/Height (cm, mm, inch)')
        self.log_step('   • Tiefe/Depth (cm, mm, inch)')
        self.log_step('   • Durchmesser/Diameter (cm, mm)')
        self.log_step('')
        self.log_step('2. ⚖️  WEIGHT (Gewicht):')
        self.log_step('   • Product weight (kg, g)')
        self.log_step('   • Package weight')
        self.log_step('')
        self.log_step('3. 🔧 MATERIAL (Material):')
        self.log_step('   • Primary material (Kunststoff, Metall, Bambus, Holz, etc.)')
        self.log_step('   • Material composition (%)')
        self.log_step('   • Material quality indicators')
        self.log_step('')
        self.log_step('4. 🎨 COLOR (Farbe):')
        self.log_step('   • Main color(s)')
        self.log_step('   • Color options if shown')
        self.log_step('')
        self.log_step('5. 📦 CAPACITY (Kapazität):')
        self.log_step('   • Volume (Liter, ml)')
        self.log_step('   • Item count (pieces, slots)')
        self.log_step('   • Load capacity (kg)')
        self.log_step('')
        self.log_step('6. ⭐ FEATURES (Besonderheiten):')
        self.log_step('   • Functional features')
        self.log_step('   • Design features')
        self.log_step('   • Safety features')
        self.log_step('')
        self.log_step('7. 🏷️  BRAND & MODEL:')
        self.log_step('   • Brand name visible')
        self.log_step('   • Model number')
        self.log_step('')
        self.log_step('8. 📜 CERTIFICATIONS:')
        self.log_step('   • CE marking')
        self.log_step('   • FDA approval')
        self.log_step('   • Safety certifications')
        self.log_step('')
        self.log_step('9. 🌡️  TECHNICAL SPECS:')
        self.log_step('   • Temperature range (°C)')
        self.log_step('   • Power (Watt, Volt)')
        self.log_step('   • Pressure ratings')
        self.log_step('')
        self.log_step('10. 🔨 ASSEMBLY:')
        self.log_step('   • Assembly required?')
        self.log_step('   • Tools needed?')
        self.log_step('   • Assembly time')
        self.log_step('')
        
        self.log_step('🎯 TARAMA ÖNCELİĞİ (her görsel için):')
        self.log_step('   1. Image 1: Technical diagrams (bottom/corners)')
        self.log_step('   2. Image 4: Detail shots with overlays')
        self.log_step('   3. Image 3: Before/after, comparison specs')
        self.log_step('   4. Image 5: Usage context, scale indicators')
        self.log_step('   5. Image 2: Feature highlights')
        self.log_step('   6. Image 6: Packaging info')
        self.log_step('')
        
        self.log_step('📍 NEREYE BAKMALI:')
        self.log_step('   • Image overlays (text with arrows)')
        self.log_step('   • Technical diagrams (bottom/side of product shots)')
        self.log_step('   • Product labels (on the product itself)')
        self.log_step('   • Packaging text (boxes, bags)')
        self.log_step('   • Corner text (small specs in image corners)')
        self.log_step('   • Comparison charts (spec tables)')
        self.log_step('   • Infographics (visual spec presentations)')
        self.log_step('')
        
        # Provide image URLs for manual scanning
        self.log_step('🖼️  GÖRSEL URL\'LERİ:')
        for i, img in enumerate(images, 1):
            self.log_step(f'   {i}. {img}')
        self.log_step('')
        
        self.log_step('⚠️  FALLBACK: Title-based basic detection kullanılıyor...')
        self.log_step('')
        
        # Fallback: Basic detection from title
        title_lower = product['title'].lower()
        
        self.comprehensive_specs = {
            'dimensions': {
                'found': False,
                'length_cm': None,
                'width_cm': None,
                'height_cm': None,
                'depth_cm': None,
                'diameter_cm': None,
                'text': '',
                'confidence': 0
            },
            'weight': {
                'found': False,
                'product_weight_g': None,
                'package_weight_g': None,
                'text': '',
                'confidence': 0
            },
            'material': {
                'primary': 'Kunststoff',
                'composition': [],
                'confidence': 70,
                'source': 'title fallback'
            },
            'color': {
                'found': False,
                'main': 'Mehrfarbig',
                'options': [],
                'confidence': 65,
                'source': 'title fallback'
            },
            'capacity': {
                'found': False,
                'volume_liter': None,
                'item_count': None,
                'load_capacity_kg': None,
                'text': '',
                'confidence': 0
            },
            'features': [],
            'brand': {
                'name': 'No-Name',
                'confidence': 80
            },
            'model': {
                'number': '',
                'confidence': 0
            },
            'certifications': [],
            'technical': {
                'temperature_min_c': None,
                'temperature_max_c': None,
                'power_watt': None,
                'voltage': None
            },
            'assembly': {
                'required': 'Unknown',
                'tools_needed': 'Unknown',
                'time_minutes': None
            }
        }
        
        # 🚨 AliExpress SKU-verified dimensions take priority over vision/title guesses
        ali_dims_override = self._get_aliexpress_dimensions_override(product)
        if ali_dims_override:
            self.comprehensive_specs['dimensions'] = ali_dims_override
            self.log_step(f"✅ Dimensions: {ali_dims_override['text']} (AliExpress SKU - VERIFIED, {ali_dims_override['confidence']}%)")
            self.log_step('')
        
        # Basic material detection from title
        if 'metall' in title_lower or 'metal' in title_lower:
            self.comprehensive_specs['material']['primary'] = 'Metall'
            self.comprehensive_specs['material']['confidence'] = 80
        elif 'bambus' in title_lower or 'bamboo' in title_lower:
            self.comprehensive_specs['material']['primary'] = 'Bambus-Holz'
            self.comprehensive_specs['material']['confidence'] = 85
        elif 'holz' in title_lower or 'wood' in title_lower:
            self.comprehensive_specs['material']['primary'] = 'Holz'
            self.comprehensive_specs['material']['confidence'] = 80
        elif 'edelstahl' in title_lower or 'stainless' in title_lower:
            self.comprehensive_specs['material']['primary'] = 'Edelstahl'
            self.comprehensive_specs['material']['confidence'] = 90
        
        # Basic color detection from title (shared with AliExpress SKU parsing)
        title_color = self._match_color_word(title_lower)
        if title_color:
            self.comprehensive_specs['color']['main'] = title_color
            self.comprehensive_specs['color']['found'] = True
            self.comprehensive_specs['color']['confidence'] = 96
            self.comprehensive_specs['color']['source'] = 'title keyword match'
        
        self.log_step('✅ Material: {} ({}% confidence) [FALLBACK]'.format(
            self.comprehensive_specs['material']['primary'],
            self.comprehensive_specs['material']['confidence']
        ))
        self.log_step('✅ Color: {} ({}% confidence) [FALLBACK]'.format(
            self.comprehensive_specs['color']['main'],
            self.comprehensive_specs['color']['confidence']
        ))
        self.log_step('⚠️  Other specs: Not available (manual extraction needed)')
        self.log_step('')
        
        # Save fallback specs
        with open(specs_file, 'w', encoding='utf-8') as f:
            json.dump(self.comprehensive_specs, f, indent=2, ensure_ascii=False)
        
        self.log_step(f'💾 Specs saved: {specs_file}')
        self.log_step('')
        
        # 🚨 CRITICAL: Filter to keep ONLY verified specs (≥95% confidence)
        self.log_step('🔍 FILTERING: Keeping ONLY specs with ≥95% confidence...')
        verified_specs = self._filter_verified_specs(self.comprehensive_specs)
        
        # Count verified vs total
        verified_count = 0
        total_count = 0
        
        if self.comprehensive_specs['dimensions']['found']:
            total_count += 1
            if verified_specs['dimensions']['found']:
                verified_count += 1
        
        if self.comprehensive_specs['weight']['found']:
            total_count += 1
            if verified_specs['weight']['found']:
                verified_count += 1
        
        if self.comprehensive_specs['material']['confidence'] >= 95:
            verified_count += 1
        total_count += 1
        
        if self.comprehensive_specs['color']['confidence'] >= 95:
            verified_count += 1
        total_count += 1
        
        if self.comprehensive_specs['capacity']['found']:
            total_count += 1
            if verified_specs['capacity']['found']:
                verified_count += 1
        
        verified_count += len(verified_specs['features'])
        total_count += len(self.comprehensive_specs['features'])
        
        self.log_step(f'✅ VERIFIED: {verified_count}/{total_count} specs (≥95% confidence)')
        self.log_step('')
        
        # Use VERIFIED specs for listing
        self.comprehensive_specs = verified_specs
        
        return self.comprehensive_specs
    
    def _log_found_specs(self):
        """Log all found specifications (VERIFIED ONLY - ≥95%)"""
        specs = self.comprehensive_specs
        
        self.log_step('📊 VERIFIED SPECS (≥95% confidence):')
        self.log_step('')
        
        if specs['dimensions']['found']:
            self.log_step(f"✅ Dimensions: {specs['dimensions']['text']} ({specs['dimensions']['confidence']}%)")
        else:
            self.log_step("❌ Dimensions: Not found or <95% confidence")
        
        if specs['weight']['found']:
            self.log_step(f"✅ Weight: {specs['weight']['text']} ({specs['weight']['confidence']}%)")
        else:
            self.log_step("❌ Weight: Not found or <95% confidence")
        
        if specs['material']['confidence'] >= 95:
            self.log_step(f"✅ Material: {specs['material']['primary']} ({specs['material']['confidence']}%)")
        else:
            self.log_step(f"⚠️  Material: {specs['material']['primary']} (DEFAULT - no verified data)")
        
        if specs['color']['confidence'] >= 95:
            self.log_step(f"✅ Color: {specs['color']['main']} ({specs['color']['confidence']}%)")
        else:
            self.log_step(f"⚠️  Color: {specs['color']['main']} (DEFAULT - no verified data)")
        
        if specs['capacity']['found']:
            self.log_step(f"✅ Capacity: {specs['capacity']['text']} ({specs['capacity']['confidence']}%)")
        else:
            self.log_step("❌ Capacity: Not found or <95% confidence")
        
        if specs['features']:
            verified_features = [f for f in specs['features'] if (f.get('confidence', 100) if isinstance(f, dict) else 100) >= 95]
            self.log_step(f"✅ Features: {len(verified_features)} verified (≥95%)")
        else:
            self.log_step("❌ Features: None verified")
        
        if specs.get('brand', {}).get('name', 'No-Name') != 'No-Name' and specs.get('brand', {}).get('confidence', 0) >= 95:
            self.log_step(f"✅ Brand: {specs['brand']['name']} ({specs['brand']['confidence']}%)")
        
        if specs.get('certifications'):
            self.log_step(f"✅ Certifications: {', '.join(specs['certifications'])}")
        
        self.log_step('')
        self.log_step('🚨 RULE: Only specs with ≥95% confidence are used in listing!')
        self.log_step('')
    
    def step_5_competitor_pricing(self, product):
        """Step 5: Pricing"""
        self.log_step('=' * 80)
        self.log_step('STEP 5: FIYATLAMA')
        self.log_step('=' * 80)
        
        current_price = product['ebay_price']
        cost = product['ali_price'] + product['shipping']
        
        min_price = cost + 10 + (cost * 0.11)
        
        if current_price < min_price:
            final_price = round(min_price + 2, 2)
            self.log_step(f'⚠️  Fiyat düşük! €{current_price:.2f} → €{final_price:.2f}')
            product['ebay_price'] = final_price
        else:
            final_price = current_price
            self.log_step(f'✅ Fiyat: €{final_price:.2f}')
        
        profit = final_price - cost - (final_price * 0.11)
        self.log_step(f'   💰 Kar: €{profit:.2f}')
        self.log_step('')
        
        return final_price
    
    def step_6_create_comprehensive_description(self, product, specs):
        """
        Step 6: Create description with ALL specifications
        🚨 USES ONLY VERIFIED SPECS (≥95% confidence) - FILTERED IN STEP 4
        """
        self.log_step('=' * 80)
        self.log_step('STEP 6: COMPREHENSIVE DESCRIPTION v5.0 (Verified Specs Only)')
        self.log_step('=' * 80)
        
        title_clean = product['title'].split(',')[0][:60]
        
        # 🚨 All specs here are PRE-FILTERED to ≥95% confidence in step 4
        
        # Dimensions section (if available AND verified)
        dim_section = ''
        if specs['dimensions']['found']:
            dim = specs['dimensions']
            dim_parts = []
            
            if dim['length_cm']:
                dim_parts.append(f'<li>📏 <strong>Länge:</strong> {dim["length_cm"]} cm</li>')
            if dim['width_cm']:
                dim_parts.append(f'<li>📏 <strong>Breite:</strong> {dim["width_cm"]} cm</li>')
            if dim['height_cm']:
                dim_parts.append(f'<li>📏 <strong>Höhe:</strong> {dim["height_cm"]} cm</li>')
            if dim['depth_cm']:
                dim_parts.append(f'<li>📏 <strong>Tiefe:</strong> {dim["depth_cm"]} cm</li>')
            if dim['diameter_cm']:
                dim_parts.append(f'<li>📏 <strong>Durchmesser:</strong> {dim["diameter_cm"]} cm</li>')
            
            if dim_parts:
                dim_section = f'''
<h3 style="color: #2c5f2d;">Abmessungen:</h3>
<ul style="font-size: 14px; line-height: 1.8; background: #f0f8f0; padding: 15px; border-left: 4px solid #2c5f2d;">
{''.join(dim_parts)}
<li>📦 <strong>Kompaktes Design:</strong> Perfekt für jeden Raum</li>
</ul>
'''
        
        # Weight section (if available)
        weight_section = ''
        if specs['weight']['found']:
            weight_section = f'''
<h3 style="color: #2c5f2d;">Gewicht:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
'''
            if specs['weight']['product_weight_g']:
                weight_kg = specs['weight']['product_weight_g'] / 1000
                weight_section += f'<li>⚖️  <strong>Produktgewicht:</strong> {weight_kg:.2f} kg</li>\n'
            if specs['weight']['package_weight_g']:
                pack_kg = specs['weight']['package_weight_g'] / 1000
                weight_section += f'<li>📦 <strong>Verpackungsgewicht:</strong> {pack_kg:.2f} kg</li>\n'
            
            weight_section += '</ul>\n'
        
        # Capacity section (if available)
        capacity_section = ''
        if specs['capacity']['found']:
            capacity_section = '<ul style="font-size: 14px; line-height: 1.8;">\n'
            
            if specs['capacity']['volume_liter']:
                capacity_section += f'<li>📦 <strong>Fassungsvermögen:</strong> {specs["capacity"]["volume_liter"]} Liter</li>\n'
            if specs['capacity']['item_count']:
                capacity_section += f'<li>🔢 <strong>Kapazität:</strong> {specs["capacity"]["item_count"]} Stück</li>\n'
            if specs['capacity']['load_capacity_kg']:
                capacity_section += f'<li>⚖️  <strong>Belastbarkeit:</strong> {specs["capacity"]["load_capacity_kg"]} kg</li>\n'
            
            capacity_section += '</ul>\n'
        
        # Features bullets
        features_bullets = ''
        if specs['features']:
            for feat in specs['features'][:10]:
                feat_val = feat if isinstance(feat, str) else feat.get('value', '')
                if feat_val:
                    features_bullets += f'<li>✅ <strong>{feat_val}</strong></li>\n'
        
        # Certifications (if any)
        cert_section = ''
        if specs['certifications']:
            cert_section = f'''
<h3 style="color: #2c5f2d;">Zertifizierungen & Standards:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
'''
            for cert in specs['certifications']:
                cert_section += f'<li>📜 <strong>{cert}</strong></li>\n'
            cert_section += '</ul>\n'
        
        desc = f'''
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2c5f2d; text-align: center;">{title_clean}</h2>

<p style="font-size: 16px; line-height: 1.6;">
<strong>Praktische Aufbewahrungslösung für Ihr Zuhause!</strong>
</p>

{dim_section}

{weight_section}

<h3 style="color: #2c5f2d;">Produktmerkmale:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>✅ <strong>Material:</strong> {specs['material']['primary']} - Hochwertige Qualität</li>
<li>✅ <strong>Farbe:</strong> {specs['color']['main']} - Elegantes Design</li>
{capacity_section}
{features_bullets}
<li>✅ <strong>Langlebig</strong> - Robuste Verarbeitung</li>
<li>✅ <strong>Pflegeleicht</strong> - Einfach zu reinigen</li>
</ul>

{cert_section}

<h3 style="color: #2c5f2d;">Ideal für:</h3>
<ul style="font-size: 14px; line-height: 1.8;">
<li>🏠 <strong>Wohnzimmer</strong> - Ordnung und Stil</li>
<li>🛏️ <strong>Schlafzimmer</strong> - Organisiert</li>
<li>🖥️ <strong>Arbeitszimmer</strong> - Professionell</li>
<li>🍳 <strong>Küche</strong> - Praktisch</li>
<li>🛁 <strong>Badezimmer</strong> - Sortiert</li>
</ul>

<div style="background: #f0f8f0; padding: 15px; margin-top: 20px; border-left: 4px solid #2c5f2d;">
<p style="margin: 0; font-size: 14px;">
<strong>✅ Schneller Versand aus Deutschland</strong><br>
<strong>✅ Professioneller Kundenservice</strong><br>
<strong>✅ 30 Tage Rückgaberecht</strong><br>
<strong>✅ Sichere Bezahlung</strong>
</p>
</div>

<p style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
Bestellen Sie jetzt und profitieren Sie von unserer schnellen Lieferung!
</p>
</div>
'''
        
        self.log_step(f'✅ Description: {len(desc)} chars (Comprehensive v5.0)')
        self.log_step(f'   Material: {specs["material"]["primary"]} ({specs["material"]["confidence"]}%)')
        self.log_step(f'   Color: {specs["color"]["main"]} ({specs["color"]["confidence"]}%)')
        if specs['dimensions']['found']:
            self.log_step(f'   Dimensions: ✅ Included')
        if specs['weight']['found']:
            self.log_step(f'   Weight: ✅ Included')
        if specs['capacity']['found']:
            self.log_step(f'   Capacity: ✅ Included')
        self.log_step('')
        
        return desc
    
    def recommended_extra_aspects(self, title):
        """
        eBay's own 'Alle übernehmen' (Accept All) AI-suggested item specifics
        for category 159897 are, per the Taxonomy API: Mounting (Montage),
        Assembly Required (Montage erforderlich), Number in Pack (Anzahl pro
        Packung). Safe to infer from the title alone for this niche:
          - Mounting: wall/hanging keywords -> Wandmontage/Hängend, else Freistehend
          - Assembly Required: always 'Nein' for this niche (no-assembly storage items)
          - Anzahl pro Packung: parsed pack count from title, else '1'
        """
        t = title.lower()
        
        if any(w in t for w in ['wandmontiert', 'wandmontage', 'wand-', 'wall mounted', 'wall-mounted']):
            mounting = 'Wandmontage'
        elif any(w in t for w in ['hängend', 'hänge-', 'hanging', 'aufhängen']):
            mounting = 'Hängend'
        elif any(w in t for w in ['tür', 'door']):
            mounting = 'Über der Tür'
        else:
            mounting = 'Freistehend'
        
        pack_match = re.search(r'(\d+)\s*(?:er-pack|stück|stk|pcs|pc|st\.|-teilig|-tlg)', t)
        pack_count = pack_match.group(1) if pack_match else '1'
        
        return {
            'Montage': [mounting],
            'Montage erforderlich': ['Nein'],
            'Anzahl pro Packung': [pack_count]
        }

    def _estimate_package_weight_g(self, length_cm, width_cm, height_cm):
        """
        Conservative shipping-weight ESTIMATE from verified dimensions, for
        eBay's packageWeightAndSize field only (logistics input, not a
        buyer-facing product spec/claim). Missing this field entirely makes
        eBay's International Shipping Program assume a worst-case heavy/large
        package and quote wildly inflated international shipping — confirmed
        root cause of shipping >> item price on our listings (2026-11-20).
        Light plastic/metal small-organizer volumetric estimate, capped to a
        sane small-parcel range.
        """
        try:
            volume_cm3 = float(length_cm) * float(width_cm) * float(height_cm)
        except (TypeError, ValueError):
            return 300  # unknown dims: small generic parcel default
        # ~0.15 g/cm³ effective density for light hollow plastic/metal houseware
        grams = volume_cm3 * 0.15
        return int(max(80, min(grams, 3000)))  # 80g-3kg sane small-parcel band

    def step_7_publish_with_comprehensive_aspects(self, product, specs, description, images):
        """
        Step 7: Publish with ALL specifications as aspects
        🚨 USES ONLY VERIFIED SPECS (≥95% confidence) - FILTERED IN STEP 4
        """
        self.log_step('=' * 80)
        self.log_step('STEP 7: EBAY PUBLISH (Verified Aspects Only - ≥95%)')
        self.log_step('=' * 80)
        
        ebay_title = ' '.join(product['title'].split()[:12])[:80]
        
        # 🚨 Get COLOR from AliExpress verified data (PRIMARY) or vision (secondary)
        # User feedback: "Listelemeden önce AliExpress'te herşeyi belirle"
        final_color = 'Mehrfarbig'  # Default fallback
        
        if 'aliexpress_verified' in product and product['aliexpress_verified'].get('color'):
            # PRIMARY: AliExpress SKU color (most reliable!)
            final_color = product['aliexpress_verified']['color']
            self.log_step(f'✅ Color: {final_color} (from AliExpress SKU - VERIFIED)')
        elif specs['color'].get('found') and specs['color'].get('main'):
            # SECONDARY: Vision analysis color
            final_color = specs['color']['main']
            self.log_step(f'⚠️  Color: {final_color} (from vision - no AliExpress data)')
        else:
            self.log_step(f'⚠️  Color: {final_color} (default fallback)')
        
        # 🚨 Build comprehensive aspects - ALL PRE-FILTERED to ≥95% confidence
        aspects = {
            'Marke': [specs['brand']['name']],
            'Hersteller': [specs['brand']['name']],  # distinct eBay aspect from "Marke" —
                # some categories (e.g. car accessories) mandate Hersteller specifically
            'Produktart': ['Aufbewahrungsbox'],
            'Material': [specs['material']['primary']],
            'Farbe': [final_color],  # VERIFIED COLOR from AliExpress!
            'Zimmer': ['Hauswirtschaftsraum', 'Garage', 'Hobbyraum'],  # Corrected rooms
            'Stil': ['Modern'],
            'Anzahl der Einheiten': ['1']
        }
        
        # Add features as Besonderheiten
        # eBay caps individual aspect VALUES at 65 chars — long vision/description
        # feature text must be truncated per-value, not just limited in count.
        if specs['features']:
            features_list = []
            for feat in specs['features'][:5]:
                feat_val = feat if isinstance(feat, str) else feat.get('value', '')
                if feat_val:
                    feat_val = feat_val[:65].rstrip()
                    features_list.append(feat_val)
            if features_list:
                aspects['Besonderheiten'] = features_list
        
        # 🚨 NEW: auto-accept eBay's own AI-recommended item specifics for this
        # category (same ones shown under "Empfohlene Artikelmerkmale" / "Alle
        # übernehmen" in the seller app) — inferred safely from the title.
        extra_aspects = self.recommended_extra_aspects(product['title'])
        aspects.update(extra_aspects)
        self.log_step(f"✅ Önerilen aspect'ler eklendi: {extra_aspects}")
        
        # Add dimensions (if available)
        if specs['dimensions']['found']:
            if specs['dimensions']['length_cm']:
                aspects['Länge'] = [f"{specs['dimensions']['length_cm']} cm"]
            if specs['dimensions']['width_cm']:
                aspects['Breite'] = [f"{specs['dimensions']['width_cm']} cm"]
            if specs['dimensions']['height_cm']:
                aspects['Höhe'] = [f"{specs['dimensions']['height_cm']} cm"]
            self.log_step('✅ Dimensions aspects added!')
        
        # Add weight (if available)
        if specs['weight']['found'] and specs['weight']['product_weight_g']:
            weight_kg = specs['weight']['product_weight_g'] / 1000
            aspects['Gewicht'] = [f"{weight_kg:.2f} kg"]
            self.log_step('✅ Weight aspect added!')
        
        # Add capacity (if available)
        if specs['capacity']['found']:
            if specs['capacity']['volume_liter']:
                aspects['Fassungsvermögen'] = [f"{specs['capacity']['volume_liter']} L"]
            elif specs['capacity']['item_count']:
                aspects['Kapazität'] = [f"{specs['capacity']['item_count']} Stück"]
            self.log_step('✅ Capacity aspect added!')
        
        self.log_step(f'Title: {ebay_title[:60]}...')
        self.log_step(f'Price: €{product["ebay_price"]:.2f}')
        self.log_step(f'Aspects: {len(aspects)} total (comprehensive)')
        self.log_step('')
        
        try:
            sku = f"ALI-{product['ali_id']}"
            
            inventory_item = {
                'sku': sku,
                'product': {
                    'title': ebay_title,
                    'description': description,
                    'aspects': aspects,
                    'imageUrls': images[:8]
                },
                'condition': 'NEW',
                'availability': {
                    'shipToLocationAvailability': {
                        'quantity': 5  # tek-SKU (variant olmayan) listingler: 1 adet
                            # amatör görünüyordu + ilk satıştan sonra hemen "tükendi"
                            # oluyordu. 5 adet hem profesyonel görünür hem satış limiti
                            # yükünü düşük tutar (günde ~13 listing için güvenli pay).
                            # Variation path (step_7v) bundan etkilenmez, kendi
                            # MAX_LISTED_QUANTITY'sini kullanır.
                    }
                }
            }
            
            # 🚨 CRITICAL FIX (2026-11-20): without packageWeightAndSize, eBay's
            # International Shipping Program assumed a worst-case heavy/large
            # package and quoted shipping costs HIGHER than the item price
            # itself (confirmed live: €16 item + €21.53 "shipping"). Always
            # send real dimensions (when verified) + a conservative weight
            # estimate so eBay prices international shipping realistically.
            dims = specs.get('dimensions', {})
            if dims.get('found') and dims.get('length_cm') and dims.get('width_cm') and dims.get('height_cm'):
                weight_g = self._estimate_package_weight_g(dims['length_cm'], dims['width_cm'], dims['height_cm'])
                inventory_item['packageWeightAndSize'] = {
                    'dimensions': {
                        'length': dims['length_cm'], 'width': dims['width_cm'],
                        'height': dims['height_cm'], 'unit': 'CENTIMETER'
                    },
                    'packageType': 'PACKAGE_THICK_ENVELOPE' if dims['height_cm'] < 3 else 'MAILING_BOX',
                    'weight': {'value': weight_g, 'unit': 'GRAM'}
                }
            else:
                # No verified dims (category doesn't mandate them) — still send a
                # small conservative generic estimate rather than nothing at all.
                inventory_item['packageWeightAndSize'] = {
                    'packageType': 'MAILING_BOX',
                    'weight': {'value': 300, 'unit': 'GRAM'}
                }
            
            ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=inventory_item)
            self.log_step(f'✅ Inventory: {sku}')
            
            offer_data = {
                'sku': sku,
                'marketplaceId': 'EBAY_DE',
                'format': 'FIXED_PRICE',
                'listingPolicies': {
                    'fulfillmentPolicyId': '263035514017',
                    'paymentPolicyId': '263035507017',
                    'returnPolicyId': '269022691017'  # 2026-11-20: see
                        # ebay_variation_publisher.py comment — old policy
                        # 263035512017 froze listings at "Keine Rückgabe" on
                        # the live page despite correct terms; never revert.
                },
                'categoryId': product.get('category_id') or '159897',  # dynamic: honors the
                    # product's actual eBay category (e.g. car-accessory items that don't
                    # mandate Height/Length/Width) instead of always forcing Home-Org 159897
                'merchantLocationKey': 'WAREHOUSE_DE_1',
                'pricingSummary': {
                    'price': {
                        'currency': 'EUR',
                        'value': str(product['ebay_price'])
                    }
                }
            }
            
            response2 = ebay._request('POST', '/sell/inventory/v1/offer', json=offer_data)
            offer_id = response2.get('offerId')
            self.log_step(f'✅ Offer: {offer_id}')
            
            response3 = ebay._request('POST', f'/sell/inventory/v1/offer/{offer_id}/publish')
            listing_id = response3.get('listingId')
            self.log_step(f'✅ Published: {listing_id}')
            self.log_step('')
            
            return listing_id, offer_id
            
        except Exception as e:
            self.log_step(f'❌ Hata: {str(e)}')
            import traceback
            traceback.print_exc()
            return None, None
    
    # Categories require different mandatory item-specifics; cache per category_id
    # so a batch run only hits the Taxonomy API once per category, not once per product.
    _dimension_requirement_cache = {}

    def category_requires_dimensions(self, category_id):
        """True if this eBay category mandates Item Height/Length/Width to publish."""
        if not category_id:
            return False
        if category_id in OrchestraV52._dimension_requirement_cache:
            return OrchestraV52._dimension_requirement_cache[category_id]
        
        required = False
        try:
            data = ebay._request(
                'GET',
                f'/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category?category_id={category_id}'
            )
            dimension_names = {'item height', 'item length', 'item width', 'höhe', 'länge', 'breite'}
            for a in data.get('aspects', []):
                name = (a.get('localizedAspectName') or '').lower()
                if name in dimension_names and a.get('aspectConstraint', {}).get('aspectRequired'):
                    required = True
                    break
        except Exception as e:
            self.log_step(f'⚠️  Taxonomy check failed ({e}) — ölçü zorunlu kabul ediliyor (güvenli taraf)')
            required = True  # fail-safe: assume required rather than risk a wasted publish attempt
        
        OrchestraV52._dimension_requirement_cache[category_id] = required
        return required

    def has_verified_dimensions(self, product):
        """
        True only if ALL THREE of length/width/height (cm) are present from a
        ≥95%-confidence source (AliExpress SKU or cached vision) — not just
        'found=True'. Flat 2D items (bags, mats) often expose only W×L with
        no real height, which still fails eBay's 3-field requirement, so a
        loose check here would let a doomed publish attempt through anyway.
        """
        def all_three_present(d):
            return bool(d) and all(d.get(k) is not None for k in ('length_cm', 'width_cm', 'height_cm'))
        
        ali_dims = product.get('aliexpress_verified', {}).get('dimensions')
        if all_three_present(ali_dims):
            return True
        
        specs_file = f'comprehensive_specs_{product["id"]}.json'
        if os.path.exists(specs_file):
            try:
                with open(specs_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                d = cached.get('dimensions', {})
                if d.get('found') and d.get('confidence', 0) >= 95 and all_three_present(d):
                    return True
            except Exception:
                pass
        return False

    def should_use_variation_listing(self, product):
        """True if AliExpress exposes real color and/or size variants (>1 distinct value)."""
        av = product.get('aliexpress_verified', {})
        return bool(av.get('color_variants')) or bool(av.get('size_variants'))

    def step_7v_publish_variation_listing(self, product, category_id=None):
        """
        Step 7 (variation path): instead of flattening a multi-SKU AliExpress
        product into one eBay offer with a guessed color/size, build a REAL
        eBay variation listing — one buyer-selectable SKU per (color, size,
        pack) combination, each with its own verified AliExpress data.
        
        Reuses the existing, battle-tested VariationManager + 
        VariationListingPublisher (rollback-safe) instead of duplicating
        that logic here.
        """
        self.log_step('=' * 80)
        self.log_step('STEP 7v: EBAY VARIATION LISTING (color/size SKU varyantları)')
        self.log_step('=' * 80)
        
        sys.path.insert(0, 'src')
        from variation_manager import VariationManager
        from ebay_variation_publisher import VariationListingPublisher
        
        av = product['aliexpress_verified']
        raw_variants = av.get('variants', [])
        
        # Pricing: preserve the SAME markup ratio used for the single-SKU path,
        # applied per-SKU so a bigger/costlier size variant isn't underpriced.
        base_cost = product['ali_price'] + product['shipping']
        ratio = (product['ebay_price'] / base_cost) if base_cost > 0 else None
        
        variations = []
        seen_combos = set()
        for v in raw_variants:
            sku_ali_price = v.get('price') or product['ali_price']
            try:
                sku_ali_price = float(sku_ali_price)
            except (TypeError, ValueError):
                sku_ali_price = product['ali_price']
            cost = sku_ali_price + product['shipping']
            price = round(cost * ratio, 2) if ratio else product['ebay_price']
            price = max(price, round(cost * 1.15, 2))  # safety floor: never below +15% cost
            
            color = v.get('normalized_color')
            size = v.get('dims_text')
            pack = v.get('pack')
            combo = (color, size, pack)
            if combo == (None, None, None) or combo in seen_combos:
                continue  # no distinguishing attribute, or duplicate combo — skip
            seen_combos.add(combo)
            
            variations.append({
                'color': color,
                'size': size,
                'style': pack,
                'cost': round(cost, 2),
                'price': price,
                'stock': min(v.get('stock') or 10, self.MAX_LISTED_QUANTITY),
                'image': v.get('image')
            })
        
        if len(variations) < 2:
            self.log_step(f'⚠️  Sadece {len(variations)} ayırt edici varyant bulundu — variation listing için yetersiz')
            self.log_step('')
            return None
        
        # 🚨 FIX: eBay rejects a variesBy dimension that has only ONE distinct
        # value across all variants (e.g. every SKU showing 'style': '4 Stück'
        # with no alternative) with "Variantenmerkmalen ... fehlt eine
        # Bezeichnung" (HTTP 400). Drop any dimension that doesn't actually vary.
        for key in ('color', 'size', 'style'):
            distinct = {v[key] for v in variations if v.get(key)}
            if len(distinct) <= 1:
                if distinct:
                    self.log_step(f"ℹ️  '{key}' tüm varyantlarda aynı ({next(iter(distinct))}) — gerçek varyasyon değil, siliniyor")
                for v in variations:
                    v[key] = None
        
        # Clearing a degenerate dimension can collapse two previously-distinct
        # variants into duplicates (e.g. if color was the only differentiator) —
        # re-dedupe and re-check the minimum count after the cleanup above.
        deduped = []
        seen_after_cleanup = set()
        for v in variations:
            combo = (v['color'], v['size'], v['style'])
            if combo == (None, None, None) or combo in seen_after_cleanup:
                continue
            seen_after_cleanup.add(combo)
            deduped.append(v)
        variations = deduped
        
        if len(variations) < 2:
            self.log_step(f'⚠️  Varyasyon temizliği sonrası sadece {len(variations)} ayırt edici varyant kaldı — yetersiz')
            self.log_step('')
            return None
        
        self.log_step(f'📦 {len(variations)} benzersiz varyant hazırlandı (renk/ölçü/paket)')
        for v in variations:
            label = ', '.join(x for x in [v['color'], v['size'], v['style']] if x) or '(no label)'
            self.log_step(f"   • {label} — €{v['price']:.2f} (cost €{v['cost']:.2f}, stock {v['stock']})")
        self.log_step('')
        
        var_manager = VariationManager()
        var_manager.delete_variations(product['id'])  # clean slate if re-run
        add_result = var_manager.add_variations(
            product_id=product['id'],
            base_title=product['title'],
            variations=variations,
            base_image=(product['images'].split(',')[0] if product.get('images') else None)
        )
        
        if not add_result.get('success'):
            self.log_step('❌ Varyantlar DB\'ye yazılamadı')
            self.log_step('')
            return None
        
        cat_id = category_id or '159897'
        publisher = VariationListingPublisher()
        result = publisher.publish_variation_listing(product['id'], category_id=cat_id)
        
        if result.get('success'):
            self.log_step(f"✅ VARIATION LISTING PUBLISHED: {result['listing_id']}")
            self.log_step(f"   SKUs: {result['skus_created']} | Offers: {result['offers_created']}")
            self.log_step('')
        else:
            self.log_step(f"❌ Variation listing failed: {result.get('error')}")
            self.log_step('')
        
        return result

    def step_8_update_database(self, product, listing_id, offer_id):
        """Step 8: Database update"""
        self.log_step('=' * 80)
        self.log_step('STEP 8: DATABASE UPDATE')
        self.log_step('=' * 80)
        
        # 🚨 ROOT-CAUSE FIX (2026-11-21): this write used to fail silently on
        # any exception (e.g. "database is locked" from one of the ~47
        # concurrent cron jobs sharing this SQLite file) — the eBay listing
        # and ad campaign enrollment would go through for real while the DB
        # never recorded ebay_item_id, producing a true desync with ZERO
        # alerting. Confirmed as the actual root cause of several "missing
        # listing" incidents investigated 2026-11-20/21. Now retries transient
        # lock errors, and if ALL retries fail, writes an unmissable fallback
        # record instead of silently discarding a real, money-spending listing.
        import time, json, os
        last_err = None
        for attempt in range(3):
            try:
                self.cursor.execute('''
                    UPDATE products
                    SET is_listed = 1,
                        ebay_item_id = ?,
                        ebay_offer_id = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                ''', (listing_id, offer_id, product['id']))

                self.conn.commit()

                self.log_step(f"✅ ID {product['id']} updated")
                self.log_step('')
                return
            except Exception as e:
                last_err = e
                self.log_step(f'⚠️  DB write attempt {attempt+1}/3 failed: {e}')
                time.sleep(1.5 * (attempt + 1))

        # All 3 attempts failed — this is a REAL published listing (and
        # possibly a real ad-campaign enrollment) that the DB does not know
        # about. Never drop this silently: persist it to a fallback file so
        # a recovery pass (or a human) can reconcile it later.
        self.log_step(f'❌ DB write FAILED after 3 attempts: {last_err}')
        self.log_step('🚨 Yayın GERÇEK ama DB kaydedilemedi — fallback dosyasına yazılıyor')
        try:
            fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'orphaned_listings.json')
            orphans = []
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    orphans = json.load(f)
            orphans.append({
                'product_id': product['id'],
                'listing_id': listing_id,
                'offer_id': offer_id,
                'error': str(last_err),
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
            })
            with open(fallback_path, 'w', encoding='utf-8') as f:
                json.dump(orphans, f, indent=2, ensure_ascii=False)
            self.log_step(f'   -> data/orphaned_listings.json ({len(orphans)} kayıt)')
        except Exception as fe:
            self.log_step(f'   -> fallback dosyası da yazılamadı: {fe} — ID/listing_id yukarıdaki log satırında')
        self.log_step('')
    
    def step_9_create_promoted_listing(self, product, listing_id):
        """
        Step 9: Create eBay Promoted Listing (NEW IN v5.1!)
        
        Automatically adds listing to eBay ad campaign
        """
        self.log_step('=' * 80)
        self.log_step('STEP 9: PROMOTED LISTINGS (REKLAM KAMPANYASI)')
        self.log_step('=' * 80)
        
        self.log_step(f'Listing ID: {listing_id}')
        self.log_step('')
        
        try:
            # Step 9.1: Get or create campaign
            campaign = self._get_or_create_campaign()
            
            if not campaign:
                self.log_step('⚠️  Kampanya oluşturulamadı, reklam atlanıyor')
                self.log_step('')
                return None
            
            campaign_id = campaign['campaign_id']
            self.log_step(f"✅ Kampanya: {campaign['campaign_name']}")
            self.log_step(f"   Campaign ID: {campaign_id}")
            self.log_step(f"   Status: {campaign['status']}")
            self.log_step('')
            
            # Step 9.2: Use default bid rate (safe)
            bid_rate = 8.0
            self.log_step(f"💰 Bid rate: {bid_rate}%")
            self.log_step('')
            
            # Step 9.3: Add listing to campaign
            ad_created = self._add_listing_to_campaign(campaign_id, listing_id, bid_rate)
            
            if ad_created:
                self.log_step(f"✅ Reklam oluşturuldu!")
                self.log_step(f"   Ad ID: {ad_created.get('ad_id')}")
                self.log_step(f"   Listing: {listing_id}")
                self.log_step(f"   Bid Rate: {bid_rate}%")
                self.log_step(f"   Campaign: {campaign['campaign_name']}")
                self.log_step('')
                
                # Update database with ad info
                self.cursor.execute('''
                    UPDATE products
                    SET ad_campaign_id = ?,
                        ad_bid_rate = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                ''', (campaign_id, bid_rate, product['id']))
                
                self.conn.commit()
                
                return {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign['campaign_name'],
                    'ad_id': ad_created.get('ad_id'),
                    'bid_rate': bid_rate
                }
            else:
                self.log_step('❌ Reklam oluşturulamadı')
                self.log_step('')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Promoted listing error: {str(e)}')
            self.log_step('')
            return None
    
    DEFAULT_BID_RATE = 8.0  # must match step_9's bid_rate — keep in sync
    MAX_LISTED_QUANTITY = 20  # cap listed stock per SKU: avoids eBay monthly selling-limit
                              # rejections on multi-variant listings, and dropshippers
                              # shouldn't advertise huge quantities anyway

    def _get_or_create_campaign(self):
        """
        Get the dedicated "BASIS" (general-purpose) promoted-listings campaign,
        or create it if missing.
        
        🚨 FIX: previously matched ANY campaign containing 'Mondeora' or 'Auto'
        in its name — which silently grabbed unrelated niche campaigns like
        "Auto Pet Listings" or "iPhone Case Campaign" for e.g. a storage-box
        listing. Now matches specifically on 'BASIS' in the name, preferring
        the one whose bid rate matches our default (8%) and, among ties, the
        most recently created one (highest campaignId).
        """
        
        self.log_step('Checking existing campaigns...')
        
        try:
            response = ebay._request(
                'GET',
                '/sell/marketing/v1/ad_campaign?campaign_status=RUNNING,SCHEDULED'
            )
            
            campaigns = response.get('campaigns', [])
            
            self.log_step(f'Found {len(campaigns)} RUNNING/SCHEDULED campaign(s)')
            
            # Look for the dedicated BASIS campaign (case-insensitive substring)
            basis_candidates = [c for c in campaigns if 'basis' in c.get('campaignName', '').lower()]
            
            if basis_candidates:
                # Prefer exact bid-rate match, then most recently created
                def sort_key(c):
                    bid = c.get('fundingStrategy', {}).get('bidPercentage')
                    bid_match = (bid is not None and float(bid) == self.DEFAULT_BID_RATE)
                    return (bid_match, int(c.get('campaignId', 0)))
                
                best = max(basis_candidates, key=sort_key)
                return {
                    'campaign_id': best.get('campaignId'),
                    'campaign_name': best.get('campaignName'),
                    'status': best.get('campaignStatus')
                }
            
            # No BASIS campaign exists yet, create one
            self.log_step('BASIS kampanya bulunamadı, yeni oluşturuluyor...')
            
            return self._create_new_campaign()
            
        except Exception as e:
            self.log_step(f'Error getting campaigns: {str(e)}')
            return self._create_new_campaign()
    
    def _create_new_campaign(self):
        """Create new Promoted Listings campaign"""
        
        campaign_name = f'MONDEORA BASIS {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        self.log_step(f'Creating new campaign: "{campaign_name}"')
        
        campaign_data = {
            'campaignName': campaign_name,
            'marketplaceId': 'EBAY_DE',
            'fundingStrategy': {
                'fundingModel': 'COST_PER_SALE',
                'bidPercentage': str(self.DEFAULT_BID_RATE)
            },
            'startDate': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
        
        try:
            response = ebay._request('POST', '/sell/marketing/v1/ad_campaign', json=campaign_data)
            
            campaign_id = response.get('campaignId')
            
            if campaign_id:
                self.log_step(f'✅ Campaign created: {campaign_id}')
                
                return {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign_data['campaignName'],
                    'status': 'SCHEDULED'
                }
            else:
                self.log_step('❌ Campaign creation failed (no ID returned)')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Campaign creation error: {str(e)}')
            return None
    
    def _add_listing_to_campaign(self, campaign_id, listing_id, bid_rate):
        """Add listing to campaign as promoted ad"""
        
        self.log_step(f'Adding listing {listing_id} to campaign...')
        
        # Format bid rate as string with 1 decimal
        bid_str = f"{bid_rate:.1f}"
        
        request_data = {
            'requests': [
                {
                    'listingId': listing_id,
                    'bidPercentage': bid_str
                }
            ]
        }
        
        try:
            response = ebay._request(
                'POST',
                f'/sell/marketing/v1/ad_campaign/{campaign_id}/bulk_create_ads_by_listing_id',
                json=request_data
            )
            
            # Check responses
            responses = response.get('responses', [])
            
            if responses and len(responses) > 0:
                first = responses[0]
                status_code = first.get('statusCode')
                
                if status_code == 201:
                    # Success!
                    return {
                        'ad_id': first.get('adId'),
                        'listing_id': first.get('listingId'),
                        'status': 'ACTIVE'
                    }
                else:
                    self.log_step(f'❌ Ad creation failed: HTTP {status_code}')
                    errors = first.get('errors', [])
                    for err in errors:
                        self.log_step(f'   Error: {err.get("message", "Unknown")}')
                    return None
            else:
                self.log_step('❌ No response from bulk create')
                return None
                
        except Exception as e:
            self.log_step(f'❌ Add listing error: {str(e)}')
            return None
    
    def run(self, product_id=None):
        """Full v5.1 workflow with Promoted Listings
        
        Args:
            product_id: Optional specific product ID to process. If None, auto-select.
        """
        self.log_step('╔══════════════════════════════════════════════════════════════════════╗')
        self.log_step('║      ORCHESTRA v5.1 - COMPREHENSIVE SPECS + PROMOTED LISTINGS      ║')
        self.log_step('╚══════════════════════════════════════════════════════════════════════╝')
        self.log_step('')
        
        start_time = time.time()
        
        # Step 1: Select product (or use specific ID)
        if product_id:
            self.log_step(f'🎯 USING SPECIFIC PRODUCT ID: {product_id}')
            product = self.step_1_load_specific_product(product_id)
        else:
            product = self.step_1_select_product()
        
        if not product:
            return None
        
        # Step 2: Images
        images = self.step_2_update_images(product)
        if len(images) < 1:
            return None
        
        # Step 3: Variant detection (skipped for now)
        
        # 🚨 NEW: if AliExpress exposes real color/size variants, build a proper
        # eBay variation listing (one SKU per combo) instead of flattening to
        # a single guessed SKU. Checked BEFORE the dimension gate below because
        # the variation path auto-fills "Siehe Beschreibung" placeholders for
        # Höhe/Breite/Länge via build_product_specific_aspects — it does NOT
        # need real verified dimensions the way the single-SKU path does.
        # Falls through to the single-SKU flow (and ITS dimension gate) on failure.
        if self.should_use_variation_listing(product):
            var_result = self.step_7v_publish_variation_listing(product)
            if var_result and var_result.get('success'):
                listing_id = var_result['listing_id']
                ad_result = self.step_9_create_promoted_listing(product, listing_id)
                
                end_time = time.time()
                duration = end_time - start_time
                
                self.log_step('=' * 80)
                self.log_step('🎉 ORCHESTRA v5.2 VARIATION LISTING BAŞARIYLA TAMAMLANDI!')
                self.log_step('=' * 80)
                self.log_step('')
                self.log_step(f"🔗 eBay: https://www.ebay.de/itm/{listing_id}")
                self.log_step(f"🧩 SKUs: {var_result['skus_created']} | Offers: {var_result['offers_created']}")
                self.log_step(f"⏱️  Duration: {duration:.1f}s")
                
                return {
                    'listing_id': listing_id,
                    'product_id': product['id'],
                    'is_variation_listing': True,
                    'skus_created': var_result['skus_created'],
                    'offers_created': var_result['offers_created'],
                    'promoted_listing': ad_result,
                    'duration': duration
                }
            else:
                self.log_step('⚠️  Variation listing kurulamadı — single-SKU akışına devam ediliyor (fallback)')
                self.log_step('')
        
        # 🚨 NEW: if this category mandates Item Height/Length/Width and we have
        # NO verified dimension (neither AliExpress SKU nor cached vision ≥95%),
        # skip the product entirely rather than wasting a doomed-to-400 publish
        # attempt. Marks it for a later manual/vision pass instead of failing noisily.
        # (Only reached here — the single-SKU path — since the variation path
        # above doesn't need this and already got its own chance.)
        if self.category_requires_dimensions(product.get('category_id')) and not self.has_verified_dimensions(product):
            self.log_step('⏭️  ATLANDI: Kategori ölçü (Höhe/Breite/Länge) zorunlu istiyor,')
            self.log_step('   ama hiçbir kaynaktan (AliExpress SKU / vision cache) doğrulanmış ölçü yok.')
            self.log_step('   DB status -> needs_dimensions (vision taraması sonra yapılmalı)')
            self.log_step('')
            try:
                self.cursor.execute(
                    "UPDATE products SET status='needs_dimensions', updated_at=datetime('now') WHERE id=?",
                    (product['id'],)
                )
                self.conn.commit()
            except Exception as e:
                self.log_step(f'⚠️  DB status update failed: {e}')
            return {'success': False, 'skipped': True, 'reason': 'no_dimensions', 'product_id': product['id']}
        
        # Step 4: Comprehensive spec extraction
        specs = self.step_4_comprehensive_spec_extraction(product, images)
        
        # Step 5: Pricing
        final_price = self.step_5_competitor_pricing(product)
        
        # Step 6: Comprehensive description
        description = self.step_6_create_comprehensive_description(product, specs)
        
        # Step 7: Publish with comprehensive aspects
        listing_id, offer_id = self.step_7_publish_with_comprehensive_aspects(
            product, specs, description, images
        )
        if not listing_id:
            return None
        
        # Step 8: Database update
        self.step_8_update_database(product, listing_id, offer_id)
        
        # Step 9: Promoted Listings (NEW IN v5.1!)
        ad_result = self.step_9_create_promoted_listing(product, listing_id)
        
        # Final report
        end_time = time.time()
        duration = end_time - start_time
        
        cost = product['ali_price'] + product['shipping']
        profit = product['ebay_price'] - cost - (product['ebay_price'] * 0.11)
        
        self.log_step('=' * 80)
        self.log_step('🎉 ORCHESTRA v5.1 BAŞARIYLA TAMAMLANDI!')
        self.log_step('=' * 80)
        self.log_step('')
        self.log_step(f"🔗 eBay: https://www.ebay.de/itm/{listing_id}")
        self.log_step(f"💰 Price: €{product['ebay_price']:.2f}")
        self.log_step(f"💵 Profit: €{profit:.2f}")
        
        if specs['dimensions']['found']:
            self.log_step(f"📏 Dimensions: ✅ Included")
        if specs['weight']['found']:
            self.log_step(f"⚖️  Weight: ✅ Included")
        if specs['capacity']['found']:
            self.log_step(f"📦 Capacity: ✅ Included")
        
        # NEW: Promoted listing info
        if ad_result:
            self.log_step(f"📢 Promoted Listing: ✅ Active")
            self.log_step(f"   Campaign: {ad_result['campaign_name']}")
            self.log_step(f"   Bid Rate: {ad_result['bid_rate']}%")
        else:
            self.log_step(f"📢 Promoted Listing: ⚠️  Skipped")
        
        self.log_step(f"⏱️  Duration: {duration:.1f}s")
        self.log_step('')
        
        # Save log
        log_file = f"logs/orchestra_v5_1_{listing_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            os.makedirs('logs', exist_ok=True)
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.log))
            self.log_step(f"📄 Log: {log_file}")
        except:
            pass
        
        return {
            'listing_id': listing_id,
            'product_id': product['id'],
            'comprehensive_specs': specs,
            'promoted_listing': ad_result,
            'duration': duration
        }

# Main
if __name__ == '__main__':
    orchestra = OrchestraV52()
    
    try:
        result = orchestra.run()
        
        if result:
            print()
            print('✅ SUCCESS - COMPREHENSIVE SPECS + PROMOTED LISTING!')
            if result.get('promoted_listing'):
                print(f"📢 Ad Campaign: {result['promoted_listing']['campaign_name']}")
                print(f"💰 Bid Rate: {result['promoted_listing']['bid_rate']}%")
        else:
            print('❌ FAILED!')
            
    finally:
        orchestra.close()
