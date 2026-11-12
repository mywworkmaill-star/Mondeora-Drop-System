"""Category resolution via eBay Taxonomy API (tree 77 = Germany), by voting over several queries.
Never trust a single suggestion. Returns confidence + needs_review so low-confidence items go to a human."""
import re
from collections import defaultdict

TREE = '77'
BAD_ROOTS_FOR_NON_APPAREL = ('Kleidung & Accessoires',)
APPAREL_WORDS = ('kleid', 'hose', 'shirt', 'jacke', 'rock', 'pullover', 'socken')


def clean(title):
    t = re.sub(r'\([^)]*\)', ' ', title or '')
    t = re.sub(r'\b\w*\d\w*\b', ' ', t)          # tokens with digits / sizes / model codes
    t = re.sub(r'[^\w\säöüÄÖÜß-]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def queries(title, props):
    base = clean(title)
    words = base.split()
    qs = [base[:100], ' '.join(words[:4]), ' '.join(words[-4:])]
    for n, v in props:
        if n.lower() in ('produktart', 'typ', 'art', 'artikel', 'produkttyp', 'anwendung'):
            qs.append(f'{v} {words[0] if words else ""}'.strip())
    seen, out = set(), []
    for q in qs:
        if q and q.lower() not in seen:
            seen.add(q.lower()); out.append(q)
    return out[:5]


def suggest(ebay, q):
    r = ebay._request('GET', f'/commerce/taxonomy/v1/category_tree/{TREE}/get_category_suggestions', params={'q': q})
    res = []
    for s in (r.get('categorySuggestions') or [])[:3]:
        c = s['category']
        path = ' > '.join(a['categoryName'] for a in (s.get('categoryTreeNodeAncestors') or [])[::-1]) + ' > ' + c['categoryName']
        res.append((str(c['categoryId']), c['categoryName'], path.strip(' >')))
    return res


PET_WORDS = ('hund', 'katze', 'katzen', 'haustier', 'welpe', 'kätzchen', 'nager', 'hamster', 'vogel', 'aquarium')


def _hints(title):
    t = (title or '').lower()
    pet = any(w in t for w in PET_WORDS)
    dog, cat = 'hund' in t or 'welpe' in t, 'katz' in t or 'kätzchen' in t
    return pet, dog and not cat, cat and not dog


def resolve(ebay, title, props=()):
    """Vote over several queries; domain hints (pet vs non-pet, dog vs cat) filter impossible paths.
    confidence = share of queries whose TOP suggestion is the winner (agreement). needs_review if < 0.5."""
    pet, dog_only, cat_only = _hints(title)
    apparel = any(w in (title or '').lower() for w in APPAREL_WORDS)
    qs = queries(title, props)
    votes, names, top_hits, used = defaultdict(float), {}, defaultdict(int), 0
    for q in qs:
        try:
            sugg = suggest(ebay, q)
        except Exception:
            continue
        ok = []
        for cid, name, path in sugg:
            if not apparel and path.startswith(BAD_ROOTS_FOR_NON_APPAREL):
                continue
            if pet and not path.startswith('Haustierbedarf'):
                continue
            if not pet and path.startswith('Haustierbedarf'):
                continue
            if dog_only and path.startswith('Haustierbedarf > Katzen'):
                continue
            if cat_only and path.startswith('Haustierbedarf > Hunde'):
                continue
            ok.append((cid, name, path))
        if not ok:
            continue
        used += 1
        top_hits[ok[0][0]] += 1
        for rank, (cid, name, path) in enumerate(ok[:3]):
            votes[cid] += (3, 2, 1)[rank]; names[cid] = path
    if not votes:
        return {'category_id': None, 'path': None, 'confidence': 0.0, 'needs_review': True, 'alternatives': []}
    ranked = sorted(votes.items(), key=lambda kv: (-top_hits[kv[0]], -kv[1]))
    best = ranked[0][0]
    conf = round(top_hits[best] / max(used, 1), 2)
    return {'category_id': best, 'path': names[best], 'confidence': conf, 'needs_review': conf < 0.5,
            'queries_used': used, 'alternatives': [(c, names[c], top_hits[c]) for c, _ in ranked[1:4]]}


def resolve_for_product(ebay, pid, title, props=()):
    """Reviewed override first (config/category_overrides.json), else auto-resolve. blocked -> no category."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parents[2] / 'config' / 'category_overrides.json'
    try:
        o = json.loads(f.read_text(encoding='utf-8')).get(str(pid))
    except (OSError, ValueError):
        o = None
    if o and o.get('blocked'):
        return {'category_id': None, 'path': None, 'confidence': 0.0, 'needs_review': True, 'blocked': True, 'note': o.get('note')}
    if o and o.get('category_id'):
        return {'category_id': o['category_id'], 'path': o['path'], 'confidence': 1.0, 'needs_review': o.get('level') == 'low',
                'source': 'override', 'level': o.get('level'), 'note': o.get('note')}
    r = resolve(ebay, title, props)
    r['source'] = 'auto'
    return r


def aspects_for(ebay, category_id):
    r = ebay._request('GET', f'/commerce/taxonomy/v1/category_tree/{TREE}/get_item_aspects_for_category',
                      params={'category_id': str(category_id)})
    out = []
    for a in r.get('aspects', []):
        c = a['aspectConstraint']
        out.append({'name': a['localizedAspectName'], 'required': bool(c.get('aspectRequired')),
                    'variation_ok': bool(c.get('aspectEnabledForVariations')), 'mode': c.get('aspectMode'),
                    'multi': c.get('itemToAspectCardinality') == 'MULTI',
                    'values': [v['localizedValue'] for v in a.get('aspectValues', [])][:300]})
    return out


def fill_aspects(meta, props):
    """Map AliExpress German properties onto the category's aspects. Returns (aspects, missing_required)."""
    by_name = {n.lower(): v for n, v in props}
    out, missing = {}, []
    for a in meta:
        n = a['name']
        v = by_name.get(n.lower())
        if n == 'Marke':
            v = 'Markenlos'
        if v and a['mode'] == 'SELECTION_ONLY' and a['values'] and v not in a['values']:
            v = None
        if v:
            v = v.title() if v.isupper() and len(v) > 3 else v
            out[n] = [v[:65]]
        elif a['required']:
            missing.append(n)
    return out, missing
