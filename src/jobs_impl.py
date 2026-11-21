"""Standalone job runner: one scheduled task = one command.

    "C:/Program Files/Python311/python.exe" -m src.jobs <job>      (run from the project root)
    "C:/Program Files/Python311/python.exe" -m src.jobs --list

Every job: single-instance file lock -> fail-closed live-write check -> self-healing wrapper ->
result JSON in data/jobs/last_<job>.json -> incidents into vector memory. Exit code 0 = ok/blocked/busy,
1 = failed. Write-capable engine jobs still honour AUTOMATION_LIVE_WRITES, SUPPLIER_AGREEMENT_CONFIRMED
and (for purchases) ALLOW_ORDER_PURCHASES + supervised approvals, exactly as inside the engine.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / 'data' / 'jobs'
STALE_LOCK_SECONDS = 3600


_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from src.automation.engine import AutamationEngine
        _ENGINE = AutamationEngine()
    return _ENGINE


def _checked(call):
    """AutamationEngine._run swallows exceptions into {'status': 'failed'}; re-raise so healing
    can classify them (message comes from the engine's already-sanitised exception)."""
    result = call()
    if isinstance(result, dict) and result.get('status') == 'failed':
        raise RuntimeError(f"{result.get('error')}: {str(getattr(_engine(), '_last_exc', ''))[:200]}")
    return result


def _enforce_readiness():
    """Same rule as main.py: live writes only when the readiness report says ready_for_live OR ready_for_supervised_trial."""
    from src.runtime import read_config, writes_allowed, enable_read_only
    if not writes_allowed(read_config()):
        return 'read_only'
    try:
        report = json.loads((ROOT / 'data/readiness_report.json').read_text(encoding='utf-8'))
        if report.get('ready_for_live'):
            return 'live'
        if report.get('ready_for_supervised_trial'):
            return 'supervised_trial'
    except (OSError, ValueError):
        pass
    enable_read_only()
    return 'read_only (readiness gate not passed)'


_READINESS_REFRESH_JOBS = {'listing_prepare', 'product_sync', 'listing_pipeline',
                           'publish_ready', 'new_variation_listing'}


def _refresh_listing_readiness(name):
    """Refresh stale/malformed evidence with GET-only checks, never auto-approve blockers."""
    if name not in _READINESS_REFRESH_JOBS:
        return
    from src.readiness import build_report, save_report
    from src.listing_quality.ready_plan import readiness_blockers
    invalid = {'readiness_report_missing', 'readiness_report_stale', 'readiness_report_from_future',
               'readiness_report_timestamp_invalid', 'readiness_checks_invalid', 'readiness_checks_missing'}

    def read_cached():
        try:
            return json.loads((ROOT / 'data/readiness_report.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None

    def needs_refresh(report):
        return (not isinstance(report, dict) or report.get('live_api_checks_performed') is not True
                or bool(invalid.intersection(readiness_blockers(report))))

    if not needs_refresh(read_cached()):
        return
    with JobLock('readiness_refresh'):
        # Another listing alias may have refreshed while this process waited.
        if needs_refresh(read_cached()):
            report = build_report(live=True)
            if needs_refresh(report):
                raise ValueError('Invalid refreshed readiness report')
            save_report(report)


def job_token_refresh():
    e = _engine()
    # The client's cached path only renews inside the last 2 minutes; renew early (< 30 min left)
    # so the watchdog threshold and this job agree and the token never sits near expiry.
    try:
        left = float(json.loads((ROOT / 'data/ebay_oauth_metadata.json').read_text())['expires_at']) - time.time()
    except (OSError, ValueError, KeyError):
        left = 0
    if left < 1800:
        res = e.ebay_client.refresh_access_token(force=True)
        if not (res is True or (isinstance(res, dict) and res.get('success'))):
            raise RuntimeError('eBay early token refresh not confirmed')
    return {'ebay': _checked(e.check_and_renew_ebay_token), 'aliexpress': _checked(e.refresh_aliexpress_token_complete)}


def job_watchdog():
    from src.intelligence.healing import watchdog
    return watchdog()


def job_orders_poll():
    return _checked(_engine().poll_order_statuses)


def job_orders_sync():
    return _checked(_engine().sync_ebay_orders_and_place_aliexpress_orders)


def job_inventory_sync():
    return _checked(_engine().sync_inventory)


def job_price_optimize():
    return _checked(_engine().analyze_competition_and_optimize_prices)


def job_product_sync():
    # Legacy product-sync also published; it must not bypass the prepared buffer.
    return job_listing_prepare()


def job_research():
    return _checked(_engine().research_products)


def job_memory_index():
    from src.intelligence.memory import get_memory
    m = get_memory()
    return {'indexed': m.index_project(), 'totals': m.stats()}


def job_diagnose():
    """Ask the reasoning model (if any key exists) to triage recent incidents using memory context."""
    from src.intelligence.memory import get_memory
    from src.intelligence.model_router import route
    mem = get_memory()
    recent = mem.search('failed error blocked incident', k=8, kind='incident', min_score=0.0)
    if not recent:
        return {'status': 'ok', 'incidents': 0}
    text = '\n'.join(r['text'] for r in recent)
    answer = route('diagnose_incident', 'Group these incidents by likely root cause and give the single next action for each:\n' + text)
    return {'status': 'ok', 'incidents': len(recent), 'model': (answer or {}).get('model'),
            'analysis': (answer or {}).get('text', 'no model key configured; rule-based healing only')}


def job_weekly_report():
    import sqlite3
    from contextlib import closing
    from src.intelligence.model_router import route
    with closing(sqlite3.connect(f'file:{(ROOT / "data/dropshipping.db").as_posix()}?mode=ro', uri=True)) as db:
        stats = {
            'products_by_status': dict(db.execute('select status,count(*) from products group by status').fetchall()),
            'orders': db.execute('select count(*) from order_lines').fetchone()[0],
            'sync_7d': dict(db.execute("select status,count(*) from sync_logs where started_at >= datetime('now','-7 day') group by status").fetchall()),
        }
    answer = route('weekly_report', 'Write a 6-line weekly status for the operator (Turkish) from: ' + json.dumps(stats))
    report = {'stats': stats, 'summary': (answer or {}).get('text')}
    (ROOT / 'data' / 'weekly_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return report


def _plan_target():
    """Today's listing target from config/daily_listing_plan.json (last entry if past the plan)."""
    plan = json.loads((ROOT / 'config/daily_listing_plan.json').read_text(encoding='utf-8'))['daily_listing_plan']
    today = time.strftime('%Y-%m-%d')
    rows = plan['schedule']
    return next((r['listings'] for r in rows if r['date'] == today), rows[-1]['listings'] if today > rows[-1]['date'] else 0)


def job_listing_pipeline():
    """Scheduled release consumes saved, fully gated plans only; never prepares during release."""
    return job_publish_ready()


def job_listing_prepare():
    """Read-only remote preparation; maintain a local target of ten real ready products."""
    from src.listing_quality import ready_workflow
    e = _engine()
    return ready_workflow.prepare(e.aliexpress_client, e.ebay_client)


def job_publish_ready():
    """One launch action; shared lock, stock/price preflight, daily cap and buyer readback."""
    from src.listing_quality import ready_workflow
    e = _engine()
    return ready_workflow.publish_ready(e.aliexpress_client, e.ebay_client)


def job_listing_buffer_status():
    from src.listing_quality import ready_workflow
    return ready_workflow.buffer_status()


def job_listing_standards():
    """Bounded GET-only catalog audit, coverage report and persistent review queue."""
    from src.api.ebay_client import eBayAPIClient
    from src.listing_quality.standards import run_cycle
    settings = json.loads((ROOT / 'config/listing_standards.json').read_text(encoding='utf-8'))
    max_items = int(settings['max_items_per_run'])
    max_seconds = float(settings['max_seconds_per_run'])
    if not 1 <= max_items <= 30 or not 1 <= max_seconds <= 90:
        raise ValueError('Invalid listing standards audit budget')
    return run_cycle(eBayAPIClient(), ROOT, max_items=max_items, max_seconds=max_seconds)


def job_listing_standards_resolve():
    """Bounded real-evidence resolver over the review queue: additive aspect PUTs
    (never overwrite/remove an existing value) and local category_overrides.json
    confirmation only (never an eBay category write). Safe dry run by default --
    remote_mutations only turns on when config explicitly opts in."""
    from src.api.aliexpress_client import AliExpressAPIClient
    from src.api.ebay_client import eBayAPIClient
    from src.listing_quality.standards_resolve import resolve_cycle
    settings = json.loads((ROOT / 'config/listing_standards.json').read_text(encoding='utf-8'))
    max_items = int(settings['max_items_per_run'])
    max_seconds = float(settings['max_seconds_per_run'])
    if not 1 <= max_items <= 30 or not 1 <= max_seconds <= 90:
        raise ValueError('Invalid listing standards resolve budget')
    remote_mutations = bool(settings.get('resolve_remote_mutations', False))
    return resolve_cycle(eBayAPIClient(), AliExpressAPIClient(), ROOT, max_items=max_items,
                         max_seconds=max_seconds, remote_mutations=remote_mutations)


def _live_only(name):
    from src.runtime import writes_allowed
    if not writes_allowed():
        return {'status': 'blocked', 'reason': f'{name} needs live-write switches + readiness gate'}
    return None


def job_sales_check():
    from sales_tracker import SalesTracker
    t = SalesTracker()
    sales = t.run_check_cycle() or []
    notify_errors = []
    for sale in sales:
        # Hata 8 pattern (per-item isolation): send_notification() indexes sale['order_id']/
        # ['title']/['sale_price']/['profit']/['buyer_username']/['sale_date'] with no .get()
        # fallback, and _mark_notified() opens its own sqlite3 connection with no try/except
        # (a concurrent "database is locked" from another cron job is a real risk here). Either
        # one failing for ONE sale must not stop notifications for the OTHER sales in this batch.
        try:
            t.send_notification(sale)
        except Exception as ex:
            notify_errors.append({'order_id': sale.get('order_id') if isinstance(sale, dict) else None,
                                   'error': f'{type(ex).__name__}: {ex}'[:200]})
            continue
    return {'status': 'ok', 'new_sales': len(sales), 'notify_errors': notify_errors}


def job_db_sync():
    from auto_database_sync import AutoDatabaseSync
    return {'status': 'ok', 'result': AutoDatabaseSync().sync_ebay_to_database()}


def job_customer_comm():
    blocked = _live_only('customer_comm')
    if blocked:
        return blocked
    from auto_customer_communication import AutoCustomerCommunication
    return {'status': 'ok', 'result': AutoCustomerCommunication().process_communications()}


def job_social_media():
    blocked = _live_only('social_media')
    if blocked:
        return blocked
    from auto_social_media import SocialMediaAutoPoster
    return {'status': 'ok', 'result': SocialMediaAutoPoster().run_automation()}


def job_db_backup(keep=14):
    import shutil
    import sqlite3
    from contextlib import closing
    out = ROOT / 'data' / 'backups'
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    done, errors = [], []
    for name in ('dropshipping.db', 'memory_vectors.db', 'learning_database.db'):
        src = ROOT / 'data' / name
        if not src.exists():
            continue
        dst = out / f'{name}.{stamp}'
        try:
            # Hata 35 pattern (per-item isolation): dropshipping.db is being written by most
            # other cron jobs at the same time db_backup runs, so sqlite3.OperationalError
            # ('database is locked') on ONE db's backup() is a real possibility - it must not
            # stop memory_vectors.db/learning_database.db (later in this tuple) from being
            # backed up this run.
            with closing(sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True)) as a, closing(sqlite3.connect(dst)) as b:
                a.backup(b)  # consistent online copy
            done.append(dst.name)
            for old in sorted(out.glob(f'{name}.*'))[:-keep]:
                old.unlink(missing_ok=True)
        except Exception as ex:
            dst.unlink(missing_ok=True)   # drop any partial/zero-byte backup file
            errors.append({'db': name, 'error': f'{type(ex).__name__}: {ex}'[:200]})
            continue
    return {'status': 'ok' if not errors else 'partial', 'backed_up': done, 'errors': errors, 'kept_per_db': keep}


def job_log_cleanup(days=30):
    cutoff = time.time() - days * 86400
    removed, errors = 0, []
    for pattern in ('logs/*.log.*', 'logs/*.json', 'data/jobs/*.lock'):
        for f in ROOT.glob(pattern):
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    # Hata 35 pattern (per-item isolation): missing_ok=True only swallows
                    # FileNotFoundError - a file still open/locked by a concurrent cron job
                    # (PermissionError on Windows) must not stop the rest of this sweep.
                    f.unlink(missing_ok=True); removed += 1
                except OSError as ex:
                    errors.append({'file': str(f), 'error': f'{type(ex).__name__}: {ex}'[:150]})
                    continue
    usage = ROOT / 'data/model_usage.jsonl'
    if usage.exists() and usage.stat().st_size > 5_000_000:
        lines = usage.read_text(encoding='utf-8').splitlines()[-5000:]
        usage.write_text('\n'.join(lines) + '\n', encoding='utf-8'); removed += 1
    return {'status': 'ok' if not errors else 'partial', 'removed': removed, 'errors': errors}


def job_daily_report():
    """One digest of every job's last result so a silent day is still visible."""
    rows, counts, errors = [], {}, []
    for f in sorted(JOBS_DIR.glob('last_*.json')):
        try:
            # Hata 35 pattern (per-item isolation): one job's last_<job>.json truncated
            # mid-write by a crash/kill during a concurrent run must not hide every OTHER
            # job's status behind one corrupt/incomplete file.
            d = json.loads(f.read_text(encoding='utf-8'))
            counts[d['status']] = counts.get(d['status'], 0) + 1
            rows.append(f"{d['job']}:{d['status']}@{d['at'][5:16]}")
        except (OSError, ValueError, KeyError) as ex:
            errors.append({'file': f.name, 'error': f'{type(ex).__name__}: {ex}'[:150]})
            continue
    from core.job_tracking import recent_runs
    return {'status': 'ok' if not errors else 'partial', 'counts': counts, 'jobs': rows,
            'errors': errors, 'tracked_runs': recent_runs(30) or []}


# ---------------------------------------------------------------------------
# Jobs that were previously called directly from cron scripts (outside the hub)
# or AliExpress client integrations that no job used yet. All go through the
# same lock / readiness / healing / tracking path now.
# ---------------------------------------------------------------------------

def job_tracking_sync():
    """AliExpress order tracking (aliexpress.ds.order.tracking.get) -> eBay shipping fulfillment."""
    blocked = _live_only('tracking_sync')
    if blocked:
        return blocked
    from auto_tracking_management import AutoTrackingManagement
    return {'status': 'ok', 'result': AutoTrackingManagement().process_pending_tracking()}


def job_order_fulfillment():
    """SAFE mode: paid eBay orders -> pending AliExpress order file + desktop notification (no payment)."""
    from auto_order_fulfillment import AutoOrderFulfillment
    return {'status': 'ok', 'result': AutoOrderFulfillment().process_pending_orders()}


def job_link_verify():
    """Read-only AliExpress<->eBay link verification -> data/link_verification_latest.json."""
    import subprocess
    proc = subprocess.run([sys.executable, str(ROOT / 'verify_aliexpress_links_readonly.py')],
                          capture_output=True, text=True, timeout=1500, cwd=str(ROOT),
                          stdin=subprocess.DEVNULL)
    report = {}
    try:
        report = json.loads((ROOT / 'data/link_verification_latest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    summary = report.get('summary') if isinstance(report, dict) else None
    return {'status': 'ok' if proc.returncode == 0 else 'failed', 'exit': proc.returncode,
            'summary': summary, 'error': None if proc.returncode == 0 else proc.stderr[-300:]}


def job_health_check():
    """Live read-only probes of every dependency -> health_checks table (+ system_health_check.py report)."""
    from core.job_tracking import record_health
    e = _engine()
    checks = {}

    def probe(name, fn):
        t0 = time.time()
        try:
            fn()
            ms = round((time.time() - t0) * 1000)
            record_health(name, True, ms)
            checks[name] = {'ok': True, 'ms': ms}
        except Exception as exc:  # noqa: BLE001
            ms = round((time.time() - t0) * 1000)
            record_health(name, False, ms, type(exc).__name__)
            checks[name] = {'ok': False, 'ms': ms, 'error': type(exc).__name__}

    probe('ebay_inventory_read', lambda: e.ebay_client.get_inventory_items(limit=1)
          if hasattr(e.ebay_client, 'get_inventory_items') else e.ebay_client._request('GET', '/sell/inventory/v1/inventory_item', params={'limit': 1}))
    probe('aliexpress_signed_read', e.aliexpress_client.check_token_validity)      # aliexpress.ds.category.get
    probe('database_write', lambda: record_health('self_test', True, 0))
    for meta, name in (('data/ebay_oauth_metadata.json', 'ebay_token_ttl'),
                       ('data/aliexpress_oauth_metadata.json', 'aliexpress_token_ttl')):
        try:
            d = json.loads((ROOT / meta).read_text(encoding='utf-8'))
            exp = d.get('expires_at') or d.get('access_token_expires_at') or 0
            if isinstance(exp, str):   # ISO timestamp variant used by the older refresh manager
                from datetime import datetime as _dt
                exp = _dt.fromisoformat(exp).timestamp()
            left = float(exp) - time.time()
            ok = left > 300
            record_health(name, ok, None, None if ok else f'{int(left)}s left')
            checks[name] = {'ok': ok, 'seconds_left': int(left)}
        except (OSError, ValueError, TypeError):
            checks[name] = {'ok': False, 'error': 'metadata_missing'}
    unhealthy = [k for k, v in checks.items() if not v.get('ok')]
    return {'status': 'ok' if not unhealthy else 'degraded', 'checks': checks, 'unhealthy': unhealthy}


def job_supplier_probe():
    """Exercise the otherwise-unused AliExpress read integrations and persist what the account can do.
    aliexpress.ds.member.benefit.get, aliexpress.ds.category.get, ds.product.specialinfo.get (one product)."""
    e = _engine()
    ali = e.aliexpress_client
    out = {'status': 'ok'}
    for key, fn in (('member_benefits', ali.get_member_benefits),
                    ('categories_root', lambda: len(ali.get_categories(language='de') or []))):
        try:
            out[key] = fn()
        except Exception as exc:  # noqa: BLE001
            out[key] = {'error': type(exc).__name__}
    from src.database.models import get_session, Product
    with get_session(e.engine) as session:
        p = session.query(Product).filter(Product.is_listed.is_(True)).order_by(Product.id).first()
        pid = p.aliexpress_product_id if p else None
    if pid:
        try:
            info = ali.get_product_special_info(pid, ('DE',))
            out['special_info_sample'] = {'product_id': pid,
                                          'qualifications': len(info.get('item_qualification_list', []))}
        except Exception as exc:  # noqa: BLE001
            out['special_info_sample'] = {'product_id': pid, 'error': type(exc).__name__}
    (ROOT / 'data' / 'supplier_capabilities.json').write_text(
        json.dumps(dict(out, at=time.strftime('%Y-%m-%d %H:%M:%S')), ensure_ascii=False, indent=1, default=str),
        encoding='utf-8')
    return out


def job_price_refresh():
    """Refresh products.aliexpress_price for listed products from AliExpress API (SKU fallback).
    Runs after freight_sync so shipping_cost is also fresh for margin calc."""
    from datetime import datetime
    from src.database.models import get_session, Product
    e = _engine()
    ali = e.aliexpress_client
    updated, skipped, errors = 0, {}, {}

    with get_session(e.engine) as session:
        products = session.query(Product).filter(
            Product.is_listed.is_(True)
        ).all()
        for p in products:
            if not p.aliexpress_product_id:
                skipped['no_aliexpress_id'] = skipped.get('no_aliexpress_id', 0) + 1
                continue
            if p.aliexpress_product_id.startswith(('MANUAL-', 'PREMIUM-')):
                skipped['fake_id'] = skipped.get('fake_id', 0) + 1
                continue
            try:
                d = ali.get_product_details(str(p.aliexpress_product_id))
                skus = d.get('skus', [])
                # Try top-level price first, then SKU min price as fallback
                price = d.get('target_sale_price') or d.get('sale_price') or d.get('min_price')
                if not price and skus:
                    sku_prices = [float(s.get('sale_price') or s.get('sku_price') or 0)
                                  for s in skus if s.get('sale_price') or s.get('sku_price')]
                    price = min(sku_prices) if sku_prices else None
                if price is None:
                    skipped['no_price'] = skipped.get('no_price', 0) + 1
                    continue
                new_price = float(price)
                if p.aliexpress_price != new_price:
                    p.aliexpress_price = new_price
                    p.last_synced = datetime.utcnow()
                    session.commit()
                    updated += 1
                else:
                    skipped['unchanged'] = skipped.get('unchanged', 0) + 1
            except Exception as exc:
                errors[type(exc).__name__] = errors.get(type(exc).__name__, 0) + 1
    return {'status': 'ok', 'updated': updated, 'skipped': skipped,
            'errors': errors, 'total': updated + sum(skipped.values()) + sum(errors.values())}


def job_new_variation_listing():
    """Compatibility alias: only release already prepared single/variation listings."""
    return job_publish_ready()


def job_listing_health():
    """Read-only daily health scan: diagnoses every blocked/pending product (plan_for dry run) and writes a
    Turkish, human-readable report to data/audit/listing_health_report.json. Never writes to eBay/AliExpress/DB.
    Replaces manual ad-hoc diagnostic scripts with one scheduled, reusable check."""
    import json
    from datetime import datetime, timezone
    e = _engine()
    from src.listing_quality import diagnostics
    report = diagnostics.scan_products(e.aliexpress_client, e.ebay_client)
    blocked = [r for r in report if r['result'] == 'blocked']
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanned': len(report),
           'blocked': len(blocked), 'ok': len(report) - len(blocked),
           'by_code': {c: sum(1 for r in blocked if r.get('code') == c) for c in {r.get('code') for r in blocked}},
           'items': report}
    path = ROOT / 'data' / 'audit' / 'listing_health_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': 'ok', 'scanned': out['scanned'], 'blocked': out['blocked'], 'ok': out['ok'],
            'by_code': out['by_code'], 'report': str(path)}


def job_listing_integrity_check():
    """Read-only ground-truth audit of EVERY real eBay listing (paginated directly from eBay -
    never the DB's is_listed=1 filter, which has been proven to drift/undercount). Never writes
    to eBay/AliExpress/DB. Catches, per listing:

    1. category_name_leaked_into_aspect: an aspect VALUE (most often Produktart) is literally
       the display name of a (wrong) eBay category - the exact, confirmed bug pattern from the
       2026-11 audit (a Grill-Abdeckhauben category assigned to a clothes storage bag, with
       Produktart="Grill-Abdeckhauben"). Checked against the listing's OWN current category name
       AND the category's own Produktart picklist (literal category-name strings never belong
       in a closed Produktart list, so a match there is instant corruption too).
    2. category_inconsistent_across_group: SKUs in the same variation-group listing point at
       different categoryIds (seen live after a partial category-change write).
    3. missing_required_aspect: a currently-required aspect for the live categoryId has no value.
    4. low_aspect_count: fewer than 10 real aspects (ebay-listing-aspect-enrichment target).

    Report: data/audit/listing_integrity_report.json. Status is 'critical' if any #1/#2 found
    (these indicate broken/corrupted live data), 'warning' for #3/#4 only, else 'ok'.
    """
    import json
    from datetime import datetime, timezone
    from collections import defaultdict
    e = _engine()
    ebay = e.ebay_client

    skus = []
    limit, offset = 100, 0
    while True:
        resp = ebay._request('GET', '/sell/inventory/v1/inventory_item', params={'limit': limit, 'offset': offset})
        items = resp.get('inventoryItems', [])
        skus.extend(i.get('sku') for i in items if i.get('sku'))
        total = resp.get('total', 0)
        if not items or offset + limit >= total:
            break
        offset += limit

    cat_name_cache, cat_aspects_cache = {}, {}

    def category_name(cid):
        if cid not in cat_name_cache:
            try:
                r = ebay._request('GET', f'/commerce/taxonomy/v1/category_tree/77/get_category_subtree',
                                   params={'category_id': cid})
                cat_name_cache[cid] = (r.get('categorySubtreeNode', {}).get('category', {}) or {}).get('categoryName')
            except Exception:
                cat_name_cache[cid] = None
        return cat_name_cache[cid]

    def category_aspect_meta(cid):
        if cid not in cat_aspects_cache:
            try:
                r = ebay._request('GET', '/commerce/taxonomy/v1/category_tree/77/get_item_aspects_for_category',
                                   params={'category_id': str(cid)})
                out = []
                for a in r.get('aspects', []):
                    c = a['aspectConstraint']
                    out.append({'name': a['localizedAspectName'], 'required': bool(c.get('aspectRequired')),
                                'mode': c.get('aspectMode'),
                                'values': [v['localizedValue'] for v in a.get('aspectValues', [])][:300]})
                cat_aspects_cache[cid] = out
            except Exception:
                cat_aspects_cache[cid] = []
        return cat_aspects_cache[cid]

    by_listing = defaultdict(list)
    errors = []
    for sku in skus:
        try:
            item = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
            aspects = (item.get('product') or {}).get('aspects') or {}
        except Exception as ex:
            errors.append({'sku': sku, 'stage': 'inventory_item', 'error': f'{type(ex).__name__}: {ex}'[:150]})
            continue
        try:
            offer_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
            offers = offer_resp.get('offers', [])
        except Exception as ex:
            errors.append({'sku': sku, 'stage': 'offer', 'error': f'{type(ex).__name__}: {ex}'[:150]})
            continue
        if not offers:
            continue
        o = offers[0]
        listing = o.get('listing') or {}
        if listing.get('listingStatus') not in ('ACTIVE', 'OUT_OF_STOCK'):
            continue
        by_listing[listing.get('listingId')].append({
            'sku': sku, 'category_id': o.get('categoryId'), 'aspects': aspects,
        })

    problems, listings_report = [], []
    for listing_id, rows in by_listing.items():
        cat_ids = {r['category_id'] for r in rows}
        listing_problems = []
        if len(cat_ids) > 1:
            listing_problems.append({'code': 'category_inconsistent_across_group', 'severity': 'critical',
                                      'detail': {'category_ids_seen': sorted(cat_ids)}})
        for cid in cat_ids:
            if not cid:
                continue
            real_name = category_name(cid)
            meta = category_aspect_meta(cid)
            produktart_meta = next((a for a in meta if a['name'] == 'Produktart'), None)
            required_names = {a['name'] for a in meta if a['required']}
            for r in rows:
                if r['category_id'] != cid:
                    continue
                for aname, avals in r['aspects'].items():
                    for av in (avals if isinstance(avals, list) else [avals]):
                        av_s = str(av)
                        if real_name and av_s == real_name:
                            listing_problems.append({'code': 'category_name_leaked_into_aspect', 'severity': 'critical',
                                                      'detail': {'sku': r['sku'], 'aspect': aname, 'value': av_s,
                                                                 'category_id': cid}})
                        elif produktart_meta and aname == 'Produktart' and produktart_meta['mode'] == 'SELECTION_ONLY' \
                                and produktart_meta['values'] and av_s not in produktart_meta['values']:
                            listing_problems.append({'code': 'produktart_not_in_category_picklist', 'severity': 'critical',
                                                      'detail': {'sku': r['sku'], 'value': av_s, 'category_id': cid}})
                missing = sorted(required_names - set(r['aspects'].keys()))
                if missing:
                    listing_problems.append({'code': 'missing_required_aspect', 'severity': 'warning',
                                              'detail': {'sku': r['sku'], 'missing': missing}})
                if len(r['aspects']) < 10:
                    listing_problems.append({'code': 'low_aspect_count', 'severity': 'warning',
                                              'detail': {'sku': r['sku'], 'aspect_count': len(r['aspects'])}})
        if listing_problems:
            problems.extend({**p, 'listing_id': listing_id} for p in listing_problems)
        listings_report.append({'listing_id': listing_id, 'sku_count': len(rows),
                                 'category_ids': sorted(cat_ids), 'problem_count': len(listing_problems)})

    critical = [p for p in problems if p['severity'] == 'critical']
    status = 'critical' if critical else ('warning' if problems else 'ok')
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'listings_scanned': len(by_listing),
           'skus_scanned': len(skus), 'problem_count': len(problems), 'critical_count': len(critical),
           'problems': problems, 'listings': listings_report, 'fetch_errors': errors}
    path = ROOT / 'data' / 'audit' / 'listing_integrity_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': status, 'listings_scanned': out['listings_scanned'], 'skus_scanned': out['skus_scanned'],
            'problem_count': out['problem_count'], 'critical_count': out['critical_count'],
            'by_code': {c: sum(1 for p in problems if p['code'] == c) for c in {p['code'] for p in problems}},
            'report': str(path)}


def job_rank_audit():
    """Read-only weekly 'will this rank #1' scan of every LIVE listing: real score (0-100) from
    rank_audit.audit_listing() (title, category confidence, required aspects, gallery images,
    description quality, price vs real eBay.de market median, Promoted Listings status). Writes
    data/audit/rank_audit_report.json. Never writes to eBay/AliExpress/DB - a diagnosis, not a fix."""
    import json
    from datetime import datetime, timezone
    from src.database.models import Product, get_session
    from src.listing_quality import rank_audit
    e = _engine()
    items, errors = [], []
    traffic = rank_audit.real_traffic(e.ebay_client)
    with get_session(e.engine) as session:
        rows = session.query(Product).filter_by(is_listed=True).all()
        for p in rows:
            row = {'title': p.title, 'category_id': p.category_id, 'ebay_price': p.ebay_price,
                   'aliexpress_price': p.aliexpress_price, 'shipping_cost': p.shipping_cost,
                   'description': p.description, 'ebay_item_id': p.ebay_item_id}
            try:
                result = rank_audit.audit_listing(e.aliexpress_client, e.ebay_client, row, p.aliexpress_product_id, traffic=traffic)
                items.append({'id': p.id, 'aliexpress_product_id': p.aliexpress_product_id,
                              'title': p.title, **result})
            except Exception as ex:
                errors.append({'id': p.id, 'error': f'{type(ex).__name__}: {ex}'[:200]})
    scored = [i for i in items if i.get('score') is not None]
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanned': len(items), 'errors': errors,
           'average_score': round(sum(i['score'] for i in scored) / len(scored), 1) if scored else None,
           'below_80': [{'id': i['id'], 'title': i['title'][:50], 'score': i['score'], 'gaps': i['gaps']}
                        for i in scored if i['score'] < 80],
           'items': items}
    path = ROOT / 'data' / 'audit' / 'rank_audit_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': 'ok', 'scanned': out['scanned'], 'average_score': out['average_score'],
            'below_80_count': len(out['below_80']), 'errors': len(errors), 'report': str(path)}


