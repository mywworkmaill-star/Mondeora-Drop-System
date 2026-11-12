import json
import time

import pytest

from src.intelligence import healing, model_router
from src.intelligence.memory import MemoryStore, scrub


@pytest.fixture
def mem(tmp_path):
    return MemoryStore(tmp_path / 'm.db')


def test_scrub_removes_secrets():
    t = scrub('token=abc123456789 and v^1.1#i^1#secretsecretsecret plus password: hunter22222')
    assert 'abc123456789' not in t and 'secretsecret' not in t and 'hunter22222' not in t


def test_memory_semantic_search_and_idempotency(mem):
    mem.add('incident', 'eBay token expired error 932 refresh failed', key='a')
    mem.add('incident', 'eBay token expired error 932 refresh failed', key='a')  # same key -> one row
    mem.add('doc', 'phone case supplier shipping price margin', key='b')
    assert mem.stats() == {'incident': 1, 'doc': 1}
    top = mem.search('ebay token expired', k=1)
    assert top and top[0]['kind'] == 'incident'
    assert 'expired' in mem.context_for('token expired')


def test_memory_never_stores_secrets(mem):
    mem.add('incident', 'failed with token=SUPERSECRETVALUE123')
    assert 'SUPERSECRETVALUE123' not in mem.search('failed', k=1, min_score=0)[0]['text']


@pytest.mark.parametrize('msg,cat', [
    ('database is locked', healing.DB_LOCK), ('HTTP 401 Unauthorized', healing.AUTH),
    ('429 Too Many Requests', healing.RATE), ('Read timed out', healing.TRANSIENT),
    ('KeyError: sku', healing.PERMANENT)])
def test_classify(msg, cat):
    assert healing.classify(RuntimeError(msg)) == cat


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(healing, 'STATE', tmp_path / 'state.json')
    monkeypatch.setattr(healing, 'record_incident', lambda *a, **k: None)


def test_heal_retries_transient_then_succeeds(isolated_state):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError('connection timed out')
        return 'ok'
    assert healing.heal('t1', flaky, sleep=lambda s: None) == 'ok' and len(calls) == 3


def test_heal_never_retries_permanent_or_non_idempotent(isolated_state):
    calls = []

    def bad():
        calls.append(1); raise RuntimeError('timed out')
    with pytest.raises(RuntimeError):
        healing.heal('t2', bad, idempotent=False, sleep=lambda s: None)
    assert len(calls) == 1
    calls.clear()

    def perm():
        calls.append(1); raise KeyError('x')
    with pytest.raises(KeyError):
        healing.heal('t3', perm, sleep=lambda s: None)
    assert len(calls) == 1


def test_heal_auth_triggers_refresh_once(isolated_state, monkeypatch):
    refreshed = []
    monkeypatch.setattr(healing, 'remediate_auth', lambda: refreshed.append(1) or True)
    state = {'n': 0}

    def fn():
        state['n'] += 1
        if state['n'] == 1:
            raise RuntimeError('401 unauthorized')
        return 'done'
    assert healing.heal('t4', fn, sleep=lambda s: None) == 'done' and refreshed == [1]


def test_circuit_opens_after_repeated_failures(isolated_state):
    for _ in range(5):
        with pytest.raises(KeyError):
            healing.heal('t5', lambda: (_ for _ in ()).throw(KeyError('x')))
    with pytest.raises(healing.CircuitOpen):
        healing.heal('t5', lambda: 1)


def test_router_falls_back_across_providers_and_returns_none_without_keys(tmp_path, monkeypatch, isolated_state):
    monkeypatch.setattr(model_router, 'USAGE', tmp_path / 'u.jsonl')
    monkeypatch.setattr(model_router, 'get_memory', lambda: MemoryStore(tmp_path / 'm.db'))
    monkeypatch.setattr(model_router, '_key', lambda p: None)
    assert model_router.route('classify', 'x') is None
    monkeypatch.setattr(model_router, '_key', lambda p: 'k')
    seen = []

    def caller(provider, model, system, prompt, mt, to):
        seen.append(provider)
        if provider == 'anthropic':
            raise RuntimeError('503')
        return 'hi', 1, 1
    r = model_router.route('classify', 'x', caller=caller)
    assert r['provider'] == 'openai' and seen == ['anthropic', 'openai']


def test_router_tiers_and_unknown_task():
    cfg = model_router.load_config()
    assert cfg['task_to_tier']['diagnose_incident'] == 'reasoning' and cfg['task_to_tier']['classify'] == 'fast'
    with pytest.raises(ValueError):
        model_router.route('nope', 'x')


def test_jobs_registry_and_lock(tmp_path, monkeypatch):
    from src import jobs
    assert {'token_refresh', 'watchdog', 'orders_sync', 'inventory_sync', 'memory_index'} <= set(jobs.JOBS)
    assert jobs.JOBS['orders_sync'][1] is False  # purchase path is never auto-retried
    monkeypatch.setattr(jobs, 'JOBS_DIR', tmp_path)
    with jobs.JobLock('x'):
        with pytest.raises(BlockingIOError):
            with jobs.JobLock('x'):
                pass
    with jobs.JobLock('x'):
        pass
