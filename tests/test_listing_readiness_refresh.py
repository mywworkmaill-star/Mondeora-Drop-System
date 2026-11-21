"""Readiness refresh is bounded, GET-only and precedes the write-permission latch."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from src import jobs, readiness
from src.intelligence import healing
from core import job_tracking


def fresh_report():
    return {'generated_at':datetime.now(timezone.utc).isoformat(), 'ready_for_live':True,
        'ready_for_supervised_trial':False, 'live_api_checks_performed':True,
        'checks':[{'name':'supplier_agreement', 'passed':True, 'detail':'hypothetical test'}]}


@pytest.fixture
def offline_job(tmp_path, monkeypatch):
    data = tmp_path/'data'
    data.mkdir()
    events = []
    monkeypatch.setattr(jobs, 'ROOT', tmp_path)
    monkeypatch.setattr(jobs, 'JOBS_DIR', data/'jobs')
    monkeypatch.setattr(jobs, '_enforce_readiness', lambda: events.append('enforce') or 'offline')
    monkeypatch.setattr(healing, 'heal', lambda *a, **kw: events.append('job') or {'status':'ok','published_count':0})
    tracker = SimpleNamespace(finish=lambda *a:None)
    monkeypatch.setattr(job_tracking, 'TrackedJob', lambda *a:SimpleNamespace(__enter__=lambda:tracker))
    def build(*, live=False):
        assert live is True
        events.append('build')
        return fresh_report()
    def save(report):
        events.append('save')
        (data/'readiness_report.json').write_text(json.dumps(report), encoding='utf-8')
    monkeypatch.setattr(readiness, 'build_report', build)
    monkeypatch.setattr(readiness, 'save_report', save)
    return data, events


@pytest.mark.parametrize('name', ['listing_prepare','product_sync','listing_pipeline','publish_ready','new_variation_listing'])
def test_stale_report_refreshes_before_permission_latch_and_job(offline_job, name):
    data, events = offline_job
    report = fresh_report()
    report['generated_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    (data/'readiness_report.json').write_text(json.dumps(report), encoding='utf-8')
    assert jobs.run(name) == 0
    assert events == ['build','save','enforce','job']


@pytest.mark.parametrize('stage', ['build','save','invalid_report'])
def test_refresh_failure_never_reaches_job_and_is_safely_recorded(offline_job, monkeypatch, capsys, stage):
    data, events = offline_job
    secret = 'private-provider-message-never-persist'
    def fail(*args, **kwargs):
        events.append(stage)
        raise RuntimeError(secret)
    if stage == 'invalid_report':
        monkeypatch.setattr(readiness, 'build_report', lambda **kw: {'generated_at':'invalid'})
    else:
        monkeypatch.setattr(readiness, 'build_report' if stage=='build' else 'save_report', fail)
    assert jobs.run('listing_pipeline', semantic_outcome=True) == 2
    assert 'job' not in events and 'enforce' not in events
    saved = (data/'jobs/last_listing_pipeline.json').read_text(encoding='utf-8')
    output = capsys.readouterr()
    assert secret not in saved + output.out + output.err
    result = json.loads(saved)
    assert result['status'] == 'blocked'
    assert result['result']['published_count'] == 0
    assert result['result']['blockers'] == ['readiness_refresh_failed']


@pytest.mark.parametrize('name', ['listing_prepare','product_sync','listing_pipeline','publish_ready','new_variation_listing'])
def test_fresh_report_is_reused_without_new_api_probe(offline_job, name):
    data, events = offline_job
    (data/'readiness_report.json').write_text(json.dumps(fresh_report()), encoding='utf-8')
    assert jobs.run(name) == 0
    assert events == ['enforce','job']


def test_fresh_failed_supplier_check_is_not_replaced_with_approval(offline_job):
    data, events = offline_job
    report = fresh_report()
    report['ready_for_live'] = False
    report['checks'][0]['passed'] = False
    report['blockers'] = ['supplier_agreement']
    (data/'readiness_report.json').write_text(json.dumps(report), encoding='utf-8')
    jobs._refresh_listing_readiness('listing_pipeline')
    assert events == []
    assert json.loads((data/'readiness_report.json').read_text(encoding='utf-8')) == report


def test_other_jobs_do_not_trigger_listing_readiness_probe(offline_job):
    data, events = offline_job
    assert jobs.run('health_check') == 0
    assert events == ['enforce','job']

