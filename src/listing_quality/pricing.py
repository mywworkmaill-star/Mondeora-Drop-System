"""Per-variant price calculation. Uses the REAL eBay fee from .env (EBAY_FEE_PERCENT), not a hard-coded 10%.

Minimum profit/margin are TIERED by landed cost (cost+ship), not one flat floor. Grounded in real data
gathered 2026-11-12: industry benchmarks (nichedropshipping.com, velocityspy.com) report net margins of
15-30% and 2.5-3.75x markup multipliers for sub-$15 landed-cost items - a flat EUR25 absolute floor on a
EUR2-5 AliExpress item meant a 10-17x multiplier, which priced 6 real niche products 46-74% above the
REAL eBay.de competitor median (checked that day via gates.demand()). The tier boundaries/values below
were chosen so the resulting price lands at-or-near those real medians instead of a one-size rule.
"""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (landed_cost upper bound EXCLUSIVE, min_profit EUR, min_margin fraction) - first matching bound wins,
# ordered low to high. Cheap items lean on a smaller absolute floor + a higher margin fraction (fee drag
# hits cheap items harder - "fee asymmetry"); the top tier (>= EUR25 landed) keeps the original EUR25/25%
# rule, which is already proportionate at that cost level.
TIERS = (
    (10.0, 15.0, 0.35),
    (25.0, 20.0, 0.30),
    (float('inf'), 25.0, 0.25),
)

# Pre-2026-11-12 flat rule, kept ONLY for products grandfathered via config/price_pinned_products.json.
LEGACY_MIN_PROFIT, LEGACY_MIN_MARGIN = 25.0, 0.25


def _env():
    try:
        from dotenv import dotenv_values
        return dotenv_values(ROOT / '.env')
    except Exception:
        return {}


def settings():
    e = _env()
    return {'fee_pct': float(e.get('EBAY_FEE_PERCENT') or 13.5), 'fixed_fee': 0.35}


def is_pinned(aliexpress_product_id):
    """True if this product is grandfathered at the pre-tiered flat EUR25/25% rule
    (config/price_pinned_products.json) - the user chose 2026-11-12 to apply tiering only to
    NEW listings, leaving already-live ones at their existing price/formula."""
    import json
    try:
        data = json.loads((ROOT / 'config' / 'price_pinned_products.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return str(aliexpress_product_id) in {str(p) for p in data.get('pinned', [])}


def tier_minimums(landed_cost):
    """landed_cost = cost + shipping, before fees. Returns (min_profit EUR, min_margin fraction)."""
    for upper, profit, margin in TIERS:
        if landed_cost < upper:
            return profit, margin
    return TIERS[-1][1], TIERS[-1][2]


def net_profit(price, cost, ship, cfg=None):
    cfg = cfg or settings()
    return price * (1 - cfg['fee_pct'] / 100) - cfg['fixed_fee'] - cost - ship


def price_for(cost, ship, cfg=None, legacy=False):
    """Smallest x.99 price that gives net >= the tiered min_profit AND net/price >= the tiered min_margin
    for this item's own landed cost (cost + ship) - see TIERS. legacy=True forces the pre-tiering flat
    EUR25/25% rule instead (grandfathered products only - see is_pinned())."""
    cfg = cfg or settings()
    min_profit, min_margin = (LEGACY_MIN_PROFIT, LEGACY_MIN_MARGIN) if legacy else tier_minimums(cost + ship)
    keep = 1 - cfg['fee_pct'] / 100
    need = max((cost + ship + cfg['fixed_fee'] + min_profit) / keep,
               (cost + ship + cfg['fixed_fee']) / (keep - min_margin))
    price = math.floor(need) + 0.99
    if price < need:
        price += 1
    price = round(price, 2)
    return price, round(net_profit(price, cost, ship, cfg), 2)
