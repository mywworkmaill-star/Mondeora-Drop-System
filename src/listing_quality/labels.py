"""Variant labels from the SELLER'S OWN definition name (property_value_definition_name, e.g. 'Camel white-square'), translated
token by token to German. The German sku_property_value that AliExpress returns is machine-translated and often WRONG
(e.g. 'Himmelblau' for three different products, XXXL for the smallest size), so it is never trusted when the English
definition exists. Unknown tokens stay as the seller wrote them (never invented)."""
import re

COLORS = {'red': 'Rot', 'green': 'Grün', 'blue': 'Blau', 'bule': 'Blau', 'yellow': 'Gelb', 'orange': 'Orange', 'pink': 'Rosa',
          'purple': 'Lila', 'violet': 'Lila', 'white': 'Weiß', 'black': 'Schwarz', 'gray': 'Grau', 'grey': 'Grau', 'brown': 'Braun',
          'camel': 'Kamel', 'silver': 'Silber', 'gold': 'Gold', 'beige': 'Beige', 'khaki': 'Khaki', 'coffee': 'Kaffee',
          'navy': 'Marineblau', 'transparent': 'Transparent', 'colorful': 'Mehrfarbig', 'multicolor': 'Mehrfarbig',
          'rainbow': 'Regenbogen', 'rosa': 'Rosa', 'rot': 'Rot', 'grün': 'Grün', 'blau': 'Blau', 'gelb': 'Gelb', 'schwarz': 'Schwarz',
          'weiß': 'Weiß', 'weiss': 'Weiß', 'grau': 'Grau', 'braun': 'Braun'}
WORDS = {'square': 'eckig', 'round': 'rund', 'soap': 'Seife', 'ball': 'Ball', 'stress': 'Stress', 'box': 'Box', 'smart': 'Smart',
         'normal': 'Normal', 'tail': 'Schwanz', 'plush': 'Plüsch', 'rat': 'Ratte', 'toy': 'Spielzeug', 'bird': 'Vogel', 'cat': 'Katze',
         'and': 'und', 'with': 'mit', 'set': 'Set', 'battery': 'Batterie', 'pcs': 'Stück', 'pc': 'Stück'}
SHADE = {'dark': 'Dunkel', 'light': 'Hell'}


def _title(w):
    return w[:1].upper() + w[1:]


def translate(en):
    s = str(en or '').strip()
    if not s:
        return ''
    m = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:inch|in|zoll|")', s, re.I)
    if m:
        return f"{round(float(m.group(1).replace(',', '.')) * 2.54)} cm"
    s = re.sub(r'(?i)\bno\s+battery\b', 'ohne Batterie', s)
    s = re.sub(r'(?i)\bno\s+box\b', 'ohne Box', s)
    s = re.sub(r'(?i)(\d+)\s*(pcs?|pieces?|stück)\b', r'\1 Stück', s)
    toks = [t for t in re.split(r'[\s/_,+&-]+', s) if t]
    out, i = [], 0
    while i < len(toks):
        t, low = toks[i], toks[i].lower()
        if low in SHADE and i + 1 < len(toks) and toks[i + 1].lower() in COLORS:
            out.append(SHADE[low] + COLORS[toks[i + 1].lower()].lower())
            i += 2
            continue
        if low in COLORS:
            out.append(COLORS[low])
        elif low in WORDS:
            out.append(WORDS[low])
        else:
            out.append(_title(t) if t.islower() or t.isupper() else t)
        i += 1
    return ' '.join(out)[:65]


def has_color(en):
    return any(t.lower() in COLORS for t in re.split(r'[\s/_,+&-]+', str(en or '')))


def label(en, de):
    """-> (value, verified). verified=False when only the unreliable German label exists.
    Root cause handled here: AliExpress sometimes sends a BARE SLOT LETTER as property_value_definition_name
    (e.g. 'A', 'B', 'F' — an internal option-slot code, not a translatable word). Treating that code as a
    trusted English name would publish a meaningless 'A'/'B' label. A bare code is a SINGLE PURE-ALPHA token
    of length <= 2 (so real short codes that embed a number, like size '30L', are never misclassified —
    only to a true single/double-letter slot code).
    For a bare code we fall back to the German value ONLY when it is itself one of OUR fixed color words —
    that's a direct lookup in our own vocabulary (not an invented translation), so it stays verified=True.
    Otherwise (bare code, unrecognized German value) the result is unverified, same as the no-definition-name
    case."""
    en_s = str(en or '').strip()
    de_s = str(de or '').strip()
    if en_s:
        en_tokens = [t.lower() for t in re.split(r'[\s/_,+&-]+', en_s) if t]
        recognized = any(t in COLORS or t in WORDS or t in SHADE for t in en_tokens)
        is_bare_code = (not recognized and len(en_tokens) == 1
                        and en_tokens[0].isalpha() and len(en_tokens[0]) <= 2)
        if not is_bare_code:
            v = translate(en_s)
            return v, bool(v)
        if de_s.lower() in COLORS:
            return COLORS[de_s.lower()], True
        return (de_s or en_s)[:65], False
    return de_s[:65], False
