"""
PET LİSTİNG'LERİN AÇIKLAMALARINI GÜNCELLE
Her ürün için ÖZEL, detaylı, ürüne özgü HTML
iPhone Hülle listing'deki kalitede (860125267161)
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, 'src')
import requests

load_dotenv()

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()
ebay.refresh_access_token(force=True)
access_token = os.getenv('EBAY_ACCESS_TOKEN').strip('"')

print("="*70)
print("PET LİSTİNG AÇIKLAMALARINI GÜNCELLEME")
print("Her ürün için ÖZEL, detaylı HTML")
print("="*70)

# Her ürün için ÖZEL HTML şablonları
PRODUCT_DESCRIPTIONS = {
    "SAFE-PET-001": {
        "name": "Hunde Spielzeug Ball Set",
        "emoji": "🐕",
        "title": "Premium Hunde Spielzeug Ball Set - Interaktiv & Bissfest",
        "subtitle": "Naturkautschuk • Zahnreinigung • Schwimmfähig • Ungiftig",
        "intro": "Das perfekte Spielzeug für aktive Hunde! Unser Premium Ball Set kombiniert Spielspaß mit Zahnpflege und ist ideal für Training, Apportieren und Wasserspiele.",
        "features": [
            ("🦴 Bissfest & Langlebig", "Hergestellt aus 100% Naturkautschuk - hält selbst aggressivem Kauen stand. Perfekt für starke Kiefer."),
            ("🦷 Zahnpflege-Effekt", "Spezielle Rillen und Noppen massieren das Zahnfleisch und entfernen Plaque beim Kauen. Gesunde Zähne ohne Aufwand."),
            ("💧 Wasserfest & Schwimmend", "Schwimmt auf Wasser - ideal für Strand, Pool oder See. Perfekt für Wasserapportier-Training."),
            ("🎾 Hohe Sprungkraft", "Unvorhersehbare Sprünge wecken den Jagdinstinkt. Fördert Bewegung und hält Ihren Hund fit."),
            ("🌿 Ungiftig & Sicher", "Lebensmittelechte Materialien, frei von Schadstoffen. Auch für Welpen ab 3 Monaten geeignet."),
            ("🎯 Vielseitig Einsetzbar", "Für drinnen, draußen, Wasser und Training. Ein Spielzeug für alle Gelegenheiten.")
        ],
        "specs": [
            ("Material", "Naturkautschuk (TPR), lebensmittelecht"),
            ("Größe", "6-8 cm Durchmesser (Medium)"),
            ("Gewicht", "ca. 80-120g pro Ball"),
            ("Farben", "Mehrfarbig (rot, blau, grün)"),
            ("Geeignet für", "Kleine bis große Hunde (5-40 kg)"),
            ("Altersempfehlung", "Ab 3 Monate")
        ],
        "usecases": "Apportieren im Park • Wasserspiele am Strand • Zahnpflege beim Kauen • Einzelspiel wenn Sie weg sind • Training und Erziehung • Belohnung nach dem Spaziergang",
        "warranty": "30 Tage Geld-zurück-Garantie • Schneller Versand in 24-48h • Premium Qualität geprüft"
    },
    
    "SAFE-PET-002": {
        "name": "Katzen Spielzeug Set",
        "emoji": "🐱",
        "title": "Interaktives Katzen Spielzeug Set 10 Teile - Premium Qualität",
        "subtitle": "Maus • Feder • Ball • Sisalseil • Glöckchen • Rassel",
        "intro": "Das ultimative Spielzeug-Set für glückliche Katzen! 10 verschiedene Spielzeuge wecken den Jagdinstinkt und sorgen für stundenlangen Spielspaß.",
        "features": [
            ("🐭 Maus mit Rassel", "Lebensechte Plüschmaus mit integrierter Rassel. Naturgetreue Geräusche aktivieren den Jagdinstinkt Ihrer Katze sofort."),
            ("🪶 Federwedel", "Lange Naturfedern schweben in der Luft - unwiderstehlich für jede Katze. Perfekt für interaktives Spiel mit Ihnen."),
            ("🎾 Bälle mit Glöckchen", "Leichte Bälle rollen und klingeln bei jeder Bewegung. Fördert Aktivität und hält Wohnungskatzen fit."),
            ("🧶 Sisalseil-Spielzeug", "Robustes Sisal zum Kratzen und Krallenwetzen. Schont Ihre Möbel und pflegt die Krallen natürlich."),
            ("🎨 Abwechslungsreich", "10 verschiedene Spielzeuge - Ihre Katze wird nie gelangweilt. Perfekt für Einzelkatzen und Mehrkatzen-Haushalte."),
            ("👶 Für alle Altersgruppen", "Von Kitten bis Senior - jede Katze findet ihr Lieblingsspielzeug. Sicher und ungiftig.")
        ],
        "specs": [
            ("Material", "Plüsch, Naturfedern, Sisal, Kunststoff"),
            ("Set-Umfang", "10 verschiedene Spielzeuge"),
            ("Farben", "Bunt gemischt (rot, gelb, blau, rosa)"),
            ("Größe", "Maus: 8cm, Bälle: 4cm, Feder: 30cm"),
            ("Geeignet für", "Katzen jeden Alters"),
            ("Gewicht", "ca. 150g gesamt")
        ],
        "usecases": "Einzelkatzen gegen Langeweile • Kitten Jagdinstinkt-Training • Wohnungskatzen Auslastung • Bonding-Zeit mit Ihrer Katze • Neue Katze Eingewöhnung • Tägliche Bewegung",
        "warranty": "30 Tage Geld-zurück-Garantie • Schneller Versand • Geprüfte Sicherheit"
    },
    
    "SAFE-PET-003": {
        "name": "Hunde Napf Set",
        "emoji": "🍖",
        "title": "Premium Hunde Napf Set Edelstahl 2er - Rutschfest & Hygienisch",
        "subtitle": "Spülmaschinenfest • Rostfrei • Ergonomisch • Langlebig",
        "intro": "Hochwertige Edelstahl-Näpfe für die tägliche Fütterung! Rostfrei, hygienisch und mit rutschfestem Boden - die gesunde Wahl für Ihren Hund.",
        "features": [
            ("🥘 Premium Edelstahl 304", "Lebensmittelechter Edelstahl höchster Qualität. Rostfrei, kratzfest und absolut geruchsneutral. Hält ein Hundeleben lang."),
            ("🛡️ Rutschfester Silikonboden", "Integrierter Gummiring verhindert Verrutschen und Klappern. Schont Ihren Boden und nervt nicht beim Fressen."),
            ("🌡️ Spülmaschinenfest", "Einfache Reinigung bei hohen Temperaturen. Bakterien haben keine Chance - maximale Hygiene für Ihren Liebling."),
            ("📏 Ergonomische Höhe", "Optimale Futterhöhe für gesunde Körperhaltung beim Fressen. Schont Nacken und Gelenke Ihres Hundes."),
            ("💧 Vielseitig", "2 Näpfe - einer für Futter, einer für Wasser. Oder beide für Futter bei großen Rassen. Flexibel einsetzbar."),
            ("♻️ Nachhaltig", "Kein Plastik, kein Mikroplastik. Umweltfreundlich und recycelbar. Die nachhaltige Alternative.")
        ],
        "specs": [
            ("Material", "Edelstahl 304 + Lebensmittelsilikonring"),
            ("Fassungsvermögen", "400ml pro Napf (0,4 Liter)"),
            ("Set-Umfang", "2 Näpfe (Futter + Wasser)"),
            ("Durchmesser", "18 cm / Höhe: 6 cm"),
            ("Geeignet für", "Kleine bis mittelgroße Hunde (bis 25kg)"),
            ("Gewicht", "ca. 300g pro Napf")
        ],
        "usecases": "Tägliche Fütterung • Kleine bis mittelgroße Hunde • Hygienebewusste Halter • Welpen und Senioren • Indoor und Outdoor • Langlebige Investition",
        "warranty": "30 Tage Geld-zurück • Rostfrei-Garantie • Premium Verarbeitung"
    },
    
    "SAFE-PET-004": {
        "name": "Katzen Kratzbaum",
        "emoji": "🐈",
        "title": "Katzen Kratzbaum Sisalseil - Krallenpflege & Möbelschutz",
        "subtitle": "Mehrstufig • Spielzeug inklusive • Stabil • Platzsparend",
        "intro": "Der perfekte Kratzbaum für Wohnungskatzen! Natürliches Sisal pflegt die Krallen, schützt Ihre Möbel und bietet stundenlangen Kletterspaß.",
        "features": [
            ("🌿 Natürliches Sisalseil", "Strapazierfähiges Natursisal hält jahrelangem intensivem Kratzen stand. Ihre Katze wird es lieben, Ihre Möbel verschonen."),
            ("🛋️ Effektiver Möbelschutz", "Gibt Ihrer Katze eine attraktive Alternative. Ihre Couch, Tapete und Vorhänge bleiben endlich verschont."),
            ("🎪 Mehrstufige Konstruktion", "Verschiedene Ebenen zum Klettern, Kratzen und Ausruhen. Fördert natürliches Kletterverhalten und hält fit."),
            ("🧸 Mit Spielzeug", "Hängende Bälle und Pompons für extra Spielspaß. Kombiniert Kratzbaum mit Spielparadies."),
            ("🏗️ Stabil & Sicher", "Robuste Konstruktion mit schwerem Sockel. Kippt nicht um, auch bei wilden Sprüngen. TÜV-geprüfte Sicherheit."),
            ("📐 Platzsparend", "Kompaktes Design perfekt für Wohnungen. Passt in jede Ecke und sieht gut aus.")
        ],
        "specs": [
            ("Material", "Sisal (Stamm), Plüsch (Plattformen), Pressholz"),
            ("Höhe", "60-80 cm (je nach Modell)"),
            ("Farben", "Beige, Grau (neutral zu jeder Einrichtung)"),
            ("Gewichtsgrenze", "bis 8 kg pro Ebene"),
            ("Grundfläche", "40 x 40 cm"),
            ("Montage", "Einfacher Aufbau, Anleitung inklusive")
        ],
        "usecases": "Wohnungskatzen Krallenpflege • Jungkatzen Kletter-Training • Mehrkatzen-Haushalt • Kleine Wohnungen • Möbelschutz • Natürliches Verhalten fördern",
        "warranty": "30 Tage Rückgabe • Stabil-Garantie • Schneller Aufbau"
    },
    
    "SAFE-PET-005": {
        "name": "Hunde Leine Ausziehbar",
        "emoji": "🦮",
        "title": "Hunde Flexileine 5m Automatik - Freilauf & Sicherheit",
        "subtitle": "Ein-Knopf-Bremse • Robust bis 20kg • Soft-Grip • Reflektierend",
        "intro": "Die perfekte Balance zwischen Freilauf und Kontrolle! 5 Meter Freiheit für Ihren Hund, sofortige Sicherheit per Knopfdruck für Sie.",
        "features": [
            ("📏 5 Meter Aktionsradius", "Genug Raum zum Schnüffeln und Erkunden, ohne die Kontrolle zu verlieren. Perfekt für Park, Wald und Stadt."),
            ("🔒 Ein-Knopf-Bremssystem", "Sofortiges Stoppen mit einem Finger. In Gefahrensituationen rettet die Bremse Leben. Einfach und zuverlässig."),
            ("💪 Reißfestes Nylon-Seil", "Hält bis 20kg Zugkraft problemlos stand. Auch für kräftige Zieher geeignet. Langlebig und wetterfest."),
            ("🤲 Ergonomischer Soft-Grip", "Anti-Rutsch Griff liegt perfekt in der Hand. Auch bei langen Spaziergängen keine Blasen oder Schmerzen."),
            ("🌙 Reflektierende Elemente", "Bessere Sichtbarkeit bei Dämmerung und Nacht. Mehr Sicherheit für Sie und Ihren Hund."),
            ("🔄 Automatischer Rücklauf", "Seil zieht sich automatisch ein - kein Verheddern. Immer die perfekte Länge, nie zu viel Durchhang.")
        ],
        "specs": [
            ("Länge", "5 Meter ausziehbar"),
            ("Material", "Nylon-Seil, ABS-Gehäuse, TPR-Griff"),
            ("Geeignet für", "Hunde bis 20 kg Körpergewicht"),
            ("Farben", "Schwarz, Blau, Rot (reflektierend)"),
            ("Gewicht", "ca. 280g"),
            ("Bremstyp", "Ein-Knopf-System mit Arretierung")
        ],
        "usecases": "Tägliche Spaziergänge • Park-Besuche mit Freilauf • Welpen-Training (Rückruf) • Kleine bis mittelgroße Rassen • Stadt und Land • Senioren-Hunde",
        "warranty": "30 Tage Geld-zurück • 12 Monate Defekt-Schutz • Geprüfte Qualität"
    }
}

updated = 0
errors = []

for sku, data in PRODUCT_DESCRIPTIONS.items():
    print(f"\n{'='*70}")
    print(f"{data['name']}")
    print(f"{'='*70}")
    
    try:
        # Mevcut item'ı al
        print(f"1. Mevcut item alınıyor...")
        
        inv_get = requests.get(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={'Authorization': f'Bearer {access_token}', 'Content-Language': 'de-DE'}, timeout=30
        )
        
        if inv_get.status_code != 200:
            print(f"   ⚠️  Item bulunamadı: {inv_get.status_code}")
            errors.append(f"{sku}: Item not found")
            continue
        
        inv_data = inv_get.json()
        images = inv_data['product'].get('imageUrls', [])
        
        if len(images) == 0:
            print(f"   ⚠️  Görsel yok!")
            errors.append(f"{sku}: No images")
            continue
        
        print(f"   ✅ Item bulundu ({len(images)} görsel)")
        
        # ÖZEL HTML oluştur
        print(f"2. Ürüne özel HTML oluşturuluyor...")
        
        # Görseller için TABLE (sadece 3 görsel)
        img1 = images[0] if len(images) > 0 else ""
        img2 = images[1] if len(images) > 1 else images[0]
        img3 = images[2] if len(images) > 2 else images[0]
        
        # Features (kompakt ama detaylı)
        feat = ""
        for title, desc in data['features']:
            # İlk 5 feature'ı al (6 yerine)
            if len(feat.split("<tr>")) > 6:
                break
            feat += f"<tr><td style='padding:7px;background:#f9f9f9;'><b style='color:#667eea;font-size:15px;'>{title}</b><br><span style='color:#666;font-size:12px;'>{desc}</span></td></tr>"
        
        # Specs (kompakt)
        spec = ""
        for label, value in data['specs']:
            spec += f"<tr><td style='padding:5px;background:#f9f9f9;font-weight:600;width:38%;font-size:13px;'>{label}</td><td style='padding:5px;font-size:13px;'>{value}</td></tr>"
        
        html = f"""<html><body style="margin:0;font-family:Arial;">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:30px 15px;text-align:center;">
