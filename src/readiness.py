"""Evidence-based readiness checks. No marketplace writes or purchases."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import ast
import json
import sys
import requests
from src.runtime import PROJECT_ROOT, read_config, writes_allowed
from src.database.models import init_database, get_session, Product, OrderLine


def classify_remaining(checks):
    """Keep unfinished code and counterparty evidence out of the user's task list."""
    result={'agent_work':[],'external_dependencies':[],'user_actions':[],'safety_controls':[]}
    user={'credentials_present','commercial_account_status','business_and_tax_setup','purchase_permission'}
    external={'supplier_agreement','automatic_supplier_payment','image_rights','supplier_product_compliance','scoped_finance_evidence'}
    for check in checks:
        if check.get('passed'):continue
        name=check.get('name')
        group=('safety_controls' if name == 'live_write_permission' else
               'user_actions' if name in user else
               'external_dependencies' if name in external else 'agent_work')
        result[group].append({'name':name,'detail':check.get('detail')})
    return result


def probe_supplier_product(client,product_id,sku_id):
    """Check a real selected SKU, not the empty aggregate fields of multi-SKU goods."""
    product=client.get_product_details(product_id)
    if not isinstance(product,dict) or str(product.get('product_id'))!=product_id:
        raise ValueError('Supplier product identity mismatch')
    skus=product.get('skus') or [product]
    if not isinstance(skus,list):raise ValueError('Invalid supplier SKU list')
    matches=[s for s in skus if isinstance(s,dict) and str(s.get('sku_id'))==sku_id]
    if len(matches)!=1:raise ValueError('Selected supplier SKU missing or ambiguous')
    sku=matches[0]
    try:
        cost=Decimal(str(sku.get('sale_price')));stock=Decimal(str(sku.get('warehouse_count')))
    except InvalidOperation:raise ValueError('Selected SKU cost or stock unavailable') from None
    if sku.get('currency',product.get('currency'))!='EUR' or not cost.is_finite() or cost<=0 or not stock.is_finite() or stock<0 or stock!=stock.to_integral_value():
        raise ValueError('Selected EUR SKU cost or stock invalid')
    return {'passed':True,'capability':'product_details_selected_sku','product_id':product_id,'sku_id':sku_id,
            'stock_known':True,'source_cost_known':True,'purchase_ready':False,'shipping_final_verified':False}


def probe_payment_execution(client=None,live=False):
    """A method or approval flag is not proof that an API payment actually worked."""
    from contextlib import closing
    import sqlite3
    if client is None:
        from src.api.aliexpress_client import AliExpressAPIClient
        client=AliExpressAPIClient()
    implemented=callable(getattr(client,'pay_order',None))
    result={'passed':False,'software_implemented':implemented,'reason':'No independently reconciled API-payment receipt',
            'settlement_amount_verified':False}
    if not implemented or not live:return result
    try:
        from src.payment_executor import PaymentExecutor
        executor=PaymentExecutor(client)
        with closing(sqlite3.connect(executor.database.as_uri()+'?mode=ro',uri=True)) as conn:
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'supplier_payment_attempts' not in tables:return result
            rows=conn.execute("SELECT supplier_order_id FROM supplier_payment_attempts WHERE state='paid' AND accepted=1 ORDER BY checked_at DESC LIMIT 3").fetchall()
        for (order_id,) in rows:
            evidence=executor.reconcile(order_id)
            if evidence.get('payment_verified') is True and evidence.get('accepted') is True and evidence.get('readback_state')=='bound_paid_time':
                return dict(result,passed=True,reason='API request and exact supplier order paid-time independently reconciled')
    except Exception as error:
        return dict(result,error_type=type(error).__name__)
    return result


def finance_policy_status(cfg):
    """Validate the category model actually used by the engine, not a legacy rate."""
    from src.finance import RULES, RESERVE_PER_UNIT, fee_quote, number
    try:
        minimum = max(Decimal('25'), number(cfg.get('MIN_PROFIT_EUR') or '25'))
        margin = max(Decimal('.25'), number(cfg.get('MIN_MARGIN_PERCENT') or '25') / 100)
        valid = bool(RULES) and minimum >= 25 and margin < 1 and RESERVE_PER_UNIT == Decimal('2')
        for root in RULES:
            quote = fee_quote('100', root)
            valid = valid and 0 < quote['gross_fee'] < 100
    except (ValueError, InvalidOperation, KeyError, TypeError):
        valid = False
    return {'passed': bool(valid), 'software_implemented': True,
            'model': 'category_scoped_commercial_forecast',
            'reserve_eur_per_unit': str(RESERVE_PER_UNIT),
            'actual_expenses_verified': False, 'checkout_evidence_required': True,
            'legacy_global_percent_required': False}


