"""Automatic quality correction system: actively fixes quality gate failures.

Each auto_fix_* function:
1. Detects the issue (using gates.py checks)
2. Applies the fix (API calls)
3. Validates the result (Browse API verification)
4. Returns a structured report

Usage:
    from src.listing_quality import auto_fix
    
    result = auto_fix.auto_fix_title(ebay, ali, product_id, current_title)
    if result['success']:
        print(f"Title fixed: {result['new_title']}")
    else:
        print(f"Fix failed: {result['error']}")
"""
import json
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from src.listing_quality import gates, categories, description, publish, source, images

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / 'data' / 'auto_fix_logs'

logger = logging.getLogger(__name__)


class _RevisionBlocked(ValueError):
    pass


def _error(exc):
    # Provider error text can contain secrets/customer data; never persist it.
    return str(exc) if isinstance(exc, _RevisionBlocked) else type(exc).__name__


def _apply_verified_change(ebay, product_id, sku, field, value, artifact):
    """In-place single-listing revision only, with independent proof and readback."""
    from src import runtime
    from src.listing_quality import listing_evidence, ready_launch, ready_plan, ready_workflow
    if not isinstance(artifact, dict):
        raise _RevisionBlocked('verified_prepared_revision_required')
    listing_evidence.validate_saved(str(product_id), artifact)
    if ready_plan.readiness_blockers(ready_workflow.read_readiness()):
        raise _RevisionBlocked('current_readiness_not_verified')
    if artifact.get('config_fingerprint') != ready_plan.config_fingerprint():
        raise _RevisionBlocked('configuration_changed')
    if artifact['st']['plan']['is_variation']:
        raise _RevisionBlocked('variation_revision_requires_group_workflow')
    payloads = ready_launch.compile_payloads(str(product_id), artifact)
    matching = [item for item in payloads['items'] if item['sku'] == sku]
    if len(matching) != 1:
        raise _RevisionBlocked('exact_prepared_sku_required')
    expected = (str(artifact['st']['cat']['category_id']) if field == 'categoryId'
                else matching[0]['body']['product'][field])
    if value != expected:
        raise _RevisionBlocked('revision_differs_from_verified_content')
    runtime.require_writes()
    offers = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku}).get('offers', [])
    offers = [o for o in offers if o.get('sku') == sku and o.get('marketplaceId') == 'EBAY_DE'
              and o.get('status') == 'PUBLISHED' and o.get('listing', {}).get('listingId')]
    if len(offers) != 1:
        raise _RevisionBlocked('unique_published_offer_required')
    offer = offers[0]
    if field == 'categoryId':
        path = '/sell/inventory/v1/offer/' + quote(str(offer['offerId']), safe='')
        body = deepcopy(payloads['offers'][0]['body'])
        # Only the category changes; preserve every other current writable field.
        for key in body:
            if key in offer:
                body[key] = deepcopy(offer[key])
        body['categoryId'] = value
    else:
        path = '/sell/inventory/v1/inventory_item/' + quote(str(sku), safe='')
        current = ebay._request('GET', path)
        body = {key: deepcopy(current[key]) for key in
                ('product', 'availability', 'condition', 'conditionDescription', 'packageWeightAndSize') if key in current}
        body['product'][field] = deepcopy(value)
    ebay._request('PUT', path, json=body)
    readback = ebay._request('GET', path)
    actual = str(readback.get('categoryId')) if field == 'categoryId' else readback.get('product', {}).get(field)
    if actual != value:
        raise _RevisionBlocked('revision_needs_reconciliation_sell_readback')
    buyer = ebay._request('GET', '/buy/browse/v1/item/get_item_by_legacy_id',
                         params={'legacy_item_id': offer['listing']['listingId']})
    if field == 'categoryId':
        verified = str(buyer.get('categoryId')) == value or any(str(c.get('categoryId')) == value for c in buyer.get('categories', []))
    elif field == 'aspects':
        actual_aspects = {a.get('name'): a.get('value') for a in buyer.get('localizedAspects', [])}
        verified = all(len(v) == 1 and actual_aspects.get(k) == v[0] for k, v in value.items())
    else:
        verified = buyer.get(field) == value
    if not verified:
        raise _RevisionBlocked('revision_needs_reconciliation_buyer_readback')
    return {'api_updated': True, 'verified': True}


