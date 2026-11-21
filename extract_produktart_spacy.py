"""
Context-Aware Produktart Extraction using spaCy German NLP
Solves: "Küche Unter-Waschbecken... Bad Rack" → "Küchen-Organizer" (not "Badezimmer-Organizer")
"""

import spacy
from typing import Dict, List, Tuple

# Load German model
try:
    nlp = spacy.load("de_core_news_sm")
except:
    print("⚠️ German model not loaded - falling back to basic extraction")
    nlp = None


def extract_produktart_spacy(title: str) -> str:
    """
    Context-aware Produktart extraction using spaCy NLP
    
    Priority:
    1. Position in title (earlier = higher priority)
    2. Part-of-speech (NOUN/PROPN preferred)
    3. Keyword matching
    """
    
    if not nlp:
        # Fallback to basic extraction
        return extract_produktart_basic(title)
    
    doc = nlp(title)
    
    # Keyword mapping with priority
    keyword_mapping = {
        # Kitchen (highest priority in this niche)
        'küche': ('Küchen-Organizer', 10),
        'küchen': ('Küchen-Organizer', 10),
        'kitchen': ('Küchen-Organizer', 10),
        
        # Bathroom
        'badezimmer': ('Badezimmer-Organizer', 8),
        'bad': ('Badezimmer-Organizer', 5),  # Lower priority (ambiguous)
        'bathroom': ('Badezimmer-Organizer', 8),
        
        # Living room
        'wohnzimmer': ('Wohnzimmer-Organizer', 8),
        'living': ('Wohnzimmer-Organizer', 8),
        
        # Specific product types (high priority)
        'kleiderbügel': ('Kleiderbügel', 15),  # 🔍 NEW: Clothes hanger
        'bügel': ('Kleiderbügel', 12),  # 🔍 NEW: Hanger
        'hanger': ('Kleiderbügel', 12),  # 🔍 NEW: English
        
        'angelgerät': ('Angelbox', 12),
        'angelbox': ('Angelbox', 12),
        'fishing': ('Angelbox', 12),
        
        'werkzeug': ('Werkzeugbox', 12),
        'tool': ('Werkzeugbox', 12),
        
        'kabel': ('Kabelorganizer', 12),
        'cable': ('Kabelorganizer', 12),
        
        'fernbedienung': ('Fernbedienungshalter', 12),
        'remote': ('Fernbedienungshalter', 12),
        
        'müll': ('Müllbeutelhalter', 12),
        'trash': ('Müllbeutelhalter', 12),
        'garbage': ('Müllbeutelhalter', 12),
        
        'gewürz': ('Gewürzregal', 12),
        'spice': ('Gewürzregal', 12),
        
        'schublade': ('Schubladen-Organizer', 10),
        'drawer': ('Schubladen-Organizer', 10),
        
        # Generic
        'organizer': ('Organizer', 3),
        'aufbewahrung': ('Aufbewahrungsbox', 5),
        'storage': ('Aufbewahrungsbox', 5),
        'box': ('Aufbewahrungsbox', 3),
        'halter': ('Halter', 3),
        'holder': ('Halter', 3),
    }
    
    # Analyze tokens with context
    matches = []
    
    for i, token in enumerate(doc):
        lemma = token.lemma_.lower()
        text = token.text.lower()
        
        # Check both lemma and text
        for keyword, (produktart, base_priority) in keyword_mapping.items():
            if keyword in lemma or keyword in text:
                # Calculate priority
                priority = base_priority
                
                # Position weight (earlier = higher priority)
                # First 3 tokens get +5, next 3 get +3, rest get 0
                if i < 3:
                    priority += 5
                elif i < 6:
                    priority += 3
                
                # POS weight (NOUN/PROPN get +2)
                if token.pos_ in ['NOUN', 'PROPN']:
                    priority += 2
                
                matches.append((produktart, priority, i, keyword))
    
    # Sort by priority (highest first)
    matches.sort(key=lambda x: (-x[1], x[2]))  # Priority desc, position asc
    
    if matches:
        best_match = matches[0]
        # Debug info (optional)
        # print(f"   🔍 spaCy: '{best_match[3]}' → {best_match[0]} (priority: {best_match[1]}, pos: {best_match[2]})")
        return best_match[0]
    
    # Fallback to basic extraction
    return extract_produktart_basic(title)


def extract_produktart_basic(title: str) -> str:
    """Basic keyword extraction (fallback)"""
    title_lower = title.lower()
    
    # Priority order
    if 'angelgerät' in title_lower or 'angelbox' in title_lower:
        return "Angelbox"
    if 'werkzeug' in title_lower:
        return "Werkzeugbox"
    if 'kabel' in title_lower:
        return "Kabelorganizer"
    if 'fernbedienung' in title_lower:
        return "Fernbedienungshalter"
    if 'müll' in title_lower or 'beutel' in title_lower:
        return "Müllbeutelhalter"
    if 'gewürz' in title_lower:
        return "Gewürzregal"
    if 'schublade' in title_lower:
        return "Schubladen-Organizer"
    if 'küche' in title_lower or 'kitchen' in title_lower:
        return "Küchen-Organizer"
    if 'badezimmer' in title_lower or 'bathroom' in title_lower:
        return "Badezimmer-Organizer"
    if 'bad' in title_lower:
        return "Badezimmer-Organizer"
    if 'wohnzimmer' in title_lower:
        return "Wohnzimmer-Organizer"
    if 'organizer' in title_lower:
        return "Organizer"
    if 'aufbewahrung' in title_lower or 'storage' in title_lower:
        return "Aufbewahrungsbox"
    if 'box' in title_lower:
        return "Aufbewahrungsbox"
    if 'halter' in title_lower or 'holder' in title_lower:
        return "Halter"
    
    return "Organizer"  # Ultimate fallback


# Test cases
if __name__ == "__main__":
    test_titles = [
        "2 Stück Küche Unter-Waschbecken Lagerung Box Gewürze Organizer Bad Rack",
        "Werkzeugteile-Aufbewahrungsbox-Set",
        "Angelgerät-Box mit 14 Fächern",
        "4-Fach-Fernbedienungs-Organizer",
        "Toocki Kabel-Organizer Kabelmanagement",
        "Müll Taschen Halter Wand Montiert",
        "Küchen-Kabelaufwickler ohne Spuren"
    ]
    
    print("🧪 TESTING CONTEXT-AWARE PRODUKTART EXTRACTION")
    print("=" * 70)
    print()
    
    for i, title in enumerate(test_titles, 1):
        produktart = extract_produktart_spacy(title)
        print(f"{i}. Title: {title[:60]}")
        print(f"   → Produktart: {produktart}")
        print()
    
    print("✅ Context-aware extraction ready!")
