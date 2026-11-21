#!/usr/bin/env python3
"""
Extract Product-Specific Aspects from Title and Description
Per user instruction: "Her ürünün kendi aspect ve aciklamsini yap"
"""

import re
from typing import Dict, List

# Try to import spaCy context-aware extractor
try:
    from extract_produktart_spacy import extract_produktart_spacy
    HAS_SPACY = True
except:
    HAS_SPACY = False


def extract_produktart(title: str) -> str:
    """
    Extract Produktart from title
    Uses spaCy context-aware extraction if available, otherwise fallback to basic
    """
    
    # Use spaCy if available (context-aware!)
    if HAS_SPACY:
        return extract_produktart_spacy(title)
    
    # Fallback to basic keyword matching
    title_lower = title.lower()
    
    # Specific product types
    if 'angelgerät' in title_lower or 'angelbox' in title_lower:
        return "Angelbox"
    elif 'kleiderbügel' in title_lower or 'bügel' in title_lower:
        return "Kleiderbügel"  # 🔍 NEW: Clothes hanger
    elif 'kabelorganizer' in title_lower or 'kabelaufwickler' in title_lower:
        return "Kabelorganizer"
    elif 'fernbedienungs' in title_lower:
        return "Fernbedienungshalter"
    elif 'müll' in title_lower and ('halter' in title_lower or 'taschen' in title_lower):
        return "Müllbeutelhalter"
    elif 'werkzeug' in title_lower and 'box' in title_lower:
        return "Werkzeugbox"
    elif 'aufbewahrungsbox' in title_lower:
        return "Aufbewahrungsbox"
    elif 'organizer' in title_lower:
        # Generic organizer - try to be more specific
        if 'küchen' in title_lower:
            return "Küchenorganizer"
        elif 'bad' in title_lower or 'bathroom' in title_lower:
            return "Badezimmer-Organizer"
        else:
            return "Organizer"
    elif 'box' in title_lower or 'koffer' in title_lower:
        return "Aufbewahrungsbox"
    else:
        return "Organizer"  # Fallback


def extract_dimensions(title: str, ali_data: dict = None) -> Dict[str, str]:
    """
    Multi-source dimension extraction with fallback priority:
    1. Title (highest - customer visible)
    2. AliExpress package_info_dto
    3. AliExpress properties
    4. Smart defaults
    """
    dimensions = {
        "Breite": None,
        "Höhe": None,
        "Länge": None
    }
    
    # === SOURCE 1: TITLE EXTRACTION ===
    
    # Pattern: "30x20x10 cm" or "30 x 20 x 10cm"
    pattern = r'(\d+(?:,\d+)?)\s*[xX×]\s*(\d+(?:,\d+)?)\s*[xX×]\s*(\d+(?:,\d+)?)\s*cm'
    match = re.search(pattern, title)
    
    if match:
        l, w, h = match.groups()
        dimensions["Länge"] = f"{l.replace(',', '.')} cm"
        dimensions["Breite"] = f"{w.replace(',', '.')} cm"
        dimensions["Höhe"] = f"{h.replace(',', '.')} cm"
        return dimensions
    
    # Pattern: "30cm x 20cm" (2 dimensions)
    pattern2 = r'(\d+(?:,\d+)?)\s*cm\s*[xX×]\s*(\d+(?:,\d+)?)\s*cm'
    match2 = re.search(pattern2, title)
    
    if match2:
        l, w = match2.groups()
        dimensions["Länge"] = f"{l.replace(',', '.')} cm"
        dimensions["Breite"] = f"{w.replace(',', '.')} cm"
        return dimensions
    
    # Pattern: "1m", "2m", "3m", "5m" (Kabel length)
    pattern_meter = r'(\d+(?:,\d+)?)\s*m\b'
    match_meter = re.search(pattern_meter, title.lower())
    
    if match_meter:
        length = match_meter.group(1).replace(',', '.')
        dimensions["Länge"] = f"{length} Meter"
        return dimensions
    
    # Pattern: "30cm", "20mm" (single dimension)
    pattern_single = r'(\d+(?:,\d+)?)\s*(cm|mm)\b'
    match_single = re.search(pattern_single, title.lower())
    
    if match_single:
        value, unit = match_single.groups()
        dimensions["Länge"] = f"{value.replace(',', '.')} {unit}"
        return dimensions
    
    # === SOURCE 2: ALIEXPRESS PACKAGE INFO ===
    if ali_data and 'package_info_dto' in ali_data:
        pkg = ali_data['package_info_dto']
        
        if pkg.get('package_length'):
            dimensions["Länge"] = f"{pkg['package_length']} cm"
        if pkg.get('package_width'):
            dimensions["Breite"] = f"{pkg['package_width']} cm"
        if pkg.get('package_height'):
            dimensions["Höhe"] = f"{pkg['package_height']} cm"
        
        # If we got at least one dimension, return
        if any(dimensions.values()):
            return dimensions
    
    # === SOURCE 3: ALIEXPRESS PROPERTIES ===
    if ali_data and 'properties' in ali_data:
        for prop in ali_data['properties']:
            name = prop.get('name', '').lower()
            value = prop.get('value', '')
            
            if not value:
                continue
            
            if any(x in name for x in ['length', 'länge', 'long']):
                dimensions["Länge"] = value
            elif any(x in name for x in ['width', 'breite', 'wide']):
                dimensions["Breite"] = value
            elif any(x in name for x in ['height', 'höhe', 'high', 'tall']):
                dimensions["Höhe"] = value
        
        # If we got at least one dimension, return
        if any(dimensions.values()):
            return dimensions
    
    # === SOURCE 4: SMART DEFAULTS (product type based) ===
    # Return None for now - let caller decide defaults
    return dimensions