def scoped_finance_status(cfg, products):
    """Validate current engine scope/freshness without pretending source access exists."""
    result = {'passed': False, 'software_implemented': True,
              'checkout_capture_adapter_implemented': True,
              'live_checkout_layout_verified': False,
              'evidence_validated_products': 0, 'blockers': [],
              'technical_limitations': [],
              'external_access_pending': ['authenticated_checkout_browser_session_access_required']}
    path = cfg.get('FINANCE_EVIDENCE_FILE')
    if not isinstance(path, str) or not path:
        result['blockers'].append('finance_evidence_file_not_configured')
        return result
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        records = payload['records']
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError('finance_records_required')
        identities = [(row.get('product_id'), row.get('sku_id'), row.get('quantity')) for row in records]
        if len(set(identities)) != len(identities):
            raise ValueError('duplicate_or_conflicting_finance_scope')
        if not products:
            result['blockers'].append('no_vetted_product_scope')
        from src.finance_evidence import validate_scoped_record
        for product in products:
            matches = [row for row in records if row.get('product_id') == str(product.aliexpress_product_id)
                       and row.get('sku_id') == str(product.sku_id) and row.get('quantity') == 1]
            if len(matches) != 1:
                raise ValueError('unique_current_product_finance_record_required')
            validate_scoped_record(matches[0], product)
            from src.checkout_evidence import verify_record
            verify_record(matches[0], cfg)
            result['evidence_validated_products'] += 1
        if products and result['evidence_validated_products'] == len(products):
            result.update(passed=True, live_checkout_layout_verified=True, external_access_pending=[])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        from src.checkout_evidence import SourceUnavailable
        result['blockers'].append(str(error) if isinstance(error, SourceUnavailable)
                                  else 'scoped_finance_evidence_missing_invalid_or_stale')
    return result


