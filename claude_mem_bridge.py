"""Local-only, LLM-free bridge for Mondeora job snapshots and claude-mem."""
import ast
import hashlib
import json

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

COUNTERS = frozenset(('scanned', 'ready_count', 'shortfall', 'published_count', 'updated',
                      'indexed', 'processed', 'processed_count', 'processed_this_run',
                      'verified_count', 'remaining_count', 'catalog_total', 'fetch_error_count',
                      'budget_stop_count', 'removed_count', 'unresolved_count', 'errors_count',
                      'issues_count', 'critical_count', 'problem_count', 'blocked', 'total'))
STATUSES = frozenset(('ok', 'failed', 'blocked', 'busy', 'partial', 'verified', 'shortfall',
                      'deferred', 'success', 'completed', 'skipped', 'needs_reconciliation',
                      'publication_needs_reconciliation'))
MODES = frozenset(('live', 'read_only', 'supervised_trial', '-',
                   'read_only (readiness gate not passed)'))


def safe_summary(job, record):
    """Allowlist only job health; never copy errors, bodies, IDs or buyer data."""
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', job) or not isinstance(record, dict):
        raise ValueError('invalid_job_record')
    if record.get('job') != job:
        raise ValueError('job_identity_mismatch')
    at = record.get('at')
    if not isinstance(at, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', at):
        raise ValueError('invalid_timestamp')
    datetime.strptime(at, '%Y-%m-%d %H:%M:%S')
    result = record.get('result')
    result = result if isinstance(result, dict) else {}
    status, mode = record.get('status'), record.get('mode')
    safe = {'job': job, 'status': status if isinstance(status, str) and status in STATUSES else 'unknown',
            'mode': mode if isinstance(mode, str) and mode in MODES else 'unknown', 'at': at}
    seconds = record.get('seconds')
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and 0 <= seconds <= 86400:
        safe['seconds'] = round(seconds, 2)
    safe['counters'] = {k: v for k, v in result.items()
                        if k in COUNTERS and type(v) is int and 0 <= v <= 1_000_000_000}
    return safe


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fingerprint(summary):
    return hashlib.sha256(('mondeora-job-v1\0' + encoded(summary)).encode()).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base='http://127.0.0.1:37709', *, project='Mondeora-Drop-System', token=''):
        parsed = urllib.parse.urlsplit(base)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
                or parsed.username or parsed.password or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment):
            raise ValueError('loopback_worker_required')
        self.base, self.project = base.rstrip('/'), project
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None):
        if not path.startswith('/api/') or '://' in path:
            raise ValueError('invalid_api_path')
        body = encoded(payload).encode() if payload is not None else None
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if self.token:
            headers['X-Claude-Mem-Token'] = self.token
        for attempt in range(3):
            try:
                req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
                with self.opener.open(req, timeout=3) as response:
                    raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise ValueError('response_too_large')
                return json.loads(raw)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (429, 500, 502, 503, 504)
                if method != 'GET' or not retryable or attempt == 2:
                    raise
                time.sleep(0.25 * 2 ** attempt)
        raise RuntimeError('request_failed')

    def save(self, summary):
        text, key = encoded(summary), fingerprint(summary)
        metadata = {'source': 'mondeora-job-v1', 'platformSource': 'hermes', 'sourceFingerprint': key}
        saved = self.request('POST', '/api/memory/save', {
            'project': self.project, 'title': 'Mondeora job: ' + summary['job'] + ' ' + summary['at'],
            'text': text, 'metadata': metadata,
        })
        if (not isinstance(saved, dict) or saved.get('success') is not True
                or type(saved.get('id')) is not int or saved['id'] <= 0
                or saved.get('project') != self.project):
            raise ValueError('save_unconfirmed')
        row = self.request('GET', '/api/observation/' + str(saved['id']))
        meta = row.get('metadata') if isinstance(row, dict) else None
        if isinstance(meta, str):
            meta = json.loads(meta)
        if (not isinstance(row, dict) or row.get('id') != saved['id']
                or row.get('project') != self.project or row.get('narrative') != text
                or not isinstance(meta, dict) or meta.get('sourceFingerprint') != key
                or meta.get('platformSource') != 'hermes'):
            raise ValueError('readback_mismatch')
        return {'id': saved['id'], 'duplicate': saved.get('duplicate') is True}


