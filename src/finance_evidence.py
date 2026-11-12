"""Read-only finance source collection. Never creates orders or invents checkout costs.

Supplier contract: aliexpress.trade.ds.order.get, documented user_order_amount
and child_order_list.ae_child_order_info.product_price in user currency.
An existing order total is NOT a final freight/VAT/import breakdown. This adapter
stages the exact response and stays blocked until a documented scoped checkout
source exists. No arbitrary JSON import or manual verified:true promotion.

CLI: python -m src.finance_evidence (safe missing-precondition report).
Existing-order reads require a persisted unique supplier-order binding. Raw
readbacks may contain customer information: keep optional --receipt output local.
"""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from src.finance import number

SUPPLIER_METHOD = 'aliexpress.trade.ds.order.get'
SUPPLIER_DOC = ('https://openservice.aliexpress.com/doc/api.htm?cid=20900'
                '#/api?cid=21038&path=aliexpress.trade.ds.order.get&methodType=GET/POST')


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _identity(value):
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 160 or any(ord(c) < 32 for c in value):
        raise ValueError('exact_identity_required')
    return value


def _eur(value):
    if not isinstance(value, dict) or value.get('currency_code') != 'EUR':
        raise ValueError('authoritative_eur_amount_required')
    return str(number(value.get('amount')))


def inspect_supplier_order(client, scope):
    """Only get_order; caller must bind the known order to its persisted line."""
    for field in ('supplier_order_id', 'product_id', 'sku_id'):
        _identity(scope.get(field))
    if not re.fullmatch(r'[0-9]+', scope['supplier_order_id']):
        raise ValueError('numeric_supplier_order_id_required')
    if type(scope.get('quantity')) is not int or not 1 <= scope['quantity'] <= 10000:
        raise ValueError('positive_integer_quantity_required')
    raw = client.get_order(scope['supplier_order_id'])
    if not isinstance(raw, dict) or str(raw.get('order_id')) != scope['supplier_order_id'] or not raw.get('order_status'):
        raise ValueError('supplier_order_identity_mismatch')
    children = raw.get('child_order_list')
    if isinstance(children, dict):
        children = children.get('ae_child_order_info')
    if not isinstance(children, list) or len(children) != 1 or not isinstance(children[0], dict):
        raise ValueError('unique_documented_child_required')
    child = children[0]
    count = child.get('product_count')
    if isinstance(count, str) and count.isascii() and count.isdigit():
        count = int(count)
    if (str(child.get('product_id')) != scope['product_id'] or child.get('sku_id') != scope['sku_id']
            or type(count) is not int or count != scope['quantity'] or child.get('end_reason')):
        raise ValueError('supplier_child_scope_mismatch')
    total, unit = _eur(raw.get('user_order_amount')), _eur(child.get('product_price'))
    if number(total) <= 0 or number(unit) <= 0 or number(unit) * count > number(total):
        raise ValueError('supplier_amounts_inconsistent')
    observed = datetime.now(timezone.utc).isoformat()
    return {'status': 'blocked', 'software_implemented': True, 'read_only': True,
            'engine_evidence_written': False, 'scope': dict(scope),
            'provenance': {'kind': 'authenticated_supplier_order_readback', 'method': SUPPLIER_METHOD,
                           'source_url': 'https://api-sg.aliexpress.com/sync',
                           'documentation': SUPPLIER_DOC, 'observed_at': observed,
                           'hash_semantics': 'sha256_canonical_json_utf8', 'sha256': sha256(_canonical(raw)).hexdigest()},
            'raw_response': raw,
            'observed_amounts': {'supplier_order_total': total, 'unit_source': unit,
                                 'shipping_total': None, 'source_tax_total': None,
                                 'additional_import_cost': None},
            'amount_semantics': {'supplier_order_total': 'user_order_amount in user pay currency; not a freight or VAT breakdown',
                                 'unit_source': 'child product_price; VAT inclusion not established'},
            'blockers': ['final_checkout_postcode_not_established', 'source_vat_semantics_unknown',
                         'final_shipping_breakdown_unknown', 'additional_import_cost_unknown'],
            'standalone_unattended_checkout': False}


