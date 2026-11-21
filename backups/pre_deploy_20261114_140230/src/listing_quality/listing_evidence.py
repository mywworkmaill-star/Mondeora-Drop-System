"""Consume authenticated, scoped document reviews; never create or approve one.

A valid HMAC authenticates the configured review authority, NOT the legal truth
of an arbitrary document. That authority must actually inspect supplier rights
and compliance before signing. This module has no signing/auto-approval path.
Finance, demand, risk acknowledgements and global readiness remain independent.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re

from src import runtime

DOCUMENT_REQUIREMENTS = {
    'supplier_product_compliance': 'supplier_product_compliance_unverified',
    'supplier_agreement': 'supplier_agreement_missing',
    'manufacturer_eu_responsible_person': 'manufacturer_eu_responsible_person_missing',
    'image_rights': 'image_rights_unverified',
    'dispatch_origin': 'dispatch_origin_unverified',
}
MAX_AGE = timedelta(hours=24)
MAX_MANIFEST_BYTES = 2_000_000
MAX_DOCUMENT_BYTES = 10_000_000


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _identity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{6,}', value):
        raise ValueError('invalid_identity')
    return value


def _time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone_required')
    return value.astimezone(timezone.utc)


def scope_digest(product_id, st):
    """Bind approval to exact source, all variants and final saved content."""
    _identity(product_id)
    content = {key: st[key] for key in ('res', 'title', 'desc', 'cat', 'shared', 'plan', 'imgs')}
    return hashlib.sha256(_canonical({'product_id': product_id, 'content': content})).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _path_beneath(base, relative):
    if not isinstance(relative, str) or not relative or ':' in relative or '\\' in relative:
        raise ValueError('relative_document_path_required')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('relative_document_path_required')
    target = (base / path).resolve()
    if not target.is_relative_to(base.resolve()) or not target.is_file():
        raise ValueError('scoped_file_required')
    return target


def _record(record, key, scope, directory, now):
    if not isinstance(record, dict) or set(record) != {
        'requirement', 'decision', 'reviewed_by', 'reviewed_at', 'expires_at', 'scope', 'documents', 'signature'
    }:
        raise ValueError('record_schema_invalid')
    signature = record['signature']
    signed = {k: v for k, v in record.items() if k != 'signature'}
    expected = hmac.new(key, _canonical(signed), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ValueError('review_signature_invalid')
    if record['decision'] != 'approved' or not isinstance(record['reviewed_by'], str) or not record['reviewed_by'].strip():
        raise ValueError('authorized_review_required')
    if record['scope'] != scope:
        raise ValueError('review_scope_mismatch')
    reviewed, expires = _time(record['reviewed_at']), _time(record['expires_at'])
    if not reviewed <= now < expires or now - reviewed > MAX_AGE or expires - reviewed > MAX_AGE:
        raise ValueError('review_stale_or_future')
    documents = record['documents']
    if not isinstance(documents, list) or not 1 <= len(documents) <= 20:
        raise ValueError('review_documents_required')
    seen = set()
    for document in documents:
        if not isinstance(document, dict) or set(document) != {'path', 'sha256'}:
            raise ValueError('document_schema_invalid')
        path = _path_beneath(directory, document['path'])
        if path in seen:
            raise ValueError('duplicate_document')
        seen.add(path)
        if not 0 < path.stat().st_size <= MAX_DOCUMENT_BYTES:
            raise ValueError('document_size_invalid')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if not isinstance(document['sha256'], str) or not hmac.compare_digest(digest, document['sha256']):
            raise ValueError('document_hash_mismatch')
    return expires


def verify_product(product_id, st, *, now=None):
    """Read-only review validation; return stable codes, never secrets/documents."""
    out = {'basis': 'authenticated_scoped_document_review', 'accepted_requirements': [],
           'satisfied_blockers': [], 'missing_blockers': list(DOCUMENT_REQUIREMENTS.values()),
           'errors': {}, 'review_fingerprint': None, 'valid_until': None}
    try:
        product_id = _identity(product_id)
        observed = _time(datetime.now(timezone.utc) if now is None else now)
        sku_ids = [_identity(v['sku_id']) for v in st['plan']['variants']]
        if not sku_ids or len(set(sku_ids)) != len(sku_ids):
            raise ValueError('unique_variant_scope_required')
        scope = {'product_id': product_id, 'sku_ids': sorted(sku_ids), 'marketplace': 'EBAY_DE',
                 'currency': 'EUR', 'content_sha256': scope_digest(product_id, st)}
        cfg = runtime.read_config()
        raw_key = cfg.get('LISTING_EVIDENCE_HMAC_KEY')
        if not isinstance(raw_key, str) or re.fullmatch(r'[0-9a-fA-F]{64}', raw_key) is None:
            raise ValueError('trusted_review_key_not_configured')
        key = bytes.fromhex(raw_key)
        relative = cfg.get('LISTING_EVIDENCE_FILE') or 'data/listing_evidence/manifest.json'
        path = _path_beneath(runtime.PROJECT_ROOT, relative)
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError('manifest_too_large')
        manifest = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(manifest, dict) or set(manifest) != {'version', 'records'} or type(manifest['version']) is not int or manifest['version'] != 1:
            raise ValueError('manifest_schema_invalid')
        records = manifest['records']
        if not isinstance(records, list) or len(records) > 1000 or any(not isinstance(r, dict) for r in records):
            raise ValueError('manifest_records_invalid')
        matched = [r for r in records if isinstance(r.get('scope'), dict) and r['scope'].get('product_id') == product_id]
        accepted, expiries = [], []
        for requirement, blocker in DOCUMENT_REQUIREMENTS.items():
            candidates = [r for r in matched if r.get('requirement') == requirement]
            try:
                if len(candidates) != 1:
                    raise ValueError('unique_review_required')
                expires = _record(candidates[0], key, scope, path.parent / 'documents', observed)
                out['accepted_requirements'].append(requirement)
                out['satisfied_blockers'].append(blocker)
                accepted.append(candidates[0])
                expiries.append(expires)
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                out['errors'][requirement] = 'missing_invalid_stale_or_scope_mismatched_review'
        out['missing_blockers'] = [b for b in DOCUMENT_REQUIREMENTS.values() if b not in out['satisfied_blockers']]
        if accepted:
            out['review_fingerprint'] = hashlib.sha256(_canonical(accepted)).hexdigest()
            out['valid_until'] = min(expiries).isoformat()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        # Do not expose paths, file text, parser messages, signing keys or provider data.
        out['errors']['source'] = 'review_source_missing_invalid_or_unconfigured'
    return out


def validate_saved(product_id, artifact, *, now=None):
    """Re-read signatures/files/expiry before remote writes; never trust cached OK."""
    saved = artifact.get('document_evidence')
    current = verify_product(product_id, artifact['st'], now=now)
    if (not isinstance(saved, dict) or current['missing_blockers']
            or not current['review_fingerprint']
            or saved.get('review_fingerprint') != current['review_fingerprint']):
        raise ValueError('document_evidence_changed_missing_or_expired')
    return current
