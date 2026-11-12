"""Fetch the RAW aliexpress.ds.product.get response (the client's get_product_details() drops
ae_item_properties, package_info_dto, detail HTML and ratings). Read-only."""
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data' / 'audit'


def fetch_raw(ali, product_id, use_cache=False):
    f = CACHE / f'raw_{product_id}.json'
    if use_cache and f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    env = ali._request('aliexpress.ds.product.get', {'product_id': str(product_id), 'ship_to_country': 'DE',
                                                      'target_currency': 'EUR', 'target_language': 'de'})
    res = env.get('result')
    if not isinstance(res, dict) or not isinstance(res.get('ae_item_base_info_dto'), dict):
        raise ValueError('unsupported product schema')
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8')
    return res


def properties(res):
    """[(name, value)] German product attributes, junk removed."""
    out = []
    items = (res.get('ae_item_properties') or {}).get('ae_item_property') or []
    for p in items:
        n = _html.unescape(str(p.get('attr_name') or '')).strip()
        v = _html.unescape(str(p.get('attr_value') or '')).strip()
        if not n or not v or v.upper() in ('NONE', 'KEINE', 'N/A'):
            continue
        if n.lower() in ('markenname', 'modellnummer', 'herkunft', 'ursprungsort', 'wahl', 'ist elektrisch'):
            continue
        out.append((n, v))
    return out


def detail_text(res, limit=700):
    """Plain, Latin-only text from the detail HTML (empty when the seller only used images).
    Fully HTML-unescapes (named + numeric entities, e.g. '&ouml;' -> 'ö') so description.build()'s
    single html.escape() pass produces correct text, not a double-escaped '&amp;ouml;' visible to buyers."""
    html_text = (res.get('ae_item_base_info_dto') or {}).get('detail') or ''
    txt = re.sub(r'<(script|style).*?</\1>', ' ', html_text, flags=re.S | re.I)
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = _html.unescape(txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    if re.search(r'[\u3400-\u9fff]', txt):
        txt = ' '.join(w for w in txt.split() if not re.search(r'[\u3400-\u9fff]', w))
    return txt[:limit] if len(txt) >= 80 else ''


def package(res):
    p = res.get('package_info_dto') or {}
    return {'l': p.get('package_length'), 'w': p.get('package_width'), 'h': p.get('package_height'),
            'kg': p.get('gross_weight')}
