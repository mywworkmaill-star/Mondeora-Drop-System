"""
Retrofit packageWeightAndSize onto ALL already-published inventory items.
Root-cause fix for eBay quoting international shipping > item price: missing
packageWeightAndSize made eBay assume a worst-case heavy/large package.
Reads real L/W/H from the live inventory item's own aspects when present
(no guessing — these are the values we already published), else applies a
small conservative generic parcel estimate.
"""
import sys, re, json, sqlite3, time
sys.path.insert(0, 'src')
from api.ebay_client import eBayAPIClient

sys.path.insert(0, '.')
from orchestra_v5_2_aliexpress_verified import OrchestraV52
o = OrchestraV52()
ebay = o.ebay if hasattr(o, 'ebay') else eBayAPIClient()

conn = sqlite3.connect('data/dropshipping.db')
c = conn.cursor()
c.execute("SELECT id, aliexpress_product_id FROM products WHERE is_listed=1")
rows = c.fetchall()
conn.close()

def parse_cm(val):
    if not val:
        return None
    m = re.search(r'([\d.,]+)', str(val))
    if not m:
        return None
    return float(m.group(1).replace(',', '.'))

fixed, skipped, failed = 0, 0, 0
for pid, ali_id in rows:
    sku = f'ALI-{ali_id}'
    try:
        item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
    except Exception as e:
        failed += 1
        print(f'[{pid}] GET FAIL {sku}: {e}')
        continue

    if item.get('packageWeightAndSize'):
        skipped += 1
        continue  # already fixed (e.g. created after the code patch)

    aspects = item.get('product', {}).get('aspects', {})
    L = parse_cm((aspects.get('Länge') or [None])[0])
    W = parse_cm((aspects.get('Breite') or [None])[0])
    H = parse_cm((aspects.get('Höhe') or [None])[0])

    if L and W and H:
        weight_g = o._estimate_package_weight_g(L, W, H)
        pkg = {
            'dimensions': {'length': L, 'width': W, 'height': H, 'unit': 'CENTIMETER'},
            'packageType': 'PACKAGE_THICK_ENVELOPE' if H < 3 else 'MAILING_BOX',
            'weight': {'value': weight_g, 'unit': 'GRAM'}
        }
    else:
        pkg = {'packageType': 'MAILING_BOX', 'weight': {'value': 300, 'unit': 'GRAM'}}

    item['packageWeightAndSize'] = pkg
    try:
        ebay._request('PUT', f'/sell/inventory/v1/inventory_item/{sku}', json=item)
        fixed += 1
        print(f'[{pid}] FIXED {sku} -> {pkg}')
    except Exception as e:
        failed += 1
        print(f'[{pid}] PUT FAIL {sku}: {e}')

print()
print(f'=== TOPLAM: {len(rows)} | Duzeltildi: {fixed} | Zaten OK: {skipped} | Basarisiz: {failed} ===')
o.close()
