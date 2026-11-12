"""Source-unit ceiling, not a daily budget. No payment credentials belong here."""
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


def money(value, positive=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid EUR amount') from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError('EUR amount must be finite and positive' if positive else 'EUR amount must be finite and nonnegative')
    return number


def supervised_claim(config, order_id, line_id, product_id, sku_id, quantity, *, consume=False, now=None):
    """Require exact, unexpired supervision for EVERY create; never issue approvals.

    JSON: {"approvals": [{"supervised": true, "ebay_order_id": "...",
    "ebay_line_item_id": "...", "product_id": "...", "sku_id": "...",
    "quantity": 1, "expires_at": "...+00:00"}]}.
    Tests inject this same local-file schema in isolated temporary directories.
    Exclusive durable claims beside the file are not credentials. A consumed
    claim or pending DB reservation requires manual reconciliation, not retry.
    """
    from datetime import datetime, timezone
    from hashlib import sha256
    import os
    path = config.get('SUPERVISED_PURCHASE_APPROVAL_FILE')
    if not path:
        raise ValueError('Exact supervised purchase approval required')
    path = Path(path).resolve()
    approvals = json.loads(path.read_text(encoding='utf-8'))['approvals']
    if not isinstance(approvals, list):
        raise ValueError('Invalid supervised approvals')
    now = now or datetime.now(timezone.utc)
    scope = {'ebay_order_id': order_id, 'ebay_line_item_id': line_id,
             'product_id': product_id, 'sku_id': sku_id, 'quantity': quantity}
    matches = [a for a in approvals if isinstance(a, dict) and a.get('supervised') is True
               and all(a.get(k) == v and type(a.get(k)) is type(v) for k, v in scope.items())]
    if len(matches) != 1:
        raise ValueError('Supervised authorization scope missing or ambiguous')
    expiry = datetime.fromisoformat(matches[0]['expires_at'].replace('Z', '+00:00'))
    if expiry.tzinfo is None or expiry <= now:
        raise ValueError('Supervised authorization expired or lacks timezone')
    key = sha256(json.dumps([order_id, line_id], separators=(',', ':')).encode()).hexdigest()
    directory = path.parent / '.supervised_purchase_claims'
    claim = directory / key
    if not consume:
        if claim.exists():
            raise ValueError('Supervised authorization already consumed')
        return
    directory.mkdir(exist_ok=True)
    fd = os.open(str(claim), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump({'claimed_at': now.isoformat(), 'scope': scope}, handle)
        handle.flush()
        os.fsync(handle.fileno())


def unit_cost_limit(config=None, decisions=None):
    """Read fresh live config/recorded choices; default ceiling is fail-closed EUR40."""
    if config is None:
        from src.runtime import read_config
        config = read_config()
    if decisions is None:
        path = Path(config.get('OPERATOR_DECISIONS_FILE') or
                    Path(__file__).resolve().parents[2] / 'config/operator_decisions.json')
        decisions = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    value = config.get('MAX_SOURCE_UNIT_COST_EUR', decisions.get('approved_source_unit_budget_eur', '40'))
    if decisions and decisions.get('unit_budget_includes_shipping_and_tax') is not False:
        raise ValueError('Source-unit budget scope must exclude freight and tax')
    return min(money(value, positive=True), Decimal('40'))


def source_unit_cap(config):
    return unit_cost_limit(config)


def validate_source_unit_cost(amount, config=None, decisions=None):
    number = money(amount, positive=True)
    if number > unit_cost_limit(config, decisions):
        raise ValueError('Source-unit EUR ceiling exceeded')
    return number



def validate_source_unit(value, config, currency='EUR'):
    if currency != 'EUR':
        raise ValueError('Verified source currency must be EUR')
    number = money(value, positive=True)
    if number > source_unit_cap(config):
        raise ValueError('Source-unit EUR ceiling exceeded')
    return number
