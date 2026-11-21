"""Read-only, evidence-aware prepared listing artifacts. Never publishes or edits products."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from copy import deepcopy
import hashlib
import json
import math
import re

from src import runtime
from src.listing_quality import categories, gates, pricing, publish, source


_CONTEXT_KEYS = {
    'fulfillmentPolicyId': 'EBAY_FULFILLMENT_POLICY_ID',
    'paymentPolicyId': 'EBAY_PAYMENT_POLICY_ID',
    'returnPolicyId': 'EBAY_RETURN_POLICY_ID',
    'merchantLocationKey': 'EBAY_MERCHANT_LOCATION_KEY',
}
_CONFIG_FILES = ('risk_rules.json', 'risk_ack.json', 'category_overrides.json',
                 'price_pinned_products.json', 'finance_policy.json')


def publication_context():
    """Only the configured eBay policy/location identifiers; never credentials."""
    cfg = runtime.read_config()
    return {key: cfg.get(env_key) for key, env_key in _CONTEXT_KEYS.items()}


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def config_fingerprint():
    """Fingerprint policy/risk/category/pricing inputs, never .env credential bytes."""
    cfg = runtime.read_config()
    files = {}
    for name in _CONFIG_FILES:
        try:
            files[name] = hashlib.sha256((runtime.PROJECT_ROOT / 'config' / name).read_bytes()).hexdigest()
        except FileNotFoundError:
            files[name] = None
    return _digest({'publication_context': publication_context(), 'config_files': files,
                    'fee_percent': cfg.get('EBAY_FEE_PERCENT'), 'pricing': pricing.settings(),
                    'tiers': [[str(upper), profit, margin] for upper, profit, margin in pricing.TIERS],
                    'legacy': [pricing.LEGACY_MIN_PROFIT, pricing.LEGACY_MIN_MARGIN]})


_LISTING_ONLY_IGNORED = {'controlled_end_to_end_acceptance', 'automatic_supplier_payment'}
MAX_EVIDENCE_AGE = timedelta(hours=24)


def _utc(value=None):
    value = datetime.now(timezone.utc) if value is None else value
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def _check_name(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_]{1,100}', value) is not None


def readiness_blockers(readiness, now=None):
    """Check the live summary, all relevant checks and a maximum 24-hour report age.

    Only payment execution and the post-sale end-to-end acceptance are out of
    scope here. Ignoring those checks does not turn a false live summary true.
    
    NEW: Includes automated quality gates for title, images, description, 
    item specifics, and category confidence.
    """
    if not isinstance(readiness, dict):
        return ['readiness_report_missing']
    blockers = []
    if readiness.get('ready_for_live') is not True:
        blockers.append('readiness_not_ready_for_live')
    try:
        age = _utc(now) - _utc(readiness.get('generated_at') or '')
        if age < timedelta(0):
            blockers.append('readiness_report_from_future')
        elif age > MAX_EVIDENCE_AGE:
            blockers.append('readiness_report_stale')
    except (ValueError, TypeError, OverflowError):
        blockers.append('readiness_report_timestamp_invalid')
    checks = readiness.get('checks')
    if not isinstance(checks, list):
        blockers.append('readiness_checks_invalid')
    elif not checks:
        blockers.append('readiness_checks_missing')
    else:
        for check in checks:
            if not isinstance(check, dict) or not _check_name(check.get('name')):
                blockers.append('readiness_checks_invalid')
                continue
            name = check['name']
            if name not in _LISTING_ONLY_IGNORED and check.get('passed') is not True:
                blockers.append('readiness_' + name)
    reported = readiness.get('blockers', [])
    if not isinstance(reported, list):
        blockers.append('readiness_checks_invalid')
    else:
        for name in reported:
            if not _check_name(name):
                blockers.append('readiness_checks_invalid')
            elif name not in _LISTING_ONLY_IGNORED:
                blockers.append('readiness_' + name)
    return list(dict.fromkeys(blockers))


# Conservative defaults: only authenticated scoped document review can discharge
# its own requirements. Demand and full cost/profit need independent sources.
_MISSING_EVIDENCE = (
    'supplier_product_compliance_unverified', 'supplier_agreement_missing',
    'manufacturer_eu_responsible_person_missing', 'image_rights_unverified',
    'dispatch_origin_unverified', 'demand_unverified', 'complete_cost_profit_unverified',
)


def _number(value, *, positive=False, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(value, bool) or not math.isfinite(number) or (number <= 0 if positive else number < 0):
        return None
    return number if not integer or number.is_integer() else None


def _current_skus(details, pid):
    if not isinstance(details, dict) or str(details.get('product_id')) != pid:
        return {}, 'supplier_product_identity_mismatch'
    rows = details.get('skus')
    if not isinstance(rows, list):
        return {}, 'no_current_in_stock_eur_sku'
    eligible, seen = {}, set()
    for sku in rows:
        if not isinstance(sku, dict):
            continue
        sid = str(sku.get('sku_id') or '')
        if sid in seen:
            return {}, 'supplier_sku_identity_ambiguous'
        seen.add(sid)
        if (re.fullmatch(r'[0-9]{6,}', sid)
                and sku.get('currency', details.get('currency')) == 'EUR'
                and _number(sku.get('sale_price'), positive=True) is not None
                and _number(sku.get('warehouse_count'), positive=True, integer=True) is not None):
            eligible[sid] = sku
    return eligible, None if eligible else 'no_current_in_stock_eur_sku'


def _quote_problem(quote, pid, sku, now=None):
    if (not isinstance(quote, dict)
            or str(quote.get('product_id')) != pid or str(quote.get('sku_id')) != sku
            or type(quote.get('quantity')) is not int or quote['quantity'] != 1
            or quote.get('ship_to_country') != 'DE' or quote.get('currency') != 'EUR'):
        return 'freight_scope_mismatch'
    if _number(quote.get('cost')) is None:
        return 'freight_cost_invalid'
    service = quote.get('service_name')
    if not isinstance(service, str) or not service.strip():
        return 'freight_service_unverified'
    try:
        age = _utc(now) - _utc(quote.get('quoted_at') or '')
        if age < timedelta(0):
            return 'freight_quote_from_future'
        if age > MAX_EVIDENCE_AGE:
            return 'freight_quote_stale'
    except (ValueError, TypeError, OverflowError):
        return 'freight_timestamp_invalid'
    if quote.get('is_estimate') is not True or quote.get('transaction_ready') is not False:
        return 'freight_evidence_level_invalid'
    return None


def _content_failure(error):
    # Classify known gate messages without persisting supplier text, URLs or tokens.
    reason = 'content_unavailable'
    message = str(error)
    for prefix, code in (
        ('IDENTITY MISMATCH', 'identity_mismatch'), ('GATE REVIEW', 'gate_review'),
        ('GATE BLOCK', 'gate_block'), ('category not approved', 'category_unapproved'),
        ('no candidate category fit', 'category_aspects_incomplete'),
        ('no sellable variants', 'no_sellable_variants'), ('needs human review', 'variant_review'),
    ):
        if message.startswith(prefix):
            reason = code
            break
    return 'content_gate_failed:' + type(error).__name__ + ':' + reason


def _read_quote(ali, pid, sku, blockers, now=None):
    try:
        quote = ali.get_shipping_quote(pid, sku, quantity=1, ship_to_country='DE')
    except Exception as error:
        blockers.append('freight_unavailable:' + type(error).__name__)
        return None
    problem = _quote_problem(quote, pid, sku, now=now)
    if problem:
        blockers.append(problem)
        return None
    return quote


def _sanitize(value):
    """Keep product content/raw facts, dropping only credential-bearing field names."""
    secret_names = {'accesstoken', 'refreshtoken', 'appsecret', 'clientsecret', 'password',
                    'authorization', 'cookie', 'setcookie', 'token', 'apikey', 'appkey'}
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()
                if re.sub(r'[^a-z]', '', str(key).lower()) not in secret_names}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, Decimal):
        # API amounts are JSON numbers; never stringify freight into a value that
        # cannot be compared to the next current supplier response.
        number = float(value)
        return number if math.isfinite(number) else str(value)
    return value


def build_prepared(ali, ebay, product_row, *, readiness, now=None):
    """Build a full gated draft and retain it even when publication evidence is missing.

    The returned blockers are stable codes, not approval flags. Freight is an
    explicitly scoped supplier forecast, never final checkout/payment evidence.
    """
    observed = _utc(now)
    row = dict(product_row)
    pid = str(row.get('aliexpress_product_id') or '')
    blockers = readiness_blockers(readiness, now=observed) + list(_MISSING_EVIDENCE)
    result = {'product_id': pid, 'artifact': None, 'blockers': blockers}
    if not re.fullmatch(r'[0-9]{6,}', pid):
        blockers.append('product_id_invalid')
        return result
    if row.get('is_listed') not in (0, False, None, '0', '') or row.get('ebay_item_id'):
        blockers.append('already_listed')
        return result
    initial_config = None
    try:
        initial_config = config_fingerprint()
    except Exception as error:
        blockers.append('preparation_config_unavailable:' + type(error).__name__)
    try:
        details = ali.get_product_details(pid)
    except Exception as error:
        blockers.append('supplier_details_failed:' + type(error).__name__)
        return result
    current_skus, problem = _current_skus(details, pid)
    if problem:
        blockers.append(problem)
        return result
    anchor = next(iter(current_skus))
    quote = _read_quote(ali, pid, anchor, blockers, now=now)
    if quote is None:
        return result
    try:
        st = deepcopy(publish.plan_for(ali, ebay, pid, float(quote['cost']), db_title=row.get('title')))
    except Exception as error:
        blockers.append(_content_failure(error))
        return result
    if str(st['res']['ae_item_base_info_dto'].get('product_id')) != pid:
        blockers.append('content_source_product_identity_mismatch')
    quotes = {}
    changed = False
    legacy = pricing.is_pinned(pid)
    for variant in st['plan']['variants']:
        sku = str(variant['sku_id'])
        if not re.fullmatch(r'[0-9]{6,}', sku):
            blockers.append('retained_sku_id_invalid')
            continue
        if sku not in current_skus:
            blockers.append('variant_source_unverified')
        elif (_number(variant.get('cost'), positive=True) != _number(current_skus[sku]['sale_price'], positive=True)
              or _number(variant.get('stock'), positive=True, integer=True)
              != _number(current_skus[sku]['warehouse_count'], positive=True, integer=True)):
            blockers.append('variant_source_changed')
        current = quote if sku == anchor else _read_quote(ali, pid, sku, blockers, now=now)
        if current is None:
            continue
        quotes[sku] = deepcopy(current)
        try:
            price, net = pricing.price_for(float(variant['cost']), float(current['cost']), legacy=legacy)
            if _number(price, positive=True) is None or _number(net) is None:
                blockers.append('variant_pricing_invalid')
                continue
            changed = changed or variant['price'] != price
            variant.update(price=price, net=net)
        except Exception as error:
            blockers.append('variant_pricing_failed:' + type(error).__name__)
        if current.get('is_estimate') or current.get('transaction_ready') is not True:
            blockers.append('freight_estimate_only')
    if changed:
        try:
            subject = st['res']['ae_item_base_info_dto']['subject']
            info, review = gates.demand(ebay, categories.queries(subject, source.properties(st['res'])),
                                        min(v['price'] for v in st['plan']['variants']))
            st['gates'].update(demand=info, demand_review=review)
            if review and 'demand' not in gates.acknowledged(pid):
                blockers.append('repriced_market_review_required')
        except Exception as error:
            blockers.append('repriced_market_unavailable:' + type(error).__name__)
    
    # Validate the actual saved publication fields, never the nested variant plan.
    try:
        quality_warnings = []
        def add_quality(name, problems):
            for problem in problems:
                if name == 'images' and problem.startswith('below ideal image count'):
                    quality_warnings.append(problem)
                else:
                    blockers.append('quality_' + name + ':' + problem.replace(' ', '_').replace(':', '-'))

        add_quality('title', gates.check_title_quality(st['title']))
        problems, info = gates.check_description_quality(st['desc'])
        add_quality('description', problems)
        quality = {'description': info, 'variants': [], 'warnings': quality_warnings}
        problems, info = gates.check_category_confidence(st['cat'])
        add_quality('category', problems)
        quality['category'] = info
        for variant in st['plan']['variants']:
            # This is exactly the per-variant gallery/aspect merge compiled for eBay.
            gallery = ([variant['image']] if variant.get('image') else []) + [
                url for url in st['imgs'] if url != variant.get('image')]
            gallery = list(dict.fromkeys(gallery))[:12]
            problems, image_info = gates.check_image_count(gallery)
            add_quality('images', problems)
            aspects = {**st['shared'], **{key: [value] for key, value in variant['aspects'].items()}}
            problems, aspect_info = gates.check_item_specifics_count(aspects)
            add_quality('aspects', problems)
            quality['variants'].append({'sku_id': variant['sku_id'],
                                        'images': image_info, 'aspects': aspect_info})
        st['gates']['quality'] = quality
    except Exception as error:
        blockers.append('quality_gates_failed:' + type(error).__name__)
    try:
        context = publication_context()
    except Exception as error:
        blockers.append('publication_context_unavailable:' + type(error).__name__)
        context = dict.fromkeys(_CONTEXT_KEYS)
    final_config = None
    try:
        final_config = config_fingerprint()
        if initial_config is not None and final_config != initial_config:
            blockers.append('preparation_config_changed')
    except Exception as error:
        blockers.append('preparation_config_unavailable:' + type(error).__name__)
    if any(not isinstance(value, str) or not value.strip()
           or value.casefold() in {'default', 'none', 'placeholder', 'default-warehouse'}
           for value in context.values()):
        blockers.append('publication_context_incomplete')
    st = _sanitize(st)
    from src.listing_quality import listing_evidence
    document_evidence = listing_evidence.verify_product(pid, st, now=observed)
    # Only authenticated product/SKU/content-scoped document reviews can discharge
    # their own requirements. Never waive finance, demand, risk or readiness here.
    if 'source' not in document_evidence['errors']:
        satisfied = set(document_evidence['satisfied_blockers'])
        blockers = [reason for reason in blockers if reason not in satisfied]
    artifact = {'st': st, 'shipping_quotes': _sanitize(quotes), 'publication_context': context,
                'observed_at': observed.isoformat(), 'config_fingerprint': initial_config or final_config,
                'source_fingerprint': _digest(json.loads(json.dumps(st, default=str))),
                'document_evidence': document_evidence}
    return {'product_id': pid, 'artifact': artifact, 'blockers': list(dict.fromkeys(blockers))}
