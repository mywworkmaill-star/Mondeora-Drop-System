"""Real low-competition + high-demand product discovery ("Blue Ocean"), grounded ONLY in actual
API data:
  - demand signal: AliExpress sold-volume search (supplier.search_product_page(sort_by='SALES_DESC'),
    real provider-reported 'orders' aggregate per item)
  - competition signal: real eBay Browse API total result count (EBAY_DE), NOT html scraping.

Replaces the legacy blue_ocean_finder.py, which (a) was never actually invoked by its own cron
script (mondeora_blue_ocean.sh only constructed the class and printed a placeholder string,
evaluate_product_potential() was never called), and (b) scraped eBay.de search-result HTML with
requests+BeautifulSoup, fragile under eBay's WAF, and used a backwards 'search_volume_estimate'
that INCREASED with competition count instead of measuring real demand.

This module never auto-publishes. find_and_seed() only inserts a candidate into the products
table (status='needs_variation_listing', is_listed=False) after it passes the SAME real-data
gates used everywhere else in this project (gates.check_risk, gates.demand price-vs-market,
pricing tier profit floor, real in-stock EUR SKU + real freight quote) - so the existing daily
pipeline (mondeora-listing-pipeline / mondeora-new-variation-listing) picks it up the next run,
exactly like a human-sourced niche candidate would be.
"""
from decimal import Decimal


# Established niche (2026-11-12 user decision: Haus & Garten -> home organization/storage).
# Edit this list to pivot niche; nothing else in this module is niche-specific.
DEFAULT_KEYWORDS = (
    'Kuechenorganizer', 'Schubladen Organizer', 'Badezimmer Aufbewahrung',
    'Kleiderschrank Organizer', 'Kabelorganizer', 'Gewuerz Organizer',
    'Schrank Organizer Box', 'Kosmetik Organizer', 'Schreibtisch Organizer',
    'Werkzeug Organizer Box',
)


def ebay_competition_count(ebay, query):
    """Real total matching listing count on eBay.de for this query (not capped at page size,
    not scraped HTML - the Browse API 'total' field)."""
    try:
        r = ebay._request('GET', '/buy/browse/v1/item_summary/search',
                           params={'q': query, 'limit': 1, 'filter': 'deliveryCountry:DE'})
        return int(r.get('total') or 0)
    except Exception:
        return None


