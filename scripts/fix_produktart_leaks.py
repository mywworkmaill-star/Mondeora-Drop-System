"""Fix 15 listings where the Produktart aspect value was literally the (correct-for-
the-listing) category's own display name - a weaker, lower-confidence corruption
than the earlier category_id-is-also-wrong case, but still worth real values. No
category change here - these categories ARE right for the product, only the
Produktart VALUE was wrong/generic. Real values chosen from each category's own
get_item_aspects_for_category picklist (FREE_TEXT mode everywhere here, so a precise
descriptive German term is fine even when not literally in the suggestion list).
"""
import sys
import json
sys.path.insert(0, '.')
from src.api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()

# listing_id -> real Produktart replacement value
FIXES = {
    '860138343669': 'Löffelablage',
    '860138544587': 'Organizer',
    '860138341251': 'Kabelaufwickler',
    '860138344632': 'Gemischtes Werkzeugset',
    '860138359448': 'Müllbeutelhalter',
    '860139554274': 'Tackle Box',
    '860134874458': 'Bälle',
    '860134884632': 'Knautschball',
    '860139537428': 'Kabelaufwickler',
    '860139545709': 'Mehrzweckhaken',
    '860135446221': 'Rahmenpuzzle',
    '860143527490': 'Hosenbügel-Organizer',
    '860144774087': 'Werkzeugaufbewahrungsständer',
    '860134905415': 'Kauspielzeug',
    '860139539563': 'Kabelbinder',
}

audit = [json.loads(l) for l in open('data/audit/full_inventory_audit.jsonl', encoding='utf-8')]
by_listing_skus = {}
for r in audit:
    if r.get('listing_status') in ('ACTIVE', 'OUT_OF_STOCK'):
        by_listing_skus.setdefault(r['listing_id'], []).append(r['sku'])

results = []
for listing_id, new_value in FIXES.items():
    skus = by_listing_skus.get(listing_id, [])
    print(f'=== {listing_id} ({len(skus)} SKU) -> Produktart = {new_value!r} ===', flush=True)
    grp_key = None
    try:
        # Find the real group key: try every distinct AliExpress product_id prefix in this group.
        import re
        pids = {m.group(1) for sku in skus if (m := re.match(r'^AE-([0-9]{6,})-', sku))}
        for pid in pids:
            try:
                grp = ebay._request('GET', f'/sell/inventory/v1/inventory_item_group/GRP-{pid}')
                grp['aspects'] = {**(grp.get('aspects') or {}), 'Produktart': [new_value]}
                ebay._request('PUT', f'/sell/inventory/v1/inventory_item_group/GRP-{pid}', json=grp)
                grp_key = f'GRP-{pid}'
            except Exception as ex:
                print(f'  grup atlandi ({pid}): {type(ex).__name__}: {ex}'[:200], flush=True)
    except Exception as ex:
        print('  grup hata:', ex, flush=True)

    for sku in skus:
        entry = {'listing_id': listing_id, 'sku': sku}
        try:
            item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            aspects = dict((item.get('product') or {}).get('aspects') or {})
            before = aspects.get('Produktart')
            aspects['Produktart'] = [new_value]
            item.setdefault('product', {})['aspects'] = aspects
            ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=item)
            entry.update(ok=True, before=before, after=new_value)
        except Exception as ex:
            entry.update(ok=False, error=f'{type(ex).__name__}: {ex}'[:250])
        results.append(entry)
        print(' ', entry, flush=True)

ok = sum(1 for r in results if r.get('ok'))
print(f'\nTOPLAM: {ok}/{len(results)} SKU basarili', flush=True)
with open('data/audit/produktart_fix_log.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
