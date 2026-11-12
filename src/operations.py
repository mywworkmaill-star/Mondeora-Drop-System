"""Offline operational utilities. Importing this module has no side effects.

Snapshots contain business records: keep the backup directory private. No .env,
configuration, credentials, network notification, or live write action is copied.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import time
from pathlib import Path
import os
import re
import sqlite3
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_ROOT = PROJECT_ROOT.parent / 'Mondeora-runtime-backups'
_SNAPSHOT_NAME = re.compile(r'mondeora-snapshot-\d{8}T\d{12}Z-[0-9a-f]{32}\.sqlite3\Z')


def snapshot_database(source, backup_root=DEFAULT_BACKUP_ROOT, *, retain=7):
    """Online SQLite backup (includes committed WAL), verified before publication.

    Retention applies only to this utility's strict generated filename pattern;
    no recursion, symlinks, arbitrary files, environment files or raw DB copies.
    The caller must arrange a private ACL for backup_root on Windows.
    """
    if type(retain) is not int or not 1 <= retain <= 1000:
        raise ValueError('retain must be between 1 and 1000')
    source = Path(source).resolve(strict=True)
    root = Path(backup_root)
    if root.is_symlink():
        raise ValueError('backup root cannot be a symlink')
    root = root.resolve()
    if root == PROJECT_ROOT or PROJECT_ROOT in root.parents:
        raise ValueError('backups must be outside project')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = root / f'mondeora-snapshot-{stamp}-{uuid.uuid4().hex}.sqlite3'
    pending = target.with_suffix('.partial')
    deadline = time.monotonic() + 30
    def check_deadline(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError('snapshot timeout')
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10)) as src:
            with closing(sqlite3.connect(pending)) as dst:
                src.backup(dst, pages=256, progress=check_deadline, sleep=0.05)
                if dst.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('snapshot integrity verification failed')
        os.chmod(pending, 0o600)
        with pending.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)
    candidates = sorted((p for p in root.iterdir() if _SNAPSHOT_NAME.fullmatch(p.name)
                         and p.is_file() and not p.is_symlink()), key=lambda p: p.name, reverse=True)
    for old in candidates[retain:]:
        old.unlink()
    manifest = {'schema': 1, 'snapshots': []}
    for item in candidates[:retain]:
        digest = hashlib.sha256()
        with item.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        manifest['snapshots'].append({'filename': item.name, 'sha256': digest.hexdigest(),
                                      'bytes': item.stat().st_size})
    _atomic_json(root / 'manifest.json', manifest)
    return target


def _atomic_json(path, data):
    pending = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with pending.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(pending, 0o600)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


_STATUS_VALUES = frozenset({'ok', 'degraded', 'error', 'unknown'})
_COUNT_KEYS = frozenset({'backups', 'errors', 'orders', 'products', 'pending', 'blocked'})


def record_status(state_root, *, status='ok', counts=None, message=None,
                  max_event_bytes=262144):
    """Write local-only alerts; arbitrary messages are discarded, never interpolated.

    Only fixed status values and bounded integer counts escape. Serialize callers
    and set a private Windows ACL. Two bounded event files; no remote delivery.
    """
    if type(max_event_bytes) is not int or not 1024 <= max_event_bytes <= 10485760:
        raise ValueError('invalid event size limit')
    root = Path(state_root)
    if root.is_symlink():
        raise ValueError('state root cannot be a symlink')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('status.json', 'alerts.jsonl', 'alerts.jsonl.1'):
        if (root / name).is_symlink():
            raise ValueError('state file cannot be a symlink')
    clean = {key: value for key, value in (counts.items() if type(counts) is dict else [])
             if type(key) is str and key in _COUNT_KEYS and type(value) is int
             and 0 <= value <= 1000000000}
    event = {'schema': 1, 'timestamp': datetime.now(timezone.utc).isoformat(),
             'status': status if type(status) is str and status in _STATUS_VALUES else 'unknown',
             'counts': clean, 'delivery': 'local_only'}
    payload = (json.dumps(event, sort_keys=True) + '\n').encode('utf-8')
    events = root / 'alerts.jsonl'
    if events.exists() and events.stat().st_size + len(payload) > max_event_bytes:
        os.replace(events, root / 'alerts.jsonl.1')
    with events.open('ab') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(events, 0o600)
    _atomic_json(root / 'status.json', event)
    return event


class OperationalLifecycle:
    """One serialized scheduler job; hourly online backup and minute heartbeat."""
    def __init__(self, engine, *, state_root=None, backup_root=DEFAULT_BACKUP_ROOT):
        import threading
        self.engine = engine
        self.state_root = Path(state_root or PROJECT_ROOT / 'data/operations')
        self.backup_root = Path(backup_root)
        self._lock = threading.Lock()
        self._next_backup = 0
        self.backups = 0
        self.errors = 0
        self.last_status = 'unknown'

    def install(self):
        # Pending jobs are not deduplicated by replace_existing until start().
        if self.engine.scheduler.get_job('operations') is not None:
            self.engine.scheduler.remove_job('operations')
        return self.engine.scheduler.add_job(self.tick, 'interval', seconds=60,
            id='operations', replace_existing=True, max_instances=1, coalesce=True)

    def tick(self):
        if not self._lock.acquire(blocking=False):
            return
        status = 'error'
        try:
            health = self.engine.status()
            status = 'ok' if health.get('running') else 'degraded'
            if any(result.get('status') in {'failed', 'error', 'partial'}
                   for result in health.get('last_results', {}).values()
                   if isinstance(result, dict)):
                status = 'degraded'
            if time.monotonic() >= self._next_backup:
                database = self.engine.engine.url
                if database.get_backend_name() != 'sqlite' or not database.database or database.database == ':memory:':
                    raise ValueError('online snapshot requires file SQLite')
                snapshot_database(database.database, self.backup_root, retain=7)
                self.backups += 1
                self._next_backup = time.monotonic() + 3600
        except Exception:
            self.errors += 1
            status = 'error'
            # Retry failed backups no faster than the bounded heartbeat interval.
            self._next_backup = time.monotonic() + 60
        finally:
            self.last_status = status
            try:
                record_status(self.state_root, status=status,
                    counts={'backups': self.backups, 'errors': self.errors})
            except Exception:
                self.last_status = 'error'
                self.errors += 1
            self._lock.release()

    def status(self):
        return {'status': self.last_status, 'backups': self.backups,
                'errors': self.errors, 'delivery': 'local_only',
                'heartbeat_seconds': 60, 'backup_seconds': 3600}