def _fresh(value):
    try:
        observed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if observed.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 86400:
            raise ValueError('stale_or_future_finance_source')
    except (TypeError, AttributeError):
        raise ValueError('timezone_aware_source_timestamp_required') from None
    return observed


def validate_supplier_receipt(receipt):
    """Integrity/scope validation, NOT proof that an imported file is authentic.

    There is deliberately no import-to-checkout promotion path. Only fresh
    get_order results are collected by the CLI; a self-authored receipt cannot
    satisfy the engine's final checkout requirement.
    """
    if not isinstance(receipt, dict):
        raise ValueError('supplier_receipt_required')
    provenance = receipt.get('provenance', {})
    if (provenance.get('kind') != 'authenticated_supplier_order_readback'
            or provenance.get('method') != SUPPLIER_METHOD
            or provenance.get('source_url') != 'https://api-sg.aliexpress.com/sync'
            or provenance.get('documentation') != SUPPLIER_DOC
            or provenance.get('hash_semantics') != 'sha256_canonical_json_utf8'):
        raise ValueError('documented_readback_provenance_required')
    _fresh(provenance.get('observed_at'))
    raw = receipt.get('raw_response')
    if sha256(_canonical(raw)).hexdigest() != provenance.get('sha256'):
        raise ValueError('source_hash_mismatch')
    class StoredRead:
        def get_order(self, order_id):
            return raw
    expected = inspect_supplier_order(StoredRead(), receipt.get('scope', {}))
    if any(receipt.get(key) != expected[key] for key in
           ('status', 'read_only', 'engine_evidence_written', 'observed_amounts', 'amount_semantics', 'blockers', 'standalone_unattended_checkout')):
        raise ValueError('readback_semantics_or_scope_mismatch')
    return {'passed': True, 'integrity_verified': True, 'provider_authenticity_independently_verified': False,
            'final_checkout_verified': False, 'status': 'blocked'}


def validate_scoped_record(record, product, *, quantity=1, postal_code=None):
    """Validate engine-compatible schema, never certify a self-authored source.

    A successful result means structural/current-price validation only. Source
    authenticity and category ancestry require independent provider readback.
    Unknown import costs, missing VAT semantics and gross/net double-counting
    must not be promoted into an engine input.
    """
    from src.finance import RULES
    if not isinstance(record, dict):
        raise ValueError('scoped_finance_record_required')
    expected = {'product_id': str(product.aliexpress_product_id), 'sku_id': str(product.sku_id),
                'category_id': str(product.category_id), 'currency': 'EUR', 'ship_to_country': 'DE',
                'category_source': 'verified_ebay_category_mapping', 'cost_source': 'supplier_checkout'}
    if any(record.get(key) != value for key, value in expected.items()) or product.currency != 'EUR':
        raise ValueError('finance_identity_category_currency_or_destination_mismatch')
    if (type(quantity) is not int or not 1 <= quantity <= 10000
            or type(record.get('quantity')) is not int or record['quantity'] != quantity):
        raise ValueError('finance_quantity_mismatch')
    postcode = record.get('ship_to_postal_code')
    if not isinstance(postcode, str) or not re.fullmatch(r'[0-9]{5}', postcode) or (postal_code is not None and postcode != postal_code):
        raise ValueError('exact_germany_postcode_required')
    if record.get('category_root') not in RULES:
        raise ValueError('unsupported_category_tariff')
    for field in ('category_evidence_reference', 'cost_evidence_reference'):
        _identity(record.get(field))
    _fresh(record.get('observed_at'))
    unit = number(record.get('unit_source'))
    if unit <= 0 or unit != number(product.aliexpress_price):
        raise ValueError('current_supplier_price_mismatch')
    for field in ('shipping_total', 'source_tax_total', 'additional_import_cost'):
        if record.get(field) is None:
            raise ValueError('explicit_complete_cost_amount_required')
        number(record[field])
    semantics = record.get('source_vat_semantics')
    if semantics == 'included_in_unit_source':
        if number(record['source_tax_total']) != 0:
            raise ValueError('included_source_vat_must_not_be_added_twice')
    elif semantics != 'excluded_from_unit_source_explicit_tax_total':
        raise ValueError('explicit_source_vat_semantics_required')
    if record.get('import_cost_scope') != 'all_additional_import_costs_explicit':
        raise ValueError('explicit_complete_import_scope_required')
    return {'schema_valid': True, 'source_authenticated': False, 'ready_for_purchase': False}


