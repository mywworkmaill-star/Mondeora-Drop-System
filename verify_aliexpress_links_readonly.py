"""Read-only AliExpress link verification for Mondeora listings.
Compares each DB product's AliExpress source (via DS API) with the eBay inventory item.
Writes data/link_verification_latest.json (no secrets). No DB or remote writes.
"""
import os, sys, json, re, sqlite3, io, hashlib, traceback
from datetime import datetime
from decimal import Decimal

ROOT = r'C:\Users\Administrator\Desktop\Mondeora-Drop-System'
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import requests
from PIL import Image
from src.api.aliexpress_client import AliExpressAPIClient, AliExpressAPIError
from src.api.ebay_client import eBayAPIClient, EBayAPIError

OUT = os.path.join(ROOT, 'data', 'link_verification_latest.json')
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# --- helpers -----------------------------------------------------------------
def dhash(url, size=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        img = Image.open(io.BytesIO(r.content)).convert('L').resize((size + 1, size), Image.LANCZOS)
        px = list(img.getdata())
        bits = []
        for row in range(size):
            for col in range(size):
                bits.append(px[row * (size + 1) + col] > px[row * (size + 1) + col + 1])
        return bits
    except Exception:
        return None

def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))

STOP = set('für fur mit und der die das von zum zur aus ein eine stück stuck pro max neu new 1 2 3 4 5 6 10 the for with and of to in on a an pcs pc set'.split())
def tokens(s):
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9äöüß ]+', ' ', s)
    return {t for t in s.split() if len(t) > 2 and t not in STOP}

# --- load products -----------------------------------------------------------
con = sqlite3.connect('data/dropshipping.db')
cols = [r[1] for r in con.execute('pragma table_info(products)')]
rows = [dict(zip(cols, r)) for r in con.execute(
    "select * from products where aliexpress_product_id is not null and status not like 'REMOVED%' order by id")]
con.close()

report = {'run_at': datetime.now().isoformat(timespec='seconds'), 'scope': 'read_only',
          'checked': 0, 'products': [], 'ebay_fetch': None}

# --- eBay inventory snapshot (one pass) ---------------------------------------
ebay_by_listing = {}
try:
    eb = eBayAPIClient()
    inv_items = list(eb._pages(eb.inventory_path + '/inventory_item', 'inventoryItems'))
    for inv in inv_items:
        sku = inv.get('sku')
        if not sku:
            continue
        for offer in eb._offers(sku):
            lid = offer.get('listing', {}).get('listingId')
            if lid:
                ebay_by_listing[lid] = {
                    'sku': sku,
                    'title': inv.get('product', {}).get('title'),
                    'images': inv.get('product', {}).get('imageUrls', []) or [],
                    'price': offer.get('pricingSummary', {}).get('price', {}).get('value'),
                    'currency': offer.get('pricingSummary', {}).get('price', {}).get('currency'),
                    'listing_status': offer.get('listing', {}).get('listingStatus'),
                    'quantity': offer.get('availableQuantity'),
                }
    report['ebay_fetch'] = {'status': 'ok', 'inventory_items': len(inv_items), 'listings': len(ebay_by_listing)}
except Exception as e:
    report['ebay_fetch'] = {'status': 'failed', 'error': type(e).__name__ + ': ' + str(e)[:200]}

