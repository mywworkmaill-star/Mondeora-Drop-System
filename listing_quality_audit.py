"""Dry-run audit of every live listing: category, variants, per-variant price, description. NO eBay/DB writes.
Usage: python311 listing_quality_audit.py [--cache]"""
import json, sqlite3, sys
sys.path.insert(0, '.')
from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayAPIClient
from src.listing_quality import categories, description, gates, pricing, source, variants

ali, ebay = AliExpressAPIClient(), eBayAPIClient()
cfg = pricing.settings()
db = sqlite3.connect('data/dropshipping.db'); db.row_factory = sqlite3.Row
rows = db.execute('select id, aliexpress_product_id pid, ebay_item_id, category_id cur_cat, title, ebay_price, shipping_cost '
                  'from products where is_listed=1 order by id').fetchall()
report = []
for r in rows:
    pid = r['pid']
    try:
        res = source.fetch_raw(ali, pid, use_cache='--cache' in sys.argv)
    except Exception as ex:
        report.append({'id': r['id'], 'pid': pid, 'error': str(ex)[:120]}); continue
    title = res['ae_item_base_info_dto'].get('subject') or r['title']
    props = source.properties(res)
    cat = categories.resolve_for_product(ebay, pid, title, props)
    meta = categories.aspects_for(ebay, cat['category_id']) if cat['category_id'] else []
    asp, missing = categories.fill_aspects(meta, props)
    ship = float(r['shipping_cost'] or 1.99)
    plan = variants.build(pid, res, ship, cfg)
    desc = description.build(title, res, plan)
    gv = gates.evaluate(pid, res['ae_item_base_info_dto'].get('subject') or title, props, ebay,
                        categories.queries(res['ae_item_base_info_dto'].get('subject') or title, props), cur if (cur := float(r['ebay_price'] or 0)) else None)
    from src.listing_quality.publish import make_title
    gv['block'] += [f'title: {p_}' for p_ in gates.check_title(make_title(title))]
    cur = float(r['ebay_price'] or 0)
    _tok = lambda x: {w for w in categories.clean(x).lower().split() if len(w) > 3}
    _a, _b = _tok(title), _tok(r['title'])
    overlap = round(len(_a & _b) / max(len(_a | _b), 1), 2)
    loss = []
    for v in plan['variants']:
        n = pricing.net_profit(cur, v['cost'], ship, cfg)
        if n < cfg['min_profit']:
            loss.append((v['aspects'], v['cost'], round(n, 2)))
    report.append({'id': r['id'], 'pid': pid, 'ebay_item_id': r['ebay_item_id'], 'title': title[:70],
                   'current_category': r['cur_cat'], 'db_title': (r['title'] or '')[:70], 'title_overlap': overlap, 'new_category': cat, 'missing_required_aspects': missing,
                   'is_variation': plan['is_variation'], 'variant_count': len(plan['variants']),
                   'dropped': len(plan['dropped']), 'flags': plan['flags'],
                   'price_min': plan['variants'][0]['price'] if plan['variants'] else None,
                   'price_max': plan['variants'][-1]['price'] if plan['variants'] else None,
                   'current_price': cur, 'variants_below_min_profit_at_current_price': len(loss),
                   'worst_variant_net_at_current_price': min([l[2] for l in loss], default=None),
                   'desc_chars': len(desc), 'gates': gv, 'spec': [(s['name'], len(s['values'])) for s in plan['specifications']]})
json.dump(report, open('data/audit/listing_quality_report.json', 'w'), ensure_ascii=False, indent=1)
for x in report:
    if 'error' in x:
        print(x['id'], 'ERR', x['error']); continue
    c = x['new_category']
    print(f"#{x['id']} {x['title'][:48]}{'  !!! IDENTITY MISMATCH db_title=' + x['db_title'] if x['title_overlap'] < 0.15 else ''}\n   cat {x['current_category']} -> {c['category_id']} {c['path']} conf={c['confidence']}{' REVIEW' if c['needs_review'] else ''}"
          f"\n   var={x['is_variation']} n={x['variant_count']} {x['spec']} price {x['price_min']}-{x['price_max']} (now {x['current_price']}) "
          f"under-min-profit={x['variants_below_min_profit_at_current_price']} worst_net={x['worst_variant_net_at_current_price']} "
          f"desc={x['desc_chars']}ch missing_req={x['missing_required_aspects']} flags={x['flags']}"
          f"\n   GATES block={x['gates']['block']} review={x['gates']['review']} market={x['gates']['info']}")
