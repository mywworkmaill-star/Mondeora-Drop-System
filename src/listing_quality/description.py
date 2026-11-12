"""Unique German HTML description built ONLY from real product data (title, attributes, variants,
package size, manufacturer text, manufacturer photos). No generic filler, no unverifiable claims —
the richer 'Beschreibung / Spezifikation / Paket beinhaltet / Hinweis' sections below are populated
from the supplier's OWN detail HTML (its numbered feature points, its own package line, its own
embedded photos), not invented copy.

Layout: two visually distinct, styled sections (inline CSS only — eBay strips <style>/<script> blocks,
inline style="" survives) so the listing page reads as "Seite 1" (general/sales copy: Beschreibung,
variants, shipping) and "Seite 2" (technical facts: Spezifikation, Paket beinhaltet, Hinweis) instead
of a flat wall of text.

eBay caps inventory_item.product.description at 4000 chars — build() trims the least essential parts
first (extra photos, then the properties table, then the free text) until the whole thing fits,
instead of failing the PUT.
"""
import html

from src.listing_quality.source import detail_images, detail_sections, package, properties

_MAX_LEN = 3900
_ACCENT = '#1a5276'
_BG = '#f4f6f7'
_BD = '#d6dbdf'
_HINWEIS = ('Bitte beachten Sie, dass es aufgrund manueller Messung und unterschiedlicher '
            'Monitoreinstellungen zu geringfügigen Abweichungen bei Farbe und Maßen kommen kann.')


def _e(x):
    return html.escape(str(x), quote=True)


def _tag(label, title):
    return (f'<div style="background:{_ACCENT};color:#fff;font-size:11px;font-weight:bold;'
            f'padding:3px 8px;border-radius:3px;display:inline-block;">{_e(label)}</div>'
            f'<h2 style="margin:6px 0 10px;font-size:20px;">{_e(title)}</h2>')


def _box(inner, bg=_BG, border=_BD):
    return f'<div style="background:{bg};border:1px solid {border};border-radius:6px;padding:12px 14px;margin:0 0 12px;">{inner}</div>'


def _beschreibung_box(bullets):
    if not bullets:
        return ''
    if len(bullets) == 1:
        body = f'<p style="font-size:14px;line-height:1.5;margin:0;">{_e(bullets[0])}</p>'
    else:
        items = ''.join(f'<li style="margin:0 0 6px;">{_e(b)}</li>' for b in bullets)
        body = f'<ol style="font-size:14px;line-height:1.5;margin:4px 0 0;padding:0 0 0 18px;">{items}</ol>'
    return _box(f'<h3 style="margin:0 0 8px;font-size:15px;color:{_ACCENT};">Beschreibung</h3>' + body)


def _images_row(imgs, n):
    if n <= 0 or not imgs:
        return ''
    cells = ''.join(
        f'<td style="padding:4px;text-align:center;"><img src="{_e(u)}" alt="Produktfoto" '
        f'style="max-width:150px;width:100%;border-radius:6px;border:1px solid {_BD};"></td>'
        for u in imgs[:n]
    )
    return f'<table style="width:100%;margin:0 0 12px;"><tr>{cells}</tr></table>'


def _paket_box(title, pkg_line):
    line = pkg_line.replace(' * ', ' x ').replace('*', ' x ').strip() if pkg_line else f'1x {title}'
    return _box(f'<h3 style="margin:0 0 6px;font-size:15px;color:{_ACCENT};">Paket beinhaltet</h3>'
                f'<p style="font-size:13px;margin:0;">{_e(line)}</p>', bg='#fff')


def _hinweis_box():
    return _box(f'<h3 style="margin:0 0 6px;font-size:15px;color:{_ACCENT};">Hinweis</h3>'
                f'<p style="font-size:12px;margin:0;color:#666;">{_e(_HINWEIS)}</p>')


def _render(title, bullets, pkg_line, plan, pk, props, n_props, imgs, n_imgs, ship_days):
    page1 = [_tag('Seite 1 - Allgemeine Beschreibung', title)]
    desc_box = _beschreibung_box(bullets)
    if desc_box:
        page1.append(desc_box)
    imgs_row = _images_row(imgs, n_imgs)
    if imgs_row:
        page1.append(imgs_row)
    if plan and plan.get('is_variation'):
        lis = ''.join(f"<li><b>{_e(sp['name'])}:</b> {_e(', '.join(sp['values'][:40]))}</li>" for sp in plan['specifications'])
        page1.append(_box(f'<p style="font-size:14px;margin:0 0 2px;"><b>Varianten:</b> siehe Auswahl oben im Angebot.</p>'
                           f'<ul style="font-size:13px;margin:0 0 0 16px;">{lis}</ul>'))
    page1.append(_box(
        f'<p style="font-size:13px;margin:0;"><b>Versand &amp; Rückgabe</b><br>Neu, Versand aus dem Ausland, '
        f'Lieferzeit ca. {_e(ship_days)} Werktage. Rückgabe gemäß Angebotsbedingungen.</p>',
        bg='#fff', border=_ACCENT,
    ))

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

    page2 = [_tag('Seite 2 - Wichtige Produktinformationen', 'Spezifikation')]
    if rows:
        page2.append(_box(f'<table style="width:100%;border-collapse:collapse;font-size:13px;">{rows}</table>', bg='#fff'))
    page2.append(_paket_box(title, pkg_line))
    page2.append(_hinweis_box())

    out = '<div style="font-family:Arial,sans-serif;">' + ''.join(page1)
    out += f'<hr style="border:none;border-top:2px dashed {_BD};margin:16px 0;">' + ''.join(page2)
    return out + '</div>'


def build(title, res, plan, ship_days='7-15'):
    props = properties(res)
    pk = package(res)
    bullets, pkg_line = detail_sections(res)
    imgs = detail_images(res)
    n_props = min(20, len(props))
    n_imgs = min(2, len(imgs))
    n_bul = len(bullets)
    out = _render(title, bullets[:n_bul], pkg_line, plan, pk, props, n_props, imgs, n_imgs, ship_days)
    # Compression order: drop the least essential parts first (extra photos, then the properties
    # table — already duplicated in eBay's own aspects panel) and only cut INTO the real supplier
    # feature bullets (the main content upgrade) as a last resort, one bullet at a time (keeping the
    # earlier, usually most important points) instead of collapsing everything to one mangled blob.
    while len(out) > _MAX_LEN and (n_imgs > 0 or n_props > 0 or n_bul > 1):
        if n_imgs > 0:
            n_imgs -= 1
        elif n_props > 0:
            n_props -= 1
        else:
            n_bul -= 1
        out = _render(title, bullets[:n_bul], pkg_line, plan, pk, props, n_props, imgs, n_imgs, ship_days)
    if len(out) > _MAX_LEN and bullets[:n_bul]:
        # absolute last resort: trim the text of the one remaining bullet
        trimmed = list(bullets[:n_bul])
        over = len(out) - _MAX_LEN
        trimmed[-1] = trimmed[-1][:max(0, len(trimmed[-1]) - over - 20)]
        out = _render(title, trimmed, pkg_line, plan, pk, props, n_props, imgs, n_imgs, ship_days)
    return out