def job_image_reupload():
    """Audit live eBay listings via Inventory API and detect those with <3 photos. Read-only report
    generation: data/audit/image_reupload_report.json. Never auto-uploads - operator reviews and runs
    a separate write flow if needed."""
    import sqlite3
    from datetime import datetime, timezone
    from contextlib import closing
    from urllib.parse import quote
    e = _engine()
    ebay = e.ebay_client
    candidates, errors = [], []
    with closing(sqlite3.connect(f'file:{(ROOT / "data/dropshipping.db").as_posix()}?mode=ro', uri=True)) as db:
        # Hata 39: this used to guess a stale 'AUTO-PET-{ali_id}' SKU pattern that no
        # current listing actually uses (real SKUs are 'AE-{pid}-{sku_id}', or 'VAR-'/
        # legacy prefixes for older listings), so it 404'd on every is_listed=1 product
        # every run. The one source of truth for a product's real, currently-registered
        # SKU(s) is product_variants (written by publish/ready_workflow) - use that, and
        # skip (don't guess) products with no variant rows recorded yet.
        rows = db.execute('''SELECT p.id, pv.sku, p.ebay_item_id, p.title
                              FROM products p JOIN product_variants pv ON p.id = pv.product_id
                              WHERE p.is_listed = 1''').fetchall()
        skipped_no_variants = db.execute('''SELECT COUNT(*) FROM products p
            WHERE p.is_listed = 1
              AND p.id NOT IN (SELECT product_id FROM product_variants)''').fetchone()[0]
    seen_products = set()
    for pid, ebay_sku, ebay_id, title in rows:
        if not ebay_sku or pid in seen_products:
            continue
        seen_products.add(pid)
        try:
            path = f'/sell/inventory/v1/inventory_item/{quote(ebay_sku, safe="")}'
            resp = ebay._request('GET', path)
            product_obj = resp.get('product', {})
            image_urls = product_obj.get('imageUrls') or []
            photo_count = len(image_urls)
            if photo_count < 3:
                candidates.append({'product_id': pid, 'ebay_sku': ebay_sku, 'ebay_item_id': ebay_id,
                                   'title': (title or '')[:60], 'current_photos': photo_count,
                                   'image_urls': image_urls})
        except Exception as ex:
            errors.append({'product_id': pid, 'ebay_sku': ebay_sku,
                           'error': f'{type(ex).__name__}: {ex}'[:200]})
            continue
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanned': len(seen_products),
           'skipped_no_variants_recorded': skipped_no_variants,
           'needs_reupload': candidates, 'errors': errors}
    path = ROOT / 'data' / 'audit' / 'image_reupload_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': 'ok', 'scanned': len(seen_products), 'needs_reupload_count': len(candidates),
            'errors_count': len(errors), 'skipped_no_variants_recorded': skipped_no_variants,
            'report': str(path)}


