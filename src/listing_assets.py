"""Exact-SKU local image selection. No inference from gallery ordering or color names."""
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit
from PIL import Image
from src.runtime import PROJECT_ROOT

PNG_FOLDER=Path('data/product_images/ebay_png_1600x1600')


def image_key(url):
    if not isinstance(url,str):return None
    parsed=urlsplit(url)
    host=parsed.hostname or ''
    if parsed.scheme!='https' or not any(host==d or host.endswith('.'+d) for d in ('alicdn.com','aliexpress-media.com')):return None
    found=re.search(r'(/kf/[^/?]+?\.(?:jpg|jpeg|png|webp|gif|avif))(?:[_./]|$)',parsed.path,re.I)
    return found.group(1) if found else None


def validated_asset(asset,root=PROJECT_ROOT):
    root=Path(root).resolve();base=(root/PNG_FOLDER).resolve()
    path=(root/asset['file']).resolve()
    if not path.is_relative_to(base):raise ValueError('Image path outside selected PNG set')
    content=path.read_bytes()
    if len(content)>12000000 or hashlib.sha256(content).hexdigest()!=asset['sha256']:raise ValueError('Selected PNG changed or exceeds size bound')
    with Image.open(path) as image:
        if image.format!='PNG' or image.size!=(1600,1600):raise ValueError('1600x1600 PNG required')
        if getattr(image,'n_frames',1)!=1:raise ValueError('Animated PNG requires separate review')
        image.verify()
    with Image.open(path) as image:image.load()
    return path


def select_variant_assets(product_id,sku_id,raw,originals,png_manifest,*,root=PROJECT_ROOT):
    for value in (product_id,sku_id):
        if not isinstance(value,str) or not value.isascii() or not value.isdigit():raise ValueError('Exact product/SKU identifiers required')
    if str(raw.get('ae_item_base_info_dto',{}).get('product_id'))!=product_id:raise ValueError('Supplier product mismatch')
    skus=raw.get('ae_item_sku_info_dtos',{})
    skus=skus.get('ae_item_sku_info_d_t_o',[]) if isinstance(skus,dict) else skus
    matches=[s for s in skus if str(s.get('sku_id'))==sku_id]
    if len(matches)!=1:raise ValueError('Selected SKU missing or ambiguous')
    properties=matches[0].get('ae_sku_property_dtos',{})
    properties=properties.get('ae_sku_property_d_t_o',[]) if isinstance(properties,dict) else properties
    keys={image_key(p.get('sku_image')) for p in properties if isinstance(p,dict)}-{None}
    product_rows=[p for p in originals.get('products',[]) if p.get('product_id')==product_id]
    if len(product_rows)!=1:raise ValueError('Image collection product missing or ambiguous')
    pngs={p['file']:p for p in png_manifest.get('images',[])}
    assets=[];seen=set();excluded=0
    for img in product_rows[0].get('images',[]):
        key=image_key(img.get('original_url') or img.get('url'))
        if img.get('status')!='downloaded' or key not in keys:
            excluded+=1;continue
        relative=Path(img['file']).with_suffix('.png').as_posix()
        p=pngs.get(relative)
        if p is None:raise ValueError('Selected-SKU PNG missing from manifest')
        if key in seen:continue
        asset={'file':(PNG_FOLDER/relative).as_posix(),'sha256':p['sha256'],'source_image_url':img['url'],
               'match_basis':'exact_selected_sku_image_reference','product_id':product_id,'sku_id':sku_id}
        validated_asset(asset,root)
        assets.append(asset);seen.add(key)
    return {'product_id':product_id,'sku_id':sku_id,'assets':assets,'excluded_count':excluded,
            'status':'matched' if assets else 'no_explicit_sku_image','image_rights_verified':False,
            'remote_upload_performed':False,'gallery_images_require_separate_review':True}


def validated_visual_review(asset,root=PROJECT_ROOT):
    import json
    from datetime import datetime
    pid,sku=asset.get('product_id'),asset.get('sku_id')
    if any(not isinstance(v,str) or not v.isascii() or not v.isdigit() for v in (pid,sku)):
        raise ValueError('Scoped visual review identifiers required')
    review_path=Path(root)/'data/image_reviews'/(pid+'_'+sku+'.json')
    review=json.loads(review_path.read_text(encoding='utf-8'))
    if (review.get('product_id')!=pid or review.get('sku_id')!=sku
            or review.get('reviewed_png_sha256')!=asset['sha256']
            or review.get('reviewer')!='agent_visual_review' or not review.get('visible_findings')
            or review.get('asset',{}).get('file')!=asset['file']):
        raise ValueError('Scoped visual image review mismatch')
    observed=datetime.fromisoformat(review.get('observed_at',''))
    if observed.tzinfo is None:raise ValueError('Dated visual review required')
    path=validated_asset(asset,root)
    if not path.is_relative_to((Path(root)/PNG_FOLDER/pid).resolve()):raise ValueError('Reviewed image belongs to another product')
    return path