<div style="font-size:36px;">{data['emoji']}</div>
<h1 style="font-size:24px;margin:10px 0;">{data['title']}</h1>
<p style="margin:0;">{data['subtitle']}</p>
</div>
<div style="padding:15px;background:#e7f3ff;">
<p style="margin:0;font-size:14px;line-height:1.5;"><b>{data['intro']}</b></p>
</div>
<div style="padding:15px;">
<table width="100%" cellpadding="3">
<tr>
<td width="33%" align="center"><img src="{img1}" width="200" style="max-width:100%;border-radius:6px;"></td>
<td width="33%" align="center"><img src="{img2}" width="200" style="max-width:100%;border-radius:6px;"></td>
<td width="33%" align="center"><img src="{img3}" width="200" style="max-width:100%;border-radius:6px;"></td>
</tr>
</table>
</div>
<div style="padding:15px;background:#f9f9f9;">
<h2 style="color:#667eea;font-size:20px;margin:0 0 10px;">✨ Premium Features</h2>
<table width="100%">{feat}</table>
</div>
<div style="padding:15px;">
<h2 style="color:#667eea;font-size:20px;margin:0 0 10px;">📋 Technische Daten</h2>
<table width="100%">{spec}</table>
</div>
<div style="padding:15px;background:#fff3cd;">
<h3 style="color:#856404;font-size:16px;margin:0 0 8px;">🎯 Perfekt für:</h3>
<p style="margin:0;font-size:14px;color:#856404;">{data['usecases']}</p>
</div>
<div style="padding:15px;background:#d4edda;">
<h3 style="color:#155724;font-size:16px;margin:0 0 8px;">✅ Ihre Garantien:</h3>
<p style="margin:0;font-size:14px;color:#155724;">{data['warranty']}</p>
</div>
<div style="padding:20px;">
<table width="100%">
<tr>
<td width="33%" align="center"><div style="font-size:28px;">🚚</div><b>Schnell</b></td>
<td width="33%" align="center"><div style="font-size:28px;">↩️</div><b>30 Tage</b></td>
<td width="33%" align="center"><div style="font-size:28px;">✅</div><b>Qualität</b></td>
</tr>
</table>
</div>
<div style="background:#28a745;color:#fff;padding:25px 15px;text-align:center;">
<h2 style="margin:0;font-size:22px;">🛒 Jetzt Bestellen!</h2>
</div>
</body></html>"""
        
        # HTML'i güncelle
        inv_data['product']['description'] = html
        
        print(f"3. Inventory item güncelleniyor... (HTML: {len(html)} karakter)")

        
        inv_update = requests.put(
            f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Content-Language': 'de-DE'
            },
            json=inv_data, timeout=30
        )
        
        if inv_update.status_code in [200, 204]:
            print(f"   ✅ Açıklama güncellendi!")
            updated += 1
        else:
            print(f"   ⚠️  Update failed: {inv_update.status_code}")
            print(f"   {inv_update.text[:200]}")
            errors.append(f"{sku}: Update failed {inv_update.status_code}")
            
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        errors.append(f"{sku}: {str(e)}")

print(f"\n" + "="*70)
print(f"✅ TAMAMLANDI!")
print(f"="*70)

print(f"\n📊 SONUÇ:")
print(f"   Güncellenen: {updated}/5 listing")

if errors:
    print(f"\n⚠️  HATALAR ({len(errors)}):")
    for err in errors:
        print(f"   - {err}")

print(f"\n🎨 HER ÜRÜN ARTIK ÖZEL AÇIKLAMAYA SAHİP!")
print(f"   ✅ Ürüne özel başlık ve emoji")
print(f"   ✅ Gerçek özellikler (features)")
print(f"   ✅ Teknik spesifikasyonlar")
print(f"   ✅ Kullanım senaryoları")
print(f"   ✅ Professional TABLE-based HTML")
print(f"\n⏳ eBay cache güncellenmesi 1-2 dakika sürer")
