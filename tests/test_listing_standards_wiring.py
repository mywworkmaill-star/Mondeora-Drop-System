from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import json
import runpy
import sqlite3
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_general_standards_job_is_registered_read_only():
    from src import jobs
    assert 'listing_standards' in jobs.JOBS
    assert jobs.JOBS['listing_standards'][1] is True


def test_daily_orchestrator_requires_standards_and_preparation_before_release():
    from src.orchestrator.master import create_daily_workflow
    workflow = create_daily_workflow()
    assert 'listing-standards' in workflow.jobs
    assert 'listing-prepare' in workflow.jobs
    assert 'listing-standards' in workflow.jobs['listing-prepare'].dependencies
    assert 'listing-prepare' in workflow.jobs['listing-pipeline'].dependencies
    assert workflow.jobs['listing-pipeline'].retry_count == 1
    for name in ('listing-standards', 'listing-prepare', 'listing-pipeline'):
        assert (ROOT / workflow.jobs[name].script).is_file()


def test_provider_errors_never_print_raw_response(capsys):
    from src.api.ebay_client import EBayAPIError, eBayAPIClient
    secret = 'test-provider-body-private-never-print'
    response = SimpleNamespace(status_code=400, text=secret)
    client = eBayAPIClient(session=SimpleNamespace(request=lambda *a, **kw: response),
                           config={'EBAY_ACCESS_TOKEN': 'offline-test-token'})
    with pytest.raises(EBayAPIError) as error:
        client._request('GET', '/sell/inventory/v1/inventory_item')
    output = capsys.readouterr()
    assert secret not in output.out + output.err + str(error.value)


def test_read_only_orchestration_has_no_publication_jobs():
    from src.orchestrator.master import create_listing_review_workflow
    workflow = create_listing_review_workflow()
    assert set(workflow.jobs) == {'listing-standards'}
    assert workflow.jobs['listing-standards'].retry_count == 1


def test_standards_wrapper_is_canonical_job_entrypoint():
    script = ROOT / 'scripts' / 'listing_standards.py'
    assert script.is_file()
    text = script.read_text(encoding='utf-8')
    assert 'listing_standards' in text
    assert 'src.jobs' in text
    assert 'fix_miscategorized' not in text


@pytest.mark.parametrize('name, result, expected, code', [
    ('listing_standards', {'status': 'partial', 'complete': False, 'fetch_error_count': 0,
                           'processed_this_run': 2, 'remaining_count': 3}, 'deferred', 3),
    ('listing_standards', {'status': 'partial', 'complete': False, 'fetch_error_count': 1}, 'failed', 1),
    ('listing_standards', {'status': 'action_required', 'complete': True, 'fetch_error_count': 0}, 'blocked', 2),
    ('listing_standards', {'status': 'verified', 'complete': True, 'fetch_error_count': 0}, 'success', 0),
    ('listing_prepare', {'status': 'shortfall', 'shortfall': 2, 'ready_count': 8}, 'deferred', 3),
    ('listing_prepare', {'status': 'ok', 'shortfall': 0, 'ready_count': 10}, 'success', 0),
    ('listing_pipeline', {'status': 'blocked', 'blockers': ['publication_needs_reconciliation:123']}, 'blocked', 2),
    ('listing_pipeline', {'status': 'ok', 'blockers': ['publication_needs_reconciliation:123']}, 'blocked', 2),
    ('listing_pipeline', {'status': 'ok', 'published_count': 1, 'blockers': []}, 'success', 0),
])
def test_listing_job_semantics_are_opt_in_and_keep_direct_cron_compatible(tmp_path, monkeypatch, capsys,
                                                                         name, result, expected, code):
    from src import jobs
    from src.intelligence import healing
    from core import job_tracking
    monkeypatch.setattr(jobs, 'JOBS_DIR', tmp_path)
    monkeypatch.setattr(jobs, '_enforce_readiness', lambda: 'offline')
    monkeypatch.setattr(healing, 'heal', lambda *a, **k: result)
    tracker = SimpleNamespace(finish=lambda *a: None)
    monkeypatch.setattr(job_tracking, 'TrackedJob', lambda *a: SimpleNamespace(__enter__=lambda: tracker))
    assert jobs.run(name) == 0  # Ordinary cron/direct jobs retain their old exit convention.
    capsys.readouterr()
    assert jobs.run(name, semantic_outcome=True) == code
    lines = capsys.readouterr().out.splitlines()
    outcome = json.loads(next(line.removeprefix('MONDEORA_JOB_OUTCOME ') for line in lines
                              if line.startswith('MONDEORA_JOB_OUTCOME ')))
    assert outcome['status'] == expected and outcome['job'] == name
    if 'processed_this_run' in result:
        assert outcome['progress']['processed_this_run'] == 2
        assert outcome['progress']['remaining_count'] == 3


