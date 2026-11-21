"""Variant model from raw SKU data: per-variant price, stock filter, eBay inventory_item_group payload (dry)."""
from src.listing_quality import labels
from src.listing_quality.pricing import price_for, settings

MAX_VARIANTS = 250
MAX_STOCK_PER_VARIANT = 5          # dropshipping exposure cap
SPREAD_REVIEW = 3.0                # max/min cost ratio above this -> human review


def parse_skus(res, verified_aspects=None):
    """verified_aspects: optional {sku_id: {aspect_name: real_value}}, for when a human has confirmed
    the true value from evidence the auto-label heuristic can't use (e.g. checked the actual per-SKU
    photo). Only overrides aspects for the exact sku_id given - every other SKU is unaffected, and an
    unmatched sku_id in the override is silently ignored (never invents a SKU that doesn't exist)."""
    verified_aspects = verified_aspects or {}
    raw = (res.get('ae_item_sku_info_dtos') or {})
    raw = raw.get('ae_item_sku_info_d_t_o', []) if isinstance(raw, dict) else raw
    out = []
    for s in raw:
        sku_id = str(s.get('sku_id'))
        override = verified_aspects.get(sku_id) or {}
        props = (s.get('ae_sku_property_dtos') or {}).get('ae_sku_property_d_t_o') or []
        asp, img, verified, color, human_override = {}, None, True, False, bool(props)
        for p in props:
            name = str(p.get('sku_property_name') or f"Option{p.get('sku_property_id')}").strip()[:65]
            if name.lower() in ('ships from', 'ship from', 'versand aus', 'warehouse'):
                continue   # logistics metadata, not a buyer-selectable product variant; must not affect label verification
            if name in override:
                asp[name] = override[name]
                verified = verified and True
            else:
                val, ok = labels.label(p.get('property_value_definition_name'), p.get('sku_property_value'))
                asp[name] = val
                verified = verified and ok
                human_override = False   # at least one aspect came from the auto-heuristic, not a human
            color = color or labels.has_color(p.get('property_value_definition_name')) or (name in override)
            img = img or p.get('sku_image')
        try:
            cost = float(s.get('offer_sale_price') or s.get('sku_price'))
        except (TypeError, ValueError):
            cost = None
        if s.get('currency_code') not in (None, 'EUR'):
            cost = None
        out.append({'sku_id': str(s.get('sku_id')), 'aspects': asp, 'image': img, 'cost': cost, 'verified': verified, 'has_color': color,
                    'human_override': human_override, 'stock': int(s.get('sku_available_stock') or 0)})
    return out


def build(pid, res, ship, cfg=None, verified_aspects=None, legacy=False):
    cfg = cfg or settings()
    skus, dropped, seen = parse_skus(res, verified_aspects), [], {}
    ambiguous = False
    keep = []
    for s in skus:
        if s['cost'] is None:
            dropped.append((s['sku_id'], 'no EUR price')); continue
        # 🚨 SECURITY/DATA-INTEGRITY FIX (2026-11-21): cost<=0 (or non-finite)
        # used to pass this check (only `is None` was rejected) and flow
        # straight into price_for() -> a real eBay listing price pushed via
        # sync.py's bulk_update_price_quantity. readiness.py already rejects
        # cost<=0/non-finite for this same AliExpress field before order
        # placement; mirror that invariant here before it drives a live price.
        if not (cost := s['cost']) or cost <= 0 or cost != cost or cost in (float('inf'), float('-inf')):
            dropped.append((s['sku_id'], 'non-positive or non-finite cost')); continue
        if s['stock'] <= 0:
            dropped.append((s['sku_id'], 'out of stock')); continue
        key = tuple(sorted(s['aspects'].items()))
        if key in seen:
            if s['human_override'] and seen[key]['human_override']:
                # Hata 48: both colliding SKUs were human-confirmed (verified_variant_labels.json,
                # real per-SKU photo review) to be the same real-world variant - e.g. 3 AliExpress
                # SKUs that all photograph as plain white. That is a deliberate, safe duplicate
                # collapse, never an ambiguous heuristic guess; silently keep the first one seen
                # and drop this one, instead of forcing both into an unverified human-review flag.
                # Heuristic-only confidence (labels.label() guessing right) does NOT qualify -
                # only an explicit verified_aspects override counts as a human decision.
                dropped.append((s['sku_id'], 'verified duplicate of ' + seen[key]['sku_id']))
                continue
            # Same label is not proof of the same pack/model. Retain both identities
            # for review; no cheapest/first-SKU equivalence is safe to publish.
            ambiguous = True
            s['verified'] = seen[key]['verified'] = False
        else:
            seen[key] = s
        s['price'], s['net'] = price_for(s['cost'], ship, cfg, legacy=legacy)
        s['sku'] = f"AE-{pid}-{s['sku_id']}"[:50]
        s['qty'] = min(s['stock'], MAX_STOCK_PER_VARIANT)
        keep.append(s)
    keep.sort(key=lambda s: s['cost'])
    if len(keep) > MAX_VARIANTS:
        dropped += [(s['sku_id'], 'over 250 variants') for s in keep[MAX_VARIANTS:]]
        keep = keep[:MAX_VARIANTS]
    names = []
    for s in keep:
        for n in s['aspects']:
            if n not in names:
                names.append(n)
    spec = [{'name': n, 'values': sorted({s['aspects'].get(n) for s in keep if s['aspects'].get(n)})} for n in names]
    is_var = len(keep) > 1 and any(len(sp['values']) > 1 for sp in spec)
    flags = []
    if ambiguous:
        flags.append('ambiguous option combination across supplier SKUs: human review')
    if is_var and any(not v['verified'] for v in keep):
        flags.append('variant labels not verifiable (no seller definition name): human review')
    if not is_var:
        for v in keep:   # single product: never publish an unverified/invented colour
            if not ambiguous and not (v['verified'] and v['has_color']):
                v['aspects'] = {}
        spec = []
    if keep and max(s['cost'] for s in keep) / min(s['cost'] for s in keep) > SPREAD_REVIEW:
        flags.append('price spread >3x: check that expensive variants are the same product')
    if not keep:
        flags.append('no sellable variant')
    return {'is_variation': is_var, 'variants': keep, 'dropped': dropped, 'specifications': spec, 'flags': flags}


def group_payload(group_key, title, description, images, shared_aspects, plan):
    """eBay inventory_item_group body (NOT sent by this module)."""
    first = plan['specifications'][0]['name'] if plan['specifications'] else None
    return {'inventoryItemGroupKey': group_key, 'title': title[:80], 'description': description,
            'imageUrls': images[:12], 'aspects': shared_aspects,
            'variesBy': {'aspectsImageVariesBy': [first] if first else [], 'specifications': plan['specifications']},
            'variantSKUs': [v['sku'] for v in plan['variants']]}
