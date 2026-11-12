"""Project-local configuration and fail-closed live operation controls."""
from pathlib import Path
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_forced_read_only = False

def enable_read_only():
    """Monotonic process-level safety latch; .env/config cannot override it."""
    global _forced_read_only
    _forced_read_only = True

def read_config():
    """The project's .env is authoritative; never use a stale loaded token."""
    return dict(dotenv_values(PROJECT_ROOT / '.env'))

def writes_allowed(config=None):
    if _forced_read_only:
        return False
    cfg = read_config() if config is None else config
    return all(str(cfg.get(k, '')).lower() == 'true' for k in (
        'AUTOMATION_LIVE_WRITES', 'SUPPLIER_AGREEMENT_CONFIRMED'))

def require_writes(config=None, purchase=False):
    cfg = read_config() if config is None else config
    if not writes_allowed(cfg):
        raise RuntimeError('Canli islemler kapali veya tedarikci anlasmasi dogrulanmamis.')
    if purchase and str(cfg.get('ALLOW_ORDER_PURCHASES', '')).lower() != 'true':
        raise RuntimeError('Ucretli siparis yetkisi kapali.')