# --- AliExpress per product ---------------------------------------------------
ali = AliExpressAPIClient()
for p in rows:
    pid = str(p['aliexpress_product_id'])
    entry = {'db_id': p['id'], 'ebay_item_id': p['ebay_item_id'], 'db_title': (p['title'] or '')[:80],
             'status': p['status'], 'aliexpress_product_id': pid,
             'aliexpress_link': f'https://www.aliexpress.com/item/{pid}.html',
             'ebay_price_db': p['ebay_price'], 'ali_price_db': p['aliexpress_price'],
             'issues': [], 'checks': {}}
    report['checked'] += 1
    if not re.fullmatch(r'\d{5,20}', pid):
        entry['issues'].append('INVALID_ID: AliExpress ürün ID sayısal değil (uydurma/yer tutucu link)')
        entry['checks']['link'] = 'invalid'
        report['products'].append(entry)
        continue
    # 1. link works / product exists via authoritative API
    try:
        d = ali.get_product_details(pid)
        entry['checks']['link'] = 'ok'
        entry['ali_title'] = (d.get('product_title') or '')[:120]
        imgs = (d.get('image_urls') or '').split(';') if d.get('image_urls') else []
        imgs = [i for i in imgs if i]
        entry['ali_image_count'] = len(imgs)
        skus = d.get('skus') or []
        prices = [s['sale_price'] for s in skus if s.get('sale_price') is not None]
        stocks = [s['warehouse_count'] for s in skus if s.get('warehouse_count') is not None]
        entry['ali_sku_count'] = len(skus)
        entry['ali_price_min_eur'] = min(prices) if prices else None
        entry['ali_price_max_eur'] = max(prices) if prices else None
        entry['ali_stock_total'] = sum(stocks) if stocks else None
        entry['db_sku_in_listing'] = (str(p.get('sku_id')) in {s.get('sku_id') for s in skus}) if skus else None
        if not imgs:
            entry['issues'].append('NO_IMAGES: AliExpress API görsel döndürmedi')
        if entry['ali_stock_total'] == 0:
            entry['issues'].append('OUT_OF_STOCK: Tüm SKU stokları 0')
        if not prices:
            entry['issues'].append('NO_EUR_PRICE: EUR fiyatı okunamadı')
    except AliExpressAPIError as e:
        msg = str(e)[:160]
        entry['checks']['link'] = 'failed'
        entry['issues'].append('LINK_BROKEN: ' + msg)
        report['products'].append(entry)
        continue
    except Exception as e:
        entry['checks']['link'] = 'error'
        entry['issues'].append('API_ERROR: ' + type(e).__name__ + ': ' + str(e)[:160])
        report['products'].append(entry)
        continue

    # 2. eBay side
    eb_data = ebay_by_listing.get(str(p['ebay_item_id']))
    if not eb_data:
        entry['checks']['ebay'] = 'not_found'
        entry['issues'].append('EBAY_NOT_FOUND: eBay Inventory offer\'larında bu listing ID yok (legacy/Trading ilanı veya kapalı)')
    else:
        entry['checks']['ebay'] = 'ok'
        entry['ebay_title'] = eb_data['title']
        entry['ebay_price_live'] = eb_data['price']
        entry['ebay_listing_status'] = eb_data['listing_status']
        entry['ebay_image_count'] = len(eb_data['images'])
        # title overlap
        t_db, t_ali = tokens(eb_data['title']), tokens(entry.get('ali_title'))
        overlap = len(t_db & t_ali) / max(1, min(len(t_db), len(t_ali)))
        entry['title_overlap'] = round(overlap, 2)
        entry['checks']['title'] = 'ok' if overlap >= 0.3 else 'weak'
        if overlap < 0.3:
            entry['issues'].append(f'TITLE_MISMATCH: eBay/AliExpress başlık kelime örtüşmesi düşük ({overlap:.0%})')
        # image match via dHash (first 4 eBay vs first 6 Ali)
        ali_h = [h for h in (dhash(u) for u in imgs[:6]) if h]
        eb_h = [h for h in (dhash(u) for u in eb_data['images'][:4]) if h]
        if ali_h and eb_h:
            best = min(hamming(a, b) for a in ali_h for b in eb_h)
            entry['image_best_hamming'] = best
            entry['checks']['images'] = 'match' if best <= 10 else ('similar' if best <= 16 else 'mismatch')
            if best > 16:
                entry['issues'].append(f'IMAGE_MISMATCH: eBay görselleri AliExpress ürün görselleriyle eşleşmiyor (hamming={best})')
        else:
            entry['checks']['images'] = 'unavailable'
            entry['issues'].append('IMAGE_CHECK_UNAVAILABLE: Görseller indirilemedi')
        # price sanity
        try:
            ep = Decimal(str(eb_data['price']))
            ap = Decimal(str(entry['ali_price_min_eur'])) if entry['ali_price_min_eur'] is not None else None
            if ap is not None:
                fee_assump = ep * Decimal('0.12') + Decimal('0.35')   # explicit assumption, not actual eBay fee
                reserve = Decimal('2')
                gross = ep - ap - fee_assump - reserve
                entry['price_gap_eur'] = float(ep - ap)
                entry['est_profit_before_freight_eur'] = float(gross.quantize(Decimal('0.01')))
                entry['markup_pct'] = float(((ep - ap) / ap * 100).quantize(Decimal('1')))
                if ep <= ap:
                    entry['checks']['price'] = 'loss'; entry['issues'].append('PRICE_LOSS: eBay fiyatı AliExpress fiyatının altında')
                elif gross < 25:
                    entry['checks']['price'] = 'below_target'
                    entry['issues'].append(f'PRICE_BELOW_TARGET: navlun öncesi tahmini kâr €{gross:.2f} < €25 hedef')
                elif ep > ap * 8:
                    entry['checks']['price'] = 'high'
                    entry['issues'].append(f'PRICE_HIGH: eBay fiyatı kaynak fiyatın {float(ep/ap):.1f} katı – alıcı karşılaştırmasında satılmama riski')
                else:
                    entry['checks']['price'] = 'ok'
                if p['ebay_price'] is not None and abs(Decimal(str(p['ebay_price'])) - ep) > Decimal('0.01'):
                    entry['issues'].append(f'DB_PRICE_DRIFT: DB eBay fiyatı {p["ebay_price"]} ≠ canlı {ep}')
                if p['aliexpress_price'] is not None and abs(Decimal(str(p['aliexpress_price'])) - ap) > Decimal('0.50'):
                    entry['issues'].append(f'ALI_PRICE_DRIFT: DB kaynak fiyatı {p["aliexpress_price"]} ≠ API {ap}')
                if p['aliexpress_price'] is None:
                    entry['issues'].append('DB_ALI_PRICE_MISSING: DB\'de kaynak fiyat yok')
        except Exception as e:
            entry['checks']['price'] = 'error'
            entry['issues'].append('PRICE_CHECK_ERROR: ' + str(e)[:100])
    report['products'].append(entry)

