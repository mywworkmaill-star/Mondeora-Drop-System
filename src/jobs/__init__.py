"""Mondeora src.jobs package.

RE-EXPORT SHIM (2026-11-21 root-cause fix): this directory used to exist
as an (almost empty) PACKAGE alongside a separate `src/jobs.py` FILE that
held every real job function (job_research, job_order_fulfillment, JobLock,
main, SEMANTIC_EXIT, PROGRESS_FIELDS, ...). Python's import resolution
always prefers a package over a same-named module, so EVERY
`from src.jobs import X` / `from src import jobs` / `python -m src.jobs
<job>` call anywhere in the codebase was silently resolving to THIS
package's near-empty `__init__.py` instead of the real file -- confirmed
live as the cause of 9 broken cron jobs (tracking_update, order_fulfillment,
link_verify, health_check, ad_bid_optimize, price_refresh, listing_integrity,
listing_standards_resolve, image_reupload), all failing with
"No module named src.jobs.__main__; 'src.jobs' is a package and cannot be
directly executed".

Fix: the real implementation moved to `src/jobs_impl.py` (unchanged
content); this package re-exports it, and `__main__.py` restores
`python -m src.jobs <job>` CLI support. Existing submodules in this
package (ebay_active_sync.py, scheduled_ebay_sync.py, etc.) are untouched
and keep working via their normal `src.jobs.<submodule>` import path --
only the package's OWN direct namespace changed, from empty to a full
re-export of jobs_impl.
"""
from src.jobs_impl import *  # noqa: F401,F403
from src.jobs_impl import (  # noqa: F401  (explicit, in case __all__ ever narrows the star-import)
    JobLock, main, run, JOBS, SEMANTIC_EXIT, PROGRESS_FIELDS, SEMANTIC_LISTING_JOBS,
)
