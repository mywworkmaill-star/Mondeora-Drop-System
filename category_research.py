"""Collect category evidence per product: supplier title/props/main image, Taxonomy suggestions, and the categories real
eBay.de listings use for the same product type (Browse API). Read-only. Output: data/audit/category_research.json"""
import json
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import categories, source

e = eBayAPIClient()
db = sqlite3.connect('data/dropshipping.db')
db.row_factory = sqlite3.Row
out = []
for r in db.execute('select id, aliexpress_product_id pid, title from products where is_listed=1 and aliexpress_product_id not like "MANUAL-%" order by id'):
    pid = r['pid']
    res = json.load(open(f'data/audit/raw_{pid}.json', encoding='utf-8'))
    subject = res['ae_item_base_info_dto']['subject']
    props = source.properties(res)
    img = (res.get('ae_multimedia_info_dto', {}).get('image_urls') or '').split(';')[0]
    words = categories.clean(subject).split()
    queries = [' '.join(words[:3]), ' '.join(words[:5]), ' '.join(words[-3:])]
    browse = Counter()
    names = {}
    for q in queries:
        try:
            d = e._request('GET', '/buy/browse/v1/item_summary/search', params={'q': q, 'limit': 30, 'filter': 'buyingOptions:{FIXED_PRICE}'})
        except Exception as ex:
            browse['ERR ' + str(ex)[:40]] += 1
            continue
        for it in d.get('itemSummaries', []):
            for c in it.get('categories', [])[:1]:
                browse[c['categoryId']] += 1
                names[c['categoryId']] = c.get('categoryName')
    tax = {}
    for q in queries:
        try:
            tax[q] = [(c, n, p) for c, n, p in categories.suggest(e, q)]
        except Exception as ex:
            tax[q] = [str(ex)[:60]]
    out.append({'id': r['id'], 'pid': pid, 'subject': subject, 'img': img, 'props': props[:8], 'queries': queries,
                'browse_top': [(c, names.get(c), n) for c, n in browse.most_common(5)], 'taxonomy': tax})
    print(r['id'], subject[:60], '| browse:', [(c, names.get(c), n) for c, n in browse.most_common(3)], flush=True)
json.dump(out, open('data/audit/category_research.json', 'w'), ensure_ascii=False, indent=1)