report['summary'] = {
    'total': report['checked'],
    'clean': sum(1 for p in report['products'] if not p['issues']),
    'with_issues': sum(1 for p in report['products'] if p['issues']),
    'link_broken': sum(1 for p in report['products'] if p['checks'].get('link') in ('failed', 'invalid')),
}
# Active eBay listings that have no AliExpress source in the DB (sale without supplier risk)
mapped = {str(p['ebay_item_id']) for p in rows}
report['unmapped_active_ebay'] = [
    {'ebay_item_id': lid, 'sku': d['sku'], 'price': d['price'], 'title': (d['title'] or '')[:60]}
    for lid, d in ebay_by_listing.items()
    if d.get('listing_status') == 'ACTIVE' and lid not in mapped]
report['summary']['unmapped_active_ebay'] = len(report['unmapped_active_ebay'])
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1, default=str)
if '--json' in sys.argv:
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
else:
    s = report['summary']
    print(f"AliExpress link doğrulama {report['run_at']}: {s['total']} ürün, temiz={s['clean']}, sorunlu={s['with_issues']}, kırık link={s['link_broken']}; eBay={report['ebay_fetch']}")
    for e in report['products']:
        flag = 'OK ' if not e['issues'] else 'WARN'
        print(f"[{flag}] db#{e['db_id']} eBay {e['ebay_item_id']} <-> AE {e['aliexpress_product_id']} | ali€{e.get('ali_price_min_eur')}-{e.get('ali_price_max_eur')} skus={e.get('ali_sku_count')} stock={e.get('ali_stock_total')} | ebay€{e.get('ebay_price_live')} {e.get('ebay_listing_status')} | img={e['checks'].get('images')} title={e['checks'].get('title')} price={e['checks'].get('price')}")
        for i in e['issues']:
            print('      -', i)
    for u in report['unmapped_active_ebay']:
        print(f"[RISK] eBay {u['ebay_item_id']} ({u['sku']}, €{u['price']}) AKTİF ama DB'de AliExpress kaynağı yok: {u['title']}")
    print(f"Rapor: {OUT}")