def _log_fix(fix_type, product_id, action, result, details=None):
    """Log every auto-fix action with timestamp and outcome."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'fix_type': fix_type,
        'product_id': product_id,
        'action': action,
        'result': result,
        'details': details or {}
    }
    
    log_file = LOG_DIR / f'{fix_type}_{datetime.utcnow().strftime("%Y%m%d")}.jsonl'
    with log_file.open('a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    return log_entry


def auto_fix_title(ebay, ali, product_id, current_title, props=None, sku=None, *, prepared_artifact=None):
    """Automatically fix title quality issues.
    
    Args:
        ebay: EBayAPIClient instance
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        current_title: Current eBay title
        props: Product properties [(name, value), ...] (optional, will fetch if None)
        sku: eBay SKU (optional, for updating existing listing)
    
    Returns:
        {
            'success': bool,
            'old_title': str,
            'new_title': str,
            'problems_found': list,
            'problems_fixed': list,
            'api_updated': bool,
            'verified': bool,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'old_title': current_title,
        'new_title': None,
        'problems_found': [],
        'problems_fixed': [],
        'api_updated': False,
        'verified': False
    }
    
    try:
        # 1. Detect problems
        problems = gates.check_title_quality(current_title)
        result['problems_found'] = problems
        
        if not problems:
            result['success'] = True
            result['new_title'] = current_title
            _log_fix('title', product_id, 'check', 'no_issues', {'title': current_title})
            return result
        
        # 2. Fetch product data if not provided
        if props is None:
            raw = source.fetch_raw(ali, product_id, use_cache=True)
            props = source.properties(raw)
            raw_title = raw.get('ae_item_base_info_dto', {}).get('subject', '')
        else:
            raw_title = current_title
        
        # 3. Generate improved title using publish.make_title()
        # This function already handles: word deduplication, foreign language removal,
        # emoji stripping, CAPS normalization, and proper German keywords
        improved_title = publish.make_title(raw_title)
        
        # 4. Verify the new title passes checks
        new_problems = gates.check_title_quality(improved_title)
        
        if new_problems:
            # If automated fix still has issues, log for manual review
            result['error'] = f"Auto-generated title still has issues: {new_problems}"
            _log_fix('title', product_id, 'generate', 'partial_fix', {
                'old_title': current_title,
                'new_title': improved_title,
                'remaining_issues': new_problems
            })
            return result
        
        result['new_title'] = improved_title
        result['problems_fixed'] = [p for p in problems if p not in new_problems]
        
        # 5. Update via API if SKU provided
        if sku:
            try:
                result.update(_apply_verified_change(ebay, product_id, sku, 'title', improved_title, prepared_artifact))
                
            except Exception as e:
                result['error'] = _error(e)
                _log_fix('title', product_id, 'update_api', 'failed', {
                    'sku': sku,
                    'error': _error(e)
                })
                return result
        
        result['success'] = True
        _log_fix('title', product_id, 'fix', 'success', {
            'old_title': current_title,
            'new_title': improved_title,
            'problems_fixed': result['problems_fixed']
        })
        
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('title', product_id, 'fix', 'error', {'error': _error(e)})
    
    return result