def job_title_quality_audit():
    """Scan live eBay listings for title quality issues: repeated words, non-German text mixing.
    Read-only report: data/audit/title_quality_report.json."""
    import sqlite3, re
    from datetime import datetime, timezone
    from contextlib import closing
    issues = []
    with closing(sqlite3.connect(f'file:{(ROOT / "data/dropshipping.db").as_posix()}?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT id, sku_id, ebay_item_id, title FROM products WHERE is_listed=1').fetchall()
    for pid, sku, ebay_id, title in rows:
        if not title:
            continue
        problems = []
        # Check for repeated words (case-insensitive)
        words = re.findall(r'\b\w+\b', title.lower())
        word_counts = {}
        for w in words:
            if len(w) > 3:  # skip short words like "für", "mit"
                word_counts[w] = word_counts.get(w, 0) + 1
        repeated = [f'{w}({c}x)' for w, c in word_counts.items() if c > 1]
        if repeated:
            problems.append(f'repeated_words:{",".join(repeated)}')
        # Check for English/Turkish keywords (common non-German words)
        foreign_keywords = ['for', 'with', 'the', 'and', 'to', 'in', 'price', 'new', 'free', 'shipping',
                             've', 'için', 'ile', 'yeni', 'ücretsiz', 'fiyat']
        found_foreign = [w for w in words if w in foreign_keywords]
        if found_foreign:
            problems.append(f'foreign_words:{",".join(set(found_foreign))}')
        if problems:
            issues.append({'product_id': pid, 'sku_id': sku, 'ebay_item_id': ebay_id,
                           'title': title, 'problems': problems})
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanned': len(rows),
           'issues_found': issues}
    path = ROOT / 'data' / 'audit' / 'title_quality_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': 'ok', 'scanned': len(rows), 'issues_count': len(issues), 'report': str(path)}


