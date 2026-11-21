import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('alert_only', [False, True])
@pytest.mark.parametrize('stage,error_type', [('lock', PermissionError), ('report', OSError)])
def test_main_outer_io_failure_prints_only_safe_error_type(
        tmp_path, monkeypatch, capsys, stage, error_type, alert_only):
    bridge = load_bridge()
    secret = 'SECRET raw buyer text buyer@example.com'
    lock_path = tmp_path / 'data/claude_mem_sync.lock'
    report_path = tmp_path / 'data/jobs/last_claude_mem_sync.json'
    original_open = Path.open
    writes = []

    def open_path(path, *args, **kwargs):
        if stage == 'lock' and path == lock_path:
            raise error_type(secret)
        return original_open(path, *args, **kwargs)

    def write_report(path, value):
        writes.append(path)
        assert path == report_path
        raise error_type(secret)

    monkeypatch.setattr(Path, 'open', open_path)
    monkeypatch.setattr(bridge, 'atomic_json', write_report)
    monkeypatch.setattr(bridge, 'client_from_settings', lambda path: object())
    monkeypatch.setattr(bridge, 'sync', lambda root, client: {'status': 'ok'})
    args = ['--root', str(tmp_path)] + (['--alert-only'] if alert_only else [])
    assert bridge.main(args) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        'job': 'claude_mem_sync', 'status': 'failed', 'error_type': error_type.__name__}
    assert captured.err == ''
    assert 'SECRET' not in captured.out and 'buyer' not in captured.out
    assert 'Traceback' not in captured.out
    assert writes == ([report_path] if stage == 'report' else [])