def _parse_orders(value):
    """Real AliExpress 'orders' field can be a plain int OR a capped display string like
    '10,000+' - parse both, never crash on the real format."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).replace(',', '').replace('+', '').strip()
    try:
        return int(float(s)) if s else 0
    except ValueError:
        return 0


def aliexpress_demand(supplier, keyword, category_id=None, sample=20):
    """Real AliExpress sold-volume signal: top SALES_DESC results for keyword. 'orders' is the
    provider's own reported aggregate order count field - a real, sourced number, used only as a
    RELATIVE ranking signal between candidates, never as a guaranteed eBay sales prediction."""
    page = supplier.search_product_page(keyword, category_id=category_id, page_num=1,
                                         page_size=sample, sort_by='SALES_DESC')
    rows = (page or {}).get('products', [])[:sample]
    out = []
    for row in rows:
        pid = str(row.get('itemId') or row.get('productId') or '')
        if not pid.isdigit():
            continue
        out.append({'product_id': pid, 'title': row.get('title'),
                     'price': row.get('targetSalePrice'), 'orders': _parse_orders(row.get('orders'))})
    return out


def score(orders, competition_count):
    """0-100: up to 50 points for demand (orders, capped), up to 50 for low competition."""
    if competition_count is None:
        return None
    demand_pts = min(50, orders // 20) if orders else 0
    if competition_count < 50:
        comp_pts = 50
    elif competition_count < 200:
        comp_pts = 30
    elif competition_count < 500:
        comp_pts = 10
    else:
        comp_pts = 0
    return demand_pts + comp_pts


def candidate_query(title):
    """Short, specific query derived from the candidate's OWN title - NOT the broad category
    keyword. A broad category word ('Kuechenorganizer') always returns a huge eBay total (tens of
    thousands) because it matches the whole category, not real competition for THIS product - that
    was verified live on 2026-11-12 (37525 for a single generic keyword). Real per-candidate
    competition needs the product's own distinguishing words, same idea as categories.py's
    clean+top-words query building, reused here instead of re-implemented differently."""
    import re
    stop = {'und', 'für', 'mit', 'das', 'der', 'die', 'von', 'zu', 'auf', 'ohne', 'the', 'for',
            'with', 'and', 'of', 'a', 'an'}
    text = re.sub(r'[^\w\säöüÄÖÜß-]', ' ', str(title or ''))
    words = [w for w in text.split() if w.lower() not in stop and not w.isdigit()]
    return ' '.join(words[:5]) or str(title or '')[:40]


def find_candidates(supplier, ebay, keywords=None, min_orders=30, max_competition=300, per_keyword=15, top_n_for_competition=5):
    """One real AliExpress sales-sorted search per keyword; real eBay competition count PER
    CANDIDATE (using that candidate's own title, not the broad category keyword - see
    candidate_query) for only the top `top_n_for_competition` by orders per keyword, to keep the
    real API call budget bounded. Returns every scored row (passing and failing) so the
    caller/report can show why something was rejected - never silently drops rows."""
    results = []
    for kw in (keywords or DEFAULT_KEYWORDS):
        try:
            demand_rows = aliexpress_demand(supplier, kw, sample=per_keyword)
        except Exception as ex:
            results.append({'keyword': kw, 'error': f'{type(ex).__name__}: {ex}'[:200]})
            continue
        demand_rows.sort(key=lambda r: r['orders'], reverse=True)
        for row in demand_rows[:top_n_for_competition]:
            query = candidate_query(row.get('title'))
            competition = ebay_competition_count(ebay, query)
            s = score(row['orders'], competition)
            passes = (s is not None and row['orders'] >= min_orders
                      and competition is not None and competition <= max_competition)
            results.append({**row, 'keyword': kw, 'competition_query': query, 'ebay_competition_count': competition,
                             'score': s, 'passes_blue_ocean_filter': passes})
    results.sort(key=lambda r: r.get('score') or -1, reverse=True)
    return results


def verify_and_seed(ali, ebay, candidate, session, Product, risk_ack_pids=()):
    """Re-fetch real current product data (price/stock/shipping may have changed since the
    sales-sorted search snapshot), run the same real gates the rest of the pipeline uses, and
    insert into the products table ONLY if every check is real and passing. Returns a dict with
    'seeded': bool and 'reason' explaining the outcome either way - never silent."""
    from src.listing_quality import gates, pricing
    pid = candidate['product_id']
    if session.query(Product).filter_by(aliexpress_product_id=pid).first():
        return {'product_id': pid, 'seeded': False, 'reason': 'already_in_database'}
    try:
        detail = ali.get_product_details(pid)
    except Exception as ex:
        return {'product_id': pid, 'seeded': False, 'reason': f'detail_fetch_failed: {type(ex).__name__}'}
    title = detail.get('product_title') or candidate.get('title') or ''
    skus = detail.get('skus') or []
    instock = [s for s in skus if (s.get('warehouse_count') or 0) > 0 and s.get('sale_price') is not None
               and s.get('currency', detail.get('currency')) == 'EUR']
    if not instock:
        return {'product_id': pid, 'seeded': False, 'reason': 'no_real_in_stock_eur_sku'}
    anchor = min(instock, key=lambda s: float(s['sale_price']))
    cost = float(anchor['sale_price'])
    try:
        quote = ali.get_shipping_quote(pid, anchor.get('sku_id'), quantity=1, ship_to_country='DE')
        ship_cost = float(quote.get('shipping_cost') or quote.get('freight') or 1.99)
    except Exception:
        ship_cost = 1.99
    props = [(a.get('attr_name', ''), a.get('attr_value', '')) for a in (detail.get('properties') or [])] \
        if isinstance(detail.get('properties'), list) else []
    block, review = gates.check_risk(title, props)
    if block:
        return {'product_id': pid, 'seeded': False, 'reason': f'risk_gate_block: {block}'}
    unacknowledged = [r for r in review if r[0] not in risk_ack_pids]
    if unacknowledged and pid not in risk_ack_pids:
        return {'product_id': pid, 'seeded': False, 'reason': f'risk_gate_needs_review: {review}'}
    ebay_price, _net_profit = pricing.price_for(cost, ship_cost)
    ebay_price = float(ebay_price)
    info, dem_review = gates.demand(ebay, [candidate['keyword'], title], our_price=ebay_price)
    if dem_review:
        return {'product_id': pid, 'seeded': False, 'reason': f'price_vs_market_review: {dem_review}',
                'market_info': info}
    n_instock = len(instock)
    status = 'needs_variation_listing' if n_instock > 1 else None
    session.add(Product(aliexpress_product_id=pid, title=title, image_url=detail.get('product_main_image_url'),
                         aliexpress_price=cost, currency='EUR', shipping_cost=round(ship_cost, 2),
                         status=status, is_listed=False, fulfillment_verified=False))
    session.commit()
    return {'product_id': pid, 'seeded': True, 'reason': 'passed_all_real_gates', 'title': title,
            'aliexpress_price': cost, 'shipping_cost': round(ship_cost, 2), 'n_instock_skus': n_instock,
            'ebay_competition_count': candidate.get('ebay_competition_count'), 'score': candidate.get('score'),
            'market_info': info}
