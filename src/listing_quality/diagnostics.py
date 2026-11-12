"""Listing-content blocker diagnosis: turns plan_for()'s raw ValueError text into a structured, human-readable
verdict (Turkish) instead of a stack trace the operator has to manually dig through each time.

This is a SECOND classifier, deliberately separate from src.intelligence.healing.classify(): healing.classify()
is for TRANSPORT failures (auth/rate-limit/timeout) that are safe to blindly retry. This one is for BUSINESS-LOGIC
gate failures from plan_for() — never retried blindly, because retrying doesn't change a category mismatch or a
missing image. auto_fixable=True only for cases where src.listing_quality.publish already has a code path that
resolves it without a human (e.g. the category-alternative fallback) — everything else genuinely needs a person.
"""
import re

CATEGORY_MISMATCH = 'category_aspect_mismatch'
CATEGORY_NO_FIT = 'category_no_fit'
MISSING_ASPECT = 'required_aspect_missing'
LABEL_UNVERIFIED = 'variant_label_unverified'
PRICE_SPREAD = 'price_spread_suspicious'
IMAGE_TOO_SMALL = 'image_below_500px'
GATE_BLOCK = 'risk_gate_block'
GATE_REVIEW = 'risk_gate_review'
IDENTITY_MISMATCH = 'supplier_identity_mismatch'
STALE_SKU_ID = 'stale_placeholder_sku_id'
UNKNOWN = 'unknown'

_PATTERNS = (
    (re.compile(r'Verified source SKU is missing or ambiguous'), STALE_SKU_ID,
     'Veritabanındaki sku_id gerçek bir AliExpress SKU numarası değil (örn. eski bir "AUTO-.../VAR-..." '
     'yer tutucu) — tedarikçide artık karşılığı yok, stok/fiyat senkronize edilemiyor.',
     'AliExpress ürün sayfasını açıp eBay\'deki mevcut rengi/varyantı bulun, gerçek sayısal '
     'sku_id\'yi products.sku_id\'ye elle yazın; tahmin etmeyin.'),
    (re.compile(r'no candidate category fit'), CATEGORY_MISMATCH,
     'Ürünün en uygun eBay kategorisi, varyant özelliğini (renk/boyut) desteklemiyor ve otomatik denenen '
     'alternatif kategoriler de uymadı.',
     'config/category_overrides.json\'a doğru kategori ID\'sini elle ekleyin (gerçek eBay taxonomy sorgusundan).'),
    (re.compile(r'category not approved'), CATEGORY_NO_FIT,
     'eBay taksonomisi bu ürün için güvenilir bir kategori önerisi bulamadı (düşük güven skoru).',
     'Ürün başlığını kontrol edin veya config/category_overrides.json\'a elle kategori ekleyin.'),
    (re.compile(r'required aspects missing: (.+)'), MISSING_ASPECT,
     'eBay bu kategori için zorunlu gördüğü bir özelliği (örn. Modell) istiyor, tedarikçi verisinde yok.',
     'Gerçek değeri biliyorsanız extra_aspects ile elle sağlayın; icat etmeyin.'),
    (re.compile(r'variant labels not verifiable'), LABEL_UNVERIFIED,
     'Varyant etiketleri (renk/boyut) satıcının güvenilir tanımından gelmiyor, makine çevirisi riskli.',
     'AliExpress ürün sayfasından gerçek varyant adlarını görüp elle onaylayın.'),
    (re.compile(r'price spread'), PRICE_SPREAD,
     'Varyantlar arası fiyat farkı 3 katın üstünde — muhtemelen farklı ürün/paket karışmış tek varyant altında.',
     'AliExpress\'te SKU\'ları tek tek kontrol edin; gerçekten aynı ürün değilse ayrı listeleme yapın.'),
    (re.compile(r'no image >= 500'), IMAGE_TOO_SMALL,
     'Hiçbir ürün görseli eBay.de\'nin minimum 500px kuralını geçemedi.',
     'Tedarikçiden/üründen daha yüksek çözünürlüklü görsel gerekli; var olanı büyütmek görseli bozar.'),
    (re.compile(r'GATE BLOCK'), GATE_BLOCK,
     'Ürün adı/özellikleri yasaklı liste ile eşleşti (marka/taklit/güvenlik riski) — asla otomatik yayınlanmaz.',
     'Kalıcı engel; ürünü değiştirin veya listelemeyin.'),
    (re.compile(r'GATE REVIEW'), GATE_REVIEW,
     'Risk gate\'i bu ürünü incelemeye düşürdü (örn. pil/elektronik kelimesi geçiyor).',
     'Gerçekten güvenliyse config/risk_ack.json\'a kullanıcı onayıyla ekleyin; aksi halde atlayın.'),
    (re.compile(r'IDENTITY MISMATCH'), IDENTITY_MISMATCH,
     'Veritabanındaki ürün başlığı ile tedarikçiden şu an gelen başlık örtüşmüyor — ürün değişmiş olabilir.',
     'Tedarikçi ürününü elle kontrol edin; farklı bir ürünse eşleştirmeyi düzeltin.'),
)