def job_price_competitiveness():
    """Compare our live eBay.de listing prices with Browse API competition medians (same keyword search).
    Read-only report: data/audit/price_competitiveness_report.json."""
    import sqlite3, statistics
    from datetime import datetime, timezone
    from contextlib import closing
    e = _engine()
    ebay = e.ebay_client
    comparisons, errors = [], []
    with closing(sqlite3.connect(f'file:{(ROOT / "data/dropshipping.db").as_posix()}?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT id, sku_id, ebay_item_id, title, ebay_price FROM products WHERE is_listed=1 AND ebay_price IS NOT NULL').fetchall()
    for pid, sku, ebay_id, title, our_price in rows[:20]:  # limit to 20 to avoid rate-limits in first run
        if not title:
            continue
        try:
            # Extract main keyword (first 3-4 words of title)
            search_keywords = ' '.join(title.split()[:4])
            # eBay Browse API: search
            url = f'https://api.ebay.com/buy/browse/v1/item_summary/search'
            params = {'q': search_keywords, 'limit': 20, 'category_ids': '1281'}  # 1281 = Haustierbedarf
            headers = {'Authorization': f'Bearer {ebay.access_token}',
                       'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE', 'Accept': 'application/json'}
            resp = ebay.session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get('itemSummaries') or []
            competitor_prices = []
            for item in items:
                price_obj = item.get('price', {})
                val = price_obj.get('value')
                currency = price_obj.get('currency')
                if val and currency == 'EUR':
                    competitor_prices.append(float(val))
            if len(competitor_prices) >= 3:
                median = statistics.median(competitor_prices)
                diff_pct = ((our_price - median) / median * 100) if median > 0 else 0
                comparisons.append({'product_id': pid, 'sku_id': sku, 'ebay_item_id': ebay_id,
                                    'title': (title or '')[:60], 'our_price': our_price,
                                    'market_median': round(median, 2), 'diff_percent': round(diff_pct, 1),
                                    'sample_size': len(competitor_prices)})
        except Exception as ex:
            errors.append({'product_id': pid, 'sku_id': sku, 'error': f'{type(ex).__name__}: {ex}'[:200]})
            continue
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'scanned': len(rows),
           'comparisons': comparisons, 'errors': errors}
    path = ROOT / 'data' / 'audit' / 'price_competitiveness_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'status': 'ok', 'scanned': len(rows), 'compared_count': len(comparisons),
            'errors_count': len(errors), 'report': str(path)}


