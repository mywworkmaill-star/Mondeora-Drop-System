"""Hata 33: job_listing_pipeline used to call sync_top_products_from_aliexpress directly, which
re-fetched/re-vetted live supplier data and attempted to publish in the SAME step. That left a
window where a product judged eligible during research could change (price/stock/content) before
the write landed, and gave no durable record across runs of why today's buffer fell short of the
10-product target. This module splits that into prepare() (read-only; builds/refreshes a
persistent, fingerprinted ready buffer) and release_pool()/publish_ready() (release ONLY from that
saved buffer, with a pre-publish freshness re-check, concurrency-safe claim, daily cap and an
independent buyer-facing readback before a product is ever marked published).

Prepare in advance; publication consumes only saved and currently valid plans."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from html import escape
import json
import re
import sqlite3
import time

from src.runtime import PROJECT_ROOT
from src.listing_quality import quality_contract, ready_launch, ready_plan
from src.listing_quality.ready_store import ReadyStore


def prepare_pool(ali, ebay, product_rows, store, *, readiness, target=10, limit=20,
                 ttl_seconds=86400, builder=None, fingerprint=None, max_seconds=150):
    builder = builder or ready_plan.build_prepared
    fingerprint = fingerprint or ready_plan.config_fingerprint()

    for record in store.ready():
        if record['artifact'].get('config_fingerprint') != fingerprint:
            store.mark(record['product_id'], 'stale', {'reason': 'configuration_changed'})
    seen, attempted, started = set(), [], time.monotonic()
    for source_row in product_rows:
        if store.summary(target)['ready_count'] >= target or len(attempted) >= limit or time.monotonic() - started > max_seconds:
            break
        row = dict(source_row)
        pid = str(row.get('aliexpress_product_id') or '')
        if not re.fullmatch(r'[0-9]{6,}', pid) or pid in seen:
            continue
        seen.add(pid)
        previous = store.get(pid)
        if previous and (previous['status'] in ('published', 'publishing', 'needs_reconciliation')
                         or any(r['product_id'] == pid for r in store.ready())):
            continue
        try:
            result = builder(ali, ebay, row, readiness=readiness)
            artifact = result.get('artifact') or {}
            blockers = list(result['blockers'])
            if artifact.get('st'):
                # Outside builder/trial filtering: actual saved content is mandatory.
                report = quality_contract.inspect_plan(artifact['st'])
                artifact['quality_contract'] = report
                blockers.extend('contract:' + reason for reason in report['blockers'])
                if not report['blockers']:
                    artifact['payloads'] = ready_launch.compile_payloads(pid, artifact)
                else:
                    artifact.pop('payloads', None)
            else:
                # Hata 37: no content plan means no payloads are possible to compile;
                # this blocker must NEVER be skipped (even under supervised_trial), or the
                # item gets marked 'ready' with an empty artifact and later crashes with
                # KeyError('payloads') inside ready_launch.execute().
                blockers.append('full_content_plan_missing')
            record = store.put(pid, artifact, blockers=list(dict.fromkeys(blockers)), ttl_seconds=ttl_seconds)
            attempted.append({'product_id': pid, 'status': record['status'], 'blockers': record['blockers']})
        except Exception as error:
            reason = 'preparation_error:' + type(error).__name__
            store.put(pid, {}, blockers=[reason], ttl_seconds=ttl_seconds)
            attempted.append({'product_id': pid, 'status': 'blocked', 'blockers': [reason]})
    summary = store.summary(target)
    summary['target'] = target
    summary['content_prepared_count'] = sum(bool(((store.get(r['product_id']) or {}).get('artifact') or {}).get('payloads'))
                                             for r in summary['items'])
    return dict(summary, status='ok' if summary['shortfall'] == 0 else 'shortfall', attempted=attempted,
                generated_at=datetime.now(timezone.utc).isoformat(), remote_mutations_performed=False)


def release_pool(ali, ebay, store, *, readiness, target=10, daily_limit=10, fingerprint=None,
                 freshness=None, sender=None, buyer_check=None, persist=None):
    """Release a prepared batch only. An uncertain result blocks further automatic attempts."""
    summary = store.summary(target)
    blockers = ready_plan.readiness_blockers(readiness)
    
    # Supervised trial: allow 1+ ready products instead of 10
    supervised_trial = readiness.get('ready_for_supervised_trial') and not readiness.get('ready_for_live')
    minimum_ready = 1 if supervised_trial else target
    
    if summary['publishing_count'] or summary['needs_reconciliation_count']:
        blockers.append('previous_publication_needs_reconciliation')
    
    if summary['ready_count'] < minimum_ready:
        blockers.append('ready_buffer_below_target')
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = max(0, daily_limit - store.published_since(midnight))
    if remaining == 0:
        blockers.append('daily_limit_reached')
    out = {'status': 'blocked' if blockers else 'ok', 'published_count': 0,
           'results': [], 'blockers': blockers, 'ready_count': summary['ready_count']}
    if blockers:
        return out
    fingerprint = fingerprint or ready_plan.config_fingerprint()
    freshness, sender = freshness or ready_launch.validate_fresh, sender or ready_launch.execute
    buyer_check, persist = buyer_check or verify_buyer, persist or persist_published
    selected = store.ready(limit=min(target, remaining))
    
    # Trial changes the minimum batch size, never evidence or write safeguards.
    for record in selected:
        pid, artifact = record['product_id'], record['artifact']
        try:
            report = quality_contract.inspect_plan(artifact.get('st'))
            if report['blockers']:
                store.mark(pid, 'blocked', {'reason': 'quality_contract_failed', 'quality_contract': report})
                out['blockers'].extend('contract:' + reason + ':' + pid for reason in report['blockers'])
                continue
            if artifact.get('config_fingerprint') != fingerprint:
                raise ValueError('configuration_changed')
            freshness(ali, pid, artifact)
        except Exception as error:
            store.mark(pid, 'stale', {'reason': 'preflight_failed:' + type(error).__name__})
            out['blockers'].append('source_or_configuration_changed:' + pid)
    if out['blockers']:
        out['status'] = 'blocked'
        out['ready_count'] = store.summary(target)['ready_count']
        return out
    for expected in selected:
        claimed = store.claim(limit=1)
        if not claimed:
            break
        record = claimed[0]
        pid, artifact = record['product_id'], record['artifact']
        
        if pid != expected['product_id'] or record['artifact_hash'] != expected['artifact_hash']:
            store.mark(pid, 'needs_reconciliation', {'reason': 'concurrent_claim_order_changed'})
            out['status'] = 'blocked'
            out['blockers'].append('concurrent_claim_order_changed')
            break
        events, result = [], None
        def journal(event):
            events.append(event)
            store.mark(pid, 'publishing', {'operations': events})
        try:
            if quality_contract.inspect_plan(artifact.get('st'))['blockers']:
                raise ValueError('Quality contract changed after preflight')
            result = sender(ebay, pid, artifact, journal=journal, supervised_trial=False)
            if buyer_check(ebay, result['listing_id'], artifact) is False:
                raise ValueError('Buyer verification failed')
            persist(pid, artifact, result)
            store.mark(pid, 'published', {**result, 'buyer_verified': True, 'operations': events})
            out['published_count'] += 1
            out['results'].append({'product_id': pid, 'listing_id': result['listing_id'], 'buyer_verified': True})
        except Exception as error:
            store.mark(pid, 'needs_reconciliation', {'error_type': type(error).__name__,
                        'result': result, 'operations': events})
            out['status'] = 'blocked'
            out['blockers'].append('publication_needs_reconciliation:' + pid)
            break
    out['ready_count'] = store.summary(target)['ready_count']
    return out


def verify_buyer(ebay, listing_id, artifact):
    """Independent buyer-facing readback, not merely a successful Sell POST."""
    st = artifact['st']
    if st['plan']['is_variation']:
        data = ebay._request('GET', '/buy/browse/v1/item/get_items_by_item_group', params={'item_group_id': listing_id})
        group_items = data.get('items', [])
        # Hata 47: get_items_by_item_group never returns the full 'description' field
        # for group/variation listings (checked live: always empty string there, while
        # the single-item get_item endpoint returns the real, full, matching text) - so
        # a strict description check against this endpoint failed every real variation
        # listing. Fetch each item's full detail by itemId instead, same as a buyer
        # clicking into the actual listing would see.
        items = [ebay._request('GET', '/buy/browse/v1/item/' + item['itemId']) for item in group_items]
    else:
        data = ebay._request('GET', '/buy/browse/v1/item/get_item_by_legacy_id', params={'legacy_item_id': listing_id})
        items = [data]
    from html import unescape
    normalize = lambda value: re.sub(r'\s+', ' ', unescape(value or '')).strip()
    if len(items) != len(st['plan']['variants']):
        raise ValueError('Buyer-visible variant count not verified')
    expected_prices = sorted(round(v['price'], 2) for v in st['plan']['variants'])
    actual_prices = []
    for item in items:
        if item.get('title') != st['title'] or normalize(item.get('description')) != normalize(st['desc']):
            raise ValueError('Buyer-visible saved content not verified')
        if item.get('price', {}).get('currency') != 'EUR':
            raise ValueError('Buyer-visible currency not verified')
        actual_prices.append(round(float(item['price']['value']), 2))
    if sorted(actual_prices) != expected_prices:
        raise ValueError('Buyer-visible prices not verified')


def persist_published(pid, artifact, result):
    st, now = artifact['st'], datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(PROJECT_ROOT / 'data' / 'dropshipping.db', timeout=30)) as db:
        row = db.execute('SELECT id,is_listed,ebay_item_id FROM products WHERE aliexpress_product_id=?', (pid,)).fetchone()
        if not row or (row[1] and str(row[2]) != result['listing_id']):
            raise ValueError('Local product mapping requires reconciliation')
        db.execute('CREATE TABLE IF NOT EXISTS product_variants (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, '
                   'sku TEXT UNIQUE, ali_sku_id TEXT, aspects TEXT, cost REAL, price REAL, qty INTEGER, updated_at TEXT)')
        for variant in st['plan']['variants']:
            db.execute('INSERT OR REPLACE INTO product_variants '
                '(product_id,sku,ali_sku_id,aspects,cost,price,qty,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                (row[0], variant['sku'], variant['sku_id'], json.dumps(variant['aspects'], ensure_ascii=False),
                 variant['cost'], variant['price'], variant['qty'], now))
        first = st['plan']['variants'][0]
        db.execute("UPDATE products SET is_listed=1,status='active',ebay_item_id=?,category_id=?,title=?,description=?,"
                   "ebay_price=?,sku_id=?,aliexpress_price=?,currency='EUR',updated_at=? WHERE id=?",
                   (result['listing_id'], st['cat']['category_id'], st['title'], st['desc'], first['price'],
                    first['sku_id'], first['cost'], now, row[0]))
        db.commit()


def publish_ready(ali, ebay):
    from src.jobs import JobLock
    with JobLock('ready_listing_release'):
        config, store = settings(), store_default()
        out = release_pool(ali, ebay, store, readiness=read_readiness(), target=config['target'],
                           daily_limit=config['daily_publish_limit'])
        if out['published_count']:
            out['replenishment'] = prepare(ali, ebay)
        return out


def settings():
    path = PROJECT_ROOT / 'config' / 'ready_listing_buffer.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('target') != 10 or config.get('daily_publish_limit') != 10:
        raise ValueError('Ready buffer and daily release target must be 10 distinct products')
    return config


def read_readiness():
    try:
        return json.loads((PROJECT_ROOT / 'data' / 'readiness_report.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def buffer_status(store=None, readiness=None):
    store = store or store_default()
    report = store.summary(target=10)
    report['content_prepared_count'] = sum(bool(((store.get(r['product_id']) or {}).get('artifact') or {}).get('payloads')) for r in report['items'])
    report['global_blockers'] = ready_plan.readiness_blockers(read_readiness() if readiness is None else readiness)
    if report['global_blockers']:
        report['ready_count'] = 0
        report['shortfall'] = 10
    return report


def store_default():
    return ReadyStore(PROJECT_ROOT / 'data' / 'listing_ready.sqlite')


def pending_rows(limit=100):
    with closing(sqlite3.connect(PROJECT_ROOT / 'data' / 'dropshipping.db')) as db:
        db.row_factory = sqlite3.Row
        # Priority: priced products first (ready_to_list, active with price)
        return [dict(row) for row in db.execute("""SELECT * FROM products WHERE is_listed=0
            AND (ebay_item_id IS NULL OR ebay_item_id='')
            AND status IN ('needs_variation_listing','manual_review','ready_to_list','active','prepared')
            ORDER BY 
                CASE 
                    WHEN status = 'ready_to_list' THEN 0
                    WHEN status = 'active' AND ebay_price > 0 THEN 1
                    WHEN status = 'prepared' THEN 2
                    WHEN status = 'needs_variation_listing' THEN 3
                    ELSE 4
                END,
                id LIMIT ?""", (limit,))]


def write_report(report, store):
    path = PROJECT_ROOT / 'data' / 'audit' / 'ready_listing_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    cards = []
    for row in report['items']:
        record = store.get(row['product_id'])
        st = (record.get('artifact') or {}).get('st') or {}
        cards.append('<article><h2>' + escape(st.get('title') or row['product_id']) + '</h2><p>'
                     + escape(row['status']) + '</p><p>' + escape(', '.join(row['blockers']))
                     + '</p><details><summary>İlan önizlemesi</summary><pre>' + escape(st.get('desc') or 'Tam içerik henüz hazırlanamadı')
                     + '</pre></details></article>')
    html = '<!doctype html><meta charset="utf-8"><title>Mondeora hazır ilan havuzu</title><style>body{font:16px sans-serif;max-width:1000px;margin:30px auto}article{border:1px solid #bbb;padding:15px;margin:15px 0}pre{white-space:pre-wrap}</style><h1>Hazır ilan: '
    html += str(report['ready_count']) + '/10</h1><p>Varyantlar ayrı ürün sayılmaz. Bloke veya süresi geçmiş ilan yayınlanmaz.</p>' + ''.join(cards)
    path.with_suffix('.html').write_text(html, encoding='utf-8')


def prepare(ali, ebay):
    config, store = settings(), store_default()
    report = prepare_pool(ali, ebay, pending_rows(), store, readiness=read_readiness(), target=config['target'],
                          limit=config['max_prepare_per_run'], ttl_seconds=config['ttl_hours'] * 3600,
                          max_seconds=config['max_prepare_seconds'])
    report['global_blockers'] = ready_plan.readiness_blockers(read_readiness())
    write_report(report, store)
    return {k: report[k] for k in ('status','target','ready_count','shortfall','content_prepared_count','blocked_count','global_blockers')}
