#!/usr/bin/env python3
"""
Extract Item Specifics (Aspects) from AliExpress Product
Parses description, properties, and product details to enrich eBay listings.
"""

import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayRESTClient
from src.listing_quality import categories
from src.runtime import read_config


def extract_dimensions_from_text(text):
    """Extract dimensions from German text (e.g., '60*40*30cm')."""
    
    patterns = [
        r'(\d+)\s*[*xX×]\s*(\d+)\s*[*xX×]\s*(\d+)\s*cm',  # 60*40*30cm
        r'(\d+)\s*cm\s*[*xX×]\s*(\d+)\s*cm\s*[*xX×]\s*(\d+)\s*cm',
        r'Größe[:\s]+(\d+)[*xX](\d+)[*xX](\d+)',
        r'(\d+)\s*[*xX×]\s*(\d+)\s*[*xX×]\s*(\d+)',  # 60*40*30 (no cm)
        r'(\d+)cm\s*[*xX×]\s*(\d+)cm\s*[*xX×]\s*(\d+)cm',  # 60cm*40cm*30cm
        r'Abmessungen?[:\s]+(\d+)\s*[*xX×]\s*(\d+)\s*[*xX×]\s*(\d+)',
        r'Maße?[:\s]+(\d+)\s*[*xX×]\s*(\d+)\s*[*xX×]\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                'breite': f"{match.group(1)} cm",
                'tiefe': f"{match.group(2)} cm",
                'höhe': f"{match.group(3)} cm"
            }
    
    # Try individual dimension patterns
    dims = {}
    if 'breite' not in dims:
        m = re.search(r'Breite[:\s]+(\d+)\s*cm', text, re.IGNORECASE)
        if m:
            dims['breite'] = f"{m.group(1)} cm"
    
    if 'höhe' not in dims:
        m = re.search(r'Höhe[:\s]+(\d+)\s*cm', text, re.IGNORECASE)
        if m:
            dims['höhe'] = f"{m.group(1)} cm"
    
    if 'tiefe' not in dims or 'länge' not in dims:
        m = re.search(r'(?:Tiefe|Länge)[:\s]+(\d+)\s*cm', text, re.IGNORECASE)
        if m:
            dims['tiefe'] = f"{m.group(1)} cm"
    
    return dims


def extract_material_from_text(text):
    """Extract material from German text."""
    
    materials = {
        'vliesstoff': 'Vliesstoff',
        'polyester': 'Polyester',
        'oxford': 'Oxford-Stoff',
        'nylon': 'Nylon',
        'baumwolle': 'Baumwolle',
        'kunststoff': 'Kunststoff',
        'edelstahl': 'Edelstahl',
        'metall': 'Metall',
        'holz': 'Holz',
        'silikon': 'Silikon',
        'gummi': 'Gummi',
    }
    
    text_lower = text.lower()
    for key, value in materials.items():
        if key in text_lower:
            return value
    
    return None


def extract_color_from_text(text):
    """Extract color from German text."""
    
    colors = {
        'schwarz': 'Schwarz',
        'weiß': 'Weiß',
        'grau': 'Grau',
        'blau': 'Blau',
        'rot': 'Rot',
        'grün': 'Grün',
        'gelb': 'Gelb',
        'beige': 'Beige',
        'navy': 'Navy',
        'rosa': 'Rosa',
        'braun': 'Braun',
    }
    
    text_lower = text.lower()
    for key, value in colors.items():
        if key in text_lower:
            return value
    
    return None


def extract_features_from_text(text):
    """Extract Besonderheiten (features) from text."""
    
    features = []
    feature_keywords = {
        'faltbar': 'Faltbar',
        'zusammenklappbar': 'Zusammenklappbar',
        'staubdicht': 'Staubdicht',
        'wasserdicht': 'Wasserdicht',
        'wetterfest': 'Wetterfest',
        'platzsparend': 'Platzsparend',
        'leicht zu reinigen': 'Leicht zu reinigen',
        'wiederverwendbar': 'Wiederverwendbar',
        'robust': 'Robust',
        'atmungsaktiv': 'Atmungsaktiv',
    }
    
    text_lower = text.lower()
    for key, value in feature_keywords.items():
        if key in text_lower:
            features.append(value)
    
    return ', '.join(features[:3]) if features else None


