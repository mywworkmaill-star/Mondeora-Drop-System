#!/usr/bin/env python3
"""
Generate Product-Specific Descriptions
Per user: "Info zum artikel ler hala ayni Eski baska ürüne Ayir"
"""
import html

def generate_product_description(title: str, produktart: str, zimmer: str, kapazitaet: str, besonderheiten: list) -> str:
    """
    Generate UNIQUE description per product based on its attributes
    NOT generic template!
    """
    
    # Clean title
    # 🚨 SECURITY FIX (2026-11-21): title is raw AliExpress supplier text
    # (ae_item_base_info_dto.subject) inserted straight into live eBay
    # listing HTML below with no escaping — a '<'/'&' in the source title
    # could break the listing's markup. html.escape() closes this.
    clean_title = html.escape(title.strip())
    
    # Product-specific highlights based on Produktart
    highlights = []
    details = {}
    benefits = []
    
    # === WERKZEUGBOX ===
    if 'Werkzeugbox' in produktart or 'werkzeug' in title.lower():
        highlights = [
            "Robuste Werkzeugbox mit mehreren Fächern",
            "Ideal für Schrauben, Muttern, Nägel und Kleinteile",
            "Transparente Deckel für schnellen Überblick",
            "Stapelbar und platzsparend",
            "Perfekt für Garage, Werkstatt und Hobbykeller"
        ]
        details = {
            "Material": "Hochwertig Kunststoff",
            "Farbe": "Mehrfarbig/Transparent",
            "Verwendung": "Garage, Werkstatt, Hobby",
            "Fächer": kapazitaet if kapazitaet != "Standard" else "Mehrere Fächer"
        }
        benefits = [
            "Hält Werkzeugteile ordentlich sortiert",
            "Transparente Deckel - kein langes Suchen",
            "Stapelbar - maximale Platzausnutzung",
            "Robuster Kunststoff - langlebig und stabil",
            "Vielseitig - für Schrauben, Bits, Nägel, etc."
        ]
    
    # === ANGELBOX ===
    elif 'Angelbox' in produktart or 'angel' in title.lower():
        highlights = [
            "Praktische Angelbox mit mehreren Fächern",
            "Ideal für Haken, Köder, Wirbel und Kleinteile",
            "Doppelseitig oder einseitig nutzbar",
            "Wasserfest und robust",
            "Perfekt für Angelausflüge und Outdoor"
        ]
        details = {
            "Material": "Wasserfester Kunststoff",
            "Farbe": "Mehrfarbig",
            "Verwendung": "Angeln, Outdoor, Hobby",
            "Fächer": kapazitaet if kapazitaet != "Standard" else "Mehrere Fächer"
        }
        benefits = [
            "Hält Angelzubehör ordentlich sortiert",
            "Wasserfest - schützt Ausrüstung",
            "Kompakt - passt in jeden Rucksack",
            "Doppelseitig - maximale Kapazität",
            "Robust - hält rauen Bedingungen stand"
        ]
    
    # === KABELORGANIZER ===
    elif 'Kabelorganizer' in produktart or 'kabel' in title.lower():
        highlights = [
            "Praktischer Kabelorganizer für ordentliche Kabel",
            "Selbstklebende Montage - keine Bohrlöcher",
            "Hält Ladekabel und Geräte griffbereit",
            "Kompaktes Design - platzsparend",
            "Wiederverwendbar und langlebig"
        ]
        details = {
            "Material": "Hochwertig Kunststoff",
            "Farbe": "Weiß/Schwarz",
            "Montage": "Selbstklebend",
            "Verwendung": zimmer or "Küche, Büro, Zuhause"
        }
        benefits = [
            "Hält Kabel ordentlich - kein Kabelsalat",
            "Selbstklebend - keine Wandbeschädigung",
            "Wiederverwendbar - mehrfach verwendbar",
            "Platzsparend - ideal für kleine Räume",
            "Vielseitig - für Ladekabel, Mixer, Toaster, etc."
        ]
    
    # === FERNBEDIENUNGSHALTER ===
    elif 'Fernbedienung' in produktart or 'fernbedienung' in title.lower():
        highlights = [
            "Praktischer Fernbedienungshalter mit mehreren Fächern",
            "Hält bis zu 4-5 Fernbedienungen ordentlich",
            "Stabiler Stand auf Tisch oder Sideboard",
            "Kompaktes Design - platzsparend",
            "Perfekt für Wohnzimmer und Schlafzimmer"
        ]
        details = {
            "Material": "Hochwertig Kunststoff",
            "Farbe": "Mehrfarbig",
            "Fächer": "4-5 Fächer",
            "Verwendung": "Wohnzimmer, Schlafzimmer"
        }
        benefits = [
            "Alle Fernbedienungen griffbereit",
            "Kein Suchen mehr - alles an einem Platz",
            "Stabiler Stand - kippt nicht um",
            "Kompakt - nimmt wenig Platz ein",
            "Ordentlich - aufgeräumtes Wohnzimmer"
        ]
    
    # === MÜLLBEUTELHALTER ===
    elif 'Müll' in produktart or 'müll' in title.lower():
        highlights = [
            "Praktischer Müllbeutelhalter für die Küche",
            "Wandmontage - spart Platz unter der Spüle",
            "Hält Müllbeutel griffbereit und ordentlich",
            "Einfache Montage ohne Bohren",
            "Perfekt für Küche und Hauswirtschaftsraum"
        ]
        details = {
            "Material": "Hochwertig Kunststoff",
            "Farbe": "Weiß/Grau",
            "Montage": "Wandmontage (selbstklebend oder Schrauben)",
            "Verwendung": "Küche, Hauswirtschaftsraum"
        }
        benefits = [
            "Müllbeutel immer griffbereit",
            "Wandmontage - spart Schubladenplatz",
            "Ordentlich - kein Müllbeutel-Chaos",
            "Einfache Entnahme - ein Zug genügt",
            "Vielseitig - für verschiedene Beutelgrößen"
        ]
    
    # === GENERIC ORGANIZER (Fallback) ===
    else:
        highlights = [
            f"Praktischer {produktart} für ordentliche Aufbewahrung",
            "Mehrere Fächer für optimale Organisation",
            "Robustes Material - langlebig",
            "Kompaktes Design - platzsparend",
            f"Perfekt für {zimmer or 'Zuhause und Büro'}"
        ]
        details = {
            "Material": "Hochwertig Kunststoff",
            "Farbe": "Mehrfarbig",
            "Verwendung": zimmer or "Universell",
            "Kapazität": kapazitaet
        }
        benefits = [
            "Hält Gegenstände ordentlich sortiert",
            "Kompakt - nimmt wenig Platz ein",
            "Robust - langlebig und stabil",
            "Vielseitig einsetzbar",
            "Gutes Preis-Leistungs-Verhältnis"
        ]
    
    # Build HTML description
    description = f"""<div style="font-family:Arial,sans-serif;">
<div style="background:#1a5276;color:#fff;font-size:11px;font-weight:bold;padding:3px 8px;border-radius:3px;display:inline-block;">Premium {produktart}</div>

<h2 style="margin:6px 0 10px;font-size:20px;">{clean_title}</h2>

<div style="background:#f4f6f7;border:1px solid #d6dbdf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#1a5276;">✨ Produkthighlights</h3>
<ul style="margin:0;padding-left:20px;">"""
    
    for highlight in highlights:
        description += f"\n<li>{highlight}</li>"
    
    description += """
</ul>
</div>

<div style="background:#fff;border:1px solid #d6dbdf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#1a5276;">📋 Produktdetails</h3>
<table style="width:100%;border-collapse:collapse;">"""
    
    for key, value in details.items():
        description += f'\n<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;"><b>{key}:</b></td><td style="padding:4px 8px;border-bottom:1px solid #eee;">{value}</td></tr>'
    
    description += """
</table>
</div>

<div style="background:#e8f8f5;border:1px solid #a9dfbf;border-radius:6px;padding:12px 14px;margin:0 0 12px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#196f3d;">✅ Vorteile</h3>
<p style="margin:0;">"""
    
    for benefit in benefits:
        description += f"\n• {benefit}<br>"
    
    description += """
</p>
</div>

<div style="background:#fef5e7;border:1px solid #f9e79f;border-radius:6px;padding:12px 14px;">
<h3 style="margin:0 0 8px;font-size:15px;color:#9a7d0a;">📦 Lieferumfang</h3>
<p style="margin:0;">"""
    
    description += f"\n1x {produktart}<br>"
    description += "\nGebrauchsanweisung"
    
    description += """
</p>
</div>

</div>"""
    
    return description


if __name__ == '__main__':
    # Test cases
    test_cases = [
        ("1/7-teiliges Werkzeugteile-Aufbewahrungsbox-Set", "Werkzeugbox", "Garage", "7 Fächer", ["Standard"]),
        ("Angelgerät-Box mit 14 Fächern", "Angelbox", "Garage", "14 Fächer", ["Doppelseitig"]),
        ("Küchen-Kabelaufwickler", "Kabelorganizer", "Küche", "Standard", ["Standard"]),
        ("4-Fach-Fernbedienungs-Organizer", "Fernbedienungshalter", "Wohnzimmer", "4 Fächer", ["Standard"]),
        ("Wand Montiert Müll Taschen Halter", "Müllbeutelhalter", "Küche", "Standard", ["Wandmontage"])
    ]
    
    for title, produktart, zimmer, kapazitaet, besonderheiten in test_cases:
        print(f"\n{'='*70}")
        print(f"Title: {title}")
        print(f"Produktart: {produktart}")
        print(f"{'='*70}")
        
        desc = generate_product_description(title, produktart, zimmer, kapazitaet, besonderheiten)
        print(f"\nDescription length: {len(desc)} chars")
        print(f"Preview: {desc[:200]}...")
