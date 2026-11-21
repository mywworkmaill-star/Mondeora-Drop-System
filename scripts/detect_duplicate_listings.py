#!/usr/bin/env python3
"""
Duplicate Active Listing Detector
==================================

ROOT CAUSE (2026-11-21): the DB vs eBay active-count comparison
("GetMyeBaySelling" vs local products table) can look like a simple sync
gap, but real investigation found 2 products genuinely listed 2-3x
simultaneously on eBay (same AliExpress source product, different SKU
naming eras: ALI-X / AE-X-Y / AEX / VAR-X-Y). This wastes monthly listing
quota, splits traffic across duplicates, and risks eBay's duplicate-listing
policy.

DELIBERATELY DETECTION-ONLY, NOT AUTO-DELETE: a naive "keep whichever has
the most views" rule is dangerous with tiny sample sizes -- confirmed live
today, where the single-SKU duplicate had 2 views vs the fully-configured
8-variant listing's 1 view, a statistically meaningless difference that
would have deleted the BETTER listing. Ending listings always needs a
human/agent judgment call weighing variant count, configuration quality,
and traffic together -- this script only surfaces the comparison.

Usage: python scripts/detect_duplicate_listings.py
"""
import sys
import re
import requests
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))


def extract_source_id(sku):
    """Same multi-era SKU parsing this session built up by hand: ALI-X,
    raw X, AE-X-Y, AEX (no separator), VAR-X-Y. Returns the AliExpress
    source product id, or None if the SKU doesn't match any known shape."""
    if not sku:
        return None
    for pattern in (
        r'^ALI-(\d{6,})$',
        r'^AE-(\d{6,})-\d+$',
        r'^AE(\d{6,})$',
        r'^VAR-\d+-(\d{6,})$',
        r'^(\d{6,})$',
    ):
        m = re.match(pattern, sku)
        if m:
            return m.group(1)
    return None


def get_active_listings(ebay, token):
    xml = '''<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
<ActiveList><Include>true</Include><Pagination><EntriesPerPage>200</EntriesPerPage><PageNumber>1</PageNumber></Pagination></ActiveList>
</GetMyeBaySellingRequest>'''
    headers = {'X-EBAY-API-SITEID': '77', 'X-EBAY-API-COMPATIBILITY-LEVEL': '1193',
               'X-EBAY-API-CALL-NAME': 'GetMyeBaySelling', 'X-EBAY-API-IAF-TOKEN': token, 'Content-Type': 'text/xml'}
    r = requests.post('https://api.ebay.com/ws/api.dll', headers=headers, data=xml, timeout=30)
    ids = re.findall(r'<ItemID>([^<]*)</ItemID>', r.text)
    titles = re.findall(r'<Title>([^<]*)</Title>', r.text)
    return list(zip(ids, titles))


def get_item_skus(ebay, token, item_id):
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents"><ItemID>{item_id}</ItemID><DetailLevel>ReturnAll</DetailLevel></GetItemRequest>'''
    headers = {'X-EBAY-API-SITEID': '77', 'X-EBAY-API-COMPATIBILITY-LEVEL': '1193',
               'X-EBAY-API-CALL-NAME': 'GetItem', 'X-EBAY-API-IAF-TOKEN': token, 'Content-Type': 'text/xml'}
    r = requests.post('https://api.ebay.com/ws/api.dll', headers=headers, data=xml, timeout=20)
    return re.findall(r'<SKU>([^<]+)</SKU>', r.text)


def get_traffic(ebay, item_ids):
    if not item_ids:
        return {}
    ids_str = '|'.join(item_ids)
    filter_str = f'marketplace_ids:{{EBAY_DE}},listing_ids:{{{ids_str}}},date_range:[20261101..20261121]'
    try:
        r = ebay._request('GET', '/sell/analytics/v1/traffic_report', params={
            'dimension': 'LISTING', 'filter': filter_str,
            'metric': 'LISTING_IMPRESSION_TOTAL,LISTING_VIEWS_TOTAL'})
    except Exception:
        return {}
    out = {}
    for rec in r.get('records', []):
        lid = rec['dimensionValues'][0]['value']
        vals = rec['metricValues']
        out[lid] = {'impressions': vals[0]['value'], 'views': vals[1]['value']}
    return out


def main():
    from api.ebay_client import eBayAPIClient
    ebay = eBayAPIClient()
    token = ebay._get_headers().get('Authorization').replace('Bearer ', '')

    listings = get_active_listings(ebay, token)
    by_source = defaultdict(list)
    unresolved = []
    for item_id, title in listings:
        skus = get_item_skus(ebay, token, item_id)
        source_ids = {sid for sku in skus if (sid := extract_source_id(sku))}
        if len(source_ids) == 1:
            by_source[next(iter(source_ids))].append((item_id, title, len(skus)))
        elif not source_ids:
            unresolved.append((item_id, title))

    dupes = {sid: items for sid, items in by_source.items() if len(items) > 1}
    if not dupes:
        return  # alert-only convention: silent on nothing to report

    all_dup_ids = [item_id for items in dupes.values() for item_id, _, _ in items]
    traffic = get_traffic(ebay, all_dup_ids)

    print(f"Duplicate listing taramasi - {len(dupes)} urun grubu, toplam {sum(len(v) for v in dupes.values())} ilan")
    for sid, items in dupes.items():
        print(f"\nAliExpress source {sid}:")
        for item_id, title, sku_count in items:
            t = traffic.get(item_id, {})
            print(f"  {item_id} | {sku_count} varyant | gosterim={t.get('impressions','?')} goruntuleme={t.get('views','?')} | {title[:50]}")
    print("\nBu bir TESPIT raporu - hangi ilanin tutulacagina (varyant sayisi + trafik birlikte "
          "degerlendirilerek) karar agent/kullanici tarafindan verilmeli, otomatik silme yapilmadi.")


if __name__ == '__main__':
    main()
