from types import SimpleNamespace
import pytest
from src import jobs
from src.listing_quality import ready_workflow


@pytest.mark.parametrize('name', ['job_listing_pipeline', 'job_new_variation_listing', 'job_publish_ready'])
def test_scheduled_publication_only_consumes_prepared_buffer(monkeypatch, name):
    engine = SimpleNamespace(aliexpress_client=object(), ebay_client=object())
    monkeypatch.setattr(jobs, '_engine', lambda: engine)
    calls = []
    def release(ali, ebay):
        calls.append((ali, ebay))
        return {'status': 'blocked', 'ready_count': 0, 'published_count': 0}
    monkeypatch.setattr(ready_workflow, 'publish_ready', release)
    assert getattr(jobs, name)()['published_count'] == 0
    assert calls == [(engine.aliexpress_client, engine.ebay_client)]


def test_product_sync_cannot_bypass_preparation(monkeypatch):
    engine = SimpleNamespace(aliexpress_client=object(), ebay_client=object())
    monkeypatch.setattr(jobs, '_engine', lambda: engine)
    monkeypatch.setattr(ready_workflow, 'prepare', lambda *a: {'status': 'shortfall', 'ready_count': 0})
    assert jobs.job_product_sync()['ready_count'] == 0
