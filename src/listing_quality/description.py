"""Unique German HTML description built ONLY from real product data (title, attributes, variants,
package size, manufacturer text). No generic filler, no unverifiable claims."""
import html

from src.listing_quality.source import detail_text, package, properties


def _e(x):
    return html.escape(str(x), quote=True)


def build(title, res, plan, ship_days='7-15'):
    props = properties(res)
    pk = package(res)
    parts = [f'<h2>{_e(title)}</h2>']
    txt = detail_text(res)
    if txt:
        parts.append(f'<p>{_e(txt)}</p>')
    if props:
        rows = ''.join(f'<tr><td><b>{_e(n)}</b></td><td>{_e(v)}</td></tr>' for n, v in props[:20])
        parts.append(f'<h3>Produktmerkmale</h3><table border="1" cellpadding="6" cellspacing="0">{rows}</table>')
    if plan and plan.get('is_variation'):
        lis = ''
        for sp in plan['specifications']:
            lis += f"<li><b>{_e(sp['name'])}:</b> {_e(', '.join(sp['values'][:40]))}</li>"
        parts.append(f'<h3>Verfügbare Varianten</h3><p>Bitte wählen Sie Ihre Variante oben im Angebot aus.</p><ul>{lis}</ul>')
    if pk.get('l') and pk.get('w') and pk.get('h'):
        kg = f", Gewicht ca. {_e(pk['kg'])} kg" if pk.get('kg') else ''
        parts.append(f"<h3>Verpackung</h3><p>Versandmaße ca. {pk['l']} x {pk['w']} x {pk['h']} cm{kg}.</p>")
    parts.append(f'<h3>Versand &amp; Rückgabe</h3><p>Zustand: Neu. Versand aus dem Ausland, Lieferzeit ca. {ship_days} Werktage. '
                 'Rückgabe gemäß den im Angebot hinterlegten Rückgabebedingungen.</p>')
    return '<div>' + ''.join(parts) + '</div>'