def auto_download_images(ali, product_id, current_images=None, target_count=8):
    """Automatically download and validate more images to meet quality requirements.
    
    Args:
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        current_images: Current image URLs (optional, will fetch if None)
        target_count: Target number of images (default 8)
    
    Returns:
        {
            'success': bool,
            'old_count': int,
            'new_count': int,
            'kept_urls': list,
            'dropped_urls': list,
            'problems_found': list,
            'problems_fixed': list,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'old_count': 0,
        'new_count': 0,
        'kept_urls': [],
        'dropped_urls': [],
        'problems_found': [],
        'problems_fixed': []
    }
    
    try:
        # 1. Fetch all available images
        if current_images is None:
            raw = source.fetch_raw(ali, product_id, use_cache=True)
            multimedia = raw.get('ae_multimedia_info_dto', {})
            image_urls = multimedia.get('image_urls', '').split(';') if multimedia.get('image_urls') else []
            # Also include SKU images
            skus = raw.get('ae_item_sku_info_dtos', {}).get('ae_item_sku_info_d_t_o', [])
            for sku in skus:
                sku_img = sku.get('sku_image')
                if sku_img and sku_img not in image_urls:
                    image_urls.append(sku_img)
        else:
            image_urls = current_images
        
        result['old_count'] = len(image_urls)
        
        # 2. Check current state
        problems, info = gates.check_image_count(image_urls)
        result['problems_found'] = problems
        
        if not problems:
            result['success'] = True
            result['kept_urls'] = image_urls
            result['new_count'] = len(image_urls)
            _log_fix('images', product_id, 'check', 'no_issues', info)
            return result
        
        # 3. Filter to valid images (≥500px)
        kept, dropped = images.filter_urls(image_urls)
        result['kept_urls'] = kept
        result['dropped_urls'] = dropped
        result['new_count'] = len(kept)
        
        # 4. Check if we meet requirements after filtering
        new_problems, new_info = gates.check_image_count(kept)
        
        if any(not problem.startswith('below ideal image count') for problem in new_problems):
            result['error'] = f"Insufficient valid images: {new_problems}"
            _log_fix('images', product_id, 'filter', 'insufficient', {
                'total': len(image_urls),
                'kept': len(kept),
                'dropped': len(dropped),
                'remaining_issues': new_problems
            })
        else:
            result['success'] = True
            result['problems_fixed'] = [p for p in problems if p not in new_problems]
            _log_fix('images', product_id, 'fix', 'success', {
                'old_count': result['old_count'],
                'new_count': result['new_count'],
                'dropped_count': len(dropped)
            })
    
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('images', product_id, 'fix', 'error', {'error': _error(e)})
    
    return result


def auto_generate_description(ebay, ali, product_id, title, current_description=None, 
                               variant_plan=None, sku=None, *, prepared_artifact=None):
    """Automatically generate or improve product description.
    
    Args:
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        title: Product title
        current_description: Current description (optional)
        variant_plan: Variant plan from variants.build() (optional)
        sku: eBay SKU (optional, for updating existing listing)
    
    Returns:
        {
            'success': bool,
            'old_description': str,
            'new_description': str,
            'old_length': int,
            'new_length': int,
            'problems_found': list,
            'problems_fixed': list,
            'api_updated': bool,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'old_description': current_description or '',
        'new_description': None,
        'old_length': len(current_description or ''),
        'new_length': 0,
        'problems_found': [],
        'problems_fixed': [],
        'api_updated': False
    }
    
    try:
        # 1. Check current description
        if current_description:
            problems, info = gates.check_description_quality(current_description)
            result['problems_found'] = problems
            
            if not problems:
                result['success'] = True
                result['new_description'] = current_description
                _log_fix('description', product_id, 'check', 'no_issues', info)
                return result
        
        # 2. Fetch product data
        raw = source.fetch_raw(ali, product_id, use_cache=True)
        
        # 3. Generate new description using description.build()
        # This creates unique, data-based HTML description with proper structure
        new_desc = description.build(title, raw, variant_plan)
        result['new_description'] = new_desc
        result['new_length'] = len(new_desc)
        
        # 4. Verify new description passes checks
        new_problems, new_info = gates.check_description_quality(new_desc)
        
        if new_problems:
            result['error'] = f"Generated description still has issues: {new_problems}"
            _log_fix('description', product_id, 'generate', 'partial_fix', {
                'length': result['new_length'],
                'remaining_issues': new_problems
            })
            return result
        
        result['problems_fixed'] = [p for p in result['problems_found'] if p not in new_problems]
        
        # 5. Update via API if SKU provided
        if sku:
            try:
                result.update(_apply_verified_change(ebay, product_id, sku, 'description', new_desc, prepared_artifact))
                
            except Exception as e:
                result['error'] = _error(e)
                _log_fix('description', product_id, 'update_api', 'failed', {
                    'sku': sku,
                    'error': _error(e)
                })
                return result
        
        result['success'] = True
        _log_fix('description', product_id, 'fix', 'success', {
            'old_length': result['old_length'],
            'new_length': result['new_length'],
            'problems_fixed': result['problems_fixed']
        })
        
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('description', product_id, 'fix', 'error', {'error': _error(e)})
    
    return result