def job_blue_ocean():
    """Daily real low-competition/high-demand product discovery. Scans DEFAULT_KEYWORDS niche
    via real AliExpress sales-sorted search + real eBay Browse API competition counts, verifies
    every passing candidate with the same real gates as the rest of the pipeline (stock, price,
    shipping, risk, price-vs-market), and seeds verified candidates into the products table as
    needs_variation_listing so mondeora-listing-pipeline/new-variation-listing publish them the
    same morning. Writes data/audit/blue_ocean_report.json. Never publishes directly."""
    import json
    from datetime import datetime, timezone
    from src.database.models import Product, get_session
    from src.listing_quality import blue_ocean
    e = _engine()
    # top_n_for_competition=10 (was 5): wider real pool per keyword so a realistic pass/fail rate
    # at verify_and_seed (today: ~50-70% of discovery-filter passes clear the strict real gates)
    # still reaches the user's target of ~10 real seeded products/day, without lowering any gate.
    scanned = blue_ocean.find_candidates(e.aliexpress_client, e.ebay_client, top_n_for_competition=10)
    passing = [c for c in scanned if c.get('passes_blue_ocean_filter')]
    seeded, skipped = [], []
    TARGET_SEEDED = 10
    # Hata 43: this call never loaded config/risk_ack.json, so a user-approved per-product
    # review acknowledgement (e.g. a storage box falsely flagged 'cosmetics_food_supplement')
    # was silently ignored every run - the ack file existed but had no real effect here.
    try:
        risk_ack_pids = frozenset(json.loads((ROOT / 'config/risk_ack.json').read_text(encoding='utf-8'))
                                   .get('acknowledged', {}).keys())
    except (OSError, ValueError):
        risk_ack_pids = frozenset()
    with get_session(e.engine) as session:
        for cand in passing:   # try every real discovery-filter pass, not just a fixed first-N,
                                # so a real rejection (category confidence, risk, price-vs-market)
                                # doesn't cost a slot - keep trying until TARGET_SEEDED or exhausted.
            if len(seeded) >= TARGET_SEEDED:
                break
            # Hata 8 pattern (per-item isolation): one candidate blowing up (bad API payload,
            # unexpected KeyError in a field, a transient DB error on commit, ...) must not stop
            # the other 9 candidates in this run from being evaluated/seeded.
            try:
                result = blue_ocean.verify_and_seed(e.aliexpress_client, e.ebay_client, cand, session, Product,
                                                     risk_ack_pids=risk_ack_pids)
            except ValueError as ex:
                session.rollback()
                skipped.append({'product_id': cand.get('product_id'), 'seeded': False,
                                 'reason': f'{type(ex).__name__}: {ex}'[:200]})
                continue
            except Exception as ex:
                # Not a known data-validation error (ValueError) - still isolate per-candidate
                # rather than losing the whole run, but keep the full exception type visible so
                # a systemic issue (e.g. DB connectivity) is easy to tell apart from a one-off bad row.
                session.rollback()
                skipped.append({'product_id': cand.get('product_id'), 'seeded': False,
                                 'reason': f'unexpected_{type(ex).__name__}: {ex}'[:200]})
                continue
            (seeded if result['seeded'] else skipped).append(result)
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'keywords_scanned': len(blue_ocean.DEFAULT_KEYWORDS),
           'rows_scanned': len(scanned), 'passing_filter': len(passing), 'target_seeded': TARGET_SEEDED,
           'seeded': seeded, 'skipped': skipped}
    path = ROOT / 'data' / 'audit' / 'blue_ocean_report.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    return {'status': 'ok', 'rows_scanned': len(scanned), 'passing_filter': len(passing),
            'seeded_count': len(seeded), 'seeded_ids': [s['product_id'] for s in seeded], 'report': str(path)}


