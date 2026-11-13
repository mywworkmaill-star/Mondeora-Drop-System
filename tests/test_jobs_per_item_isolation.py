"""Hata 23 (job_sales_check) / Hata 24 (job_blue_ocean): same per-item isolation gap as Hata 8
(src/automation/engine.py), found in src/jobs.py instead - a single bad sale/candidate must not
stop the rest of the batch. See references/known-bugs.md for the full writeup.
"""
import inspect
import sys
import types

import src.jobs as jobs_mod


def test_job_blue_ocean_isolates_per_candidate_failures():
    src = inspect.getsource(jobs_mod.job_blue_ocean)
    assert 'except ValueError as ex' in src and 'except Exception as ex' in src
    assert 'skipped.append' in src
    # both the ValueError and the generic-Exception handler must continue to the next
    # candidate, never let one bad row kill the other 9 in this run.
    # Slice each except block up to the START of the next except/except-equivalent
    # marker (or end of source for the last block) instead of a fixed char window -
    # a fixed window is brittle: a longer explanatory comment inside the block (as
    # the generic Exception handler has) pushes 'continue' past a short fixed cutoff
    # and produces a false failure even though the real code is correct.
    idx = src.index('except ValueError as ex')
    idx2 = src.index('except Exception as ex')
    assert 'continue' in src[idx:idx2]
    assert 'continue' in src[idx2:]
    # the session must be rolled back before moving on, or the next candidate's session.add()/
    # commit() can inherit a poisoned transaction from the failed one.
    assert 'session.rollback()' in src


def test_job_sales_check_isolates_per_sale_failures():
    src = inspect.getsource(jobs_mod.job_sales_check)
    assert 'except Exception as ex' in src
    assert 'notify_errors.append' in src
    idx = src.index('except Exception as ex')
    assert 'continue' in src[idx:idx + 400]
    assert 'notify_errors' in src[src.index('return {'):]


def test_job_sales_check_one_bad_sale_does_not_block_others(monkeypatch):
    """Behavioral regression: send_notification() raising for sale #1 (e.g. KeyError on a
    malformed row, or sqlite3.OperationalError('database is locked') from _mark_notified())
    must not prevent sale #2 from being notified."""
    sent = []

    class _FakeTracker:
        def __init__(self):
            pass

        def run_check_cycle(self):
            return [{'order_id': 'BAD', 'title': None}, {'order_id': 'GOOD-1'}, {'order_id': 'GOOD-2'}]

        def send_notification(self, sale):
            if sale['order_id'] == 'BAD':
                raise KeyError('sale_price')   # real shape: send_notification indexes sale['sale_price'] etc.
            sent.append(sale['order_id'])

    fake_module = types.ModuleType('sales_tracker')
    fake_module.SalesTracker = _FakeTracker
    monkeypatch.setitem(sys.modules, 'sales_tracker', fake_module)

    result = jobs_mod.job_sales_check()

    assert sent == ['GOOD-1', 'GOOD-2']   # both survived sale #1 blowing up
    assert result['new_sales'] == 3
    assert len(result['notify_errors']) == 1
    assert result['notify_errors'][0]['order_id'] == 'BAD'
    assert 'KeyError' in result['notify_errors'][0]['error']