def diagnose(error_text):
    """str(exception) -> {code, human_de... (TR), advice, auto_fixable}. Never raises."""
    text = str(error_text or '')
    for pattern, code, human, advice in _PATTERNS:
        if pattern.search(text):
            return {'code': code, 'human': human, 'advice': advice, 'auto_fixable': False, 'raw': text[:400]}
    return {'code': UNKNOWN, 'human': f'Sınıflandırılamayan hata: {text[:150]}', 'advice': 'Elle inceleyin.',
            'auto_fixable': False, 'raw': text[:400]}


_REAL_SKU_ID = re.compile(r'^\d{6,}$')   # a genuine AliExpress sku_id is a long digit string


def find_stale_sku_ids(db_path='data/dropshipping.db'):
    """Read-only, NO API calls: flags listed products whose sku_id is a legacy placeholder (e.g. 'AUTO-...',
    'VAR-...-1') rather than a real numeric AliExpress SKU id. These permanently fail sync_inventory/
    analyze_competition_and_optimize_prices (isolated there so they no longer break OTHER products), but
    without this check they stay silent until the daily job logs a skip — this surfaces them proactively,
    once, with the Turkish fix instructions, in the same report as every other blocker."""
    import sqlite3
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("select id, title, aliexpress_product_id, sku_id from products "
                      "where is_listed=1 and sku_id is not null").fetchall()
    out = []
    for row in rows:
        if not _REAL_SKU_ID.match(str(row['sku_id'])):
            entry = {'id': row['id'], 'title': (row['title'] or '')[:70],
                     'aliexpress_product_id': row['aliexpress_product_id'], 'sku_id': row['sku_id'],
                     'result': 'blocked'}
            entry.update(diagnose('Verified source SKU is missing or ambiguous'))
            out.append(entry)
    return out


def scan_products(ali, ebay, db_path='data/dropshipping.db', statuses=None):
    """Read-only health scan: for every product in `statuses` (default: everything not cleanly active),
    try plan_for(existing=True) and diagnose any failure. Never writes to eBay/AliExpress or the DB.
    Also includes the no-API-call stale-sku-id scan below, so one report covers both failure classes."""
    import sqlite3
    from src.listing_quality import publish
    statuses = statuses or ('manual_review', 'needs_variation_listing', 'needs_images_500px', 'ready_to_list',
                            'stale_sku_needs_mapping')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    qmarks = ','.join('?' * len(statuses))
    rows = db.execute(f'select * from products where status in ({qmarks}) order by id', statuses).fetchall()
    report = list(find_stale_sku_ids(db_path))
    seen_ids = {r['id'] for r in report}
    for row in rows:
        if row['id'] in seen_ids:
            continue
        entry = {'id': row['id'], 'title': (row['title'] or '')[:70], 'status': row['status'],
                 'aliexpress_product_id': row['aliexpress_product_id']}
        try:
            # Already-live listings get the same leniency revise_in_place/recategorize use (existing=True);
            # never-yet-listed ones are checked with the REAL gate a first publish attempt would hit
            # (existing=False) — otherwise this report would hide the actual blocker behind a later one.
            st = publish.plan_for(ali, ebay, row['aliexpress_product_id'],
                                   float(row['shipping_cost'] or 1.99), None, None, existing=bool(row['is_listed']))
            entry['result'] = 'ok'
            entry['category_id'] = st['cat']['category_id']
            entry['variants'] = len(st['plan']['variants'])
        except Exception as ex:
            entry['result'] = 'blocked'
            entry.update(diagnose(ex))
        report.append(entry)
    return report