def extract_farbe(title: str) -> str:
    """Extract color from title"""
    title_lower = title.lower()
    
    # German colors
    colors = {
        'weiß': 'Weiß',
        'schwarz': 'Schwarz',
        'grau': 'Grau',
        'blau': 'Blau',
        'rot': 'Rot',
        'grün': 'Grün',
        'gelb': 'Gelb',
        'rosa': 'Rosa',
        'braun': 'Braun',
        'transparent': 'Transparent',
        'beige': 'Beige'
    }
    
    for color_de, color_formal in colors.items():
        if color_de in title_lower:
            return color_formal
    
    # Default
    return "Mehrfarbig"


def extract_material(title: str, produktart: str) -> str:
    """Extract or infer material"""
    title_lower = title.lower()
    
    # Explicit materials in title
    if 'kunststoff' in title_lower or 'plastik' in title_lower or 'plastic' in title_lower:
        return "Kunststoff"
    elif 'metall' in title_lower or 'metal' in title_lower:
        return "Metall"
    elif 'holz' in title_lower or 'wood' in title_lower:
        return "Holz"
    elif 'stoff' in title_lower or 'fabric' in title_lower:
        return "Stoff"
    
    # Infer from product type
    if produktart in ['Angelbox', 'Werkzeugbox', 'Aufbewahrungsbox', 'Kabelorganizer']:
        return "Kunststoff"  # Most storage boxes are plastic
    elif produktart in ['Müllbeutelhalter', 'Fernbedienungshalter']:
        return "Kunststoff"
    else:
        return "Kunststoff"  # Safe default for organizers


def extract_kapazitaet(title: str) -> str:
    """Extract capacity or compartment count"""
    # Pattern: "14 Fächern" or "7 compartments"
    pattern = r'(\d+)\s*(?:fächern|fächer|compartments?|grids?)'
    match = re.search(pattern, title.lower())
    
    if match:
        count = match.group(1)
        return f"{count} Fächer"
    
    # Size indicators
    if 'extra große' in title.lower() or 'extra-große' in title.lower():
        return "Extra groß"
    elif 'große' in title.lower():
        return "Groß"
    elif 'klein' in title.lower():
        return "Klein"
    
    return "Standard"


def extract_besonderheiten(title: str) -> List[str]:
    """Extract special features from title"""
    features = []
    title_lower = title.lower()
    
    if 'mit griff' in title_lower or 'griff' in title_lower:
        features.append("Mit Griff")
    if 'faltbar' in title_lower or 'foldable' in title_lower:
        features.append("Faltbar")
    if 'wand' in title_lower and 'montiert' in title_lower:
        features.append("Wandmontage")
    if 'wasserdicht' in title_lower or 'waterproof' in title_lower:
        features.append("Wasserdicht")
    if 'transparent' in title_lower:
        features.append("Transparent")
    if 'stapelbar' in title_lower:
        features.append("Stapelbar")
    if 'verschließbar' in title_lower or 'mit deckel' in title_lower:
        features.append("Verschließbar")
    if 'doppelseitig' in title_lower:
        features.append("Doppelseitig")
    if 'fluoreszierend' in title_lower:
        features.append("Fluoreszierend")
    
    return features if features else ["Standard"]


def extract_zimmer(produktart: str, title: str) -> str:
    """Extract room/location"""
    title_lower = title.lower()
    
    if 'küchen' in title_lower or 'kitchen' in title_lower:
        return "Küche"
    elif 'bad' in title_lower or 'bathroom' in title_lower:
        return "Badezimmer"
    elif 'schlafzimmer' in title_lower or 'bedroom' in title_lower:
        return "Schlafzimmer"
    elif 'wohnzimmer' in title_lower:
        return "Wohnzimmer"
    elif 'büro' in title_lower or 'office' in title_lower:
        return "Büro"
    
    # Infer from Produktart
    if 'Kabelorganizer' in produktart or 'Fernbedienungshalter' in produktart:
        return "Wohnzimmer"
    elif 'Müllbeutelhalter' in produktart:
        return "Küche"
    elif 'Angelbox' in produktart or 'Werkzeugbox' in produktart:
        return "Garage"
    
    return "Universell"


