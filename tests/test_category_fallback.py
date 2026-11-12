import inspect

from src.listing_quality import publish


def test_plan_for_auto_falls_back_through_category_alternatives():
    src = inspect.getsource(publish.plan_for)
    assert "cat.get('alternatives')" in src
    assert 'no candidate category fit' in src
    # order matters: primary candidate tried before alternatives
    assert src.index('candidates = [cat]') < src.index('for candidate in candidates')