def atomic_json(path, value):
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
        temporary = stream.name
        try:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=1)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            os.unlink(temporary)
            raise
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def registered_jobs(root):
    """Read the registry as syntax only; never import the live automation engine."""
    tree = ast.parse((root / 'src/jobs.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'JOBS' for t in node.targets)
                and isinstance(node.value, ast.Dict)):
            names = {key.value for key in node.value.keys if isinstance(key, ast.Constant)
                     and isinstance(key.value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', key.value)}
            if names:
                return names
    raise ValueError('job_registry_missing')


def sync(root, client, *, budget_seconds=45):
    from pathlib import Path
    root = Path(root)
    state_path = root / 'data/claude_mem_checkpoint.json'
    scope = {'project': client.project, 'worker': getattr(client, 'base', 'test')}
    state = {'scope': scope, 'jobs': {}}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding='utf-8'))
        if not isinstance(previous, dict) or not isinstance(previous.get('jobs'), dict):
            raise ValueError('checkpoint_corrupt')
        if previous.get('scope') == scope:
            state = previous
    report = {'status': 'ok', 'scanned': 0, 'saved': 0, 'replayed': 0, 'already_verified': 0,
              'invalid': 0, 'failed': 0, 'remaining': 0, 'ids': [], 'error_types': {}}
    names = registered_jobs(root)
    files = sorted(p for p in (root / 'data/jobs').glob('last_*.json') if p.name[5:-5] in names)
    started = time.monotonic()
    for index, path in enumerate(files):
        if time.monotonic() - started >= budget_seconds:
            report['remaining'] = len(files) - index
            break
        report['scanned'] += 1
        job = path.name[5:-5]
        try:
            if path.is_symlink() or path.stat().st_size > 262144:
                raise ValueError('invalid_input_file')
            summary = safe_summary(job, json.loads(path.read_text(encoding='utf-8-sig')))
        except (OSError, ValueError, TypeError):
            report['invalid'] += 1
            continue
        key = fingerprint(summary)
        cached = state['jobs'].get(job, {})
        if isinstance(cached, dict) and cached.get('fingerprint') == key:
            report['already_verified'] += 1
            continue
        try:
            saved = client.save(summary)
            state['jobs'][job] = {'fingerprint': key, 'id': saved['id']}
            atomic_json(state_path, state)
            report['replayed' if saved['duplicate'] else 'saved'] += 1
            report['ids'].append(saved['id'])
        except Exception as exc:
            report['failed'] += 1
            kind = type(exc).__name__
            report['error_types'][kind] = report['error_types'].get(kind, 0) + 1
            if isinstance(exc, (OSError, urllib.error.URLError)):
                report['remaining'] = len(files) - index - 1
                break
    if report['failed'] or report['invalid'] or report['remaining']:
        report['status'] = 'partial'
    return report


def client_from_settings(path):
    settings = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if isinstance(settings.get('env'), dict):
        settings = settings['env']
    if (settings.get('CLAUDE_MEM_WORKER_HOST') != '127.0.0.1'
            or settings.get('CLAUDE_MEM_RUNTIME') != 'worker'
            or settings.get('CLAUDE_MEM_OBSERVER_ENABLED') != 'false'
            or settings.get('CLAUDE_MEM_CHROMA_ENABLED') != 'false'
            or settings.get('CLAUDE_MEM_CLOUD_SYNC_HUB_URL')
            or settings.get('CLAUDE_MEM_CLOUD_SYNC_TOKEN')
            or settings.get('CLAUDE_MEM_NOTION_ENABLED') == 'true'
            or settings.get('CLAUDE_MEM_GROK_BOT_WEBHOOK_URL')):
        raise ValueError('local_only_settings_required')
    port = settings.get('CLAUDE_MEM_WORKER_PORT')
    if not isinstance(port, str) or not re.fullmatch(r'[0-9]{1,5}', port) or not 1 <= int(port) <= 65535:
        raise ValueError('invalid_worker_port')
    return Client('http://127.0.0.1:' + port, token=settings.get('CLAUDE_MEM_LOCAL_API_TOKEN') or '')


@contextmanager
def sync_lock(root):
    path = Path(root) / 'data/claude_mem_sync.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BlockingIOError('sync_busy') from exc
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--settings', type=Path, default=Path.home() / '.claude-mem/settings.json')
    parser.add_argument('--alert-only', action='store_true')
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        with sync_lock(args.root):
            try:
                result = sync(args.root, client_from_settings(args.settings))
            except Exception as exc:
                result = {'status': 'failed', 'error_type': type(exc).__name__}
            out = {'job': 'claude_mem_sync', 'status': result['status'], 'mode': 'local_only',
                   'at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   'seconds': round(time.monotonic() - started, 2), 'result': result}
            atomic_json(args.root / 'data/jobs/last_claude_mem_sync.json', out)
    except BlockingIOError:
        if not args.alert_only:
            print(encoded({'job': 'claude_mem_sync', 'status': 'busy'}))
        return 3
    except Exception as exc:
        print(encoded({'job': 'claude_mem_sync', 'status': 'failed',
                       'error_type': type(exc).__name__}))
        return 1
    if not args.alert_only or result['status'] != 'ok':
        print(encoded(out))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
