"""Self-healing: error classification, bounded retries, circuit breakers, watchdog.

Scope is deliberately narrow and safe: healing may retry, back off, refresh OAuth tokens and
record incidents. It never edits source code, never re-enables write switches, never places
orders and never retries a call that may already have produced a side effect (`idempotent=False`).
"""
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'data' / 'healing_state.json'
REPORT = ROOT / 'data' / 'watchdog_report.json'

TRANSIENT, AUTH, RATE, DB_LOCK, PERMANENT = 'transient', 'auth', 'rate_limit', 'db_locked', 'permanent'


def classify(exc):
    name, msg = type(exc).__name__, str(exc).lower()
    if 'locked' in msg and ('database' in msg or 'sqlite' in msg):
        return DB_LOCK
    if any(x in msg for x in ('401', '403', 'unauthorized', 'invalid_token', 'token expired', 'expired', '932', 'invalidaccesstoken')):
        return AUTH
    if any(x in msg for x in ('429', 'rate limit', 'too many requests', 'throttl')):
        return RATE
    if name in ('Timeout', 'ReadTimeout', 'ConnectTimeout', 'ConnectionError', 'TimeoutError', 'ChunkedEncodingError') \
            or any(x in msg for x in ('timed out', 'connection', '500', '502', '503', '504', 'temporarily')):
        return TRANSIENT
    return PERMANENT


def _load():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding='utf-8')


class CircuitOpen(RuntimeError):
    pass


def circuit_check(name, threshold=5, cooldown=1800):
    c = _load().get(name, {})
    if c.get('failures', 0) >= threshold and time.time() - c.get('last_failure', 0) < cooldown:
        raise CircuitOpen(f'{name}: circuit open until {int(c["last_failure"] + cooldown - time.time())}s')


def _record(name, ok):
    s = _load(); c = s.setdefault(name, {'failures': 0})
    if ok:
        c.update(failures=0, last_ok=time.time())
    else:
        c.update(failures=c.get('failures', 0) + 1, last_failure=time.time())
    _save(s)


def remediate_auth():
    """Safe fix for expired credentials: force an OAuth refresh. Returns True if it reports success."""
    try:
        from src.api.ebay_client import eBayAPIClient
        return bool(eBayAPIClient().refresh_access_token(force=True).get('success'))
    except Exception:
        return False


def record_incident(job, exc, category, action, resolved, memory=None):
    try:
        from src.intelligence.memory import get_memory
        (memory or get_memory()).add(
            'incident', f'job={job} error={type(exc).__name__}: {str(exc)[:300]} category={category} '
                        f'action={action} resolved={resolved}', {'job': job, 'at': time.time()})
    except Exception:
        pass


def heal(job, fn, *args, retries=3, base_delay=2.0, idempotent=True, sleep=time.sleep, **kwargs):
    """Run fn with classified retries. Non-idempotent jobs are never retried after a failure."""
    circuit_check(job)
    last = None
    for attempt in range(1, retries + 1):
        try:
            result = fn(*args, **kwargs)
            _record(job, True)
            if last is not None:
                record_incident(job, last, classify(last), f'retry#{attempt}', True)
            return result
        except CircuitOpen:
            raise
        except Exception as exc:  # noqa: BLE001
            last, cat = exc, classify(exc)
            action = 'none'
            if not idempotent or cat == PERMANENT or attempt == retries:
                _record(job, False); record_incident(job, exc, cat, 'gave_up', False)
                raise
            if cat == AUTH:
                action = 'refresh_token' if remediate_auth() else 'refresh_failed'
                if action == 'refresh_failed':
                    _record(job, False); record_incident(job, exc, cat, action, False)
                    raise
            elif cat == RATE:
                action = 'backoff_long'; sleep(base_delay * 10 * attempt)
            else:
                action = 'backoff'; sleep(base_delay * 2 ** (attempt - 1))
    raise RuntimeError('unreachable')  # pragma: no cover


def similar_past_incidents(error_text, k=3):
    try:
        from src.intelligence.memory import get_memory
        return get_memory().search(error_text, k=k, kind='incident')
    except Exception:
        return []


def watchdog(now=None):
    """Read-only health probe + safe remediation. Writes data/watchdog_report.json."""
    now = now or time.time()
    issues, actions = [], []
    # eBay token
    try:
        exp = float(json.loads((ROOT / 'data/ebay_oauth_metadata.json').read_text())['expires_at'])
        if exp - now < 1800:
            issues.append('ebay_token_expiring')
            ok = remediate_auth(); actions.append(f'ebay_refresh={"ok" if ok else "failed"}')
    except Exception:
        issues.append('ebay_token_metadata_missing')
    # AliExpress token
    try:
        from datetime import datetime
        meta = json.loads((ROOT / 'data/aliexpress_token_refresh_metadata.json').read_text())
        if datetime.fromisoformat(meta['expires_at']).timestamp() - now < 1800:
            issues.append('aliexpress_token_expiring')
            try:
                from token_auto_refresh_complete import AliExpressRefreshTokenToAccessToken
                res = AliExpressRefreshTokenToAccessToken().refresh_access_token_via_refresh_token()
                actions.append(f'ali_refresh={"ok" if res else "failed"}')
            except Exception:
                actions.append('ali_refresh=failed')
    except Exception:
        issues.append('aliexpress_token_metadata_missing')
    # DB
    dbf = ROOT / 'data/dropshipping.db'
    try:
        with closing(sqlite3.connect(f'file:{dbf.as_posix()}?mode=ro', uri=True, timeout=10)) as db:
            if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
                issues.append('db_integrity_failed')
            last = db.execute("select max(strftime('%s', started_at)) from sync_logs").fetchone()[0]
            if last and now - float(last) > 6 * 3600:
                issues.append('sync_stale_over_6h')
    except Exception as e:
        issues.append(f'db_unreadable:{type(e).__name__}')
    # open circuits
    for name, c in _load().items():
        if c.get('failures', 0) >= 5:
            issues.append(f'circuit_open:{name}')
    failed = [a for a in actions if a.endswith('=failed')]
    blocking = [i for i in issues if i not in ('sync_stale_over_6h',)]
    report = {'at': now, 'healthy': not failed and not blocking if not actions else not failed,
              'issues': issues, 'actions': actions}
    REPORT.write_text(json.dumps(report, indent=1), encoding='utf-8')
    if issues:
        try:
            from src.intelligence.memory import get_memory
            get_memory().add('incident', f'watchdog issues={issues} actions={actions}', {'at': now})
        except Exception:
            pass
    return report