def build_report(live=False):
    cfg = read_config()
    try:
        decisions = json.loads((PROJECT_ROOT / 'config/operator_decisions.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        decisions = {}
    checks = []
    def add(name, passed, detail):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    add('python', sys.version_info[:2] == (3, 11), 'Python 3.11 required')
    modules = [PROJECT_ROOT / 'main.py', *list((PROJECT_ROOT / 'src').rglob('*.py'))]
    syntax_errors = []
    for path in modules:
        try:
            ast.parse(path.read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError):
            syntax_errors.append(path.relative_to(PROJECT_ROOT).as_posix())
    add('runtime_syntax', not syntax_errors, syntax_errors)
    required = ['EBAY_APP_ID', 'EBAY_CERT_ID', 'EBAY_ACCESS_TOKEN', 'EBAY_REFRESH_TOKEN',
        'ALIEXPRESS_APP_KEY', 'ALIEXPRESS_APP_SECRET', 'ALIEXPRESS_ACCESS_TOKEN', 'ALIEXPRESS_REFRESH_TOKEN']
    missing = [key for key in required if not cfg.get(key)]
    add('credentials_present', not missing, missing)
    add('market', cfg.get('TARGET_MARKET') == 'DE' and cfg.get('CURRENCY') == 'EUR', 'DE / EUR only')
    policy = finance_policy_status(cfg)
    add('fee_configuration', policy['passed'], policy)
    add('supplier_agreement', str(cfg.get('SUPPLIER_AGREEMENT_CONFIRMED', '')).lower() == 'true',
        'Wholesale supplier agreement and eBay dropshipping-policy compliance require confirmation')
    add('live_write_permission', writes_allowed(cfg), 'AUTOMATION_LIVE_WRITES and supplier confirmation must be true')
    add('purchase_permission', str(cfg.get('ALLOW_ORDER_PURCHASES', '')).lower() == 'true', 'ALLOW_ORDER_PURCHASES requires explicit authorization')
    for key in ['EBAY_PAYMENT_POLICY_ID', 'EBAY_RETURN_POLICY_ID', 'EBAY_FULFILLMENT_POLICY_ID', 'EBAY_MERCHANT_LOCATION_KEY']:
        add(key.lower(), bool(cfg.get(key)) and str(cfg[key]).lower() not in {'default', 'none', 'placeholder'}, key + ' must identify a real seller resource')
    db = init_database()
    try:
        with get_session(db) as session:
            verified = session.query(Product).filter_by(fulfillment_verified=True).all()
            valid_products = [p for p in verified if p.sku_id and p.category_id and p.shipping_cost is not None and p.currency == 'EUR']
            add('vetted_products', bool(valid_products), {'verified_with_required_mapping': len(valid_products), 'total_products': session.query(Product).count()})
            unresolved = session.query(OrderLine).filter(OrderLine.status.in_(['pending', 'reserved', 'submitting', 'manual_review', 'upload_uncertain'])).count()
            add('purchase_reconciliation', unresolved == 0, {'unresolved_lines': unresolved})
            product_id = str(valid_products[0].aliexpress_product_id) if valid_products else None
            sku_id = str(valid_products[0].sku_id) if valid_products else None
            probe_scope = 'vetted_product' if valid_products else 'research_candidate_not_listing_approval'
    finally:
        db.dispose()
    finance_evidence = scoped_finance_status(cfg, valid_products)
    add('scoped_finance_evidence', finance_evidence['passed'], finance_evidence)
    if live:
        specs = {
            'ebay_inventory': ('/sell/inventory/v1/inventory_item', {'limit': 1}, None, None),
            'ebay_fulfillment': ('/sell/fulfillment/v1/order', {'limit': 1}, None, None),
            'ebay_payment_policies': ('/sell/account/v1/payment_policy', {'marketplace_id': 'EBAY_DE'}, 'paymentPolicies', 'paymentPolicyId'),
            'ebay_return_policies': ('/sell/account/v1/return_policy', {'marketplace_id': 'EBAY_DE'}, 'returnPolicies', 'returnPolicyId'),
            'ebay_fulfillment_policies': ('/sell/account/v1/fulfillment_policy', {'marketplace_id': 'EBAY_DE'}, 'fulfillmentPolicies', 'fulfillmentPolicyId'),
            'ebay_locations': ('/sell/inventory/v1/location', {'limit': 100}, 'locations', 'merchantLocationKey'),
        }
        keys = {'ebay_payment_policies': 'EBAY_PAYMENT_POLICY_ID', 'ebay_return_policies': 'EBAY_RETURN_POLICY_ID',
            'ebay_fulfillment_policies': 'EBAY_FULFILLMENT_POLICY_ID', 'ebay_locations': 'EBAY_MERCHANT_LOCATION_KEY'}
        def probe(item):
            name, (path, params, array, identifier) = item
            try:
                response = requests.get('https://api.ebay.com' + path, params=params,
                    headers={'Authorization': 'Bearer ' + str(cfg.get('EBAY_ACCESS_TOKEN', '')), 'Accept': 'application/json'}, timeout=25)
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError('Invalid eBay response envelope')
                errors = data.get('errors', [])
                ok = response.status_code == 200 and errors == []
                detail = {'http': response.status_code,
                          'error_ids': [x.get('errorId') for x in errors if isinstance(x, dict)]
                          if isinstance(errors, list) else []}
                if ok and name in ('ebay_inventory', 'ebay_fulfillment'):
                    field, identity = (('inventoryItems', 'sku') if name == 'ebay_inventory'
                                       else ('orders', 'orderId'))
                    total = data.get('total')
                    resources = data.get(field, [])
                    ok = (type(total) is int and total >= 0 and isinstance(resources, list)
                          and len(resources) <= total and (total == 0 or bool(resources))
                          and all(isinstance(row, dict) and isinstance(row.get(identity), str)
                                  and bool(row[identity].strip()) for row in resources))
                    detail['response_schema_verified'] = ok
                if ok and array:
                    resources = data.get(array)
                    if not isinstance(resources, list) or not all(isinstance(x, dict) for x in resources):
                        raise ValueError('Invalid eBay resource envelope')
                    selected = str(cfg.get(keys[name], ''))
                    match = [x for x in resources if str(x.get(identifier)) == selected]
                    ok = bool(match)
                    detail.update(available_resources=len(resources), configured_resource_found=bool(match))
                    if name == 'ebay_locations' and match:
                        ok = ok and match[0].get('merchantLocationStatus') == 'ENABLED'
                        detail['location_enabled'] = ok
                return name, ok, detail
            except Exception as error:
                return name, False, {'error_type': type(error).__name__}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, ok, detail in pool.map(probe, specs.items()):
                add(name, ok, detail)
        if not product_id:
            try:
                snapshot=json.loads((PROJECT_ROOT/'data/sourcing_expansion_prepared.json').read_text(encoding='utf-8'))
                sample=next(c for c in snapshot.get('candidates',[]) if c.get('product_id') and c.get('sku_id'))
                product_id,sku_id=sample['product_id'],sample['sku_id']
            except (OSError,ValueError,StopIteration,KeyError,TypeError):pass
        if product_id and sku_id:
            try:
                from src.api.aliexpress_client import AliExpressAPIClient
                evidence=probe_supplier_product(AliExpressAPIClient(),product_id,sku_id)
                evidence['scope']=probe_scope
                add('aliexpress_product_api', evidence['passed'], evidence)
            except Exception as error:
                add('aliexpress_product_api', False, {'error_type': type(error).__name__})
        else:
            add('aliexpress_product_api', False, 'No real product ID/SKU is available for a scoped read-only capability check')
    else:
        add('live_apis', False, 'Not tested: run main.py --live-check')
    from src.acceptance import verify_acceptance, source_fingerprint
    acceptance = verify_acceptance(live=live)
    add('controlled_end_to_end_acceptance', acceptance['passed'], acceptance)
    add('commercial_account_status', decisions.get('ebay_account_type_reported') == 'commercial',
        'Operator currently reports a private account; planned resale requires correct account/commercial setup')
    add('business_and_tax_setup', decisions.get('gewerbe_registration_status') == 'confirmed' and decisions.get('vat_status') not in (None, 'not_confirmed'),
        'Business registration and applicable tax treatment have not been established')
    payment_evidence=probe_payment_execution(live=live)
    add('automatic_supplier_payment', payment_evidence['passed'], payment_evidence)
    cap_enforced = False
    try:
        from src.automation.spending import validate_source_unit_cost
        cap = Decimal(str(cfg.get('MAX_SOURCE_UNIT_COST_EUR') or decisions.get('approved_source_unit_budget_eur', '40')))
        validate_source_unit_cost(cap, config=cfg, decisions=decisions)
        try:
            validate_source_unit_cost(cap + Decimal('0.01'), config=cfg, decisions=decisions)
        except ValueError:
            tree = ast.parse((PROJECT_ROOT / 'src/automation/engine.py').read_text(encoding='utf-8'))
            cap_enforced = any(isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == 'validate_source_unit_cost') or (isinstance(n.func, ast.Attribute) and n.func.attr == 'validate_source_unit_cost')) for n in ast.walk(tree))
    except (ImportError, AttributeError, ValueError, TypeError, InvalidOperation):
        pass
    add('source_unit_cap_enforced', cap_enforced, 'Source unit cap excludes freight/tax; runtime enforcement and regression evidence are required')
    try:
        verification = json.loads((PROJECT_ROOT / 'data/software_verification.json').read_text(encoding='utf-8'))
        verified = verification.get('passed') is True and verification.get('errors') == 0 and verification.get('failures') == 0 and verification.get('source_fingerprint') == source_fingerprint()
    except (OSError, ValueError):
        verified = False
    add('current_revision_software_tests', verified, 'Only a successful test run tied to the current source revision counts')
    blockers = [item['name'] for item in checks if not item['passed']]
    # A first supervised listing precedes its real sale/payment/dispatch evidence.
    # Excluding these post-trial requirements never overrides business, sourcing,
    # product, fee, location, API or explicit write-authorization prerequisites.
    post_trial_requirements = {'controlled_end_to_end_acceptance', 'automatic_supplier_payment', 'purchase_permission'}
    trial_blockers = [name for name in blockers if name not in post_trial_requirements]
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'ready_for_live': not blockers,
        'ready_for_supervised_trial': not trial_blockers, 'supervised_trial_blockers': trial_blockers,
        'stage_rule': 'Supervised trial can establish real order evidence before unattended commerce; it does not waive other prerequisites',
        'live_api_checks_performed': bool(live), 'mode': 'live_enabled' if writes_allowed(cfg) else 'safe_monitoring',
        'checks': checks, 'blockers': blockers, 'remaining_work': classify_remaining(checks)}


def save_report(report):
    path = PROJECT_ROOT / 'data/readiness_report.json'
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    return path