def auto_fill_aspects(ebay, ali, product_id, current_aspects=None, sku=None, *, prepared_artifact=None):
    """Automatically fill or expand item specifics (aspects).
    
    Args:
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        current_aspects: Current aspects dict (optional)
        sku: eBay SKU (optional, for updating existing listing)
    
    Returns:
        {
            'success': bool,
            'old_aspects': dict,
            'new_aspects': dict,
            'old_count': int,
            'new_count': int,
            'problems_found': list,
            'problems_fixed': list,
            'api_updated': bool,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'old_aspects': current_aspects or {},
        'new_aspects': {},
        'old_count': len(current_aspects or {}),
        'new_count': 0,
        'problems_found': [],
        'problems_fixed': [],
        'api_updated': False
    }
    
    try:
        # 1. Check current aspects
        if current_aspects:
            problems, info = gates.check_item_specifics_count(current_aspects)
            result['problems_found'] = problems
            
            if not problems:
                result['success'] = True
                result['new_aspects'] = current_aspects
                result['new_count'] = len(current_aspects)
                _log_fix('aspects', product_id, 'check', 'no_issues', info)
                return result
        
        # 2. Fetch product properties from AliExpress
        raw = source.fetch_raw(ali, product_id, use_cache=True)
        props = source.properties(raw)
        
        # 3. Build aspects dict from properties
        aspects = dict(current_aspects) if current_aspects else {}
        
        # Add properties as aspects (German property names map to eBay aspects)
        for name, value in props:
            if name not in aspects and value:
                # Clean and normalize
                clean_value = str(value).strip()
                if clean_value and clean_value.upper() not in ('NONE', 'N/A', 'KEINE'):
                    aspects[name] = [clean_value]
        
        # Never invent brand, condition or manufacturer part number to hit a count.
        
        result['new_aspects'] = aspects
        result['new_count'] = len(aspects)
        
        # 4. Verify new aspects pass checks
        new_problems, new_info = gates.check_item_specifics_count(aspects)
        
        if new_problems:
            result['error'] = f"Generated aspects still insufficient: {new_problems}"
            _log_fix('aspects', product_id, 'generate', 'partial_fix', {
                'count': result['new_count'],
                'remaining_issues': new_problems
            })
            return result
        
        result['problems_fixed'] = [p for p in result['problems_found'] if p not in new_problems]
        
        # 5. Update via API if SKU provided
        if sku:
            try:
                result.update(_apply_verified_change(ebay, product_id, sku, 'aspects', aspects, prepared_artifact))
                
            except Exception as e:
                result['error'] = _error(e)
                _log_fix('aspects', product_id, 'update_api', 'failed', {
                    'sku': sku,
                    'error': _error(e)
                })
                return result
        
        result['success'] = True
        _log_fix('aspects', product_id, 'fix', 'success', {
            'old_count': result['old_count'],
            'new_count': result['new_count'],
            'added': list(set(aspects.keys()) - set(result['old_aspects'].keys()))
        })
        
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('aspects', product_id, 'fix', 'error', {'error': _error(e)})
    
    return result


def auto_correct_category(ebay, ali, product_id, title, current_category=None, 
                           props=None, sku=None, *, prepared_artifact=None):
    """Automatically correct category selection based on product data.
    
    Args:
        ebay: EBayAPIClient instance
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        title: Product title
        current_category: Current category result dict (optional)
        props: Product properties (optional, will fetch if None)
        sku: eBay SKU (optional, for updating existing listing)
    
    Returns:
        {
            'success': bool,
            'old_category': dict,
            'new_category': dict,
            'problems_found': list,
            'problems_fixed': list,
            'api_updated': bool,
            'verified': bool,
            'error': str (if failed)
        }
    """
    result = {
        'success': False,
        'old_category': current_category or {},
        'new_category': {},
        'problems_found': [],
        'problems_fixed': [],
        'api_updated': False,
        'verified': False
    }
    
    try:
        # 1. Check current category
        if current_category:
            problems, info = gates.check_category_confidence(current_category)
            result['problems_found'] = problems
            
            if not problems:
                result['success'] = True
                result['new_category'] = current_category
                _log_fix('category', product_id, 'check', 'no_issues', info)
                return result
        
        # 2. Fetch product data if needed
        if props is None:
            raw = source.fetch_raw(ali, product_id, use_cache=True)
            props = source.properties(raw)
        
        # 3. Resolve category using categories.resolve()
        # This uses voting over multiple queries and domain hints
        new_category = categories.resolve(ebay, title, props)
        result['new_category'] = new_category
        
        # 4. Verify new category passes checks
        new_problems, new_info = gates.check_category_confidence(new_category)
        
        if new_problems:
            result['error'] = f"Resolved category still has issues: {new_problems}"
            _log_fix('category', product_id, 'resolve', 'partial_fix', {
                'category': new_category,
                'remaining_issues': new_problems
            })
            return result
        
        result['problems_fixed'] = [p for p in result['problems_found'] if p not in new_problems]
        
        # 5. Update via API if SKU provided
        if sku:
            try:
                result.update(_apply_verified_change(ebay, product_id, sku, 'categoryId', str(new_category['category_id']), prepared_artifact))
                
            except Exception as e:
                result['error'] = _error(e)
                _log_fix('category', product_id, 'update_api', 'failed', {
                    'sku': sku,
                    'error': _error(e)
                })
                return result
        
        result['success'] = True
        _log_fix('category', product_id, 'fix', 'success', {
            'old_category': current_category.get('category_id') if current_category else None,
            'new_category': new_category['category_id'],
            'new_path': new_category['path'],
            'confidence': new_category['confidence']
        })
        
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('category', product_id, 'fix', 'error', {'error': _error(e)})
    
    return result


def auto_fix_all(ebay, ali, product_id, sku=None, dry_run=True, *, prepared_artifact=None):
    """Run all auto-fix operations on a product.
    
    Args:
        ebay: EBayAPIClient instance
        ali: AliExpressAPIClient instance
        product_id: AliExpress product ID
        sku: eBay SKU (optional, required for API updates)
        dry_run: If True, only check and prepare fixes without updating API
    
    Returns:
        {
            'success': bool,
            'product_id': str,
            'sku': str,
            'fixes': {
                'title': {...},
                'images': {...},
                'description': {...},
                'aspects': {...},
                'category': {...}
            },
            'summary': {
                'total_checks': int,
                'issues_found': int,
                'issues_fixed': int,
                'api_updates': int
            }
        }
    """
    result = {
        'success': False,
        'product_id': product_id,
        'sku': sku,
        'fixes': {},
        'summary': {
            'total_checks': 5,
            'issues_found': 0,
            'issues_fixed': 0,
            'api_updates': 0
        }
    }
    
    try:
        # Fetch product data once
        raw = source.fetch_raw(ali, product_id, use_cache=True)
        title = raw.get('ae_item_base_info_dto', {}).get('subject', '')
        props = source.properties(raw)
        
        # Get current data from eBay if SKU provided
        current_inv = None
        current_offer = None
        if sku:
            try:
                current_inv = ebay._request('GET', f'/sell/inventory/v1/inventory_item/{sku}')
                offers_resp = ebay._request('GET', '/sell/inventory/v1/offer', params={'sku': sku})
                current_offer = offers_resp.get('offers', [{}])[0]
            except Exception as e:
                logger.warning("Could not fetch current eBay data (%s)", type(e).__name__)
        
        # Run each fix
        update_sku = None if dry_run else sku
        
        # 1. Title
        current_title = current_inv['product']['title'] if current_inv else title
        title_result = auto_fix_title(ebay, ali, product_id, current_title, props, update_sku, prepared_artifact=prepared_artifact)
        result['fixes']['title'] = title_result
        if title_result['problems_found']:
            result['summary']['issues_found'] += len(title_result['problems_found'])
        if title_result['problems_fixed']:
            result['summary']['issues_fixed'] += len(title_result['problems_fixed'])
        if title_result.get('api_updated'):
            result['summary']['api_updates'] += 1
        
        # 2. Images
        current_images = current_inv['product'].get('imageUrls') if current_inv else None
        images_result = auto_download_images(ali, product_id, current_images)
        result['fixes']['images'] = images_result
        if images_result['problems_found']:
            result['summary']['issues_found'] += len(images_result['problems_found'])
        if images_result['problems_fixed']:
            result['summary']['issues_fixed'] += len(images_result['problems_fixed'])
        
        # 3. Description
        current_desc = current_inv['product'].get('description') if current_inv else None
        desc_result = auto_generate_description(ebay, ali, product_id, title, current_desc, None, update_sku, prepared_artifact=prepared_artifact)
        result['fixes']['description'] = desc_result
        if desc_result['problems_found']:
            result['summary']['issues_found'] += len(desc_result['problems_found'])
        if desc_result['problems_fixed']:
            result['summary']['issues_fixed'] += len(desc_result['problems_fixed'])
        if desc_result.get('api_updated'):
            result['summary']['api_updates'] += 1
        
        # 4. Aspects
        current_aspects = current_inv['product'].get('aspects') if current_inv else None
        aspects_result = auto_fill_aspects(ebay, ali, product_id, current_aspects, update_sku, prepared_artifact=prepared_artifact)
        result['fixes']['aspects'] = aspects_result
        if aspects_result['problems_found']:
            result['summary']['issues_found'] += len(aspects_result['problems_found'])
        if aspects_result['problems_fixed']:
            result['summary']['issues_fixed'] += len(aspects_result['problems_fixed'])
        if aspects_result.get('api_updated'):
            result['summary']['api_updates'] += 1
        
        # 5. Category
        current_category = {'category_id': current_offer.get('categoryId')} if current_offer else None
        category_result = auto_correct_category(ebay, ali, product_id, title, current_category, props, update_sku, prepared_artifact=prepared_artifact)
        result['fixes']['category'] = category_result
        if category_result['problems_found']:
            result['summary']['issues_found'] += len(category_result['problems_found'])
        if category_result['problems_fixed']:
            result['summary']['issues_fixed'] += len(category_result['problems_fixed'])
        if category_result.get('api_updated'):
            result['summary']['api_updates'] += 1
        
        # Overall success if all fixes succeeded
        all_success = all(
            fix_result.get('success', False) 
            for fix_result in result['fixes'].values()
        )
        result['success'] = all_success
        
        _log_fix('all', product_id, 'full_fix', 'success' if all_success else 'partial', result['summary'])
        
    except Exception as e:
        result['error'] = _error(e)
        _log_fix('all', product_id, 'full_fix', 'error', {'error': _error(e)})
    
    return result
