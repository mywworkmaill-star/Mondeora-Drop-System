"""Bounded, read-only recurring standards review (never a repair/publish path).

Only audit JSON is written. Checkpoint is the authoritative transaction: report
and queue are recoverable projections, and are never used to resolve old tasks.
A production eBay client is read through its session, WITHOUT _request's OAuth
POST/retry/logging path. Injected clients must implement GET-only _request.
max_seconds stops new work; it cannot cancel an in-flight/custom transport call
or guarantee a wall-clock upper bound for DNS, response streaming, or disk I/O.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.parse import quote
import uuid

INVENTORY = '/sell/inventory/v1/inventory_item'
OFFER = '/sell/inventory/v1/offer'
TAXONOMY = '/commerce/taxonomy/v1/category_tree/77/'
PAGE_SIZE = 100
MAX_PAGES = 100
LOCAL_LIMIT = 10000
RECURRING = ('category_decisions', 'variant_labels', 'variant_axes', 'model_quantity_collisions',
             'dimensions_units', 'origin_manufacturer', 'buyer_verification', 'competitor_research')


class _BudgetReached(Exception):
    pass


class _InvalidRead(Exception):
    pass


class _Reader:
    def __init__(self, ebay, seconds, items):
        self.ebay = ebay
        self.deadline = time.monotonic() + seconds
        self.calls = 0
        self.limit = min(1000, max(12, items * 8 + 12))

    def check(self):
        if time.monotonic() >= self.deadline or self.calls >= self.limit:
            raise _BudgetReached()

    def get(self, path, params=None):
        self.check()
        self.calls += 1
        # Deliberately bypass auto-renewal: a 401 is a read failure, NOT a POST.
        if hasattr(self.ebay, 'session') and callable(getattr(self.ebay, '_get_headers', None)):
            response = self.ebay.session.request(
                'GET', 'https://api.ebay.com' + path, params=params or {},
                headers=self.ebay._get_headers(), allow_redirects=False,
                timeout=max(0.001, min(10.0, self.deadline - time.monotonic())))
            if not 200 <= response.status_code < 300:
                raise _InvalidRead()
            data = response.json()
        else:
            data = self.ebay._request('GET', path, params=params or {})
        if not isinstance(data, dict) or data.get('errors'):
            raise _InvalidRead()
        return data

    def pages(self, path, key, params=None):
        out, seen, total = [], set(), None
        for _ in range(MAX_PAGES):
            data = self.get(path, {**(params or {}), 'limit': PAGE_SIZE, 'offset': len(out)})
            values = data.get(key, [] if data.get('total') == 0 else None)
            current = data.get('total')
            if (not isinstance(values, list) or any(not isinstance(v, dict) for v in values)
                    or (current is not None and (type(current) is not int or current < 0))
                    or (total is not None and current != total)):
                raise _InvalidRead()
            total = current
            fingerprint = json.dumps(values, sort_keys=True)
            if values and fingerprint in seen:
                raise _InvalidRead()
            seen.add(fingerprint)
            if not values:
                if data.get('next') or (total is not None and len(out) < total):
                    raise _InvalidRead()
                return out
            out.extend(values)
            if total is not None and len(out) > total:
                raise _InvalidRead()
            if total is not None and len(out) == total:
                if data.get('next'):
                    raise _InvalidRead()
                return out
            if total is None and not data.get('next') and len(values) < PAGE_SIZE:
                return out
        raise _BudgetReached()


def _atomic(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=None if compact else 2,
                      separators=(',', ':') if compact else None, allow_nan=False) + '\n'
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read(path, max_bytes=8_000_000):
    if path.stat().st_size > max_bytes:
        raise _InvalidRead()
    return json.loads(path.read_text(encoding='utf-8'))


def _error(stage, exc, sku=None):
    return {**({'sku': sku} if sku is not None else {}), 'stage': stage, 'type': type(exc).__name__}


def _check(status, **evidence):
    return {'status': status, **evidence}


def _task(sku, field, code, evidence_needed, *, product_id=None, **evidence):
    identity = [product_id, sku, field, code]
    return {'key': hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest(),
            'product_id': product_id, 'sku': sku, 'field': field, 'code': code,
            'evidence_needed': evidence_needed, 'evidence': evidence}


def _merge(state, new_tasks, stamp):
    for task in new_tasks:
        old = state['tasks'].get(task['key'], {})
        state['tasks'][task['key']] = {**old, **task, 'status': 'unresolved',
                                      'first_seen': old.get('first_seen', stamp), 'last_seen': stamp,
                                      'cycle_id': state['cycle_id']}
        state['tasks'][task['key']].pop('resolved_at', None)
        state['tasks'][task['key']].pop('resolution_basis', None)


def _reconcile(state, row, stamp):
    if not row['read_complete']:
        return
    current = {t['key'] for t in row['tasks']}
    aspects_codes = {'missing_required_aspect', 'empty_required_aspect', 'missing_optional_aspect',
                     'empty_optional_aspect', 'aspect_not_in_category_vocabulary', 'low_aspect_count',
                     'category_name_leaked_into_aspect', 'closed_picklist_invalid'}
    verified_checks = {
        'category_decision_needed': 'category_decisions',
        'category_decision_drift': 'category_decisions',
        'category_blocked': 'category_decisions',
        'variant_label_evidence_needed': 'variant_labels',
        'variant_label_mismatch': 'variant_labels',
    }
    for key, task in state['tasks'].items():
        if task['sku'] != row['sku'] or key in current:
            continue
        if task.get('product_id') != row.get('product_id') and task['code'] != 'inventory_added_during_cycle':
            continue
        relevant = verified_checks.get(task['code'])
        verified = (relevant is not None and row.get('product_id') is not None and row['offers']
                    and row['checks'].get(relevant, {}).get('status') == 'verified')
        if (verified or task['code'] in ('read_failed', 'read_deferred', 'inventory_added_during_cycle')
                or (row['offers'] and task['code'] in aspects_codes)):
            task.update(status='resolved', resolved_at=stamp, resolution_basis='full_exact_target_read')


def _groups(state, complete, stamp):
    groups = {}
    for row in state['records'].values():
        row['checks']['category_consistency'] = _check(
            'not_applicable' if row['read_complete'] and not row['offers'] else 'not_verified')
        if row['read_complete']:
            for offer in row['offers']:
                if offer['listing_id']:
                    groups.setdefault(offer['listing_id'], {})[row['sku']] = row
    new = []
    group_codes = {'category_inconsistent_across_group', 'variant_axis_model_quantity_collision'}
    for listing_id, mapping in groups.items():
        rows = list(mapping.values())
        categories = {o['category_id'] for row in rows for o in row['offers'] if o['listing_id'] == listing_id}
        inconsistent = len(categories) > 1
        for row in rows:
            row['checks']['category_consistency'] = _check(
                'action_required' if inconsistent else ('verified' if complete else 'not_verified'),
                listing_id=listing_id, category_ids=sorted(categories))
            if inconsistent:
                new.append(_task(row['sku'], 'categoryId', 'category_inconsistent_across_group',
                    ['Full sibling offer/category reads and reviewed category decision'], product_id=row.get('product_id'),
                    listing_id=listing_id, category_ids=sorted(categories)))
        if len(rows) > 1 and not inconsistent:
            category = next(iter(categories))
            meta = state['category_cache'][category]['aspects']
            axes = sorted(f['localizedAspectName'] for f in meta
                          if f['aspectConstraint'].get('aspectEnabledForVariations') is True
                          and any(f['localizedAspectName'] in r.get('aspects', {}) for r in rows))
            combos = {}
            for row in rows:
                combo = json.dumps([row.get('aspects', {}).get(axis) for axis in axes], sort_keys=True)
                combos.setdefault(combo, []).append(row)
            for collision in combos.values():
                if len(collision) < 2:
                    continue
                for row in collision:
                    row['checks']['model_quantity_collisions'] = _check('action_required', listing_id=listing_id)
                    new.append(_task(row['sku'], 'variants', 'variant_axis_model_quantity_collision',
                        ['Distinct real model/quantity/size identities and exact axis evidence; never collapse sibling SKUs'],
                        product_id=row.get('product_id'), listing_id=listing_id, axes=axes,
                        sibling_skus=sorted(r['sku'] for r in collision)))
    _merge(state, new, stamp)
    if complete:
        current = {t['key'] for t in new}
        for task in state['tasks'].values():
            listing = task.get('evidence', {}).get('listing_id')
            if (task['code'] in group_codes and task['key'] not in current
                    and task['sku'] in groups.get(listing, {})
                    and task.get('product_id') == groups[listing][task['sku']].get('product_id')):
                task.update(status='resolved', resolved_at=stamp, resolution_basis='full_exact_target_read')


def _aggregate(records, key, complete):
    counts = {status: sum(r['checks'].get(key, {}).get('status', 'not_verified') == status for r in records)
              for status in ('verified', 'action_required', 'not_verified', 'not_applicable')}
    status = ('action_required' if counts['action_required'] else 'not_verified'
              if not complete or counts['not_verified'] else 'verified'
              if counts['verified'] else 'not_applicable')
    return _check(status, counts=counts, basis='Per-target current-cycle observations; see exact evidence')


def _queue_tasks(path):
    queue = _read(path, max_bytes=64_000_000)
    if not isinstance(queue, dict) or not isinstance(queue.get('tasks'), list):
        raise _InvalidRead()
    tasks = {}
    for task in queue['tasks']:
        if (not isinstance(task, dict) or not isinstance(task.get('key'), str)
                or task.get('status') not in ('unresolved', 'resolved')
                or not all(k in task for k in ('sku', 'product_id', 'field', 'code', 'evidence_needed'))):
            raise _InvalidRead()
        tasks[task['key']] = task
    return tasks


def _table(db, table, wanted):
    # Table/column identifiers are internal allowlists, never external input.
    columns = {r[1] for r in db.execute('PRAGMA table_info("' + table + '")')}
    selected = sorted(columns & set(wanted))
    if not selected:
        return []
    sql = 'SELECT ' + ','.join('"' + c + '"' for c in selected) + ' FROM "' + table + '" LIMIT ?'
    rows = [dict(r) for r in db.execute(sql, (LOCAL_LIMIT + 1,))]
    if len(rows) > LOCAL_LIMIT:
        raise _InvalidRead()
    return rows


def _sql_read(path, reader, tables):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=0.1)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() >= reader.deadline), 1000)
        return {table: _table(db, table, columns) for table, columns in tables.items()}
    finally:
        db.close()


def _local_sources(root, reader, now):
    data = {'errors': [], 'successful_stages': [], 'category_overrides': {}, 'verified_variant_labels': {},
            'products': [], 'product_variants': [],
            'buffer': _check('not_verified', candidate_ready_count=None,
                             evidence_needed=['Fresh artifact/content, readiness and document gate validation; target 10'])}
    for name in ('category_overrides', 'verified_variant_labels'):
        path = root / 'config' / (name + '.json')
        if path.exists():
            try:
                value = _read(path)
                if not isinstance(value, dict):
                    raise _InvalidRead()
                # Underscore-prefixed metadata is documentation, never a gate.
                data[name] = {k: v for k, v in value.items() if not k.startswith('_')}
                data['successful_stages'].append(name)
            except Exception as exc:
                data['errors'].append(_error(name, exc))
    path = root / 'data/dropshipping.db'
    if path.exists():
        try:
            data.update(_sql_read(path, reader, {
                'products': ('id', 'aliexpress_product_id', 'ebay_item_id', 'ebay_sku', 'inventory_sku'),
                'product_variants': ('product_id', 'aliexpress_product_id', 'sku', 'ebay_sku', 'inventory_sku', 'ali_sku_id', 'sku_id'),
            }))
            data['successful_stages'].append('products_database')
        except Exception as exc:
            data['errors'].append(_error('products_database', exc))
    path = root / 'data/listing_ready.sqlite'
    if path.exists():
        try:
            rows = _sql_read(path, reader, {'ready_listings': (
                'product_id', 'status', 'expires_at', 'blockers', 'side_effect_started')})['ready_listings']
            candidates = set()
            for row in rows:
                if row.get('status') == 'ready':
                    expiry = datetime.fromisoformat(row['expires_at'])
                    if expiry.tzinfo is None:
                        raise _InvalidRead()
                    if (expiry > now and row.get('side_effect_started') == 0
                            and json.loads(row['blockers']) == []):
                        candidates.add(row['product_id'])
            data['buffer']['candidate_ready_count'] = len(candidates)
            data['successful_stages'].append('ready_database')
        except Exception as exc:
            data['errors'].append(_error('ready_database', exc))
    return data


def _mapping(row, sources):
    sku = row['sku']
    listings = {o['listing_id'] for o in row['offers'] if o['listing_id']}
    products = sources['products']
    variants = [v for v in sources['product_variants']
                if any(v.get(c) == sku for c in ('sku', 'ebay_sku', 'inventory_sku'))]
    matches = [p for p in products if p.get('ebay_item_id') in listings
               or any(p.get(c) == sku for c in ('ebay_sku', 'inventory_sku'))
               or any(v.get('product_id') is not None and v['product_id'] == p.get('id') for v in variants)]
    identities = {p.get('aliexpress_product_id') for p in matches if p.get('aliexpress_product_id')}
    identities.update(v['aliexpress_product_id'] for v in variants if v.get('aliexpress_product_id'))
    if len(identities) != 1:
        return None, None
    product = next(iter(identities))
    if not isinstance(product, str) or not re.fullmatch(r'[0-9]{6,}', product):
        return None, None
    suppliers = {v[c] for v in variants for c in ('ali_sku_id', 'sku_id') if v.get(c) is not None}
    if len(suppliers) != 1:
        return product, None
    supplier = next(iter(suppliers))
    return product, supplier if isinstance(supplier, str) and re.fullmatch(r'[0-9]{6,}', supplier) else None


def _local_item(row, sources, root):
    product, supplier_sku = _mapping(row, sources)
    row['product_id'] = product
    for task in row['tasks']:
        task['product_id'] = product
        task['key'] = _task(row['sku'], task['field'], task['code'], [], product_id=product)['key']
    for key in RECURRING:
        row['checks'][key] = _check('not_verified')
    if not row['read_complete'] or not row['offers']:
        if row['read_complete']:
            for key in RECURRING:
                row['checks'][key] = _check('not_applicable')
        return

    def review(field, code, evidence_needed, **evidence):
        row['tasks'].append(_task(row['sku'], field, code, evidence_needed, product_id=product, **evidence))

    override = sources['category_overrides'].get(product)
    categories = {o['category_id'] for o in row['offers']}
    if isinstance(override, dict) and override.get('blocked') is True:
        row['checks']['category_decisions'] = _check('action_required', basis='explicit_review_block')
        review('category', 'category_blocked', ['Authorized identity/category decision; do not bypass blocked gate'])
    elif isinstance(override, dict) and override.get('category_id'):
        matches = categories == {override['category_id']}
        row['checks']['category_decisions'] = _check('verified' if matches else 'action_required',
                                                     basis='local_reviewed_category_comparison')
        if not matches:
            review('category', 'category_decision_drift', ['Reviewed exact category decision and full live offer read'])
    else:
        review('category', 'category_decision_needed', ['Product identity, real taxonomy candidates and reviewed category evidence'])
    labels = sources['verified_variant_labels'].get(product, {})
    labels = labels.get(supplier_sku) if isinstance(labels, dict) else None
    if isinstance(labels, dict) and any(not k.startswith('_') for k in labels):
        matches = all(row['aspects'].get(k) == [v] for k, v in labels.items() if not k.startswith('_'))
        row['checks']['variant_labels'] = _check('verified' if matches else 'action_required',
                                                 basis='exact_local_reviewed_labels_not_supplier_identity_verification')
        if not matches:
            review('variants', 'variant_label_mismatch', ['Current exact-SKU supplier/photo evidence and reviewed label'])
    else:
        review('variants', 'variant_label_evidence_needed', ['Exact local-to-provider SKU mapping and real per-SKU photos/labels'])
    # Cached competitors establish availability only, never this product's facts.
    if isinstance(product, str) and re.fullmatch(r'[0-9]{6,}', product):
        path = root / 'data/audit/competitor_analysis' / ('analysis_' + product + '.json')
        if path.exists():
            try:
                cached = _read(path)
                if not isinstance(cached, dict):
                    raise _InvalidRead()
                competitors = cached.get('competitors')
                if isinstance(competitors, list) and any(isinstance(c, dict) and c.get('item_id') for c in competitors):
                    row['checks']['competitor_research'] = _check('not_verified', research_available=True,
                        basis='local_research_present_freshness_identity_and_source_need_review')
            except Exception as exc:
                row['errors'].append(_error('competitor_research', exc, row['sku']))
                row['read_complete'] = False
    review('competitor_research', 'competitor_research_needed',
           ['Fresh real competitor category/aspects evidence; availability does not prove product properties'])
    for field, code, needed in (
        ('variant_axes', 'variant_axis_evidence_needed', ['Supplier option semantics and category variation support; colour is not quantity/model']),
        ('model_quantity_collisions', 'model_quantity_review_needed', ['All sibling SKU axes, exact model and pack-quantity mapping']),
        ('dimensions_units', 'dimensions_units_evidence_needed', ['Measured product dimensions with units; do not substitute package dimensions']),
        ('origin_manufacturer', 'origin_manufacturer_evidence_needed', ['Verified dispatch/manufacture origin, manufacturer and EU responsible-person documents']),
        ('buyer_verification', 'buyer_verification_needed', ['Buyer Browse page/gallery, selected variants, item specifics and item-ID readback']),
    ):
        review(field, code, needed)


def _metadata(reader, state, category):
    if category not in state['category_cache']:
        meta = reader.get(TAXONOMY + 'get_item_aspects_for_category', {'category_id': category})
        if not isinstance(meta.get('aspects'), list):
            raise _InvalidRead()
        names = set()
        for field in meta['aspects']:
            if (not isinstance(field, dict) or not isinstance(field.get('localizedAspectName'), str)
                    or not field['localizedAspectName'] or field['localizedAspectName'] in names
                    or not isinstance(field.get('aspectConstraint'), dict)):
                raise _InvalidRead()
            names.add(field['localizedAspectName'])
            if field['aspectConstraint'].get('aspectMode') == 'SELECTION_ONLY' and (
                    not isinstance(field.get('aspectValues'), list) or not field['aspectValues']
                    or any(not isinstance(v, dict) or not isinstance(v.get('localizedValue'), str)
                           for v in field['aspectValues'])):
                raise _InvalidRead()
        name = reader.get(TAXONOMY + 'get_category_subtree', {'category_id': category})
        name = name.get('categorySubtreeNode', {}).get('category', {}).get('categoryName')
        if not isinstance(name, str) or not name:
            raise _InvalidRead()
        state['category_cache'][category] = {'name': name, 'aspects': meta['aspects']}
    return state['category_cache'][category]


def _audit_aspects(row, aspects, meta, category):
    fields = {f['localizedAspectName']: f for f in meta['aspects']}
    required_bad, optional_bad, valid, optional_total = [], [], 0, 0

    def issue(field, code, **evidence):
        row['tasks'].append(_task(row['sku'], field, code,
                                 ['Exact category vocabulary and real product/source evidence; no inferred values'],
                                 category_id=category, **evidence))

    for name in aspects.keys() - fields.keys():
        issue(name, 'aspect_not_in_category_vocabulary')
    for name, field in fields.items():
        constraint = field['aspectConstraint']
        required = constraint.get('aspectRequired') is True
        optional_total += not required
        values = aspects.get(name)
        empty = not isinstance(values, list) or not values or any(
            not isinstance(v, str) or not v.strip() for v in values)
        invalid = False
        if empty:
            issue(name, ('missing_' if name not in aspects else 'empty_') +
                  ('required_aspect' if required else 'optional_aspect'))
            (required_bad if required else optional_bad).append(name)
            continue
        if name == 'Produktart' and meta['name'] in values:
            issue(name, 'category_name_leaked_into_aspect', observed=meta['name'])
            invalid = True
        if constraint.get('aspectMode') == 'SELECTION_ONLY':
            allowed = {v['localizedValue'] for v in field['aspectValues']}
            rejected = [v for v in values if v not in allowed]
            if rejected:
                issue(name, 'closed_picklist_invalid', observed=rejected)
                invalid = True
        if invalid:
            (required_bad if required else optional_bad).append(name)
        else:
            valid += 1
    checks = {
        'required_aspects': _check('action_required' if required_bad else 'verified', fields=required_bad),
        'optional_aspects': _check('action_required' if optional_bad else 'verified', fields=optional_bad,
                                   total_fields=optional_total),
        'aspect_count': _check('verified' if valid >= 10 else 'action_required', valid_count=valid,
                               target=10, basis='local_quality_target_not_an_eBay_requirement'),
    }
    for name, value in checks.items():
        if row['checks'].get(name, {}).get('status') != 'action_required':
            row['checks'][name] = value
    if valid < 10:
        issue('aspects', 'low_aspect_count', valid_count=valid, target=10)


def _item(reader, state, sku):
    stage = 'inventory_item'
    row = {'sku': sku, 'read_complete': False,
           'checks': {key: _check('not_verified') for key in ('offer', 'required_aspects', 'optional_aspects', 'aspect_count')},
           'offers': [], 'tasks': [], 'errors': []}
    try:
        item = reader.get(INVENTORY + '/' + quote(sku, safe=''))
        if item.get('sku') != sku or not isinstance(item.get('product', {}), dict):
            raise _InvalidRead()
        aspects = item.get('product', {}).get('aspects') or {}
        if not isinstance(aspects, dict):
            raise _InvalidRead()
        row['aspects'] = aspects
        stage = 'offer'
        offers = reader.pages(OFFER, 'offers', {'sku': sku})
        for offer in offers:
            listing = offer.get('listing') or {}
            if not isinstance(listing, dict):
                raise _InvalidRead()
            if (listing.get('listingStatus') not in ('ACTIVE', 'OUT_OF_STOCK', 'ENDED', 'INACTIVE', 'NOT_ACTIVE')
                    and offer.get('status') != 'UNPUBLISHED'):
                raise _InvalidRead()
            if listing.get('listingStatus') in ('ACTIVE', 'OUT_OF_STOCK') and (
                    not isinstance(listing.get('listingId'), str) or not listing['listingId']):
                raise _InvalidRead()
        live = [o for o in offers if o.get('listing', {}).get('listingStatus') in ('ACTIVE', 'OUT_OF_STOCK')]
        row['checks']['offer'] = _check('verified' if live else 'not_applicable',
                                       state='active' if live else ('inactive' if offers else 'no_offer'))
        for offer in live:
            category = offer.get('categoryId')
            if not isinstance(category, str) or not category:
                raise _InvalidRead()
            row['offers'].append({'listing_id': offer.get('listing', {}).get('listingId'), 'category_id': category})
            stage = 'category_metadata'
            meta = _metadata(reader, state, category)
            _audit_aspects(row, aspects, meta, category)
        if not live:
            for key in ('required_aspects', 'optional_aspects', 'aspect_count'):
                row['checks'][key] = _check('not_applicable')
        row['read_complete'] = True
    except Exception as exc:
        row['errors'].append(_error(stage, exc, sku))
        row['checks'][stage] = _check('not_verified')
        row['tasks'].append(_task(sku, stage, 'read_deferred' if isinstance(exc, _BudgetReached) else 'read_failed',
                                  ['Successful fresh GET for this exact target']))
    return row


def _checkpoint_failure(exc, report_path, queue_path, stamp):
    summary = {'status': 'partial', 'complete': False, 'processed_skus': 0, 'total_skus': None,
               'open_reviews': None, 'fetch_error_count': 1, 'report': str(report_path), 'queue': str(queue_path),
               'cycle_id': None, 'processed_this_run': 0, 'processed_count': 0, 'catalog_total': None,
               'unresolved_count': None, 'verified_count': 0, 'remaining_count': None, 'requests_used': 0,
               'fresh_inventory_total': None, 'budget_exhausted': False, 'budget_stop_count': 0}
    _atomic(report_path, {**summary, 'generated_at': stamp, 'items': [],
                          'errors': [_error('checkpoint', exc)],
                          'checklist': {'checkpoint': _check('not_verified', evidence_needed=[
                              'Recover/inspect corrupt checkpoint without deleting review queue'])}})
    return summary


def run_cycle(ebay, root, *, max_items=20, max_seconds=75, now=None):
    """Audit at most max_items exact targets; return JSON-safe paths and counts.

    A fresh, complete inventory scan is mandatory on EVERY tick. A catalog
    cycle reconciles its SKU roster against each full snapshot and retains
    category metadata across chunks; completion starts a new cache next tick. No supplier ID
    is ever inferred from an eBay SKU. Caller must serialize concurrent ticks.

    ``complete`` describes successful reads of the current reconciled roster, not
    evidence approval or an atomic point-in-time eBay view. Confirmed removals
    are recorded separately, never counted as item verification. Added SKUs
    join immediately, ahead of failed retries. ``processed_skus`` counts
    distinct attempted targets cumulatively; ``verified_count`` counts complete
    reads, not properties certified true. Missing evidence stays not_verified.
    At most min(1000, max(12, max_items * 8 + 12)) GETs start per tick; retries
    occur on later ticks rather than an unbounded in-call retry/renewal path.
    """
    if type(max_items) is not int or not 1 <= max_items <= 200:
        raise ValueError('max_items must be between 1 and 200')
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (float, int)) or not math.isfinite(max_seconds) or max_seconds < 0:
        raise ValueError('max_seconds must be finite and nonnegative')
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    stamp = now.astimezone(timezone.utc).isoformat()
    root = Path(root)
    checkpoint = root / 'data/jobs/listing_standards_state.json'
    report_path = root / 'data/audit/listing_standards_report.json'
    queue_path = root / 'data/audit/listing_review_queue.json'
    recovered_tasks = {}
    try:
        state = _read(checkpoint, max_bytes=64_000_000) if checkpoint.exists() else None
        if state is None and queue_path.exists():
            recovered_tasks = _queue_tasks(queue_path)
        if state is not None and (
                not isinstance(state, dict) or state.get('version') != 1
                or type(state.get('complete')) is not bool
                or not isinstance(state.get('tasks'), dict) or not isinstance(state.get('records'), dict)
                or not isinstance(state.get('category_cache'), dict)
                or not isinstance(state.get('cycle_id'), str)
                or not (state.get('catalog') is None or isinstance(state.get('catalog'), list))):
            raise _InvalidRead()
    except Exception as exc:
        return _checkpoint_failure(exc, report_path, queue_path, stamp)
    previous = state
    if state is None or state['complete']:
        state = {'version': 1, 'cycle_id': uuid.uuid4().hex, 'started_at': stamp, 'catalog': None,
                 'records': {}, 'tasks': (previous or {}).get('tasks', recovered_tasks), 'complete': False,
                 'category_cache': {}, 'removals': {}}
    state.setdefault('removals', {})
    reader = _Reader(ebay, max_seconds, max_items)
    errors, snapshot, processed, fresh = [], None, 0, {}
    sources = {'buffer': _check('not_verified')}
    drift = {'added': [], 'missing': [], 'changed': []}
    try:
        values = reader.pages(INVENTORY, 'inventoryItems')
        snapshot = [i.get('sku') for i in values]
        if (any(not isinstance(s, str) or not s for s in snapshot) or len(set(snapshot)) != len(snapshot)):
            raise _InvalidRead()
        if state['catalog'] is None:
            state['catalog'] = snapshot
        fresh = {item['sku']: hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest() for item in values}
        drift['added'] = sorted(set(snapshot) - set(state['catalog']))
        drift['missing'] = sorted(set(state['catalog']) - set(snapshot))
        for sku, row in state['records'].items():
            if sku in fresh and row.get('snapshot_hash') != fresh[sku]:
                row['read_complete'] = False
                drift['changed'].append(sku)
        _merge(state, [_task(sku, 'inventory', code, ['Fresh exact inventory target and local mapping review'])
                       for key, code in (('added', 'inventory_added_during_cycle'), ('missing', 'inventory_missing_during_cycle'))
                       for sku in drift[key]], stamp)
        for sku in drift['missing']:
            state['removals'][sku] = {'sku': sku, 'confirmed_at': stamp,
                                      'basis': 'full_inventory_snapshot', 'read_complete': False}
            state['records'].pop(sku, None)
        state['catalog'] = snapshot
        _atomic(checkpoint, state, compact=True)
    except Exception as exc:
        errors.append(_error('inventory_snapshot', exc))
        _merge(state, [_task(None, 'inventory_snapshot', 'read_deferred' if isinstance(exc, _BudgetReached) else 'read_failed',
                             ['Complete fresh paginated inventory GET'])], stamp)
        snapshot = None
    if snapshot is not None:
        sources = _local_sources(root, reader, now)
        errors.extend(sources['errors'])
        _merge(state, [_task(None, 'buffer', 'buffer_verification_needed', [
            'Read-only candidate count is not artifact verification; inspect fresh full readiness gates and maintain target 10'])], stamp)
        _merge(state, [_task(None, e['stage'], 'read_failed', ['Successful fresh exact local-source read'])
                       for e in sources['errors']], stamp)
        for task in state['tasks'].values():
            if (task['sku'] is None and task['code'] in ('read_failed', 'read_deferred')
                    and task['field'] in ('inventory_snapshot', *sources['successful_stages'])):
                task.update(status='resolved', resolved_at=stamp, resolution_basis='full_exact_target_read')
        pending = [s for s in state['catalog'] if s not in state['records']]
        pending += [s for s in state['catalog'] if s in state['records'] and not state['records'][s]['read_complete']]
        for sku in pending[:max_items]:
            try:
                reader.check()
            except _BudgetReached as exc:
                errors.append(_error('budget', exc))
                break
            row = _item(reader, state, sku)
            try:
                _local_item(row, sources, root)
            except Exception as exc:
                row['read_complete'] = False
                row['errors'].append(_error('local_evidence', exc, sku))
                row['tasks'].append(_task(sku, 'local_evidence', 'read_failed',
                    ['Successful fresh exact local-evidence read'], product_id=row.get('product_id')))
            row['snapshot_hash'] = fresh.get(sku)
            state['records'][sku] = row
            _merge(state, row['tasks'], stamp)
            _reconcile(state, row, stamp)
            row['task_keys'] = sorted({t['key'] for t in row.pop('tasks')})
            processed += 1
            _atomic(checkpoint, state, compact=True)
    records = list(state['records'].values())
    good = sum(row['read_complete'] for row in records)
    total = len(state['catalog'] or [])
    complete = snapshot is not None and not errors and good == total
    _groups(state, complete, stamp)
    state['complete'] = complete
    _atomic(checkpoint, state, compact=True)
    all_errors = errors + [error for row in records for error in row['errors']]
    budget_stops = [error for error in all_errors if error['type'] == '_BudgetReached']
    all_errors = [error for error in all_errors if error['type'] != '_BudgetReached']
    status = 'partial' if not complete else ('action_required' if any(
        t['status'] == 'unresolved' for t in state['tasks'].values()) else 'verified')
    summary = {'status': status, 'report': str(report_path), 'queue': str(queue_path),
               'cycle_id': state['cycle_id'], 'complete': complete, 'catalog_total': total,
               'processed_this_run': processed, 'processed_count': len(records), 'verified_count': good,
               'remaining_count': total - good, 'removed_count': len(state['removals']),
               'requests_used': reader.calls, 'request_limit': reader.limit,
               'fetch_error_count': len(all_errors), 'budget_stop_count': len(budget_stops),
               'budget_exhausted': bool(budget_stops) or (not complete and processed == max_items),
               'unresolved_count': sum(
                   t['status'] == 'unresolved' for t in state['tasks'].values())}
    summary.update(processed_skus=summary['processed_count'], total_skus=total,
                   open_reviews=summary['unresolved_count'],
                   fresh_inventory_total=len(snapshot) if snapshot is not None else None)
    _atomic(queue_path, {'version': 1, 'generated_at': stamp, 'cycle_id': state['cycle_id'],
                         'tasks': sorted(state['tasks'].values(), key=lambda t: t['key'])})
    _atomic(report_path, {**summary, 'generated_at': stamp, 'items': records, 'errors': all_errors,
                          'budget_stops': budget_stops,
                          'checklist': {
                              'fresh_inventory': _check('verified' if snapshot is not None else 'not_verified'),
                              'inventory_drift': _check('not_verified' if snapshot is None else (
                                  'action_required' if any(drift.values()) else 'verified'), **drift),
                              'buffer': sources['buffer'] if snapshot is not None else _check('not_verified'),
                              'safe_maintenance': _check('verified', basis='GET-only; source files/DB/locks never mutated'),
                              **{key: _aggregate(records, key, complete)
                                 for key in (*RECURRING, 'required_aspects', 'optional_aspects',
                                             'aspect_count', 'category_consistency')},
                          }})
    return summary
