"""Composite 'will this rank well' audit for a single listing, built ENTIRELY from real signals this
project already computes elsewhere (gates.py, categories.py, pricing.py, ads.py, source.py) - no new
scoring heuristic is invented here, this module only aggregates and reports what's already real.

Cassini (eBay's search ranking) and Promoted Listings visibility both reward, in order of weight:
relevance (title/aspects/category), seller performance (handling time, returns, defect rate),
listing quality (images, description), price competitiveness, and sales velocity. This module checks
the first four (grounded, pre-publish) - sales velocity only exists after the listing has lived.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def real_traffic(ebay, days=30):
    """REAL ground-truth eBay Traffic Report (impressions/views/CTR/conversion) for ALL listings,
    one API call for every item - not an inferred proxy. date_range format is yyyymmdd (eBay quirk,
    NOT yyyy-mm-dd - confirmed via a live 400 error on 2026-11-12). Returns {item_id: {...}}."""
    from datetime import datetime, timedelta
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    try:
        r = ebay._request('GET', '/sell/analytics/v1/traffic_report', params={
            'dimension': 'LISTING',
            'filter': f'marketplace_ids:{{EBAY_DE}},date_range:[{start}..{end}]',
            'metric': 'CLICK_THROUGH_RATE,LISTING_IMPRESSION_TOTAL,LISTING_VIEWS_TOTAL,SALES_CONVERSION_RATE'})
    except Exception:
        return {}
    metrics = [m['key'] for m in r.get('header', {}).get('metrics', [])]
    out = {}
    for rec in r.get('records', []):
        item_id = rec['dimensionValues'][0]['value']
        out[item_id] = {k: mv['value'] for k, mv in zip(metrics, rec['metricValues'])}
    return out


def audit_listing(ali, ebay, product_row, aliexpress_product_id, traffic=None):
    """product_row: a dict-like with ebay_item_id, title, category_id, ebay_price, aliexpress_price,
    shipping_cost (as stored in the products table). traffic: optional pre-fetched real_traffic()
    dict (pass it once per batch instead of refetching per product). Returns {score 0-100, checks: [...], gaps: [...]}."""
    from src.listing_quality import source, categories, gates, pricing, ads
    checks, gaps = [], []
    score = 0
    MAX = 0

    title = product_row.get('title') or ''
    MAX += 15
    title_ok = 20 <= len(title) <= 80 and not title.isupper() and not any(c in title for c in '!?*')
    checks.append({'check': 'title_length_and_format', 'pass': title_ok, 'value': len(title)})
    score += 15 if title_ok else 0
    if not title_ok:
        gaps.append('Title should be 20-80 chars, no ALL CAPS, no !/?/* spam chars (ebay-title-rules skill)')

    res = source.fetch_raw(ali, aliexpress_product_id)
    props = source.properties(res)
    subject = res['ae_item_base_info_dto']['subject']
    cat = categories.resolve_for_product(ebay, aliexpress_product_id, subject, props)
    MAX += 20
    cat_ok = bool(cat.get('category_id')) and not cat.get('needs_review')
    checks.append({'check': 'category_confidence', 'pass': cat_ok, 'value': cat.get('confidence'), 'source': cat.get('source')})
    score += 20 if cat_ok else 0
    if not cat_ok:
        gaps.append(f"Category confidence {cat.get('confidence')} - add a reviewed entry to config/category_overrides.json")

    if cat.get('category_id'):
        meta = categories.aspects_for(ebay, cat['category_id'])
        shared, missing = categories.fill_aspects(meta, props)
        required = [a['name'] for a in meta if a.get('required')]
        # A required aspect missing from the SUPPLIER data may already be filled on the LIVE listing
        # via a human-verified extra_aspects override at publish time (e.g. real package dimensions) -
        # check the live inventory_item_group before flagging it as a real gap.
        if missing and (item_id := product_row.get('ebay_item_id')):
            try:
                live = ebay._request('GET', f"/sell/inventory/v1/inventory_item_group/GRP-{aliexpress_product_id}")
                live_aspects = (live.get('aspects') or {})
                missing = [m for m in missing if m not in live_aspects]
            except Exception:
                pass
        MAX += 20
        aspects_ok = not missing
        checks.append({'check': 'required_aspects_filled', 'pass': aspects_ok, 'missing': missing, 'required_count': len(required)})
        score += 20 if aspects_ok else max(0, 20 - 5 * len(missing))
        if missing:
            gaps.append(f'Missing required item specifics: {missing} - Cassini relevance weighting depends on these')

    gallery = [i for i in (res.get('ae_multimedia_info_dto', {}).get('image_urls') or '').split(';') if i]
    MAX += 10
    img_ok = len(gallery) >= 3
    checks.append({'check': 'image_count', 'pass': img_ok, 'value': len(gallery)})
    score += 10 if img_ok else round(10 * len(gallery) / 3)
    if not img_ok:
        gaps.append(f'Only {len(gallery)} real supplier gallery images found - eBay recommends 8-12')

    desc = product_row.get('description') or ''
    MAX += 10
    desc_ok = 2000 <= len(desc) <= 4000 and 'Spezifikation' in desc
    checks.append({'check': 'description_quality', 'pass': desc_ok, 'length': len(desc)})
    score += 10 if desc_ok else 0
    if not desc_ok:
        gaps.append('Description should be 2000-4000 chars with real Spezifikation/Paket sections (description.build())')

    cost = float(product_row.get('aliexpress_price') or 0)
    ship = float(product_row.get('shipping_cost') or 1.99)
    our_price = float(product_row.get('ebay_price') or 0)
    queries = categories.queries(subject, props)
    info, _review = gates.demand(ebay, queries, our_price)
    MAX += 15
    price_ratio = info.get('price_vs_median') if info else None
    price_ok = price_ratio is not None and price_ratio <= 1.5
    checks.append({'check': 'price_vs_real_market_median', 'pass': price_ok, 'ratio': price_ratio, 'market': info})
    score += 15 if price_ok else (8 if price_ratio and price_ratio <= 2.0 else 0)
    if not price_ok:
        gaps.append(f'Price is {price_ratio}x the real eBay.de median ({info}) - hurts click-through and Cassini relevance')

    item_id = product_row.get('ebay_item_id')
    MAX += 10
    ad_ok = False
    bid = None
    if item_id:
        try:
            ad_data = ebay._request('GET', '/sell/marketing/v1/ad_campaign/167027798017/ad', params={'limit': 100})
            for a in ad_data.get('ads', []):
                if a.get('listingId') == str(item_id):
                    bid = a.get('bidPercentage')
                    ad_ok = True
                    break
        except Exception:
            pass
    checks.append({'check': 'promoted_listing_active', 'pass': ad_ok, 'bid': bid})
    score += 10 if ad_ok else 0
    if not ad_ok:
        gaps.append('Not in a Promoted Listings campaign - add via publish.add_ad() for a visibility boost')

    # GROUND TRUTH, not a proxy: eBay's own Traffic Report. A listing can score 100 on every signal
    # above and still get near-zero real impressions (new-seller trust, thin sales/feedback history,
    # category competition) - this is the only check that proves Cassini is actually showing it.
    MAX += 10
    tr = (traffic or {}).get(str(item_id)) if item_id else None
    impressions = tr.get('LISTING_IMPRESSION_TOTAL') if tr else None
    traffic_ok = impressions is not None and impressions >= 50   # 50/30d is still low but a real baseline
    checks.append({'check': 'real_traffic_30d', 'pass': traffic_ok, 'impressions': impressions,
                   'views': tr.get('LISTING_VIEWS_TOTAL') if tr else None,
                   'conversion_rate': tr.get('SALES_CONVERSION_RATE') if tr else None})
    score += 10 if traffic_ok else 0
    if not traffic_ok:
        gaps.append(f'REAL eBay traffic report shows only {impressions if impressions is not None else "no"} '
                     f'impressions/30d - good proxy scores do NOT guarantee Cassini is showing this listing; '
                     f'see ebay-listing-optimizer skill "new listing visibility" section')

    return {'score': round(100 * score / MAX) if MAX else None, 'max_points': MAX, 'checks': checks, 'gaps': gaps}