def job_variation_sync():
    """Per-variant eBay price + stock for variation listings (legacy inventory_sync/price_optimize skip them)."""
    e = _engine()
    from src.listing_quality import sync
    return sync.run(e.aliexpress_client, e.ebay_client)


def job_ad_bid_optimize():
    """Promoted Listings bid lifecycle: new listings get a BOOST_BID visibility window (set by
    publish.add_ad at listing time), then this job steps them down to STEADY_BID once BOOST_DAYS
    has passed. Idempotent - only acts on boosts this module itself recorded, never guesses a bid."""
    e = _engine()
    from src.listing_quality import ads
    return ads.decay_due_boosts(e.ebay_client)


def job_monitoring():
    """Real-time monitoring of critical metrics with Telegram alerts."""
    from src.monitoring import collect_metrics
    from src.alerting import send_alerts_from_monitoring
    
    # Collect metrics
    monitoring_result = collect_metrics()
    
    # Send alerts if any critical/warning conditions detected
    alert_result = {}
    if monitoring_result.get('alerts'):
        alert_result = send_alerts_from_monitoring()
    
    return {
        'status': monitoring_result.get('status', 'unknown'),
        'alerts_count': len(monitoring_result.get('alerts', [])),
        'alerts_sent': alert_result.get('alerts_sent', 0),
        'metrics_summary': {
            'tokens': monitoring_result['metrics'].get('token_status', {}),
            'sales_7d': monitoring_result['metrics'].get('sales_status', {}).get('sales_7d', 0),
            'visibility_pct': monitoring_result['metrics'].get('listing_visibility', {}).get('visibility_pct', 0),
            'failed_jobs': len(monitoring_result['metrics'].get('job_failures', {}).get('failed_jobs', {}))
        }
    }


