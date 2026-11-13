"""Hata 35: same per-item isolation gap as Hata 8, found in three more src/jobs.py functions
that were never covered by tests/test_jobs_per_item_isolation.py:

- job_db_backup(): three DBs backed up in one loop with NO try/except. dropshipping.db is being
  written by most of the other hourly/daily cron jobs at the same time db_backup runs - a real
  sqlite3.OperationalError('database is locked') on ONE db's a.backup(b) call used to raise out of
  the whole function, so memory_vectors.db/learning_database.db (which come AFTER it in the tuple)
  never got backed up that night, and the job was marked fully 'failed' even though it could have
  produced two of three backups.
- job_log_cleanup(): f.unlink(missing_ok=True) has no try/except. missing_ok only swallows
  FileNotFoundError; a file still open/locked by a concurrent job (PermissionError on Windows, a
  real risk here since many cron jobs write under logs/ and data/jobs/ at overlapping times) stops
  the rest of the sweep, leaving later-matched old files un-removed.
- job_daily_report(): json.loads(f.read_text()) has no try/except. One last_<job>.json truncated
  mid-write by a crash/kill during a concurrent run makes the ENTIRE daily digest raise, hiding
  every OTHER job's status for the day behind one corrupt file.

Fix: wrap each per-item unit of work in try/except, collect errors, continue - status becomes
'partial' (not 'failed') when some but not all items succeeded, matching the rest of the pipeline.
"""
import json
import sqlite3
import time
from contextlib import closing

import pytest

import src.jobs as jobs_mod


def _make_sqlite_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute('CREATE TABLE t (x INTEGER)')
    conn.execute('INSERT INTO t VALUES (1)')
    conn.commit()
    conn.close()


def test_db_backup_one_locked_db_does_not_block_the_others(monkeypatch, tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    # dropshipping.db exists but is not a valid sqlite file - sqlite3.connect(mode=ro) opens
    # lazily and succeeds, but the real a.backup(b) call then raises sqlite3.DatabaseError
    # ("file is not a database"), the same shape of failure a lock/corruption produces live.
    (data_dir / 'dropshipping.db').write_bytes(b'not a real sqlite file' * 10)
    for name in ('memory_vectors.db', 'learning_database.db'):
        _make_sqlite_db(data_dir / name)
    monkeypatch.setattr(jobs_mod, 'ROOT', tmp_path)

    result = jobs_mod.job_db_backup(keep=14)

    # the other two DBs must still be backed up despite dropshipping.db's backup() raising
    assert any('memory_vectors.db' in b for b in result['backed_up'])
    assert any('learning_database.db' in b for b in result['backed_up'])
    assert not any('dropshipping.db' in b for b in result['backed_up'])
    assert result['status'] == 'partial'
    assert len(result['errors']) == 1
    assert result['errors'][0]['db'] == 'dropshipping.db'
    assert 'Error' in result['errors'][0]['error']
    # no zero-byte/partial backup file left behind for the failed db
    assert not list((tmp_path / 'data' / 'backups').glob('dropshipping.db.*'))


def test_log_cleanup_one_locked_file_does_not_block_the_others(monkeypatch, tmp_path):
    (tmp_path / 'logs').mkdir()
    (tmp_path / 'data' / 'jobs').mkdir(parents=True)
    old = time.time() - 40 * 86400
    locked = tmp_path / 'logs' / 'locked.log.1'
    good1 = tmp_path / 'logs' / 'old1.log.1'
    good2 = tmp_path / 'logs' / 'old2.log.1'
    for f in (locked, good1, good2):
        f.write_text('x')
        os_utime = __import__('os').utime
        os_utime(str(f), (old, old))
    monkeypatch.setattr(jobs_mod, 'ROOT', tmp_path)

    from pathlib import Path
    real_unlink = Path.unlink

    def flaky_unlink(self, missing_ok=False):
        if self.name == 'locked.log.1':
            raise PermissionError('[WinError 32] file in use by another process')
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, 'unlink', flaky_unlink)

    result = jobs_mod.job_log_cleanup(days=30)

    assert not good1.exists()
    assert not good2.exists()
    assert locked.exists()   # the locked file survives, but didn't block the other two
    assert result['removed'] == 2
    assert result['status'] == 'partial'
    assert len(result['errors']) == 1
    assert 'locked.log.1' in result['errors'][0]['file']


def test_daily_report_one_corrupt_json_does_not_hide_the_others(monkeypatch, tmp_path):
    jobs_dir = tmp_path / 'data' / 'jobs'
    jobs_dir.mkdir(parents=True)
    (jobs_dir / 'last_aaa_corrupt.json').write_text('{"job": "aaa_corrupt", "status": "ok"', encoding='utf-8')  # truncated
    (jobs_dir / 'last_bbb_good.json').write_text(
        json.dumps({'job': 'bbb_good', 'status': 'ok', 'at': '2026-11-13T09:00:00'}), encoding='utf-8')
    (jobs_dir / 'last_ccc_good.json').write_text(
        json.dumps({'job': 'ccc_good', 'status': 'failed', 'at': '2026-11-13T10:00:00'}), encoding='utf-8')
    monkeypatch.setattr(jobs_mod, 'JOBS_DIR', jobs_dir)
    monkeypatch.setattr('core.job_tracking.recent_runs', lambda limit=30: [])

    result = jobs_mod.job_daily_report()

    assert result['status'] == 'partial'
    assert len(result['errors']) == 1
    assert 'aaa_corrupt' in result['errors'][0]['file']
    assert any('bbb_good' in r for r in result['jobs'])
    assert any('ccc_good' in r for r in result['jobs'])
    assert result['counts'] == {'ok': 1, 'failed': 1}