def extract_weight_from_text(text):
    """Extract weight from text (e.g., '100g', '1.2kg')."""
    
    patterns = [
        r'(\d+)\s*g\b',
        r'(\d+\.?\d*)\s*kg',
        r'gewicht[:\s]+(\d+)\s*g',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1)
            unit = 'kg' if 'kg' in match.group(0).lower() else 'g'
            return f"{value} {unit}"
    
    return None


def get_category_specific_defaults(category_id):
    """Get default aspects for specific eBay categories."""
    
    defaults = {
        # Grill-Abdeckhauben
        '156955': {
            'Form': 'Rechteckig',
            'Besonderheiten': 'Wetterfest',
        },
        # Pet supplies - general
        '20741': {
            'Tierart': 'Nicht zutreffend',
            'Besonderheiten': 'Haustierfreundlich',
        },
        # Pet - Cats
        '20743': {
            'Tierart': 'Katze',
        },
        # Pet - Dogs
        '20744': {
            'Tierart': 'Hund',
        },
        # Home organization / storage
        '159774': {
            'Zimmer': 'Beliebiger Raum',
            'Form': 'Rechteckig',
        },
        # Kitchen & Dining
        '20625': {
            'Zimmer': 'Küche',
            'Produktart': 'Küchenhelfer',
        },
        # Electronics accessories
        '3270': {
            'Besonderheiten': 'Robust',
        },
        # Home & Garden general
        '11700': {
            'Zimmer': 'Beliebiger Raum',
        },
        # Clothing storage
        '159771': {
            'Zimmer': 'Schlafzimmer',
            'Produktart': 'Aufbewahrung',
        },
    }
    
    return defaults.get(str(category_id), {})