def job_resolve_blockers():
    """Resolve readiness and listing blockers automatically."""
    import subprocess
    script = ROOT / 'scripts/resolve_all_blockers.py'
    try:
        result = subprocess.run([sys.executable, str(script)], 
                              capture_output=True, text=True, timeout=300, cwd=ROOT)
        summary = json.loads((ROOT / 'data/audit/blocker_resolution_summary.json').read_text())
        return {
            "fixes_successful": summary['fixes_successful'],
            "fixes_failed": summary['fixes_failed'],
            "remaining_blockers": len(summary['remaining_blockers']),
            "supervised_trial_ready": summary.get('ready_for_supervised_trial', False)
        }
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}


def job_freight_sync():
    """Refresh products.shipping_cost for listed products from the supplier (aliexpress.ds.freight.query via
    the engine's own details/freight path). DB write only - eBay is NOT touched; price re-evaluation happens in
    price_optimize which reads shipping_cost."""
    from datetime import datetime
    from src.database.models import get_session, Product
    e = _engine()
    ali = e.aliexpress_client
    updated, skipped, errors = 0, {}, {}

    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1

    with get_session(e.engine) as session:
        products = session.query(Product).filter(Product.is_listed.is_(True)).all()
        for p in products:
            if not p.aliexpress_product_id:
                skip('no_supplier_id'); continue
            try:
                data = ali.get_product_details(p.aliexpress_product_id)   # aliexpress.ds.product.get
                skus = [s for s in (data.get('skus') or []) if s.get('sku_id')]
                # DB sku_id is usually the eBay SKU (AUTO-PET-...), so resolve the AliExpress SKU explicitly:
                match = [s for s in skus if str(s.get('sku_id')) == str(p.sku_id)]
                if match:
                    sku = match[0]
                elif len(skus) == 1:
                    sku = skus[0]
                elif skus and len({str(s.get('sale_price')) for s in skus}) == 1:
                    sku = min(skus, key=lambda s: str(s['sku_id']))        # same price -> freight identical
                else:
                    skip('ambiguous_sku'); continue
                quote = ali.get_shipping_quote(p.aliexpress_product_id, sku['sku_id'])   # aliexpress.ds.freight.query
                freight = float(quote['cost'])
                if p.shipping_cost is None or abs(freight - float(p.shipping_cost)) > 0.009:
                    p.shipping_cost = freight
                    p.last_synced = datetime.utcnow()
                    session.commit()
                    updated += 1
                else:
                    skip('unchanged')
            except Exception as exc:  # noqa: BLE001
                errors[type(exc).__name__] = errors.get(type(exc).__name__, 0) + 1
    return {'status': 'ok', 'updated': updated, 'skipped': skipped, 'errors': errors, 'total': len(products)}


# name: (function, idempotent, needs_engine_writes)
JOBS = {
    'token_refresh':   (job_token_refresh, True),
    'watchdog':        (job_watchdog, True),
    'orders_poll':     (job_orders_poll, True),
    'orders_sync':     (job_orders_sync, False),   # may create supplier orders -> never auto-retried
    'inventory_sync':  (job_inventory_sync, False),
    'price_optimize':  (job_price_optimize, False),
    'product_sync':    (job_product_sync, False),
    'research':        (job_research, True),
    'memory_index':    (job_memory_index, True),
    'diagnose':        (job_diagnose, True),
    'weekly_report':   (job_weekly_report, True),
    'listing_pipeline': (job_listing_pipeline, False),
    'listing_prepare': (job_listing_prepare, True),
    'publish_ready': (job_publish_ready, False),
    'listing_buffer_status': (job_listing_buffer_status, True),
    'sales_check':     (job_sales_check, False),
    'db_sync':         (job_db_sync, True),
    'customer_comm':   (job_customer_comm, False),
    'social_media':    (job_social_media, False),
    'db_backup':       (job_db_backup, True),
    'log_cleanup':     (job_log_cleanup, True),
    'daily_report':    (job_daily_report, True),
    # --- integrated 2026-11-10: previously outside the hub / unused AliExpress integrations ---
    'tracking_sync':     (job_tracking_sync, False),    # ali tracking.get -> eBay shipping fulfillment
    'order_fulfillment': (job_order_fulfillment, False),  # SAFE mode pending-order notifications
    'link_verify':       (job_link_verify, True),
    'health_check':      (job_health_check, True),       # ebay + ali signed read + token TTL -> health_checks
    'supplier_probe':    (job_supplier_probe, True),     # member.benefit, category.get, specialinfo.get
    'new_variation_listing': (job_new_variation_listing, False),  # multi-variant new products -> ONE variation listing
    'listing_health':    (job_listing_health, True),      # read-only diagnosis report, never writes to eBay/AliExpress/DB
    'listing_integrity_check': (job_listing_integrity_check, True),  # ground-truth audit: category-leak, group-consistency, aspect gaps
    'listing_standards': (job_listing_standards, True),  # bounded GET-only recurring audit + durable review queue
    'listing_standards_resolve': (job_listing_standards_resolve, False),  # real-evidence aspect/category resolver; may PUT -> non-idempotent
    'variation_sync':    (job_variation_sync, True),     # per-variant price+stock for variation listings
    'freight_sync':      (job_freight_sync, True),       # ds.freight.query -> products.shipping_cost
    'price_refresh':     (job_price_refresh, True),      # ds.product.get -> products.aliexpress_price (SKU fallback)
    'ad_bid_optimize':   (job_ad_bid_optimize, True),     # Promoted Listings: decay BOOST_BID->STEADY_BID after BOOST_DAYS
    'rank_audit':        (job_rank_audit, True),          # read-only weekly rank-readiness score per live listing
    'blue_ocean':        (job_blue_ocean, True),           # daily low-competition/high-demand discovery -> seeds listing queue
    'monitoring':        (job_monitoring, True),            # real-time critical metrics monitoring with Telegram alerts
    'resolve_blockers':  (job_resolve_blockers, True),     # auto-resolve readiness and listing blockers
    # --- 2026-11-13: new quality/audit jobs ---
    'image_reupload':       (job_image_reupload, True),       # daily audit: <3 photos detection -> report
    'title_quality_audit':  (job_title_quality_audit, True),  # weekly audit: repeated words, foreign language -> report
    'price_competitiveness': (job_price_competitiveness, True), # weekly: Browse API median price comparison -> report
}


class JobLock:
    def __init__(self, name):
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = JOBS_DIR / f'{name}.lock'

    def __enter__(self):
        for _ in range(2):
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                if time.time() - self.path.stat().st_mtime > STALE_LOCK_SECONDS:
                    self.path.unlink(missing_ok=True)
                    continue
                raise BlockingIOError('busy')
        raise BlockingIOError('busy')

    def __exit__(self, *a):
        os.close(self.fd)
        self.path.unlink(missing_ok=True)


SEMANTIC_LISTING_JOBS = {'listing_standards', 'listing_prepare', 'listing_pipeline',
                         'publish_ready', 'product_sync', 'new_variation_listing'}
