"""Pure, fail-closed content/identity contract; never fetches or invents facts.

Coverage is explicit about missing metadata/source evidence. This is not legal,
freight, demand, authorization or supplier-readiness approval; those gates remain.
"""
from collections import Counter
import html
import json
import re

from src.listing_quality import categories

VERSION = '1'


def _identity(value):
    # Hata 44: AliExpress raw payloads sometimes carry product_id/sku_id as int, not str
    # (confirmed live: ae_item_base_info_dto.product_id came back as a Python int for several
    # real products) - that is a valid numeric identity, not invalid data. Coerce int only
    # (never bool/float/None - those stay rejected) before the real format check.
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        value = str(value)
    return isinstance(value, str) and re.fullmatch(r'[0-9]{6,}', value) is not None


def _norm_id(value):
    """Same int->str coercion as _identity, for values later compared/keyed against the
    plan's own (always-str) sku/pid representation - without this, a real int-typed raw id
    and the plan's str-typed id compare unequal even though they are the same identity."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value



def _values(value):
    if isinstance(value, str):
        value = [value]
    return value if isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value) else []


def inspect_plan(st):
    """Return blockers, warnings and per-aspect/per-SKU evidence coverage.

    Unknown optional facts are reported, not padded. Assertions contradicted by or
    unsupported by available supplier source are unsafe (including competitor,
    package, placeholder and old heuristic fills). Required unknown facts block.
    Old artifacts lacking new metadata get a coverage warning, not a blanket ban.
    """
    try:
        return _inspect_plan(st)
    except (AttributeError, TypeError, ValueError, KeyError, IndexError, OverflowError) as error:
        return {'version': VERSION, 'blockers': ['contract_invalid:' + type(error).__name__],
                'warnings': [], 'coverage': {'metadata_available': False,
                    'supplier_source_available': False, 'supplier_sku_source_available': False,
                    'aspects': [], 'unknown_required': [], 'unknown_optional': [], 'sku_identity': []}}


def _inspect_plan(st):
    blockers, warnings = [], []
    coverage = {'metadata_available': False, 'supplier_source_available': False,
                'supplier_sku_source_available': False, 'aspects': [],
                'unknown_required': [], 'unknown_optional': [], 'sku_identity': []}
    out = {'version': VERSION, 'blockers': blockers, 'warnings': warnings, 'coverage': coverage}
    if not isinstance(st, dict) or not isinstance(st.get('plan'), dict):
        blockers.append('content_plan_invalid')
        return out
    plan, shared = st['plan'], st.get('shared') or {}
    kept = plan.get('variants') or []
    if not isinstance(kept, list) or not kept:
        blockers.append('no_retained_variants')
        return out
    raw = st.get('res')
    source_available = isinstance(raw, dict) and isinstance(raw.get('ae_item_base_info_dto'), dict)
    raw = raw if isinstance(raw, dict) else {}
    coverage['supplier_source_available'] = source_available
    pid = (raw.get('ae_item_base_info_dto') or {}).get('product_id')
    pid = _norm_id(pid)
    if pid is not None and not _identity(pid):
        blockers.append('supplier_product_identity_invalid')
    sku_source_available = 'ae_item_sku_info_dtos' in raw
    coverage['supplier_sku_source_available'] = sku_source_available
    sku_rows = raw.get('ae_item_sku_info_dtos') or {}
    sku_rows = sku_rows.get('ae_item_sku_info_d_t_o', []) if isinstance(sku_rows, dict) else sku_rows
    if not isinstance(sku_rows, list):
        sku_rows = []
        blockers.append('supplier_sku_schema_invalid')
    counts = Counter(_norm_id(s.get('sku_id')) for s in sku_rows if isinstance(s, dict) and _identity(s.get('sku_id')))
    if any(count > 1 for count in counts.values()):
        blockers.append('supplier_sku_identity_ambiguous')
    seen_skus, combinations = set(), set()
    for variant in kept:
        sid, sku = variant.get('sku_id'), variant.get('sku')
        match = re.fullmatch(r'AE-([0-9]{6,})-([0-9]{6,})', sku) if isinstance(sku, str) else None
        valid = bool(_identity(sid) and match and match[2] == sid and (pid is None or match[1] == pid))
        if not valid:
            blockers.append('retained_sku_identity_invalid')
        if sku in seen_skus:
            blockers.append('retained_sku_duplicate')
        seen_skus.add(sku)
        exact = counts.get(sid, 0) == 1 if sku_source_available else None
        if sku_source_available and not exact:
            blockers.append('retained_supplier_sku_not_exact_match')
        coverage['sku_identity'].append({'sku_id': sid, 'mapping_format_valid': valid,
                                         'supplier_exact_match': exact})
        asp = variant.get('aspects') or {}
        key = json.dumps(asp, ensure_ascii=False, sort_keys=True).casefold()
        if key in combinations:
            blockers.append('supplier_option_mapping_ambiguous')
        combinations.add(key)
        if asp and variant.get('verified') is False:
            blockers.append('variant_labels_unverified')
    if len(kept) > 1 and not plan.get('is_variation'):
        blockers.append('multiple_variants_without_group')
    if plan.get('flags'):
        blockers.append('variant_review_required')
    if any('duplicate option combination' in str(row) for row in plan.get('dropped', [])):
        blockers.append('supplier_option_mapping_ambiguous')
    if not sku_source_available:
        warnings.append('supplier_sku_source_unavailable')

    meta = st.get('aspect_metadata')
    if meta is None:
        meta = []
        warnings.append('category_aspect_metadata_unavailable')
    elif not isinstance(meta, list) or any(not isinstance(a, dict) or not a.get('name') for a in meta):
        blockers.append('category_aspect_metadata_invalid')
        meta = []
    else:
        coverage['metadata_available'] = True
    props = []
    for prop in (raw.get('ae_item_properties') or {}).get('ae_item_property') or []:
        name, value = prop.get('attr_name'), prop.get('attr_value')
        if isinstance(name, str) and isinstance(value, str):
            props.append((html.unescape(name).strip(), html.unescape(value).strip()))
    subject = (raw.get('ae_item_base_info_dto') or {}).get('subject') or ''
    # Also inspect asserted fields outside current taxonomy metadata: old unsafe
    # brand/dimension/competitor fills must not hide behind incomplete metadata.
    known = {a['name'] for a in meta}
    extra = [{'name': name, 'required': False, 'mode': 'FREE_TEXT'} for name in shared if name not in known]
    supported, _ = categories.fill_aspects(meta + extra, props, subject=subject)
    for a in meta + extra:
        name, required = a['name'], bool(a.get('required'))
        aspect_coverage = {'name': name, 'required': required, 'in_category_metadata': name in known, 'variants': []}
        unknown = False
        for variant in kept:
            own = variant.get('aspects') or {}
            values = _values(own[name] if name in own else shared.get(name))
            status = 'missing'
            if values:
                valid_pick = (a.get('mode') != 'SELECTION_ONLY' or not a.get('values')
                              or all(v in a['values'] for v in values))
                if not valid_pick or (len(values) > 1 and not a.get('multi')):
                    blockers.append('invalid_aspect_value:' + name)
                if name in own:
                    status = 'supported' if variant.get('verified') is True else 'unverified'
                elif (st.get('aspect_provenance') or {}).get(name, {}).get('source') == 'verified_human_review':
                    # Hata 49: an explicit, human-verified fact (read off a real listing
                    # photo via vision_analyze, or cross-checked against the category's
                    # real picklist + the supplier's own title text -
                    # config/verified_extra_aspects.json) - trusted on its own provenance,
                    # never re-derived from/compared against the supplier's raw props
                    # (which is exactly why it was missing there).
                    status = 'supported'
                elif source_available:
                    status = ('supported' if all(v in supported.get(name, []) for v in values) else 'unsupported')
                    if status == 'unsupported':
                        blockers.append('unsafe_derived_fact:' + name)
                else:
                    status = 'unverified'
            if required and status == 'missing':
                blockers.append('required_aspect_missing:' + name)
            elif required and status == 'unverified':
                blockers.append('required_aspect_unverified:' + name)
            unknown = unknown or status != 'supported'
            aspect_coverage['variants'].append({'sku_id': variant.get('sku_id'), 'status': status})
        if unknown:
            coverage['unknown_required' if required else 'unknown_optional'].append(name)
            if not required:
                warnings.append('optional_aspect_unknown:' + name)
        coverage['aspects'].append(aspect_coverage)
    # Explicit provenance is negative evidence even when raw source is unavailable.
    for name, evidence in (st.get('aspect_provenance') or {}).items():
        origin = evidence.get('source') if isinstance(evidence, dict) else evidence
        if name in shared and origin in {'competitor', 'package', 'package_dimension', 'default', 'guess', 'width_as_depth'}:
            blockers.append('unsafe_derived_fact:' + name)
    if not source_available:
        warnings.append('supplier_fact_source_unavailable')
    out['blockers'] = list(dict.fromkeys(blockers))
    out['warnings'] = list(dict.fromkeys(warnings))
    return out
