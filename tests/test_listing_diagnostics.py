from src.listing_quality import diagnostics


def test_diagnose_recognizes_category_fallback_failure():
    d = diagnostics.diagnose("no candidate category fit (tried 4): [...]")
    assert d['code'] == diagnostics.CATEGORY_MISMATCH and 'kategori' in d['human'].lower()


def test_diagnose_recognizes_label_unverified():
    d = diagnostics.diagnose("needs human review: ['variant labels not verifiable (no seller definition name)']")
    assert d['code'] == diagnostics.LABEL_UNVERIFIED


def test_diagnose_recognizes_price_spread():
    d = diagnostics.diagnose("needs human review: ['price spread >3x: check that expensive variants are the same product']")
    assert d['code'] == diagnostics.PRICE_SPREAD


def test_diagnose_recognizes_gate_block_vs_review():
    assert diagnostics.diagnose('GATE BLOCK [...]')['code'] == diagnostics.GATE_BLOCK
    assert diagnostics.diagnose('GATE REVIEW needs user acknowledgement ...')['code'] == diagnostics.GATE_REVIEW


def test_diagnose_unknown_text_never_raises():
    d = diagnostics.diagnose('some new exception text never seen before')
    assert d['code'] == diagnostics.UNKNOWN and d['auto_fixable'] is False


def test_scan_products_is_registered_as_a_job():
    from src import jobs
    assert 'listing_health' in jobs.JOBS
    fn, idempotent = jobs.JOBS['listing_health']
    assert fn is jobs.job_listing_health and idempotent is True