SEMANTIC_EXIT = {'success': 0, 'failed': 1, 'blocked': 2, 'deferred': 3}
PROGRESS_FIELDS = ('processed_this_run', 'processed_count', 'verified_count', 'remaining_count',
                   'catalog_total', 'fetch_error_count', 'budget_stop_count', 'removed_count',
                   'unresolved_count', 'ready_count', 'shortfall', 'published_count')


def _listing_outcome(name, status, result):
    """Explicit scheduler contract; never equate a zero transport exit with approval."""
    result = result if isinstance(result, dict) else {}
    outcome = 'failed'
    if status == 'busy':
        outcome = 'deferred'
    elif status == 'failed' or result.get('fetch_error_count', 0):
        outcome = 'failed'
    elif status in ('blocked', 'needs_reconciliation', 'publication_needs_reconciliation') or result.get('blockers'):
        outcome = 'blocked'
    elif name == 'listing_standards':
        if result.get('complete') is False and result.get('fetch_error_count') == 0:
            outcome = 'deferred'
        elif result.get('complete') is True and result.get('fetch_error_count') == 0:
            outcome = 'success' if status == 'verified' and not result.get('unresolved_count') else 'blocked'
    elif status in ('shortfall', 'partial') or result.get('shortfall'):
        outcome = 'deferred'
    elif status == 'ok':
        outcome = 'success'
    return {'version': 1, 'job': name, 'status': outcome,
            'progress': {key: result[key] for key in PROGRESS_FIELDS
                         if type(result.get(key)) is int and result[key] >= 0}}


def run(name, alert_only=False, *, semantic_outcome=False):
    if name not in JOBS:
        raise SystemExit(f'unknown job {name!r}; known: {", ".join(JOBS)}')
    fn, idempotent = JOBS[name]
    started = time.time()
    tracker = None
    try:
        with JobLock(name):
            try:
                _refresh_listing_readiness(name)
            except Exception as exc:
                from src.runtime import enable_read_only
                enable_read_only()
                mode, status = 'read_only (readiness refresh failed)', 'blocked'
                result = {'status': status, 'blockers': ['readiness_refresh_failed'],
                          'error_type': type(exc).__name__, 'published_count': 0}
            else:
                mode = _enforce_readiness()
                from src.intelligence.healing import heal
                from core.job_tracking import TrackedJob
                tracker = TrackedJob(name, mode).__enter__()
                try:
                    result = heal(name, fn, idempotent=idempotent)
                    status = (result.get('status') if isinstance(result, dict) else None) or 'ok'
                except Exception as exc:  # noqa: BLE001
                    result, status = {'error': type(exc).__name__}, 'failed'
                    try:
                        from src.intelligence.healing import similar_past_incidents
                        result['similar_past'] = [r['text'][:160] for r in similar_past_incidents(f'{name} {type(exc).__name__} {exc}')]
                    except Exception:
                        pass
    except BlockingIOError:
        mode, result, status = '-', {}, 'busy'
    if tracker is not None:
        tracker.finish(status, result)
    out = {'job': name, 'status': status, 'mode': mode, 'seconds': round(time.time() - started, 2),
           'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'result': result}
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / f'last_{name}.json').write_text(json.dumps(out, default=str, ensure_ascii=False, indent=1), encoding='utf-8')
    if not alert_only:
        print(json.dumps(out, default=str, ensure_ascii=False)[:3000])
    else:  # cron/no-agent mode: silent unless something needs a human
        problems = []
        if status == 'failed':
            problems.append(f"{name} FAILED ({result.get('error')}); similar past: {result.get('similar_past')}")
        if name == 'watchdog' and isinstance(result, dict):
            acts = result.get('actions', [])
            fixed = {'ebay_token_expiring': 'ebay_refresh=ok', 'aliexpress_token_expiring': 'ali_refresh=ok'}
            bad = [i for i in result.get('issues', []) if i != 'sync_stale_over_6h' and fixed.get(i) not in acts] +                   [a for a in acts if a.endswith('=failed')]
            if bad:
                problems.append('watchdog: ' + ', '.join(bad))
        if name in ('listing_pipeline', 'new_variation_listing', 'publish_ready') and isinstance(result, dict):
            problems.append(f"listing: yayinlanan={result.get('published_count', 0)} hazir={result.get('ready_count', 0)}/10 "
                            f"engeller={result.get('blockers', [])}")
        if name in ('listing_prepare', 'product_sync') and isinstance(result, dict) and result.get('shortfall'):
            problems.append(f"hazir_havuz: {result.get('ready_count', 0)}/10; eksik={result['shortfall']}; "
                            f"rapor=data/audit/ready_listing_report.json")
        if name == 'listing_health' and isinstance(result, dict) and result.get('blocked'):
            problems.append(f"listing_health: {result['blocked']} \u00fcr\u00fcn blokl\u0131 ({result.get('by_code')}) "
                            f"-> {result.get('report')}")
        if name == 'listing_integrity_check' and isinstance(result, dict) and result.get('problem_count'):
            problems.append(f"listing_integrity: {result.get('critical_count',0)} KRITIK / "
                            f"{result.get('problem_count',0)} toplam sorun ({result.get('by_code')}) "
                            f"-> {result.get('report')}")
        if name == 'listing_standards' and isinstance(result, dict):
            # Notify on semantic result changes, not every timestamp/checkpoint tick.
            import hashlib
            semantic = {k: result.get(k) for k in ('status', 'complete', 'open_reviews', 'fetch_error_count')}
            digest = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
            notice = JOBS_DIR / 'listing_standards_notice.json'
            try:
                previous = json.loads(notice.read_text(encoding='utf-8')).get('digest')
            except (OSError, ValueError, AttributeError):
                previous = None
            if previous != digest:
                temporary = notice.with_suffix('.json.tmp')
                temporary.write_text(json.dumps({'digest': digest}), encoding='utf-8')
                temporary.replace(notice)
                problems.append('listing_standards: ' + json.dumps(semantic, ensure_ascii=False)
                                + ' -> data/audit/listing_standards_report.json')
        if name == 'daily_report' and status == 'ok':
            problems.append(json.dumps(result, ensure_ascii=False)[:1200])
        if status == 'ok' and (name == 'weekly_report' or (name == 'diagnose' and result.get('model'))):
            problems.append(json.dumps(result, ensure_ascii=False, default=str)[:1500])
        if problems:
            print('Mondeora: ' + ' | '.join(problems))
    if semantic_outcome and name in SEMANTIC_LISTING_JOBS:
        outcome = _listing_outcome(name, status, result)
        print('MONDEORA_JOB_OUTCOME ' + json.dumps(outcome, sort_keys=True))
        return SEMANTIC_EXIT[outcome['status']]
    return 1 if status == 'failed' else 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if sys.version_info[:2] != (3, 11):
        print('Python 3.11 gerekli.', file=sys.stderr); return 2
    os.chdir(ROOT); sys.path.insert(0, str(ROOT))
    if not argv or argv[0] in ('--list', '-l'):
        print('\n'.join(JOBS)); return 0
    alert_only = '--alert-only' in argv
    return run(argv[0], alert_only, semantic_outcome='--semantic-outcome' in argv)


if __name__ == '__main__':
    raise SystemExit(main())
