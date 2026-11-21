"""Bounded, resumable, REAL-EVIDENCE-ONLY auto-resolver for the listing review queue.

This module never marks a task resolved itself -- that stays the exclusive job of
listing_quality.standards.run_cycle re-reading verified_checks on its next audit cycle.
All this does is ATTEMPT real-evidence-backed fixes for a bounded number of currently
unresolved tasks and report what it found/did; the queue file itself is never rewritten
here (standards.run_cycle owns data/audit/listing_review_queue.json entirely).

Reused, not reinvented:
  - listing_quality.standards._Reader for the exact same max_items/max_seconds request
    budget used by the recurring audit (imported, never copied).
  - listing_quality.source.fetch_raw/properties for the real AliExpress supplier facts.
  - listing_quality.categories.aspects_for/fill_aspects/resolve_for_product for category
    metadata, real-evidence aspect candidates and taxonomy resolution with confidence.
  - product_preparation.collect_provider_facts for the manufacturer-identity evidence
    signal (manufacturer_legal_identity_complete), not a bespoke parse of manufacturer_info.

Two write types only, both additive/non-destructive:
  1. Aspects: PUT /sell/inventory/v1/inventory_item/{sku} with a freshly-read item body
     where ONLY newly-ADDED aspect keys are merged in (never overwrite/remove an existing
     non-empty value -- that is a conflict, recorded and left for a human). This targets
     the inventory item (not the offer) because that is where eBay's Inventory API actually
     stores product.aspects; the offer only carries categoryId/price/quantity/policies.
  2. Category: a confirmed real-taxonomy match against the CURRENT live category is never
     PUT to eBay (nothing changes on the listing) -- it is recorded into
     config/category_overrides.json (same schema humans use) purely so the task stops
     recurring on the next standards audit. A mismatch changes nothing at all, anywhere.

Writes reuse the production eBay client's own `_request` (PUT/GET retry on 429/5xx,
POST/DELETE-never-retry-on-5xx, OAuth refresh on 401) instead of reimplementing retry
logic -- unlike the audit's _Reader, which deliberately bypasses that path for reads.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import quote

from src.listing_quality import categories, source
from src.listing_quality.standards import (
    INVENTORY, OFFER, _BudgetReached, _InvalidRead, _Reader, _atomic, _check, _error, _read,
)

ASPECT_CODES = frozenset({
    'missing_optional_aspect', 'aspect_not_in_category_vocabulary',
    'low_aspect_count', 'closed_picklist_invalid',
})
EVIDENCE_CODES = frozenset({'origin_manufacturer_evidence_needed', 'dimensions_units_evidence_needed'})
CATEGORY_CODE = 'category_decision_needed'
OUT_OF_SCOPE_CODES = frozenset({
    'variant_label_evidence_needed', 'variant_axis_evidence_needed', 'model_quantity_review_needed',
    'buyer_verification_needed', 'competitor_research_needed', 'buffer_verification_needed',
})
IN_SCOPE_CODES = ASPECT_CODES | EVIDENCE_CODES | {CATEGORY_CODE}

ORIGIN_HINTS = ('herkunft', 'ursprung', 'herstellungsland')
DIMENSION_HINTS = ('länge', 'laenge', 'breite', 'höhe', 'hoehe', 'durchmesser',
                   'größe', 'groesse', 'abmessung', 'maß', 'masse')
UNIT_RE = re.compile(r'\d[\d.,]*\s*(?:cm|mm|m|kg|g)\b', re.I)
LIVE_STATES = ('ACTIVE', 'OUT_OF_STOCK')
WRITABLE_ITEM_KEYS = ('product', 'availability', 'condition', 'conditionDescription', 'packageWeightAndSize')


class _ReaderProxy:
    """Presents reader.get() as a GET-only `ebay._request`, so categories.py's own
    aspects_for/resolve_for_product/suggest logic runs unmodified, with every GET they
    issue accounted for against the SAME request/time budget as everything else here."""

    def __init__(self, reader):
        self._reader = reader

    def _request(self, method, path, params=None, **kwargs):
        if method != 'GET':
            raise ValueError('category lookups in the resolver are GET-only')
        return self._reader.get(path, params)


def _explicit_evidence(code, props, manufacturer_signal):
    if code == 'origin_manufacturer_evidence_needed':
        if manufacturer_signal:
            return True
        return any(any(hint in name.casefold() for hint in ORIGIN_HINTS) for name, _ in props)
    if code == 'dimensions_units_evidence_needed':
        return any(any(hint in name.casefold() for hint in DIMENSION_HINTS) and UNIT_RE.search(value)
                   for name, value in props)
    return True


def _manufacturer_signal(product_id, raw):
    """Real verified-identity signal only (never a bare brand/attr guess)."""
    try:
        from src.product_preparation import collect_provider_facts
        facts = collect_provider_facts(product_id, raw)
        return bool(facts.get('manufacturer_legal_identity_complete'))
    except Exception:
        return False


def _live_item(reader, sku):
    item = reader.get(INVENTORY + '/' + quote(sku, safe=''))
    aspects = (item.get('product') or {}).get('aspects') if isinstance(item, dict) else None
    if not isinstance(item, dict) or item.get('sku') != sku or not isinstance(aspects, dict):
        raise _InvalidRead()
    return item, aspects


def _live_category(reader, sku):
    offers = reader.pages(OFFER, 'offers', {'sku': sku})
    for offer in offers:
        listing = offer.get('listing') or {}
        if isinstance(listing, dict) and listing.get('listingStatus') in LIVE_STATES:
            category = offer.get('categoryId')
            if not isinstance(category, str) or not category:
                raise _InvalidRead()
            return category
    return None


def _category_meta(proxy, cache, category):
    if category not in cache:
        meta = categories.aspects_for(proxy, category)
        if not isinstance(meta, list):
            raise _InvalidRead()
        cache[category] = meta
    return cache[category]


def _sku_plan(reader, proxy, meta_cache, sku, raw, props):
    """Fresh live read this run + real-evidence candidate aspects for one SKU.

    Returns {'status': 'no_live_offer'} or {'status': 'ok', ...}. Never estimates: every
    candidate value in `to_add` traces to a real supplier property via categories.fill_aspects.
    """
    item, live_aspects = _live_item(reader, sku)
    category = _live_category(reader, sku)
    if category is None:
        return {'status': 'no_live_offer'}
    meta = _category_meta(proxy, meta_cache, category)
    title = (raw.get('ae_item_base_info_dto') or {}).get('subject') or ''
    candidates, _missing_required = categories.fill_aspects(meta, props, enrich=True, subject=title)
    to_add, conflicts = {}, []
    for name, values in candidates.items():
        current = live_aspects.get(name)
        empty = (not isinstance(current, list) or not current
                or any(not isinstance(v, str) or not v.strip() for v in current))
        if empty:
            to_add[name] = values
        elif [v for v in current if v.strip()] != values:
            conflicts.append(name)
    return {'status': 'ok', 'item': item, 'live_aspects': live_aspects, 'category': category,
            'to_add': to_add, 'conflicts': conflicts}


def _apply_aspect_write(ebay, reader, remote_mutations, sku, plan, stamp, audit_trail):
    merged_item = deepcopy(plan['item'])
    merged_item.setdefault('product', {})['aspects'] = {**plan['live_aspects'], **plan['to_add']}
    if not remote_mutations:
        return {'status': 'dry_run'}
    try:
        reader.check()
        reader.calls += 1
        body = {key: merged_item[key] for key in WRITABLE_ITEM_KEYS if key in merged_item}
        ebay._request('PUT', INVENTORY + '/' + quote(sku, safe=''), json=body)
        reread_item, reread_aspects = _live_item(reader, sku)
        if any(reread_aspects.get(name) != values for name, values in plan['to_add'].items()):
            raise _InvalidRead()
        for name in plan['to_add']:
            audit_trail.append({'sku': sku, 'field': name, 'source': 'aliexpress.ds.product.get',
                                'observed_at': stamp})
        return {'status': 'written'}
    except _BudgetReached:
        raise
    except Exception as exc:
        return {'status': 'error', 'error': _error('aspect_write', exc, sku)}


def _confirm_category(root, pid, result, stamp):
    path = root / 'config' / 'category_overrides.json'
    data = _read(path) if path.exists() else {}
    if not isinstance(data, dict):
        raise _InvalidRead()
    key = str(pid)
    if key in data:
        return False
    data[key] = {
        'category_id': result['category_id'], 'path': result.get('path'),
        'level': 'auto_confirmed',
        'note': (f'Auto-confirmed by listing_standards_resolve on {stamp}: real taxonomy '
                 f'resolution (confidence={result.get("confidence")}) matches the current '
                 f'live offer category_id. Not an eBay write; local bookkeeping only.'),
    }
    _atomic(path, data)
    return True


def _rotate(tasks, last_key):
    if not tasks or last_key is None:
        return tasks
    keys = [t['key'] for t in tasks]
    if last_key not in keys:
        return tasks
    i = keys.index(last_key) + 1
    return tasks[i:] + tasks[:i]


def _load_cursor(path):
    try:
        if path.exists():
            value = _read(path)
            if isinstance(value, dict) and isinstance(value.get('last_key'), (str, type(None))):
                return value.get('last_key')
    except Exception:
        pass
    return None


def resolve_cycle(ebay, supplier, root, *, max_items=20, max_seconds=75, now=None, remote_mutations=False):
    """Attempt real-evidence fixes for at most max_items unresolved in-scope queue tasks.

    Never self-resolves a task (only the next standards.run_cycle audit can do that by
    re-reading fresh verified_checks). Dry run (remote_mutations=False, the default)
    makes zero eBay PUT calls; every count it reports is fully inspectable before anyone
    flips remote_mutations on. Out-of-scope codes (variant/model/buyer/competitor/buffer
    review) are left completely untouched and are not counted anywhere in this summary.
    """
    if type(max_items) is not int or not 1 <= max_items <= 200:
        raise ValueError('max_items must be between 1 and 200')
    if (isinstance(max_seconds, bool) or not isinstance(max_seconds, (float, int))
            or not math.isfinite(max_seconds) or max_seconds < 0):
        raise ValueError('max_seconds must be finite and nonnegative')
    if type(remote_mutations) is not bool:
        raise ValueError('remote_mutations must be boolean')
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    stamp = now.astimezone(timezone.utc).isoformat()
    root = Path(root)
    queue_path = root / 'data/audit/listing_review_queue.json'
    cursor_path = root / 'data/jobs/listing_standards_resolve_cursor.json'
    resolution_path = root / 'data/audit/listing_review_resolution.json'

    reader = _Reader(ebay, max_seconds, max_items)
    proxy = _ReaderProxy(reader)
    meta_cache, raw_cache, sku_write_cache = {}, {}, {}
    audit_trail, errors, items = [], [], []
    resolved_candidates = skipped_no_evidence = 0
    attempted_writes = written_count = write_error_count = 0
    category_confirmed_count = category_mismatch_count = 0
    budget_exhausted = False

    try:
        all_tasks = list((_read(queue_path, max_bytes=64_000_000) or {}).get('tasks', [])) if queue_path.exists() else []
    except Exception as exc:
        errors.append(_error('queue_read', exc))
        all_tasks = []
    in_scope = sorted((t for t in all_tasks if isinstance(t, dict) and t.get('status') == 'unresolved'
                       and t.get('code') in IN_SCOPE_CODES), key=lambda t: t['key'])
    last_key = _load_cursor(cursor_path)
    ordered = _rotate(in_scope, last_key)

    def fetch_raw_cached(pid):
        if pid not in raw_cache:
            raw_cache[pid] = source.fetch_raw(supplier, pid)
        return raw_cache[pid]

    processed = 0
    for task in ordered:
        if processed >= max_items:
            break
        try:
            reader.check()
        except _BudgetReached:
            budget_exhausted = True
            break
        sku, pid, code = task.get('sku'), task.get('product_id'), task.get('code')
        outcome = {'key': task['key'], 'sku': sku, 'code': code}
        try:
            if not isinstance(pid, str) or not pid:
                outcome['result'] = 'skipped_no_evidence'
                skipped_no_evidence += 1
            elif code == CATEGORY_CODE:
                raw = fetch_raw_cached(pid)
                props = source.properties(raw)
                title = (raw.get('ae_item_base_info_dto') or {}).get('subject') or ''
                result = categories.resolve_for_product(proxy, pid, title, props)
                live_category = _live_category(reader, sku)
                if (live_category is not None and result.get('category_id') is not None
                        and not result.get('needs_review')
                        and str(result['category_id']) == str(live_category)):
                    wrote = _confirm_category(root, pid, result, stamp)
                    category_confirmed_count += 1
                    resolved_candidates += 1
                    outcome.update(result='category_confirmed', resolved_category_id=result['category_id'],
                                  live_category_id=live_category, override_written=wrote)
                else:
                    category_mismatch_count += 1
                    outcome.update(result='category_mismatch', resolved_category_id=result.get('category_id'),
                                  confidence=result.get('confidence'), live_category_id=live_category)
            else:
                raw = fetch_raw_cached(pid)
                props = source.properties(raw)
                manufacturer_signal = (code == 'origin_manufacturer_evidence_needed'
                                      and _manufacturer_signal(pid, raw))
                if code in EVIDENCE_CODES and not _explicit_evidence(code, props, manufacturer_signal):
                    outcome['result'] = 'skipped_no_evidence'
                    skipped_no_evidence += 1
                else:
                    if sku not in sku_write_cache:
                        plan = _sku_plan(reader, proxy, meta_cache, sku, raw, props)
                        if plan['status'] != 'ok' or not plan['to_add']:
                            sku_write_cache[sku] = {'status': 'nothing', 'conflicts': plan.get('conflicts', [])}
                        else:
                            attempted_writes += 1
                            write_outcome = _apply_aspect_write(ebay, reader, remote_mutations, sku, plan,
                                                               stamp, audit_trail)
                            if write_outcome['status'] == 'written':
                                written_count += 1
                            elif write_outcome['status'] == 'error':
                                write_error_count += 1
                                errors.append(write_outcome['error'])
                            sku_write_cache[sku] = {'status': write_outcome['status'],
                                                    'added': sorted(plan['to_add']),
                                                    'conflicts': plan['conflicts']}
                    cached = sku_write_cache[sku]
                    if cached['status'] == 'nothing':
                        outcome['result'] = 'skipped_no_evidence'
                        skipped_no_evidence += 1
                        if cached.get('conflicts'):
                            outcome['conflicts'] = cached['conflicts']
                    else:
                        resolved_candidates += 1
                        outcome.update(result=cached['status'], added=cached['added'])
                        if cached.get('conflicts'):
                            outcome['conflicts'] = cached['conflicts']
        except _BudgetReached:
            budget_exhausted = True
            break
        except Exception as exc:
            outcome['result'] = 'error'
            errors.append(_error('resolve_task', exc, sku))
        items.append(outcome)
        processed += 1

    try:
        _atomic(cursor_path, {'version': 1, 'last_key': ordered[processed - 1]['key'] if processed else last_key})
    except Exception as exc:
        errors.append(_error('cursor_write', exc))

    # Same convention as standards.run_cycle: hitting the item cap with more real work
    # still pending counts as budget exhaustion too, not just an in-flight _BudgetReached.
    budget_exhausted = budget_exhausted or (processed == max_items and processed < len(ordered))
    status = 'partial' if budget_exhausted or errors else 'ok'
    summary = {
        'status': status, 'generated_at': stamp, 'resolution_report': str(resolution_path),
        'queue': str(queue_path), 'candidate_tasks': len(in_scope), 'processed_count': processed,
        'resolved_candidates': resolved_candidates, 'skipped_no_evidence': skipped_no_evidence,
        'attempted_writes': attempted_writes, 'written_count': written_count,
        'write_error_count': write_error_count, 'category_confirmed_count': category_confirmed_count,
        'category_mismatch_count': category_mismatch_count, 'requests_used': reader.calls,
        'request_limit': reader.limit, 'remote_mutations': remote_mutations, 'dry_run': not remote_mutations,
        'budget_exhausted': budget_exhausted, 'error_count': len(errors),
    }
    try:
        _atomic(resolution_path, {**summary, 'items': items, 'errors': errors, 'audit_trail': audit_trail})
    except Exception as exc:
        errors.append(_error('resolution_report_write', exc))
        summary['error_count'] = len(errors)
    return summary