def stage_supplier_receipt(path, receipt):
    """Atomic append to source_receipts, NEVER records/order_records promotion.

    Existing engine records and all unrelated top-level fields survive. An
    exclusive sidecar lock serializes this writer; duplicate order identities
    and conflicting readbacks hold instead of silently replacing history.
    """
    import os
    import tempfile
    validate_supplier_receipt(receipt)
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.finance-evidence.lock')
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('evidence_writer_busy_or_interrupted_lock_requires_review') from None
    temporary = None
    try:
        os.close(descriptor)
        if path.exists():
            payload = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('finance_evidence_object_required')
        else:
            payload = {'records': [], 'order_records': []}
        rows = payload.get('source_receipts', [])
        if not isinstance(rows, list):
            raise ValueError('source_receipts_list_required')
        identifiers = []
        for row in rows:
            validate_supplier_receipt(row)
            identifiers.append(row['scope']['supplier_order_id'])
        if len(set(identifiers)) != len(identifiers) or receipt['scope']['supplier_order_id'] in identifiers:
            raise ValueError('duplicate_or_conflicting_source_receipt')
        payload['source_receipts'] = rows + [receipt]
        descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(_canonical(payload))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return {'status': 'blocked', 'source_receipt_staged': True, 'engine_evidence_written': False}


def _persisted_scope(database, supplier_order_id):
    """Read-only URI never creates/migrates an order ledger."""
    import sqlite3
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''SELECT l.aliexpress_order_id AS supplier_order_id,
            l.ebay_order_id, l.ebay_line_item_id, l.quantity,
            p.aliexpress_product_id AS product_id, p.sku_id
            FROM order_lines l JOIN products p ON p.id=l.product_id
            WHERE l.aliexpress_order_id=?''', (supplier_order_id,)).fetchall()
    if len(rows) != 1:
        raise ValueError('unique_persisted_supplier_order_binding_required')
    return dict(rows[0])


def _database_path(cfg):
    from sqlalchemy.engine import make_url
    from src.runtime import PROJECT_ROOT
    url = make_url(cfg.get('DATABASE_URL') or 'sqlite:///' + (PROJECT_ROOT / 'data/dropshipping.db').as_posix())
    if url.drivername != 'sqlite' or not url.database or url.database == ':memory:':
        raise ValueError('durable_sqlite_order_ledger_required')
    path = Path(url.database)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main(argv=None):
    import argparse
    from src.runtime import read_config, enable_read_only
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--supplier-order-id', help='Existing persisted supplier order only; never creates one')
    args = parser.parse_args(argv)
    enable_read_only()
    result = {'status': 'blocked', 'read_only': True, 'engine_evidence_written': False,
              'software_implemented': True, 'standalone_unattended_checkout': False,
              'blockers': ['persisted_supplier_order_required'],
              'technical_limitations': ['documented_postcode_scoped_checkout_breakdown_adapter_not_available'],
              'external_access_pending': ['actual_scoped_checkout_source_not_observed'],
              'browser_capture_status': 'not_verified_no_login_assumption'}
    if args.supplier_order_id:
        try:
            cfg = read_config()
            scope = _persisted_scope(_database_path(cfg), args.supplier_order_id)
            from src.api.aliexpress_client import AliExpressAPIClient
            result = inspect_supplier_order(AliExpressAPIClient(), scope)
            validate_supplier_receipt(result)
            # Deliberately do not print raw supplier/customer data.
            result = {key: value for key, value in result.items() if key not in ('raw_response', 'scope')}
        except Exception as error:
            result['blockers'] = ['existing_order_readback_unavailable']
            result['error_type'] = type(error).__name__
            if isinstance(error, ValueError) and re.fullmatch(r'[a-z_]+', str(error)):
                result['reason'] = str(error)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
