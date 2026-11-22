"""
Bulk-operation velocity guard.

INCIDENT CONTEXT (2026-11-22): eBay temporarily restricted the seller
account and mass-removed all active listings, citing "activities that pose
a risk to the community." The account was 8 months old with feedback=14
(low trust signal) and had just absorbed, within the same session:
  - 59+ ad-campaign bid updates fired back-to-back
  - repeated rapid-fire product publishes
  - dozens of raw API test/debug calls (AliExpress order-create isolation
    tests, signature experiments, etc.)
all against a Privatverkäufer-labelled account showing commercial-volume
behaviour. eBay's own GoodStanding/account-health fields never flagged
this in advance - the first signal was the restriction email itself.

This is cheap insurance, not a guarantee: throttling bulk writes to a
human-plausible pace measurably reduces exposure to velocity-based risk
heuristics (a well-documented category across major marketplaces), at
near-zero cost to any legitimate batch job's wall-clock time.

Usage:
    from src.velocity_guard import throttled
    for item in bulk_items:
        with throttled('ad_bid_update'):
            ebay.update_bid(...)

Or manually:
    from src.velocity_guard import pace
    for item in bulk_items:
        pace('ad_bid_update')
        ebay.update_bid(...)
"""
import time
import random
from contextlib import contextmanager

# Minimum seconds between consecutive WRITE calls in the same category.
# Deliberately > 1s: a human clicking through Seller Hub cannot sustain
# more than roughly one meaningful action per second; this just avoids
# looking unmistakably machine-paced. Tune per category, never remove.
_MIN_INTERVAL = {
    'ad_bid_update': 2.5,
    'listing_publish': 4.0,
    'end_listing': 3.0,
    'price_update': 2.0,
    'default': 2.0,
}

_last_call_at = {}


def pace(category='default'):
    """Block until at least _MIN_INTERVAL[category] seconds have passed
    since the last call in this category, plus small random jitter so a
    batch doesn't look like a metronome. Call this immediately BEFORE each
    live write in a bulk loop."""
    floor = _MIN_INTERVAL.get(category, _MIN_INTERVAL['default'])
    now = time.monotonic()
    last = _last_call_at.get(category)
    if last is not None:
        elapsed = now - last
        wait = floor - elapsed + random.uniform(0, 0.4)
        if wait > 0:
            time.sleep(wait)
    _last_call_at[category] = time.monotonic()


@contextmanager
def throttled(category='default'):
    pace(category)
    yield
