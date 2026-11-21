"""
Professional Product Description Generator - OPTIMIZED
Maximum 3900 characters for eBay API limit (4000)
"""

def generate_cable_organizer_description_optimized():
    """Generate optimized professional description under 4000 chars"""
    
    description = """
<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">

<h1 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">
Quadratischer Kabelbinder-Organizer - Fluoreszierend
</h1>

<div style="background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 5px;">
<h3 style="color: #e74c3c; margin-top: 0;">✨ Highlights:</h3>
<ul style="line-height: 1.8;">
<li>🌟 <strong>Fluoreszierend</strong> - Leuchtet im Dunkeln</li>
<li>♻️ <strong>Wiederverwendbar</strong> - Langlebig</li>
<li>📦 <strong>Kompakt</strong> - Platzsparend (12x12x4 cm)</li>
<li>🔧 <strong>Vielseitig</strong> - Kabelbinder, Schrauben, Kleinteile</li>
</ul>
</div>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
📋 Produktbeschreibung
</h2>

<p style="line-height: 1.8;">
Praktischer quadratischer Kabelbinder-Organizer für Kabelbinder, Schrauben, 
Dübel und Kleinteile. Fluoreszierendes Material macht ihn im Dunkeln leicht auffindbar.
Die quadratische Form (12x12x4 cm) ermöglicht platzsparende Lagerung.
</p>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
🔧 Technische Daten
</h2>

<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
<tr style="background: #ecf0f1;">
<td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Material</strong></td>
<td style="padding: 8px; border: 1px solid #bdc3c7;">Kunststoff</td>
</tr>
<tr>
<td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Maße</strong></td>
<td style="padding: 8px; border: 1px solid #bdc3c7;">12 x 12 x 4 cm (L x B x H)</td>
</tr>
<tr style="background: #ecf0f1;">
<td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Farbe</strong></td>
<td style="padding: 8px; border: 1px solid #bdc3c7;">Mehrfarbig (Fluoreszierend)</td>
</tr>
<tr>
<td style="padding: 8px; border: 1px solid #bdc3c7;"><strong>Form</strong></td>
<td style="padding: 8px; border: 1px solid #bdc3c7;">Quadratisch</td>
</tr>
</table>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
✅ Anwendungen
</h2>

<div style="background: #e8f5e9; padding: 12px; border-radius: 5px; margin: 15px 0;">
<strong>Ideal für:</strong> Werkstatt, Büro, Zuhause, Auto<br>
<strong>Verwendung:</strong> Kabelbinder, Schrauben, Bits, Dübel, Nägel, Büroklammern
</div>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
📦 Lieferumfang
</h2>

<p>1x Quadratischer Kabelbinder-Organizer (fluoreszierend)</p>

<h2 style="color: #2c3e50; border-left: 4px solid #3498db; padding-left: 10px;">
🚚 Versand
</h2>

<ul style="line-height: 1.8;">
<li>✅ Versand innerhalb 1-2 Werktagen</li>
<li>📦 Sichere Verpackung</li>
<li>🔄 30 Tage Rückgaberecht</li>
</ul>

<div style="background: #fff9c4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
<strong style="font-size: 18px;">⭐ Perfekt für Ordnung! ⭐</strong>
</div>

<div style="background: #263238; color: white; padding: 15px; text-align: center; border-radius: 5px;">
Bei Fragen kontaktieren Sie uns!<br>
<strong>Vielen Dank! 😊</strong>
</div>

</div>
"""
    
    return description.strip()

if __name__ == '__main__':
    desc = generate_cable_organizer_description_optimized()
    print(desc)
    print()
    print(f'Length: {len(desc)} characters')
    
    if len(desc) > 4000:
        print(f'❌ TOO LONG! Over by {len(desc) - 4000} characters')
    else:
        print(f'✅ OK! Under limit by {4000 - len(desc)} characters')
