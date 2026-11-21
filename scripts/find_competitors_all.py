"""For each of our 31 real active products, find 10 real eBay.de competitor
listings (excluding our own item) via the authenticated Browse API search
(item_summary/search) - not scraping, not guessed/invented data. Writes one
JSON file per product to data/audit/competitor_analysis/analysis_{pid}.json,
and appends progress to data/audit/competitor_search_log.jsonl so an
interruption loses no completed work (resume skips already-done product ids).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient

ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / 'data' / 'audit' / 'full_inventory_audit.jsonl'
OUT_DIR = ROOT / 'data' / 'audit' / 'competitor_analysis'
LOG_FILE = ROOT / 'data' / 'audit' / 'competitor_search_log.jsonl'
OUT_DIR.mkdir(parents=True, exist_ok=True)

ebay = eBayAPIClient()

STOPWORDS = {
    'für', 'mit', 'und', 'oder', 'ohne', 'aus', 'von', 'der', 'die', 'das', 'den',
    'zum', 'zur', 'ein', 'eine', 'einer', 'eines', 'bei', 'auf', 'in', 'im', 'am',
}
# Compound/marketing prefixes that make the query too narrow if kept.
NOISE_PREFIXES = {
    'zusammenklappbarer', 'zusammenklappbare', 'zusammenklappbares', 'multifunktions',
    'premium', 'wiederverwendbare', 'wiederverwendbarer', 'mehrschichtiger',
    'faltbarer', 'faltbare', 'faltbares', 'tragbarer', 'tragbare', 'verstellbarer',
}


def extract_keywords(title, max_words=3):
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", title or '')
    cleaned = []
    for w in words:
        wl = w.lower()
        if wl in STOPWORDS or wl in NOISE_PREFIXES or len(w) <= 2:
            continue
        cleaned.append(w)
    # Prefer the LAST meaningful words (the product-type noun usually sits late
    # in these German titles), per competitor-aspect-scraping skill guidance.
    return ' '.join(cleaned[-max_words:]) if cleaned else (title or '')[:40]


def search_competitors(query, exclude_listing_id, limit=10, tries=3):
    """Progressively shorten the query if too few real, non-self results come back."""
    words = query.split()
    for n in range(min(tries, len(words)), 0, -1):
        q = ' '.join(words[-n:]) if n < len(words) else query
        try:
            resp = ebay._request('GET', '/buy/browse/v1/item_summary/search',
                                  params={'q': q, 'limit': 25, 'filter': 'deliveryCountry:DE'})
        except Exception as ex:
            return [], f'{type(ex).__name__}: {ex}'[:200], q
        items = [i for i in (resp.get('itemSummaries') or [])
                 if exclude_listing_id not in (i.get('itemId') or '')]
        if len(items) >= limit or n == 1:
            return items[:limit], None, q
    return [], 'no_results', query


def already_done():
    done = set()
    if LOG_FILE.exists():
        with LOG_FILE.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get('ok'):
                        done.add(rec['pid'])
                except Exception:
                    pass
    return done


def load_products():
    recs = [json.loads(l) for l in AUDIT_FILE.open(encoding='utf-8')]
    live = [r for r in recs if r.get('listing_status') in ('ACTIVE', 'OUT_OF_STOCK')]
    by_pid = {}
    for r in live:
        m = re.match(r'^AE-([0-9]{6,})-', r['sku'])
        if not m:
            continue
        pid = m.group(1)
        by_pid.setdefault(pid, {'listing_id': r.get('listing_id'), 'title': r.get('title')})
    return by_pid


def main():
    by_pid = load_products()
    print(f'Islenecek urun: {len(by_pid)}', flush=True)
    done = already_done()
    print(f'Onceden tamamlanmis (resume): {len(done)}', flush=True)
    log = LOG_FILE.open('a', encoding='utf-8')
    for i, (pid, info) in enumerate(by_pid.items()):
        if pid in done:
            continue
        title = info['title']
        listing_id = info['listing_id']
        entry = {'pid': pid, 'listing_id': listing_id, 'title': title}
        try:
            query = extract_keywords(title)
            items, err, used_query = search_competitors(query, listing_id, limit=10)
            competitors = []
            for it in items:
                price = it.get('price') or {}
                shipping = (it.get('shippingOptions') or [{}])[0].get('shippingCost') or {}
                competitors.append({
                    'item_id': it.get('itemId'),
                    'title': it.get('title'),
                    'price': price.get('value'),
                    'currency': price.get('currency'),
                    'shipping_cost': shipping.get('value'),
                    'seller': (it.get('seller') or {}).get('username'),
                    'condition': it.get('condition'),
                    'item_web_url': it.get('itemWebUrl'),
                })
            out = {
                'product_id': pid,
                'our_listing_id': listing_id,
                'our_title': title,
                'search_query_used': used_query,
                'competitors_found': len(competitors),
                'target': 10,
                'competitors': competitors,
                'search_error': err,
            }
            (OUT_DIR / f'analysis_{pid}.json').write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
            entry.update(ok=True, competitors_found=len(competitors), query=used_query)
        except Exception as ex:
            entry.update(ok=False, error=f'{type(ex).__name__}: {ex}'[:300])
        log.write(json.dumps(entry, ensure_ascii=False) + '\n')
        log.flush()
        if (i + 1) % 5 == 0:
            print(f'{i + 1}/{len(by_pid)} urun islendi', flush=True)
    log.close()
    print('COMPETITOR SEARCH COMPLETE', flush=True)


if __name__ == '__main__':
    main()
