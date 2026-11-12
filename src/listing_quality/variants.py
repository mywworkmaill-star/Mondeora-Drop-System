"""Variant model from raw SKU data: per-variant price, stock filter, eBay inventory_item_group payload (dry)."""
from src.listing_quality import labels
from src.listing_quality.pricing import price_for, settings

MAX_VARIANTS = 250
MAX_STOCK_PER_VARIANT = 5          # dropshipping exposure cap
SPREAD_REVIEW = 3.0                # max/min cost ratio above this -> human review


def parse_skus(res):
    raw = (res.get('ae_item_sku_info_dtos') or {})
    raw = raw.get('ae_item_sku_info_d_t_o', []) if isinstance(raw, dict) else raw
    out = []
    for s in raw:
        props = (s.get('ae_sku_property_dtos') or {}).get('ae_sku_property_d_t_o') or []
        asp, img, verified, color = {}, None, True, False
        for p in props:
            name = str(p.get('sku_property_name') or f"Option{p.get('sku_property_id')}").strip()[:65]
            if name.lower() in ('ships from', 'ship from', 'versand aus', 'warehouse'):
                continue   # logistics metadata, not a buyer-selectable product variant; must not affect label verification
            val, ok = labels.label(p.get('property_value_definition_name'), p.get('sku_property_value'))
            asp[name] = val
            verified = verified and ok
            color = color or labels.has_color(p.get('property_value_definition_name'))
            img = img or p.get('sku_image')
        try:
            cost = float(s.get('offer_sale_price') or s.get('sku_price'))
        except (TypeError, ValueError):
            cost = None
        if s.get('currency_code') not in (None, 'EUR'):
            cost = None
        out.append({'sku_id': str(s.get('sku_id')), 'aspects': asp, 'image': img, 'cost': cost, 'verified': verified, 'has_color': color,
                    'stock': int(s.get('sku_available_stock') or 0)})
    return out


def build(pid, res, ship, cfg=None):
    cfg = cfg or settings()
    skus, dropped, seen = parse_skus(res), [], set()
    keep = []
    for s in skus:
        if s['cost'] is None:
            dropped.append((s['sku_id'], 'no EUR price')); continue
        if s['stock'] <= 0:
            dropped.append((s['sku_id'], 'out of stock')); continue
        key = tuple(sorted(s['aspects'].items()))
        if key in seen:
            dropped.append((s['sku_id'], 'duplicate option combination')); continue
        seen.add(key)
        s['price'], s['net'] = price_for(s['cost'], ship, cfg)
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
    if is_var and any(not v['verified'] for v in keep):
        flags.append('variant labels not verifiable (no seller definition name): human review')
    if not is_var:
        for v in keep:   # single product: never publish an unverified/invented colour
            if not (v['verified'] and v['has_color']):
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
