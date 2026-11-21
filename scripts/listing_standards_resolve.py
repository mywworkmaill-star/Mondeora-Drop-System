"""Thin CLI for the bounded real-evidence listing-review-queue resolver.

Calls src.listing_quality.standards_resolve.resolve_cycle directly (ad hoc/manual runs);
src.jobs.job_listing_standards_resolve is the scheduled entrypoint. Defaults to a safe
dry run -- pass --live to actually PUT the computed aspect merges to eBay.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.listing_quality.standards_resolve import resolve_cycle  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bounded real-evidence listing review queue resolver')
    parser.add_argument('--max-items', type=int, default=20)
    parser.add_argument('--max-seconds', type=float, default=75)
    parser.add_argument('--live', action='store_true', help='Perform real PUT writes (default: dry run)')
    args = parser.parse_args(argv)
    from src.api.aliexpress_client import AliExpressAPIClient
    from src.api.ebay_client import eBayAPIClient
    summary = resolve_cycle(eBayAPIClient(), AliExpressAPIClient(), ROOT, max_items=args.max_items,
                            max_seconds=args.max_seconds, remote_mutations=args.live)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get('status') != 'failed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
