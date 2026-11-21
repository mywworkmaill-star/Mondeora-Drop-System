"""Bounded, read-only competitor research. Consensus is NEVER a product fact."""
import re
from collections import Counter, defaultdict
from urllib.parse import quote

STOPWORDS = {
    'für', 'mit', 'und', 'oder', 'ohne', 'aus', 'von', 'der', 'die', 'das', 'den',
    'zum', 'zur', 'ein', 'eine', 'einer', 'eines', 'bei', 'auf', 'in', 'im', 'am',
}
NOISE_PREFIXES = {
    'zusammenklappbarer', 'zusammenklappbare', 'zusammenklappbares', 'multifunktions',
    'premium', 'wiederverwendbare', 'wiederverwendbarer', 'mehrschichtiger',
    'faltbarer', 'faltbare', 'faltbares', 'tragbarer', 'tragbare', 'verstellbarer',
    'universell', 'universelle', 'universelles', 'universal', 'zubehör',
}


def _extract_keywords(title, max_words=3):
    words = re.findall(r'[A-Za-zÄÖÜäöüß]+', title or '')
    cleaned = [w for w in words if w.casefold() not in STOPWORDS | NOISE_PREFIXES and len(w) > 2]
    return ' '.join(cleaned[:max_words])


def _identities(value):
    value = str(value or '')
    parts = value.split('|')
    return {value, parts[1]} if len(parts) == 3 and parts[0] == 'v1' else {value}


def _category_ids(row):
    ids = [str(c['categoryId']) for c in row.get('categories', []) if c.get('categoryId')]
    if row.get('categoryId'):
        ids.append(str(row['categoryId']))
    ids.extend(str(c) for c in row.get('leafCategoryIds', []))
    return list(dict.fromkeys(ids))


def _suggestions(candidates):
    """Three independent successful listings minimum; a tie is not consensus."""
    if len(candidates) < 3:
        return {}
    votes = defaultdict(Counter)
    for row in candidates:
        for name, value in row['aspects'].items():
            votes[name][value] += 1
    out = {}
    for name, values in votes.items():
        value, count = values.most_common(1)[0]
        if count >= 3 and count / len(candidates) > .5:
            out[name] = {'value': value, 'agreeing': count, 'sample': len(candidates),
                         'item_ids': [c['item_id'] for c in candidates if c['aspects'].get(name) == value],
                         'evidence_type': 'competitor_suggestion_only'}
    return out


def research(ebay, subject, category_id, limit=10, exclude_listing_ids=()):
    """One category-filtered search, <=10 details, unique IDs and sellers.

    Caller-supplied exclusions are applied to legacy and Browse IDs. Without an
    authoritative inventory snapshot, completeness of own-list exclusion is unknown.
    Category/title checks show candidate relevance, not identity with our product.
    Error records retain types/codes only, never arbitrary provider exception bodies.
    """
    limit = min(10, max(1, int(limit)))
    query, category_id = _extract_keywords(subject), str(category_id or '')
    excluded = set().union(*(_identities(i) for i in exclude_listing_ids)) if exclude_listing_ids else set()
    out = {'status': 'not_verified', 'query': query, 'category_id': category_id,
           'source': 'ebay_buy_browse', 'product_facts_verified': False,
           'candidates': [], 'suggestions': {}, 'errors': [], 'skipped': [],
           'own_listing_exclusion': {'provided_count': len(exclude_listing_ids),
               'applied': bool(excluded), 'complete': False,
               'limitation': 'authoritative_own_listing_inventory_not_available'},
           'completeness': {'requested': limit, 'detail_attempts': 0, 'successful_independent': 0,
                            'minimum_independent': 3, 'sufficient_sample': False,
                            'search_complete': False}}
    if not query or not re.fullmatch(r'[0-9]+', category_id):
        out['errors'].append({'stage': 'search', 'code': 'meaningful_query_or_category_missing'})
        return out
    try:
        response = ebay._request('GET', '/buy/browse/v1/item_summary/search', params={
            'q': query, 'category_ids': category_id, 'limit': limit, 'filter': 'deliveryCountry:DE'})
        rows = response.get('itemSummaries') or []
        if not isinstance(rows, list):
            raise ValueError('Invalid search schema')
        out['completeness']['search_complete'] = not bool(response.get('next')) and len(rows) <= limit
    except Exception as error:
        out['errors'].append({'stage': 'search', 'error_type': type(error).__name__})
        return out
    ids, sellers = set(), set()
    leading = query.split()[0].casefold()
    for summary in rows:
        if out['completeness']['detail_attempts'] >= limit:
            break
        iid = summary.get('itemId')
        if not isinstance(iid, str) or not iid:
            out['skipped'].append({'code': 'item_id_missing'})
            continue
        identity = _identities(iid)
        seller = str((summary.get('seller') or {}).get('username') or '').casefold()
        reason = ('own_listing' if identity & excluded else
                  'duplicate_item' if identity & ids else
                  'duplicate_seller' if seller and seller in sellers else None)
        if not reason and _category_ids(summary) and category_id not in _category_ids(summary):
            reason = 'category_mismatch'
        if reason:
            out['skipped'].append({'item_id': iid, 'code': reason})
            continue
        ids.update(identity)
        out['completeness']['detail_attempts'] += 1
        try:
            detail = ebay._request('GET', '/buy/browse/v1/item/' + quote(iid, safe=''))
            if detail.get('itemId') and not identity & _identities(detail['itemId']):
                out['skipped'].append({'item_id': iid, 'code': 'detail_identity_mismatch'})
                continue
            categories = _category_ids(detail) or _category_ids(summary)
            seller = str((detail.get('seller') or summary.get('seller') or {}).get('username') or '').casefold()
            title = str(detail.get('title') or summary.get('title') or '')
            reason = ('category_mismatch' if category_id not in categories else
                      'seller_missing' if not seller else 'duplicate_seller' if seller in sellers else
                      'product_type_mismatch' if leading not in re.findall(r'\w+', title.casefold()) else None)
            if reason:
                out['skipped'].append({'item_id': iid, 'code': reason})
                continue
            aspects = {a['name']: a['value'] for a in (detail.get('localizedAspects') or [])
                       if isinstance(a.get('name'), str) and isinstance(a.get('value'), str) and a['value']}
            if not aspects:
                out['skipped'].append({'item_id': iid, 'code': 'aspects_missing'})
                continue
            sellers.add(seller)
            out['candidates'].append({'item_id': iid, 'seller': seller, 'title': title,
                'category_ids': categories, 'source': detail.get('itemWebUrl') or summary.get('itemWebUrl')
                or 'https://api.ebay.com/buy/browse/v1/item/' + quote(iid, safe=''),
                'aspects': aspects, 'evidence_type': 'competitor_not_supplier'})
        except Exception as error:
            out['errors'].append({'stage': 'detail', 'item_id': iid, 'error_type': type(error).__name__})
    count = len(out['candidates'])
    out['completeness'].update(successful_independent=count, sufficient_sample=count >= 3)
    out['suggestions'] = _suggestions(out['candidates'])
    if out['suggestions']:
        out['status'] = 'suggestions_only'
    return out


def fill_from_competitors(ebay, meta, subject, shared, limit=5):
    """Compatibility shim: no read/write enrichment. Research is suggestions only."""
    return shared
