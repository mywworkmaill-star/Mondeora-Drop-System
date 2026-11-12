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
    """Same rule as main.py: live writes only when the readiness report says ready_for_live."""
    from src.runtime import read_config, writes_allowed, enable_read_only
    if not writes_allowed(read_config()):
        return 'read_only'
    try:
        report = json.loads((ROOT / 'data/readiness_report.json').read_text(encoding='utf-8'))
        if report.get('ready_for_live'):
            return 'live'
    except (OSError, ValueError):
        pass
    enable_read_only()
    return 'read_only (readiness gate not passed)'


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
    return _checked(_engine().sync_top_products_from_aliexpress)


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
    """Daily listing: publish only VETTED products (engine enforces vetting,
    supplier stock/SKU identity, EUR cost ceiling, fee-aware price). Reports why nothing was listed.
    NOTE: research_products() calls enable_read_only() internally which blocks all writes.
    Research runs as a SEPARATE job (job_research at 02:00). Do NOT call it here."""
    e = _engine()
    target = _plan_target()
    # Load last research result for reporting (read-only, no API call)
    research_summary = {}
    try:
        import json as _json
        _rp = ROOT / 'data' / 'product_research.json'
        if _rp.exists():
            _rd = _json.loads(_rp.read_text(encoding='utf-8'))
            research_summary = {k: _rd.get(k) for k in ('status', 'candidate_count', 'new_eligible_count') if k in _rd}
    except Exception:
        pass
    publish = _checked(e.sync_top_products_from_aliexpress)
    from src.database.models import get_session, Product
    with get_session(e.engine) as session:
        total = session.query(Product).count()
        listed = session.query(Product).filter(Product.is_listed.is_(True)).count()
        unvetted = session.query(Product).filter(Product.fulfillment_verified.is_(False),
                                                 Product.status.in_(['unverified', 'AUTO_SYNCED'])).count()
    why = []
    if publish.get('status') == 'blocked':
        why.append('live_writes_or_readiness_gate')
    if unvetted and not listed:
        why.append(f'{unvetted}_products_not_vetted')
    return {'status': publish.get('status', 'ok'), 'plan_target_today': target, 'db_total': total,
            'listed_total': listed, 'unvetted': unvetted, 'why_not_listed': why,
            'research': research_summary,
            'publish': {k: publish.get(k) for k in ('status', 'reason', 'processed', 'total', 'published') if k in publish}}


def _live_only(name):
    from src.runtime import writes_allowed
    if not writes_allowed():
        return {'status': 'blocked', 'reason': f'{name} needs live-write switches + readiness gate'}
    return None


def job_sales_check():
    from sales_tracker import SalesTracker
    t = SalesTracker()
    sales = t.run_check_cycle() or []
    for sale in sales:
        t.send_notification(sale)
    return {'status': 'ok', 'new_sales': len(sales)}


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
    from auto_social_media import AutoSocialMedia
    return {'status': 'ok', 'result': AutoSocialMedia().run_automation()}


def job_db_backup(keep=14):
    import shutil
    import sqlite3
    from contextlib import closing
    out = ROOT / 'data' / 'backups'
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    done = []
    for name in ('dropshipping.db', 'memory_vectors.db', 'learning_database.db'):
        src = ROOT / 'data' / name
        if not src.exists():
            continue
        dst = out / f'{name}.{stamp}'
        with closing(sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True)) as a, closing(sqlite3.connect(dst)) as b:
            a.backup(b)  # consistent online copy
        done.append(dst.name)
        for old in sorted(out.glob(f'{name}.*'))[:-keep]:
            old.unlink(missing_ok=True)
    return {'status': 'ok', 'backed_up': done, 'kept_per_db': keep}


def job_log_cleanup(days=30):
    cutoff = time.time() - days * 86400
    removed = 0
    for pattern in ('logs/*.log.*', 'logs/*.json', 'data/jobs/*.lock'):
        for f in ROOT.glob(pattern):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True); removed += 1
    usage = ROOT / 'data/model_usage.jsonl'
    if usage.exists() and usage.stat().st_size > 5_000_000:
        lines = usage.read_text(encoding='utf-8').splitlines()[-5000:]
        usage.write_text('\n'.join(lines) + '\n', encoding='utf-8'); removed += 1
    return {'status': 'ok', 'removed': removed}


def job_daily_report():
    """One digest of every job's last result so a silent day is still visible."""
    rows, counts = [], {}
    for f in sorted(JOBS_DIR.glob('last_*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        counts[d['status']] = counts.get(d['status'], 0) + 1
        rows.append(f"{d['job']}:{d['status']}@{d['at'][5:16]}")
    from core.job_tracking import recent_runs
    return {'status': 'ok', 'counts': counts, 'jobs': rows, 'tracked_runs': recent_runs(30) or []}


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
    """List NEW multi-variant products as ONE listing with all variants (max 3/day)."""
    e = _engine()
    from src.listing_quality import publish
    return publish.list_new(e.aliexpress_client, e.ebay_client)


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


def job_variation_sync():
    """Per-variant eBay price + stock for variation listings (legacy inventory_sync/price_optimize skip them)."""
    e = _engine()
    from src.listing_quality import sync
    return sync.run(e.aliexpress_client, e.ebay_client)


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
    'variation_sync':    (job_variation_sync, True),     # per-variant price+stock for variation listings
    'freight_sync':      (job_freight_sync, True),       # ds.freight.query -> products.shipping_cost
    'price_refresh':     (job_price_refresh, True),      # ds.product.get -> products.aliexpress_price (SKU fallback)
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


def run(name, alert_only=False):
    if name not in JOBS:
        raise SystemExit(f'unknown job {name!r}; known: {", ".join(JOBS)}')
    fn, idempotent = JOBS[name]
    started = time.time()
    tracker = None
    try:
        with JobLock(name):
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
        if name == 'listing_pipeline' and isinstance(result, dict):
            problems.append(f"listing: hedef={result.get('plan_target_today')} listelenen_toplam={result.get('listed_total')} "
                            f"neden_yok={result.get('why_not_listed')}")
        if name == 'listing_health' and isinstance(result, dict) and result.get('blocked'):
            problems.append(f"listing_health: {result['blocked']} \u00fcr\u00fcn blokl\u0131 ({result.get('by_code')}) "
                            f"-> {result.get('report')}")
        if name == 'daily_report' and status == 'ok':
            problems.append(json.dumps(result, ensure_ascii=False)[:1200])
        if status == 'ok' and (name == 'weekly_report' or (name == 'diagnose' and result.get('model'))):
            problems.append(json.dumps(result, ensure_ascii=False, default=str)[:1500])
        if problems:
            print('Mondeora: ' + ' | '.join(problems))
    return 1 if status == 'failed' else 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if sys.version_info[:2] != (3, 11):
        print('Python 3.11 gerekli.', file=sys.stderr); return 2
    os.chdir(ROOT); sys.path.insert(0, str(ROOT))
    if not argv or argv[0] in ('--list', '-l'):
        print('\n'.join(JOBS)); return 0
    alert_only = '--alert-only' in argv
    return run(argv[0], alert_only)


if __name__ == '__main__':
    raise SystemExit(main())
