"""Unique German HTML description built ONLY from real product data (title, attributes, variants,
package size, manufacturer text). No generic filler, no unverifiable claims.

Layout: two visually distinct, styled sections (inline CSS only — eBay strips <style>/<script> blocks,
inline style="" survives) so the listing page reads as "Seite 1" (general/sales copy) and
"Seite 2" (technical/important product facts) instead of a flat wall of text.

eBay caps inventory_item.product.description at 4000 chars — build() trims the properties table
(longest, most compressible part) until the whole thing fits, instead of failing the PUT.
"""
import html

from src.listing_quality.source import detail_text, package, properties

_MAX_LEN = 3900
_ACCENT = '#1a5276'
_BG = '#f4f6f7'
_BD = '#d6dbdf'


def _e(x):
    return html.escape(str(x), quote=True)


def _tag(label, title):
    return (f'<div style="background:{_ACCENT};color:#fff;font-size:11px;font-weight:bold;'
            f'padding:3px 8px;border-radius:3px;display:inline-block;">{_e(label)}</div>'
            f'<h2 style="margin:6px 0 10px;font-size:20px;">{_e(title)}</h2>')


def _box(inner, bg=_BG, border=_BD):
    return f'<div style="background:{bg};border:1px solid {border};border-radius:6px;padding:12px 14px;margin:0 0 12px;">{inner}</div>'


def _render(title, txt, plan, pk, props, n_props):
    page1 = [_tag('Seite 1 - Allgemeine Beschreibung', title)]
    body = f'<p style="font-size:14px;line-height:1.5;margin:0 0 8px;">{_e(txt)}</p>' if txt else ''
    if plan and plan.get('is_variation'):
        lis = ''.join(f"<li><b>{_e(sp['name'])}:</b> {_e(', '.join(sp['values'][:40]))}</li>" for sp in plan['specifications'])
        body += f'<p style="font-size:14px;margin:8px 0 2px;"><b>Varianten:</b> siehe Auswahl oben im Angebot.</p><ul style="font-size:13px;margin:0 0 0 16px;">{lis}</ul>'
    if body:
        page1.append(_box(body))
    page1.append(_box(
        f'<p style="font-size:13px;margin:0;"><b>Versand &amp; Rückgabe</b><br>Neu, Versand aus dem Ausland, '
        f'Lieferzeit ca. 7-15 Werktage. Rückgabe gemäß Angebotsbedingungen.</p>',
        bg='#fff', border=_ACCENT,
    ))

    page2 = []
    rows = ''
    if props[:n_props]:
        rows = ''.join(
            f'<tr><td style="padding:5px 8px;background:{_BG};font-weight:bold;width:38%;">{_e(n)}</td>'
            f'<td style="padding:5px 8px;">{_e(v)}</td></tr>'
            for n, v in props[:n_props]
        )
    if pk.get('l') and pk.get('w') and pk.get('h'):
        kg = f", ca. {_e(pk['kg'])} kg" if pk.get('kg') else ''
        rows += (f'<tr><td style="padding:5px 8px;background:{_BG};font-weight:bold;">Verpackung</td>'
                  f'<td style="padding:5px 8px;">ca. {pk["l"]} x {pk["w"]} x {pk["h"]} cm{kg}</td></tr>')
    if rows:
        page2.append(_tag('Seite 2 - Wichtige Produktinformationen', 'Produktmerkmale'))
        page2.append(_box(f'<table style="width:100%;border-collapse:collapse;font-size:13px;">{rows}</table>', bg='#fff'))

    out = '<div style="font-family:Arial,sans-serif;">' + ''.join(page1)
    if page2:
        out += f'<hr style="border:none;border-top:2px dashed {_BD};margin:16px 0;">' + ''.join(page2)
    return out + '</div>'


def build(title, res, plan, ship_days='7-15'):
    props = properties(res)
    pk = package(res)
    txt = detail_text(res)
    n_props = min(20, len(props))
    out = _render(title, txt, plan, pk, props, n_props)
    while len(out) > _MAX_LEN and n_props > 0:
        n_props -= 1
        out = _render(title, txt, plan, pk, props, n_props)
    if len(out) > _MAX_LEN and txt:
        # last resort: trim the free-text body, properties table already at 0
        txt = txt[:max(0, len(txt) - (len(out) - _MAX_LEN) - 20)]
        out = _render(title, txt, plan, pk, props, n_props)
    return out
