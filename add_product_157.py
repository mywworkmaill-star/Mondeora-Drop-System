import json
import sqlite3
from datetime import datetime

with open('temp_new_product.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

title = d['title']
images = d['images']

# Professional description (optimized <3500 chars)
desc = f'''<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0;">
<h1 style="margin:0;font-size:24px;">{title}</h1>
<p style="margin:10px 0 0;font-size:16px;opacity:0.9;">Premium Qualität • Schneller Versand • 30 Tage Rückgabe</p>
</div>
<div style="padding:20px;">
<h2 style="color:#667eea;font-size:18px;margin:20px 0 10px 0;">🌟 Produkthighlights</h2>
<p style="background:#f8f9fa;padding:12px;margin:8px 0;border-left:4px solid #667eea;"><strong>7 Fächer</strong><br>Perfekte Organisation für Make-up und Kosmetik</p>
<p style="background:#f8f9fa;padding:12px;margin:8px 0;border-left:4px solid #764ba2;"><strong>Transparent</strong><br>Alles auf einen Blick sichtbar</p>
<p style="background:#f8f9fa;padding:12px;margin:8px 0;border-left:4px solid #667eea;"><strong>Robuster Kunststoff</strong><br>Langlebig und leicht zu reinigen</p>
<p style="background:#f8f9fa;padding:12px;margin:8px 0;border-left:4px solid #764ba2;"><strong>Multifunktional</strong><br>Schreibtisch, Badezimmer, Schminktisch</p>
<h2 style="color:#667eea;font-size:18px;margin:20px 0 10px 0;">💡 Anwendungen</h2>
<table width="100%" cellpadding="10"><tr>
<td width="50%"><strong>💄 Kosmetik</strong><br>Lippenstifte, Pinsel, Mascara</td>
<td width="50%"><strong>💅 Nagelpflege</strong><br>Lacke, Feilen, Tools</td>
</tr><tr>
<td width="50%"><strong>📝 Schreibtisch</strong><br>Stifte, Clips, Bürozubehör</td>
<td width="50%"><strong>🛁 Badezimmer</strong><br>Kleine Utensilien organisieren</td>
</tr></table>
<h2 style="color:#667eea;font-size:18px;margin:20px 0 10px 0;">📦 Versand & Garantie</h2>
<div style="background:#e8f5e9;padding:15px;border-radius:8px;border:2px solid #4caf50;color:#2e7d32;">
<strong>✓ Schneller Versand</strong> • <strong>✓ 30 Tage Rückgabe</strong> • <strong>✓ Geprüfte Qualität</strong>
</div>
</div>
<div style="background:#f8f9fa;padding:20px;text-align:center;border-radius:0 0 10px 10px;">
<p style="margin:0;color:#666;">🛒 Jetzt bestellen und Ordnung schaffen!</p>
</div>
</div>'''

print(f'Description: {len(desc)} chars')

if len(desc) > 4000:
    print(f'⚠️  Over limit ({len(desc)} > 4000)')
else:
    print(f'✅ OK ({len(desc)} <= 4000)')

# Aspects (array format!)
aspects = {
    'Marke': ['No-Name'],
    'Produktart': ['Kosmetikorganizer'],
    'Material': ['Kunststoff'],
    'Farbe': ['Transparent'],
    'Zimmer': ['Badezimmer', 'Schlafzimmer'],
    'Besonderheiten': ['7 Fächer', 'Transparent', 'Multifunktional'],
    'Stil': ['Modern'],
    'Anzahl der Einheiten': ['1']
}

# Add to database
conn = sqlite3.connect('data/dropshipping.db')
cursor = conn.cursor()

now = datetime.now().isoformat()

cursor.execute('''
    INSERT INTO products (
        aliexpress_product_id, sku_id, title, image_url, description,
        aliexpress_price, shipping_cost, ebay_price,
        currency, category_id, fulfillment_verified,
        is_listed, status, aspects,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    d['ali_id'], d['sku_id'], title,
    ','.join(images), desc,
    d['price'], d['shipping'], d['ebay_price'],
    'EUR', '20741', 1,
    0, 'ready_to_list', json.dumps(aspects, ensure_ascii=False),
    now, now
))

conn.commit()
new_id = cursor.lastrowid
conn.close()

print()
print('✅ DATABASE EKLENDI!')
print(f'   ID: {new_id}')
print(f'   Aspects: {len(aspects)} items')
print()

d['db_id'] = new_id
with open('temp_new_product.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print(f'Product ID {new_id} - Şimdi VISION ANALYSIS yapılmalı!')
