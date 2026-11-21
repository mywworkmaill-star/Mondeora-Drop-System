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


def check_title_quality(title, rules=None):
    """Enhanced title quality gate: 60-80 char target, 8+ words, natural German keywords."""
    t = (rules or _load('risk_rules.json'))['title']
    probs = []
    tlen = len(title.strip())
    
    # Character range check (60-80 is optimal, warn if outside)
    if tlen < 60:
        probs.append(f'title too short ({tlen} < 60 chars) - add more descriptive keywords')
    elif tlen > 80:
        probs.append(f'title too long ({tlen} > 80 chars)')
    
    # Word count (8+ is optimal for German keywords)
    words = re.findall(r'[\wäöüÄÖÜß]+', title)
    if len(words) < 8:
        probs.append(f'too few keywords ({len(words)} < 8 words)')
    
    # Check for non-German characters/words (excluding real model names)
    foreign_chars = re.findall(r'[^\x00-\x7F\u00C0-\u017F\u0370-\u03FF\s\d\-.,!?()]', title)
    if foreign_chars:
        probs.append(f'non-German characters: {set(foreign_chars)}')
    
    return probs


def check_image_count(image_urls, rules=None):
    """Image count gate: min 6, ideal 8-12, all ≥500px (uses images.filter_urls)."""
    from src.listing_quality.images import filter_urls
    
    rules = rules or _load('risk_rules.json')
    img_rules = rules.get('images', {'min_count': 6, 'ideal_count': 8})
    
    if not image_urls or not isinstance(image_urls, (list, tuple)):
        return ['no images provided'], {'total': 0, 'valid': 0, 'dropped': 0}
    
    kept, dropped = filter_urls(list(image_urls))
    info = {
        'total': len(image_urls),
        'valid': len(kept),
        'dropped': len(dropped),
        'ideal': img_rules['ideal_count']
    }
    
    probs = []
    if len(kept) < img_rules['min_count']:
        probs.append(f'insufficient images ({len(kept)} < {img_rules["min_count"]} min)')
    elif len(kept) < img_rules['ideal_count']:
        probs.append(f'below ideal image count ({len(kept)} < {img_rules["ideal_count"]} ideal)')
    
    if dropped:
        probs.append(f'{len(dropped)} images dropped (< 500px or invalid)')
    
    return probs, info


def check_description_quality(description, rules=None):
    """Description quality gate: min 500 chars, HTML structure, bullet points."""
    rules = rules or _load('risk_rules.json')
    desc_rules = rules.get('description', {'min_length': 500})
    
    if not description or not isinstance(description, str):
        return ['empty description'], {'length': 0}
    
    clean_text = re.sub(r'<[^>]+>', '', description)  # Strip HTML for length check
    text_length = len(clean_text.strip())
    
    info = {
        'length': text_length,
        'has_html': '<' in description and '>' in description,
        'has_lists': '<ol' in description.lower() or '<ul' in description.lower() or '<li' in description.lower(),
        'has_table': '<table' in description.lower() or '<tr' in description.lower(),
    }
    
    probs = []
    if text_length < desc_rules['min_length']:
        probs.append(f'description too short ({text_length} < {desc_rules["min_length"]} chars)')
    
    if not info['has_html']:
        probs.append('no HTML formatting (plain text only)')
    
    if not info['has_lists']:
        probs.append('no bullet points or numbered lists')
    
    if not info['has_table']:
        probs.append('no specification table')
    
    return probs, info


def check_item_specifics_count(aspects, rules=None):
    """Item specifics gate: min 10 aspects (eBay's own requirement + quality)."""
    rules = rules or _load('risk_rules.json')
    aspect_rules = rules.get('aspects', {'min_count': 10})
    
    if not aspects or not isinstance(aspects, (list, dict)):
        return ['no item specifics provided'], {'count': 0}
    
    count = len(aspects) if isinstance(aspects, dict) else len([a for a in aspects if isinstance(a, (tuple, list)) and len(a) >= 2])
    info = {'count': count, 'min_required': aspect_rules['min_count']}
    
    probs = []
    if count < aspect_rules['min_count']:
        probs.append(f'insufficient item specifics ({count} < {aspect_rules["min_count"]} min)')
    
    return probs, info


def check_category_confidence(category_result, rules=None):
    """Category confidence gate: ≥ 0.6 confidence, needs_review flag check."""
    rules = rules or _load('risk_rules.json')
    cat_rules = rules.get('category', {'min_confidence': 0.6})
    
    if not isinstance(category_result, dict):
        return ['invalid category result'], {'confidence': 0.0}
    
    confidence = category_result.get('confidence', 0.0)
    needs_review = category_result.get('needs_review', True)
    category_id = category_result.get('category_id')
    
    info = {
        'confidence': confidence,
        'needs_review': needs_review,
        'category_id': category_id
    }
    
    probs = []
    if confidence < cat_rules['min_confidence']:
        probs.append(f'low category confidence ({confidence:.2f} < {cat_rules["min_confidence"]})')
    
    if needs_review:
        probs.append('category flagged for manual review')
    
    if not category_id:
        probs.append('no category ID assigned')
    
    return probs, info


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