def extract_aspects_for_product(ali, ebay, product_id, category_id, include_competitors=True):
    """
    Extract all possible aspects for a product.
    
    Returns:
        dict: {aspect_name: value, ...}
    """
    
    print(f"\n🔍 Extracting aspects for product {product_id}...")
    
    # Get product details from AliExpress - use source.fetch_raw() for full data
    try:
        from src.listing_quality import source
        res = source.fetch_raw(ali, product_id)
        base_info = res.get('ae_item_base_info_dto', {})
    except Exception as e:
        print(f"  ❌ Failed to get AliExpress details: {e}")
        return {}
    
    # Get description and properties
    subject = base_info.get('subject', '')
    description = base_info.get('detail', '')
    combined_text = f"{subject} {description}"
    
    if not subject:
        print(f"  ⚠️  No product title found")
        return {}
    
    print(f"  📝 Title: {subject[:60]}...")
    
    # Get AliExpress properties
    props = source.properties(res)
    print(f"  📊 AliExpress properties: {len(props)}")
    
    # Debug - show properties
    if props:
        print(f"  🔍 Properties found:")
        for name, value in props[:10]:
            print(f"      {name}: {value}")
    
    # Build property lookup dict
    props_dict = {name.lower(): value for name, value in props}
    
    # Get eBay category aspects metadata
    try:
        meta = categories.aspects_for(ebay, category_id)
        print(f"  📋 eBay category aspects: {len(meta)}")
    except Exception as e:
        print(f"  ❌ Failed to get eBay aspects: {e}")
        return {}
    
    # Extract aspects
    extracted = {}
    
    # 0. COMPETITOR ASPECTS (HIGHEST PRIORITY - Real market data!)
    if include_competitors:
        print(f"\n  🏆 Scraping competitor aspects...")
        try:
            from scripts.scrape_competitor_aspects import scrape_competitor_aspects
            
            competitor_aspects = scrape_competitor_aspects(product_id)
            
            if competitor_aspects:
                # Map English aspect names to German
                aspect_name_map = {
                    'Brand': 'Marke',
                    'Unit Type': 'Einheitentyp',
                    'Country of Origin': 'Herstellungsland und -region',
                    'Country/Region of Manufacture': 'Herstellungsland und -region',
                    'Material': 'Material',
                    'Colour': 'Farbe',
                    'Color': 'Farbe',
                    'Type': 'Produktart',
                    'Style': 'Stil',
                    'Features': 'Besonderheiten',
                    'MPN': 'Herstellernummer',
                    'Model': 'Modell',
                }
                
                added_count = 0
                for eng_name, value in competitor_aspects.items():
                    german_name = aspect_name_map.get(eng_name, eng_name)
                    # Convert to list format (eBay expects lists)
                    if not isinstance(value, list):
                        value = [str(value)]
                    extracted[german_name] = value
                    added_count += 1
                    print(f"    ✅ {german_name}: {value[0] if value else ''} (competitor)")
                
                print(f"  🏆 Added {added_count} competitor aspects")
                    
        except Exception as e:
            print(f"    ⚠️  Competitor scraping failed: {e}")
            import traceback
            traceback.print_exc()
    
    # 1. First, use categories.fill_aspects() for direct mapping
    from_props, missing = categories.fill_aspects(meta, props, enrich=True)
    # Merge with competitor aspects (don't overwrite competitor data)
    for k, v in from_props.items():
        if k not in extracted:
            extracted[k] = v
    print(f"  ✅ From properties: {len(from_props)} aspects")
    
    # 2. Dimensions
    dims = extract_dimensions_from_text(combined_text)
    if dims:
        print(f"  ✅ Dimensions: {dims}")
        for aspect in meta:
            name_lower = aspect['name'].lower()
            if 'breite' in name_lower and 'breite' in dims:
                extracted[aspect['name']] = dims['breite']
            elif 'tiefe' in name_lower and 'tiefe' in dims:
                extracted[aspect['name']] = dims['tiefe']
            elif 'höhe' in name_lower and 'höhe' in dims:
                extracted[aspect['name']] = dims['höhe']
            elif 'länge' in name_lower and 'breite' in dims:
                extracted[aspect['name']] = dims['breite']
    
    # 3. Material - check if not already filled
    if not any('material' in name.lower() for name in extracted.keys()):
        material = extract_material_from_text(combined_text)
        if material:
            print(f"  ✅ Material (text): {material}")
            for aspect in meta:
                if 'material' in aspect['name'].lower():
                    extracted[aspect['name']] = material
                    break
    
    # 3. Color - check if not already filled
    if not any('farbe' in name.lower() for name in extracted.keys()):
        color = extract_color_from_text(combined_text)
        if color:
            print(f"  ✅ Color (text): {color}")
            for aspect in meta:
                if 'farbe' in aspect['name'].lower():
                    extracted[aspect['name']] = color
                    break
    
    # 4. Features/Besonderheiten - check if not already filled
    if not any('besonderheit' in name.lower() for name in extracted.keys()):
        features = extract_features_from_text(combined_text)
        if features:
            print(f"  ✅ Features (text): {features}")
            for aspect in meta:
                if 'besonderheit' in aspect['name'].lower():
                    extracted[aspect['name']] = features
                    break
    
    # 5. Weight - check if not already filled
    if not any('gewicht' in name.lower() for name in extracted.keys()):
        weight = extract_weight_from_text(combined_text)
        if weight:
            print(f"  ✅ Weight (text): {weight}")
            for aspect in meta:
                if 'gewicht' in aspect['name'].lower():
                    extracted[aspect['name']] = weight
                    break
    
    # 6. Form (shape) - check if not already filled
    if not any('form' in name.lower() for name in extracted.keys()):
        for aspect in meta:
            if 'form' in aspect['name'].lower():
                extracted[aspect['name']] = 'Rechteckig'  # Default rectangular
                print(f"  ✅ Form (default): Rechteckig")
                break
    
    # 7. Marke (brand) - always add if not present
    if 'Marke' not in extracted:
        for aspect in meta:
            if aspect['name'] == 'Marke':
                extracted['Marke'] = 'Markenlos'
                print(f"  ✅ Marke: Markenlos")
                break
    
    # 8. Category-specific defaults
    defaults = get_category_specific_defaults(category_id)
    for name, value in defaults.items():
        if name not in extracted:
            for aspect in meta:
                if aspect['name'] == name:
                    extracted[name] = value
                    print(f"  ✅ {name}: {value} (default)")
                    break
    
    # 9. Fill REQUIRED aspects with sensible defaults if still missing
    for aspect in meta:
        if aspect['required'] and aspect['name'] not in extracted:
            # Generate sensible default based on aspect name
            default_value = None
            
            name_lower = aspect['name'].lower()
            
            if 'produktart' in name_lower or 'typ' in name_lower:
                default_value = 'Sonstiges'
            elif 'farbe' in name_lower or 'color' in name_lower:
                default_value = 'Mehrfarbig'
            elif 'größe' in name_lower or 'size' in name_lower:
                default_value = 'Einheitsgröße'
            elif 'zustand' in name_lower or 'condition' in name_lower:
                default_value = 'Neu'
            elif 'zimmer' in name_lower or 'room' in name_lower:
                default_value = 'Beliebiger Raum'
            elif 'anlass' in name_lower:
                default_value = 'Alltag'
            elif 'stil' in name_lower or 'style' in name_lower:
                default_value = 'Modern'
            elif 'herstellernummer' in name_lower:
                default_value = 'Nicht zutreffend'
            elif 'modell' in name_lower or 'model' in name_lower:
                default_value = 'Nicht zutreffend'
            elif 'modifiziert' in name_lower or 'modified' in name_lower:
                default_value = 'Nein'
            
            if default_value:
                # Check if value is in allowed list
                if aspect['mode'] == 'SELECTION_ONLY' and aspect['values']:
                    if default_value not in aspect['values']:
                        # Try to find similar value in list
                        if 'Sonstiges' in aspect['values']:
                            default_value = 'Sonstiges'
                        elif 'Andere' in aspect['values']:
                            default_value = 'Andere'
                        elif 'Nicht zutreffend' in aspect['values']:
                            default_value = 'Nicht zutreffend'
                        elif aspect['values']:
                            default_value = aspect['values'][0]  # First allowed value
                
                extracted[aspect['name']] = default_value
                print(f"  ✅ {aspect['name']}: {default_value} (required default)")
    
    # 10. Fill high-value OPTIONAL aspects to boost count to 10+
    # Add common aspects that work across most categories
    common_aspects_defaults = {
        'Herstellernummer': 'Nicht zutreffend',
        'Modell': 'Nicht zutreffend',
        'Modifizierter Artikel': 'Nein',
        'Anzahl der Einheiten': '1',
        'Herstellungsland und -region': 'China',
        'Herstellergarantie': 'Keine',
        'Angebotspaket': 'Nein',
        'Ausländisches Produkt': 'Ja',
    }
    
    for name, value in common_aspects_defaults.items():
        if name not in extracted and len(extracted) < 15:
            # Check if this aspect exists in category
            for aspect in meta:
                if aspect['name'] == name:
                    # Verify value is allowed
                    if aspect['mode'] == 'SELECTION_ONLY' and aspect['values']:
                        if value not in aspect['values']:
                            # Try to find similar
                            if 'Nicht zutreffend' in aspect['values']:
                                value = 'Nicht zutreffend'
                            elif 'Nein' in aspect['values']:
                                value = 'Nein'
                            elif 'Ja' in aspect['values'] and name == 'Ausländisches Produkt':
                                value = 'Ja'
                            elif aspect['values']:
                                value = aspect['values'][0]
                            else:
                                continue  # Skip if no valid value
                    
                    extracted[name] = value
                    print(f"  ✅ {name}: {value} (common default)")
                    break
    
    # 11. Add Zimmer/Stil/Form if category supports and we're still below 10
    optional_boosts = [
        ('Zimmer', 'Beliebiger Raum'),
        ('Stil', 'Modern'),
        ('Form', 'Rechteckig'),
        ('Hauptfarbe', 'Mehrfarbig'),
    ]
    
    for aspect_name, default_value in optional_boosts:
        if len(extracted) >= 12:
            break
        
        if aspect_name not in extracted:
            for aspect in meta:
                if aspect['name'] == aspect_name:
                    # Check if value is allowed
                    if aspect['mode'] == 'SELECTION_ONLY' and aspect['values']:
                        if default_value in aspect['values']:
                            extracted[aspect_name] = default_value
                            print(f"  ✅ {aspect_name}: {default_value} (boost)")
                        elif aspect['values']:
                            extracted[aspect_name] = aspect['values'][0]
                            print(f"  ✅ {aspect_name}: {aspect['values'][0]} (boost)")
                    else:
                        extracted[aspect_name] = default_value
                        print(f"  ✅ {aspect_name}: {default_value} (boost)")
                    break
    
    print(f"\n📊 Total extracted: {len(extracted)} aspects")
    return extracted


if __name__ == '__main__':
    # Initialize clients - they auto-load credentials from .env
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    # Test with a product
    test_product = '1005012061920624'  # Hosenbügel
    test_category = '11700'  # Category ID
    
    aspects = extract_aspects_for_product(ali, ebay, test_product, test_category)
    
    print(f"\n{'='*60}")
    print("EXTRACTED ASPECTS:")
    print(f"{'='*60}")
    for name, value in aspects.items():
        print(f"  {name}: {value}")
