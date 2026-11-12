"""variation_sync: keep every VARIANT's eBay price and stock in line with AliExpress (daily job).
The legacy inventory_sync / price_optimize skip variation products because they address one SKU 'AE-<pid>'.
Per variant: price = pricing.price_for(current cost, ship) (net >= min profit at the real fee); qty = min(stock, 5),
0 when the variant is out of stock / removed / the product is no longer on sale. Writes only through
bulk_update_price_quantity. New AliExpress variants are only REPORTED (they need a republish)."""
import sqlite3
from datetime import datetime

from src.listing_quality import publish, source, variants

CHUNK = 25


def run(ali, ebay, db_path='data/dropshipping.db', dry_run=False):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    api = None if dry_run else publish.Api(ebay)
    prods = db.execute('select * from products where is_listed=1 and id in (select product_id from product_variants) order by id').fetchall()
    summary = {'products': len(prods), 'updated_variants': 0, 'errors': [], 'new_variants_pending': {}, 'dry_run': dry_run, 'changes': []}
    for p in prods:
        pid = p['aliexpress_product_id']
        try:
            res = source.fetch_raw(ali, pid)
            on_sale = (res.get('ae_item_base_info_dto') or {}).get('product_status_type') == 'onSelling'
            plan = variants.build(pid, res, float(p['shipping_cost'] or 1.99))
        except Exception as ex:
            summary['errors'].append((p['id'], str(ex)[:120]))
            continue
        live = {v['sku']: v for v in plan['variants']} if on_sale else {}
        rows = db.execute('select * from product_variants where product_id=?', (p['id'],)).fetchall()
        known = {r['sku'] for r in rows}
        new = [s for s in live if s not in known]
        if new:
            summary['new_variants_pending'][p['id']] = len(new)
        todo = []
        for r in rows:
            v = live.get(r['sku'])
            qty = v['qty'] if v else 0
            price = v['price'] if v else r['price']
            if qty != r['qty'] or abs(price - r['price']) >= 0.01:
                todo.append((r, price, qty))
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            reqs = []
            for r, price, qty in chunk:
                try:
                    offers = (api or ebay)._request('GET', '/sell/inventory/v1/offer', params={'sku': r['sku']}) if dry_run \
                        else api.call('GET', '/sell/inventory/v1/offer', params={'sku': r['sku']})
                    oid = offers['offers'][0]['offerId']
                except Exception as ex:
                    summary['errors'].append((r['sku'], str(ex)[:100]))
                    continue
                reqs.append((r, price, qty, {'sku': r['sku'], 'shipToLocationAvailability': {'quantity': qty},
                                             'offers': [{'offerId': oid, 'availableQuantity': qty,
                                                         'price': {'value': f'{price:.2f}', 'currency': 'EUR'}}]}))
            for r, price, qty, _ in reqs:
                summary['changes'].append((r['sku'], r['price'], price, r['qty'], qty))
            if dry_run or not reqs:
                continue
            resp = api.call('POST', '/sell/inventory/v1/bulk_update_price_quantity', {'requests': [x[3] for x in reqs]})
            ok_skus = {x.get('sku') for x in resp.get('responses', []) if x.get('statusCode') == 200}
            now = datetime.now().isoformat()
            for r, price, qty, _ in reqs:
                if r['sku'] in ok_skus:
                    db.execute('update product_variants set price=?, qty=?, updated_at=? where sku=?', (price, qty, now, r['sku']))
                    summary['updated_variants'] += 1
                else:
                    summary['errors'].append((r['sku'], 'bulk update not confirmed'))
            db.commit()
    summary['status'] = 'ok' if not summary['errors'] else 'partial'
    return summary
