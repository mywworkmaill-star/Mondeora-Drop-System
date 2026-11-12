"""Pre-publish gates as CODE: product risk, title rules, legal flags, demand/price check.
evaluate() returns {'block': [...], 'review': [...], 'info': {...}}. publish.plan_for() raises on any block and on any
review group that the user has not acknowledged in config/risk_ack.json."""
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    return json.loads((ROOT / 'config' / name).read_text(encoding='utf-8'))


def _hit(text, words):
    t = ' ' + re.sub(r'[^\w\säöüß-]', ' ', (text or '').lower()) + ' '
    out = []
    for w in words:
        w = w.lower()
        if re.search(r'(?<![\wäöüß])' + re.escape(w.strip()) + r'(?![\wäöüß])', t) or (len(w) >= 6 and w.strip() in t and w.strip() not in ('batterie',)):
            out.append(w.strip())
    return sorted(set(out))


def check_risk(title, props, rules=None):
    rules = rules or _load('risk_rules.json')
    neg = {'nein', 'keine', 'kein', 'none', 'no', 'nicht', 'nicht enthalten', '0', 'n/a', 'ohne'}
    text = ' '.join([title or ''] + [f'{n} {v}' for n, v in props if str(v).strip().lower() not in neg])
    block, review = [], []
    for group, words in rules['block'].items():
        h = _hit(text, words)
        if h:
            block.append((group, h))
    for group, words in rules['review'].items():
        h = _hit(text, words)
        if h:
            review.append((group, h))
    return block, review


def check_title(title, rules=None):
    t = (rules or _load('risk_rules.json'))['title']
    probs = []
    if len(title) > t['max_len']:
        probs.append(f'title {len(title)} > {t["max_len"]}')
    if not title.strip():
        probs.append('empty title')
    if any(c in title for c in t['banned_chars']):
        probs.append('banned character')
    if re.search(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]', title):
        probs.append('emoji')
    words = re.findall(r'[\wäöüÄÖÜß]+', title)
    last = (words[-1].lower() if words else '')
    if last in t['stop_endings']:
        probs.append(f'ends with stop word {last!r}')
    low = [w.lower() for w in words if len(w) > 3]
    rep = {w for w in low if low.count(w) > t['max_word_repeat']}
    if rep:
        probs.append(f'keyword stuffing {sorted(rep)}')
    alpha = [w for w in words if len(w) > 3 and w.isalpha()]
    if alpha and sum(w.isupper() for w in alpha) / len(alpha) > t['max_caps_ratio']:
        probs.append('too many CAPS words')
    return probs


def demand(ebay, queries, our_price=None, rules=None):
    """Real eBay.de fixed-price listings for the same product type: count + median price. Read-only."""
    cfg = (rules or _load('risk_rules.json'))['demand']
    prices, seen = [], set()
    for q in queries[:3]:
        try:
            d = ebay._request('GET', '/buy/browse/v1/item_summary/search',
                              params={'q': q, 'limit': 50, 'filter': 'buyingOptions:{FIXED_PRICE}'})
        except Exception:
            continue
        for it in d.get('itemSummaries', []):
            if it.get('itemId') in seen:
                continue
            seen.add(it.get('itemId'))
            try:
                if it['price']['currency'] == 'EUR':
                    prices.append(float(it['price']['value']))
            except (KeyError, ValueError, TypeError):
                pass
    info = {'listings_found': len(prices)}
    review = []
    if len(prices) < cfg['min_listings']:
        review.append('no comparable eBay.de listings found: demand unknown')
        return info, review
    med = statistics.median(prices)
    info.update({'median': round(med, 2), 'p25': round(statistics.quantiles(prices, n=4)[0], 2) if len(prices) >= 4 else None,
                 'min': min(prices), 'max': max(prices)})
    if our_price:
        info['our_price'] = our_price
        info['price_vs_median'] = round(our_price / med, 2)
        if our_price > med * cfg['max_price_over_median']:
            review.append(f'our price {our_price} is {our_price / med:.1f}x the market median {med:.2f}')
    return info, review


def acknowledged(pid):
    try:
        return _load('risk_ack.json').get('acknowledged', {}).get(str(pid), {})
    except (OSError, ValueError):
        return {}


def evaluate(pid, title, props, ebay=None, queries=None, our_price=None):
    rules = _load('risk_rules.json')
    block, review = check_risk(title, props, rules)
    tp = []   # title rules are checked by the caller on the FINAL (shortened) eBay title, not on the supplier title
    ack = acknowledged(pid)
    unack = [(g, h) for g, h in review if g not in ack]
    info = {}
    dem_review = []
    if ebay is not None and queries:
        info, dem_review = demand(ebay, queries, our_price, rules)
    res = {'block': [f'{g}: {h}' for g, h in block] + [f'title: {p}' for p in tp],
           'review': [f'{g}: {h}' for g, h in unack] + [f'demand: {r}' for r in dem_review if 'demand' not in ack],
           'acknowledged': sorted(ack), 'info': info}
    return res
