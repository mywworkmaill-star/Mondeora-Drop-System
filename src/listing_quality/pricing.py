"""Per-variant price calculation. Uses the REAL eBay fee from .env (EBAY_FEE_PERCENT), not a hard-coded 10%."""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env():
    try:
        from dotenv import dotenv_values
        return dotenv_values(ROOT / '.env')
    except Exception:
        return {}


def settings():
    e = _env()
    return {'fee_pct': float(e.get('EBAY_FEE_PERCENT') or 13.5), 'fixed_fee': 0.35,
            'min_profit': max(25.0, float(e.get('MIN_PROFIT_EUR') or 25)),
            'min_margin': max(0.25, float(e.get('MIN_MARGIN_PERCENT') or 25) / 100)}


def net_profit(price, cost, ship, cfg=None):
    cfg = cfg or settings()
    return price * (1 - cfg['fee_pct'] / 100) - cfg['fixed_fee'] - cost - ship


def price_for(cost, ship, cfg=None):
    """Smallest x.99 price that gives net >= min_profit AND net/price >= min_margin."""
    cfg = cfg or settings()
    keep = 1 - cfg['fee_pct'] / 100
    need = max((cost + ship + cfg['fixed_fee'] + cfg['min_profit']) / keep,
               (cost + ship + cfg['fixed_fee']) / (keep - cfg['min_margin']))
    price = math.floor(need) + 0.99
    if price < need:
        price += 1
    price = round(price, 2)
    return price, round(net_profit(price, cost, ship, cfg), 2)