def build_product_specific_aspects(title: str, template_aspects: Dict, ali_data: dict = None, vision_aspects: dict = None) -> Dict:
    """
    Build product-specific aspects from title + AliExpress data + VISION
    Multi-source fallback with vision priority for maximum accuracy
    Per user: "Her ürünün kendi aspect ve aciklamsini yap"
    
    Args:
        title: Product title
        template_aspects: Category template
        ali_data: AliExpress product data (optional)
        vision_aspects: Vision-extracted aspects (optional, highest priority)
    """
    
    # Extract from title + AliExpress
    produktart = extract_produktart(title)
    dimensions = extract_dimensions(title, ali_data)  # NOW WITH MULTI-SOURCE
    farbe = extract_farbe(title)
    material = extract_material(title, produktart)
    kapazitaet = extract_kapazitaet(title)
    besonderheiten = extract_besonderheiten(title)
    zimmer = extract_zimmer(produktart, title)
    
    # 🔍 VISION OVERRIDE: Use vision data if available and confident
    if vision_aspects:
        # Material: Vision > Title (more reliable)
        if 'Material' in vision_aspects:
            material = vision_aspects['Material'][0] if isinstance(vision_aspects['Material'], list) else vision_aspects['Material']
        
        # Farbe: Vision > Title (visual truth)
        if 'Farbe' in vision_aspects:
            farbe = ', '.join(vision_aspects['Farbe']) if isinstance(vision_aspects['Farbe'], list) else vision_aspects['Farbe']
        
        # Besonderheiten: Merge vision + title (combine features)
        if 'Besonderheiten' in vision_aspects:
            vision_features = vision_aspects['Besonderheiten'] if isinstance(vision_aspects['Besonderheiten'], list) else [vision_aspects['Besonderheiten']]
            # Combine unique features
            combined = list(set(besonderheiten + vision_features))
            besonderheiten = combined[:5]  # Limit to 5
    
    # Build aspects dict
    aspects = {}
    
    # Mandatory aspects (product-specific, now with vision priority)
    aspects["Produktart"] = [produktart]
    aspects["Breite"] = [dimensions["Breite"] or "Siehe Beschreibung"]
    aspects["Höhe"] = [dimensions["Höhe"] or "Siehe Beschreibung"]
    aspects["Länge"] = [dimensions["Länge"] or "Siehe Beschreibung"]
    aspects["Hauptmaterial"] = [material]
    aspects["Material"] = [material]
    aspects["Farbe"] = [farbe]
    aspects["Besonderheiten"] = besonderheiten
    aspects["Zimmer"] = [zimmer]
    aspects["Kapazität"] = [kapazitaet]
    
    # Other aspects from template but keep reasonable
    aspects["Marke"] = ["Markenlos"]
    aspects["Zustand"] = ["Neu"]
    aspects["Herstellungsland und -region"] = ["China"]
    aspects["Personalisiert"] = ["Nein"]
    aspects["Modifizierter Artikel"] = ["Nein"]
    aspects["Angebotspaket"] = ["Nein"]
    aspects["Herstellernummer"] = ["Nicht zutreffend"]
    aspects["Ausländisches Produkt"] = ["Ja"]
    
    # Optional from template
    if "Stil" in template_aspects:
        aspects["Stil"] = ["Modern"]
    if "Finish" in template_aspects:
        aspects["Finish"] = ["Glatt"]
    if "Muster" in template_aspects:
        aspects["Muster"] = ["Ohne Muster"]
    if "Zusätzlich benötigte Teile" in template_aspects:
        aspects["Zusätzlich benötigte Teile"] = ["Keine"]
    if "Eigenschaften" in template_aspects:
        aspects["Eigenschaften"] = ["Langlebig"]
    if "Altersgruppe" in template_aspects:
        aspects["Altersgruppe"] = ["Erwachsene"]
    if "Thema" in template_aspects:
        aspects["Thema"] = ["Aufbewahrung"]
    
    return aspects


if __name__ == '__main__':
    # Test cases
    test_titles = [
        "Angelgerät-Box mit 14 Fächern, Angelzubehör, Aufbewahrungskoffer",
        "Küchen-Kabelaufwickler, Haushalts-Kabelorganizer ohne Spuren",
        "2/6PCS Wand Montiert Müll Taschen Halter",
        "4-Fach-Fernbedienungs-Organizer, kreativer Aufbewahrungskoffer",
        "1/7-teiliges Werkzeugteile-Aufbewahrungsbox-Set, Werkzeug-Organizer"
    ]
    
    for title in test_titles:
        print(f"\n{'='*70}")
        print(f"Title: {title}")
        print(f"{'='*70}")
        
        aspects = build_product_specific_aspects(title, {})
        
        print("\n📋 EXTRACTED ASPECTS:")
        for key, value in list(aspects.items())[:10]:
            print(f"   {key}: {value}")