def prepare_exact_sku_image(product_id, sku_id, raw, source_url, content, *, root=PROJECT_ROOT):
    """Prepare one real explicit SKU photograph locally, without AI or rights claims.

    Download is deliberately separate; no gallery fallback, hosting or network
    mutation is possible here. Preserve original bytes and both source hashes.
    """
    import io
    from datetime import datetime, timezone
    from PIL import ImageOps
    if any(not isinstance(v, str) or not v.isascii() or not v.isdigit() for v in (product_id, sku_id)):
        raise ValueError('Exact numeric source identifiers required')
    if str(raw.get('ae_item_base_info_dto', {}).get('product_id')) != product_id:
        raise ValueError('Supplier product mismatch')
    skus = raw.get('ae_item_sku_info_dtos', {})
    skus = skus.get('ae_item_sku_info_d_t_o', []) if isinstance(skus, dict) else skus
    matches = [s for s in skus if str(s.get('sku_id')) == sku_id]
    if len(matches) != 1:
        raise ValueError('Selected SKU missing or ambiguous')
    properties = matches[0].get('ae_sku_property_dtos', {})
    properties = properties.get('ae_sku_property_d_t_o', []) if isinstance(properties, dict) else properties
    references = {image_key(p.get('sku_image')) for p in properties if isinstance(p, dict)} - {None}
    key = image_key(source_url)
    if key is None or key not in references:
        raise ValueError('No explicit selected SKU image reference')
    if not isinstance(content, bytes) or not 1 <= len(content) <= 12000000:
        raise ValueError('Bounded actual image bytes required')
    with Image.open(io.BytesIO(content)) as image:
        if image.width * image.height > 25000000 or getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Bounded single-frame image required')
        image.load()
        original_size = list(image.size)
        image = ImageOps.exif_transpose(image).convert('RGBA')
        image = ImageOps.contain(image, (1600, 1600), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (1600, 1600), 'white')
        canvas.paste(image, ((1600-image.width)//2, (1600-image.height)//2), image)
    digest = hashlib.sha256(content).hexdigest()
    root = Path(root)
    original = root/'data/product_images/sourcing_v2_originals'/product_id/(sku_id+'_'+digest[:16]+'.image')
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(content)
    relative = PNG_FOLDER/product_id/('v2_'+sku_id+'_'+digest[:16]+'.png')
    path = root/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format='PNG', optimize=True)
    asset = {'file': relative.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_image_url': source_url, 'source_sha256': digest, 'source_file': original.relative_to(root).as_posix(),
        'source_dimensions': original_size, 'product_id': product_id, 'sku_id': sku_id,
        'match_basis': 'exact_selected_sku_image_reference', 'image_rights_verified': False,
        'transformation': 'Aspect-preserving resample and white padding; no generative edits, no AI enhancement',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'remote_upload_performed': False}
    validated_asset(asset, root)
    return asset


def selected_listing_assets(data,*,root=PROJECT_ROOT):
    """Read-only draft helper: return validated exact-SKU local assets or None for unmanaged products.

    Supply source_product_id/source_sku_id and seller sku. Missing/ambiguous managed
    selections raise ValueError; callers must retain that blocker, never use old URLs.
    No hosting, network requests or upload-ledger writes are performed.
    """
    import json
    selection=Path(root)/'data/listing_asset_selection.json'
    pid=data.get('source_product_id')
    seller_sku=data.get('sku','')
    if isinstance(seller_sku,str) and seller_sku.startswith('AE-'):
        encoded_pid=seller_sku[3:]
        if pid is not None and pid!=encoded_pid:
            raise ValueError('Seller SKU and source product identifiers conflict')
        pid=encoded_pid
    decisions=Path(root)/'config/operator_decisions.json'
    preference=json.loads(decisions.read_text(encoding='utf-8')).get('listing_image_preference',{}) if decisions.exists() else {}
    requested=preference.get('operator_requested_for_live_listings') is True and pid in preference.get('selected_product_ids',[])
    selections = [selection, Path(root)/'data/listing_asset_selection_v2.json']
    if not any(path.exists() for path in selections):
        if requested:raise ValueError('Required prepared-image selection manifest is missing')
        return None
    # Additive source sets; never overwrite or fall back around a corrupt set.
    entries = []
    for path in selections:
        if path.exists():
            entries.extend(json.loads(path.read_text(encoding='utf-8')).get('entries', []))
    matches=[e for e in entries if e.get('product_id')==pid]
    if not matches:
        if requested:raise ValueError('Requested product is missing from prepared-image selection')
        return None
    sku=data.get('source_sku_id')
    exact=[e for e in matches if e.get('sku_id')==sku]
    if len(exact)!=1:raise ValueError('Prepared image selection does not match the source SKU')
    assets=exact[0].get('assets')
    if not isinstance(pid,str) or not pid.isascii() or not pid.isdigit() or not isinstance(sku,str) or not sku.isascii() or not sku.isdigit():
        raise ValueError('Exact numeric source identifiers required')
    if not isinstance(assets,list) or not 1<=len(assets)<=24:raise ValueError('No unambiguous prepared images for this SKU')
    for asset in assets:
        if asset.get('product_id')!=pid or asset.get('sku_id')!=sku:
            raise ValueError('Prepared image provenance mismatch')
        if asset.get('match_basis')=='exact_selected_sku_image_reference':
            path=validated_asset(asset,root)
            if not path.is_relative_to((Path(root)/PNG_FOLDER/pid).resolve()):raise ValueError('Image belongs to another product')
        else:raise ValueError('Prepared image provenance mismatch')
    return assets


def listing_images(data,*,root=PROJECT_ROOT,publisher=None):
    """Managed products must use exact-SKU PNGs; never fall back to supplier URLs."""
    assets=selected_listing_assets(data,root=root)
    if assets is None:return None
    if not callable(publisher):raise ValueError('Prepared-image hosting is unavailable')
    urls=[publisher(asset) for asset in assets]
    if any(not isinstance(u,str) or urlsplit(u).scheme!='https' or not (urlsplit(u).hostname or '').endswith('.ebayimg.com') for u in urls):
        raise ValueError('Verified eBay-hosted HTTPS image required')
    return urls


def build_selection(*,root=PROJECT_ROOT,supplier=None):
    import json
    from datetime import datetime,timezone
    from src.runtime import enable_read_only
    enable_read_only()
    root=Path(root)
    if supplier is None:
        from src.api.aliexpress_client import AliExpressAPIClient
        supplier=AliExpressAPIClient()
    rows=json.loads((root/'data/sourcing_expansion_prepared.json').read_text(encoding='utf-8'))['candidates']
    originals=json.loads((root/'data/product_images/aliexpress_20261106_092718/manifest.json').read_text(encoding='utf-8'))
    pngs=json.loads((root/PNG_FOLDER/'manifest.json').read_text(encoding='utf-8'))
    entries=[]
    for row in rows:
        pid,sku=row['product_id'],row['sku_id']
        try:
            raw=supplier._request('aliexpress.ds.product.get',{'product_id':pid,'ship_to_country':'DE','target_currency':'EUR','target_language':'de'})['result']
            entry=select_variant_assets(pid,sku,raw,originals,pngs,root=root)
            # A generic visually plausible gallery photo cannot establish exact-SKU identity.
            # Preserve the missing-reference blocker even when a visual-review file exists.
        except Exception as error:
            entry={'product_id':pid,'sku_id':sku,'assets':[],'status':'blocked','error_type':type(error).__name__}
        entries.append(entry)
    report={'schema_version':1,'observed_at':datetime.now(timezone.utc).isoformat(),'read_only':True,
      'image_count_in_source_set':len(pngs['images']),'entries':entries,'remote_upload_performed':False,
      'selection_rule':'Only image references on the exact currently returned selected supplier SKU; generic gallery/description images excluded',
      'image_rights_verified':False}
    path=root/'data/listing_asset_selection.json'
    temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    return report


if __name__=='__main__':
    import json
    report=build_selection()
    print(json.dumps({'products':len(report['entries']),'matched_products':sum(bool(e['assets']) for e in report['entries']),
      'selected_images':sum(len(e['assets']) for e in report['entries']),'excluded_images':sum(e.get('excluded_count',0) for e in report['entries']),
      'entries':[{'product_id':e['product_id'],'sku_id':e['sku_id'],'selected':len(e['assets']),'status':e['status']} for e in report['entries']],
      'remote_upload_performed':False}))
