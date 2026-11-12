"""Bridge between src/jobs.py (the scheduler hub) and the automation tracking tables.

Every job run becomes one automation_runs row + audit_log entries, so nothing that the
cron jobs do is ever lost. Tracking is fail-safe: a tracking error never breaks a job.
"""
import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'dropshipping.db'
SCHEMA = ROOT / 'database' / 'add_automation_tables.sql'


def ensure_schema(db_path=DB):
    """Idempotent: creates the tracking tables if a fresh DB/backup lacks them."""
    try:
        sql = SCHEMA.read_text(encoding='utf-8')
        with closing(sqlite3.connect(db_path, timeout=5)) as c:
            c.executescript(sql)
            c.commit()
    except (OSError, sqlite3.Error):
        pass


def _safe(fn):
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return None
    return wrapper


@_safe
def audit(category, action, data=None, level='info', message=None, db_path=DB):
    with closing(sqlite3.connect(db_path, timeout=5)) as c:
        c.execute('INSERT INTO audit_log (category, action, level, message, data, timestamp) VALUES (?,?,?,?,?,?)',
                  (category, action, level, message, json.dumps(data, default=str)[:4000] if data is not None else None,
                   datetime.now().isoformat()))
        c.commit()


class TrackedJob:
    """Context manager used by src.jobs.run(): one row per job execution."""

    def __init__(self, job_name, mode, db_path=DB):
        import uuid
        self.job = job_name
        self.mode = mode
        self.db_path = db_path
        self.run_id = str(uuid.uuid4())
        self.t0 = time.time()

    def __enter__(self):
        ensure_schema(self.db_path)
        self._open()
        return self

    @_safe
    def _open(self):
        with closing(sqlite3.connect(self.db_path, timeout=5)) as c:
            c.execute('INSERT INTO automation_runs (run_id, automation_name, status, started_at, current_step, metadata) '
                      'VALUES (?,?,?,?,?,?)',
                      (self.run_id, self.job, 'running', datetime.now().isoformat(), 'start',
                       json.dumps({'mode': self.mode})))
            c.commit()
        audit(self.job, 'started', {'run_id': self.run_id, 'mode': self.mode}, db_path=self.db_path)

    @_safe
    def finish(self, status, result):
        ok = status in ('ok', 'success', 'blocked', 'busy', 'read_only')
        summary = result if isinstance(result, dict) else {'value': result}
        with closing(sqlite3.connect(self.db_path, timeout=5)) as c:
            c.execute('UPDATE automation_runs SET status=?, completed_at=?, current_step=?, error_message=?, '
                      'completed_steps=completed_steps+?, failed_steps=failed_steps+?, metadata=? WHERE run_id=?',
                      ('completed' if ok else 'failed', datetime.now().isoformat(), 'end',
                       None if ok else str(summary.get('error'))[:500], 1 if ok else 0, 0 if ok else 1,
                       json.dumps({'mode': self.mode, 'job_status': status, 'seconds': round(time.time() - self.t0, 2),
                                   'result': summary}, default=str)[:8000], self.run_id))
            c.commit()
        audit(self.job, 'finished', {'run_id': self.run_id, 'status': status,
                                     'seconds': round(time.time() - self.t0, 2)},
              level='info' if ok else 'error', db_path=self.db_path)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.finish('failed', {'error': exc_type.__name__})
        return False


@_safe
def record_health(check_name, healthy, response_ms=None, error=None, db_path=DB):
    with closing(sqlite3.connect(db_path, timeout=5)) as c:
        c.execute('INSERT INTO health_checks (check_name, status, healthy, response_time_ms, error_message, checked_at) '
                  'VALUES (?,?,?,?,?,?)',
                  (check_name, 'healthy' if healthy else 'unhealthy', 1 if healthy else 0, response_ms,
                   (error or '')[:300] or None, datetime.now().isoformat()))
        c.commit()


@_safe
def recent_runs(limit=30, db_path=DB):
    with closing(sqlite3.connect(db_path, timeout=5)) as c:
        rows = c.execute('SELECT automation_name, status, started_at, completed_at, metadata FROM automation_runs '
                         'ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [{'job': r[0], 'status': r[1], 'started': r[2], 'completed': r[3],
             'mode': (json.loads(r[4]) if r[4] else {}).get('mode')} for r in rows]
