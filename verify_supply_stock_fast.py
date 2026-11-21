"""
Fast read-only AliExpress supply-link + stock verification for all active
(is_listed=1) Mondeora listings. No DB/eBay writes — report only.

For each product: calls AliExpress get_product_details() and checks
(a) the product still resolves (not pulled/removed by supplier)
(b) real stock/quantity > 0 reported by AliExpress right now.
"""
import sys, json, sqlite3
from datetime import datetime

sys.path.insert(0, '.')
from src.api.aliexpress_client import AliExpressAPIClient, AliExpressAPIError

ali = AliExpressAPIClient()
conn = sqlite3.connect('data/dropshipping.db')
c = conn.cursor()
c.execute("SELECT id, title, ebay_item_id, aliexpress_product_id FROM products WHERE is_listed=1 ORDER BY id")
rows = c.fetchall()
conn.close()

results = []
ok, broken, no_stock, no_id = 0, 0, 0, 0

for pid, title, ebay_item_id, ali_id in rows:
    if not ali_id:
        no_id += 1
        results.append({'id': pid, 'status': 'NO_ALI_ID', 'title': title[:50]})
        print(f'❌ [{pid}] AliExpress ID YOK — {title[:50]}')
        continue
    try:
        d = ali.get_product_details(str(ali_id))
        skus = d.get('skus', [])
        total_stock = sum(int(s.get('warehouse_count', 0) or 0) for s in skus) if skus else int(d.get('warehouse_count', 0) or 0)
        if total_stock <= 0:
            no_stock += 1
            results.append({'id': pid, 'status': 'NO_STOCK', 'ali_id': ali_id, 'stock': total_stock, 'title': title[:50]})
            print(f'⚠️  [{pid}] STOKSUZ (0 adet) — {title[:50]} (ali:{ali_id})')
        else:
            ok += 1
            results.append({'id': pid, 'status': 'OK', 'ali_id': ali_id, 'stock': total_stock})
    except AliExpressAPIError as e:
        broken += 1
        results.append({'id': pid, 'status': 'BROKEN', 'ali_id': ali_id, 'error': str(e)[:150], 'title': title[:50], 'ebay_item_id': ebay_item_id})
        print(f'🔴 [{pid}] KIRIK LINK — {title[:50]} (ali:{ali_id}) eBay:{ebay_item_id} -> {e}')
    except Exception as e:
        broken += 1
        results.append({'id': pid, 'status': 'ERROR', 'ali_id': ali_id, 'error': str(e)[:150], 'title': title[:50]})
        print(f'🔴 [{pid}] HATA — {title[:50]} -> {e}')

print()
print(f'=== SONUC: {len(rows)} aktif listing tarandi ===')
print(f'OK (tedarik+stok var): {ok}')
print(f'KIRIK LINK (tedarikci kaldirmis): {broken}')
print(f'STOKSUZ: {no_stock}')
print(f'ID YOK: {no_id}')

with open('data/supply_stock_verification.json', 'w', encoding='utf-8') as f:
    json.dump({'run_at': datetime.now().isoformat(), 'total': len(rows), 'ok': ok,
               'broken': broken, 'no_stock': no_stock, 'no_id': no_id, 'results': results}, f, indent=2, ensure_ascii=False)
print('Rapor: data/supply_stock_verification.json')