def load_bridge():
    parent = Path(__file__).resolve().parent
    path = (parent.parent if parent.name == 'tests' else parent) / 'claude_mem_bridge.py'
    assert path.is_file(), 'Mondeora claude-mem bridge is not implemented'
    spec = importlib.util.spec_from_file_location('claude_mem_bridge', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_is_allowlisted_and_excludes_secrets():
    bridge = load_bridge()
    summary = bridge.safe_summary('health_check', {
        'job': 'health_check', 'status': 'ok', 'mode': 'supervised_trial',
        'at': '2026-11-15 21:00:00', 'seconds': 4.23,
        'result': {'scanned': 12, 'ready_count': 2, 'errors': {'secret': 'TOKEN'},
                   'error': 'Bearer TOKEN buyer@example.com', 'access_token': 'TOKEN',
                   'customer': 'buyer@example.com', 'updated': True},
        'refresh_token': 'TOKEN',
    })
    assert summary == {
        'job': 'health_check', 'status': 'ok', 'mode': 'supervised_trial',
        'at': '2026-11-15 21:00:00', 'seconds': 4.23,
        'counters': {'scanned': 12, 'ready_count': 2},
    }
    assert 'TOKEN' not in json.dumps(summary)
    assert 'buyer@' not in json.dumps(summary)


def test_malformed_counters_and_huge_durations_do_not_abort_batch():
    bridge = load_bridge()
    record = {'job': 'health_check', 'at': '2026-11-15 21:00:00',
              'seconds': 10 ** 1000, 'status': ['TOKEN'], 'mode': {'token': 'TOKEN'},
              'result': {'scanned': 10 ** 1000, 'total': -1, 'updated': True}}
    summary = bridge.safe_summary('health_check', record)
    assert summary['status'] == 'unknown' and summary['mode'] == 'unknown'
    assert summary['counters'] == {} and 'seconds' not in summary


def test_get_retries_transient_failure_but_post_is_never_blindly_retried(monkeypatch):
    import urllib.error
    bridge = load_bridge()
    client = bridge.Client()
    attempts = []
    class FailingOpener:
        def open(self, req, timeout):
            attempts.append((req.method, timeout))
            raise urllib.error.HTTPError(req.full_url, 503, 'PRIVATE_TOKEN', {}, None)
    client.opener = FailingOpener()
    monkeypatch.setattr(bridge.time, 'sleep', lambda delay: None)
    import pytest
    with pytest.raises(urllib.error.HTTPError):
        client.request('GET', '/api/health')
    assert attempts == [('GET', 3)] * 3
    attempts.clear()
    with pytest.raises(urllib.error.HTTPError):
        client.request('POST', '/api/memory/save', {'text': 'safe'})
    assert attempts == [('POST', 3)]


def test_client_saves_with_replay_key_and_requires_exact_readback():
    from io import BytesIO
    import pytest
    bridge = load_bridge()
    notes, posted = {}, []

    class WorkerTransport:
        corrupt = False
        def open(self, request, timeout):
            assert timeout == 3
            if request.method == 'POST':
                assert request.full_url.endswith('/api/memory/save')
                payload = json.loads(request.data)
                posted.append(payload)
                notes[1] = {'id': 1, 'project': payload['project'], 'narrative': payload['text'],
                            'metadata': json.dumps(payload['metadata'])}
                return BytesIO(json.dumps({'success': True, 'id': 1, 'project': payload['project']}).encode())
            assert request.full_url.endswith('/api/observation/1')
            row = dict(notes[1])
            if self.corrupt:
                row['project'] = 'WRONG_PROJECT'
            return BytesIO(json.dumps(row).encode())

    client = bridge.Client()
    transport = WorkerTransport()
    client.opener = transport
    summary = bridge.safe_summary('health_check', {'job': 'health_check', 'status': 'ok',
        'at': '2026-11-15 21:00:00', 'result': {'scanned': 2}})
    assert client.save(summary)['id'] == 1
    assert len(posted) == 1
    assert posted[0]['metadata']['platformSource'] == 'hermes'
    assert len(posted[0]['metadata']['sourceFingerprint']) == 64
    assert json.loads(notes[1]['narrative']) == summary
    transport.corrupt = True
    with pytest.raises(ValueError, match='readback_mismatch'):
        client.save(summary)


def test_sync_checkpoints_only_after_readback_and_continues_bad_input(tmp_path):
    bridge = load_bridge()
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/jobs_impl.py').write_text("JOBS = {'health_check': None, 'orders_poll': None}")
    jobs = tmp_path / 'data/jobs'
    jobs.mkdir(parents=True)
    good = {'job': 'health_check', 'status': 'ok', 'at': '2026-11-15 21:00:00',
            'result': {'scanned': 7, 'error': 'TOKEN buyer@example.com'}}
    (jobs / 'last_health_check.json').write_text(json.dumps(good))
    (jobs / 'last_orders_poll.json').write_text('{')
    (jobs / 'last_not_registered.json').write_text(json.dumps(good))

    class FakeClient:
        project = 'Mondeora-Drop-System'
        saved = []
        fail = True
        def save(self, summary):
            self.saved.append(summary)
            if self.fail:
                raise ValueError('TOKEN buyer@example.com')
            return {'id': 42, 'duplicate': False}

    client = FakeClient()
    first = bridge.sync(tmp_path, client)
    assert first['saved'] == 0 and first['failed'] == 1
    assert 'TOKEN' not in json.dumps(first)
    assert 'buyer@' not in json.dumps(first)
    client.fail = False
    second = bridge.sync(tmp_path, client)
    assert second['saved'] == 1 and second['invalid'] == 1
    assert second['ids'] == [42]
    third = bridge.sync(tmp_path, client)
    assert third['saved'] == 0 and third['already_verified'] == 1
    assert len(client.saved) == 2
    state_path = tmp_path / 'data/claude_mem_checkpoint.json'
    assert 'TOKEN' not in state_path.read_text()
    assert 'buyer@' not in state_path.read_text()


def test_settings_fail_closed_and_cli_creates_durable_report(tmp_path, monkeypatch, capsys):
    bridge = load_bridge()
    import pytest
    settings = tmp_path / 'settings.json'
    data = {'CLAUDE_MEM_WORKER_HOST': '127.0.0.1', 'CLAUDE_MEM_WORKER_PORT': '37709',
            'CLAUDE_MEM_OBSERVER_ENABLED': 'false', 'CLAUDE_MEM_CHROMA_ENABLED': 'false',
            'CLAUDE_MEM_CLOUD_SYNC_HUB_URL': '', 'CLAUDE_MEM_RUNTIME': 'worker'}
    settings.write_text(json.dumps(data))
    assert bridge.client_from_settings(settings).base == 'http://127.0.0.1:37709'
    data['CLAUDE_MEM_OBSERVER_ENABLED'] = 'true'
    settings.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='local_only_settings_required'):
        bridge.client_from_settings(settings)
    monkeypatch.setattr(bridge, 'client_from_settings', lambda path: object())
    monkeypatch.setattr(bridge, 'sync', lambda root, client: {'status': 'ok', 'saved': 2})
    assert bridge.main(['--root', str(tmp_path), '--alert-only']) == 0
    assert capsys.readouterr().out == ''
    report = json.loads((tmp_path / 'data/jobs/last_claude_mem_sync.json').read_text())
    assert report['result']['saved'] == 2 and report['status'] == 'ok'
    with bridge.sync_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with bridge.sync_lock(tmp_path):
                pytest.fail('concurrent sync was allowed')


def test_rejects_external_worker_and_invalid_records():
    import pytest
    bridge = load_bridge()
    for url in ('https://example.com', 'http://127.0.0.1:37709/evil',
                'http://user:password@127.0.0.1:37709', 'http://localhost:37709'):
        with pytest.raises(ValueError):
            bridge.Client(url)
    for record in ([], {}, {'job': 'wrong'}, {'job': 'health_check', 'at': 'TOKEN'}):
        with pytest.raises(ValueError):
            bridge.safe_summary('health_check', record)