def test_busy_listing_job_is_deferred_but_legacy_nonlisting_exit_stays_zero(tmp_path, monkeypatch, capsys):
    from src import jobs
    monkeypatch.setattr(jobs, 'JOBS_DIR', tmp_path)
    (tmp_path / 'listing_standards.lock').write_text('123', encoding='utf-8')
    assert jobs.run('listing_standards') == 0
    assert jobs.run('listing_standards', semantic_outcome=True) == 3
    (tmp_path / 'watchdog.lock').write_text('123', encoding='utf-8')
    assert jobs.run('watchdog', semantic_outcome=True) == 0


@pytest.mark.parametrize('script', ['listing_standards', 'listing_prepare', 'listing_pipeline'])
def test_canonical_wrappers_opt_in_semantics(script, monkeypatch):
    from src import jobs
    received = []
    monkeypatch.setattr(jobs, 'main', lambda args: received.append(args) or 3)
    monkeypatch.setattr(sys, 'argv', [script + '.py'])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ROOT / 'scripts' / (script + '.py')), run_name='__main__')
    assert stopped.value.code == 3
    assert received == [[script, '--semantic-outcome']]


def offline_orchestrator(tmp_path, monkeypatch):
    from src.orchestrator import master
    logger = SimpleNamespace(log=lambda **k: None, log_error=lambda **k: None)
    monkeypatch.setattr(master, 'ROOT', tmp_path)
    monkeypatch.setattr(master, 'get_logger', lambda: logger)
    monkeypatch.setattr(master.time, 'sleep', lambda seconds: None)
    (tmp_path / 'data').mkdir(exist_ok=True)
    return master, master.Orchestrator()


@pytest.mark.parametrize('status, code', [('blocked', 2), ('deferred', 3), ('failed', 1), ('success', 0)])
def test_orchestrator_consumes_explicit_listing_semantics_without_retries(tmp_path, monkeypatch, status, code):
    import subprocess
    master, orchestrator = offline_orchestrator(tmp_path, monkeypatch)
    calls = []
    payload = {'version': 1, 'job': 'listing_standards', 'status': status,
               'progress': {'processed_this_run': 2, 'remaining_count': 3}}
    output = 'noise\nMONDEORA_JOB_OUTCOME ' + json.dumps(payload) + '\n'
    def transport(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=code, stdout=output, stderr='private-never-store')
    monkeypatch.setattr(subprocess, 'run', transport)
    job = master.Job('listing-standards', 'scripts/listing_standards.py', retry_count=3)
    assert orchestrator.execute_job(job) is (status == 'success')
    assert job.status.value == status and job.attempts == len(calls) == 1
    assert job.progress == payload['progress']
    assert 'private-never-store' not in (job.output or '') + (job.error or '')


def test_zero_exit_without_explicit_listing_outcome_fails_closed_but_legacy_succeeds(tmp_path, monkeypatch):
    import subprocess
    master, orchestrator = offline_orchestrator(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='{}', stderr=''))
    listing = master.Job('listing-standards', 'scripts/listing_standards.py', retry_count=1)
    assert not orchestrator.execute_job(listing)
    assert listing.status.value == 'failed'
    legacy = master.Job('legacy', 'scripts/health_check.py', retry_count=1)
    assert orchestrator.execute_job(legacy) and legacy.status.value == 'success'


@pytest.mark.parametrize('status, code', [('blocked', 2), ('deferred', 3), ('failed', 1)])
def test_workflow_propagates_non_success_and_skips_all_dependent_listing_stages(tmp_path, monkeypatch,
                                                                              status, code):
    import subprocess
    master, orchestrator = offline_orchestrator(tmp_path, monkeypatch)
    calls = []
    def transport(*args, **kwargs):
        calls.append(args)
        payload = {'version': 1, 'job': 'listing_standards', 'status': status,
                   'progress': {'processed_this_run': 2, 'remaining_count': 3}}
        return SimpleNamespace(returncode=code, stdout='MONDEORA_JOB_OUTCOME ' + json.dumps(payload), stderr='')
    monkeypatch.setattr(subprocess, 'run', transport)
    workflow = master.Workflow('offline', [
        master.Job('standards', 'scripts/listing_standards.py', retry_count=1),
        master.Job('prepare', 'scripts/listing_prepare.py', dependencies=['standards'], retry_count=1),
        master.Job('release', 'scripts/listing_pipeline.py', dependencies=['prepare'], retry_count=1),
    ])
    result = orchestrator.execute_workflow(workflow)
    assert result['status'] == status and result['stats'][status] == 1
    assert result['stats']['success'] == 0 and result['stats']['skipped'] == 2
    assert result['progress']['processed_this_run'] == 2
    assert len(calls) == 1
    with sqlite3.connect(orchestrator.db_path) as db:
        assert db.execute('SELECT status FROM workflow_runs').fetchone() == (status,)
    monkeypatch.setattr(master, 'Orchestrator', lambda: SimpleNamespace(execute_workflow=lambda workflow: result))
    monkeypatch.setattr(sys, 'argv', ['master', '--workflow', 'listing-review'])
    assert master.main() == code
