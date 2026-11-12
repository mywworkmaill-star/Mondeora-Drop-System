"""Bounded, read-only preparation of recorded real candidates. Never publishes.

Run: python -m src.product_preparation --limit 5
Old snapshots provide identities/provenance only: all supplier facts are reread.
No user-supplied evidence flags are accepted as verified documents or agreements.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.runtime import PROJECT_ROOT, enable_read_only, read_config
from src.automation.research import ProductResearcher
from src.acceptance import source_fingerprint


def collect_provider_facts(product_id,raw):
    """Retain real supplier claims without treating them as compliance approval."""
    if not isinstance(raw,dict) or str(raw.get('ae_item_base_info_dto',{}).get('product_id'))!=product_id:
        raise ValueError('Provider fact identity mismatch')
    properties=raw.get('ae_item_properties',{})
    properties=properties.get('ae_item_property',[]) if isinstance(properties,dict) else properties
    attributes={};conflicts=set()
    if not isinstance(properties,list):raise ValueError('Unsupported provider attribute schema')
    for row in properties:
        if not isinstance(row,dict):continue
        name,value=row.get('attr_name'),row.get('attr_value')
        if not isinstance(name,str) or not isinstance(value,str) or not name.strip() or not value.strip():continue
        if name in attributes and attributes[name]!=value:conflicts.add(name)
        else:attributes[name]=value
    for name in conflicts:attributes.pop(name,None)
    manufacturer=raw.get('manufacturer_info')
    manufacturer=manufacturer if isinstance(manufacturer,dict) else {}
    return {'source':'aliexpress.ds.product.get','source_product_id':product_id,
      'observed_at':datetime.now(timezone.utc).isoformat(),'evidence_level':'provider_claim_not_independent_verification',
      'attributes':attributes,'conflicting_attribute_names':sorted(conflicts),
      'manufacturer':manufacturer,'manufacturer_legal_identity_complete':all(isinstance(manufacturer.get(k),str) and bool(manufacturer[k].strip()) for k in ('name','address','email')),
      'store':raw.get('ae_store_info',{}),'packaging_not_product_dimensions':raw.get('package_info_dto',{}),
      'safety_compliance_verified':False,'eu_responsible_person_verified':False,'image_rights_verified':False}


def factual_german_draft(product, selected):
    """Original factual copy; scoped supplier claims, never compliance promises."""
    from html import escape, unescape
    import re
    from src.automation.research import product_kind_query
    title = str(product.get('product_title') or '')
    if not title or not selected.get('sku_id'):
        return None
    facts = product.get('provider_facts') or {}
    scoped = (facts.get('source') == 'aliexpress.ds.product.get'
              and str(facts.get('source_product_id')) == str(product.get('product_id')))
    attributes = facts.get('attributes', {}) if scoped else {}
    attributes = attributes if isinstance(attributes, dict) else {}
    kind = product_kind_query(title)
    clean = re.sub(r'<[^>]*>', '', unescape(kind)).strip()[:80]
    # Only explicit product properties are copied. Package dimensions stay out.
    names = {'material': 'Material', 'farbe': 'Farbe', 'color': 'Farbe',
             'breite': 'Breite', 'width': 'Breite', 'höhe': 'Höhe', 'height': 'Höhe',
             'länge': 'Länge', 'length': 'Länge', 'markenname': 'Marke',
             'brand name': 'Marke', 'modellnummer': 'Modell', 'model number': 'Modell'}
    aspects = {}
    for name, value in attributes.items():
        if isinstance(value, str) and name.casefold() in names:
            label = names[name.casefold()]
            if label not in aspects:
                aspects[label] = [value]
            elif aspects[label] != [value]:
                aspects.pop(label, None)
    rows = ''.join('<tr><th>' + escape(k) + '</th><td>' + escape(v[0]) + '</td></tr>' for k, v in aspects.items())
    description = ('<h2>' + escape(clean) + '</h2><p>Produktentwurf – nicht veröffentlicht.</p>'
        '<p>Lieferantenbezeichnung (ungeprüfte Angaben): ' + escape(title) + '</p>'
        '<p>Ausgewählte Lieferantenvariante: ' + escape(str(selected.get('sku_attr') or selected['sku_id'])) + '</p>'
        '<table>' + rows + '</table><p>Die aufgeführten Merkmale stammen aus der aktuellen Lieferantenantwort. '
        'Weitere Maße, Lieferumfang, Hersteller-/Sicherheitsunterlagen, Bildrechte und tatsächlicher Versandort sind vor Veröffentlichung zu belegen. '
        'Keine bestätigte Lieferfrist oder unabhängige Sicherheitsprüfung.</p>')
    return {'language': 'de-DE', 'title': clean, 'description_html': description,
        'source_product_id': str(product.get('product_id') or ''), 'source_sku_id': str(selected['sku_id']),
        'aspects': aspects, 'publication_payload': False,
        'source_facts_observed_at': facts.get('observed_at') if scoped else None,
        'supplier_attribute_claims': attributes,
        'facts_status': 'Current scoped supplier claims; not independently verified compliance, rights, demand or dispatch evidence'}


def prepare_report(input_path, output_path, *, supplier, ebay, config=None, limit=5):
    enable_read_only()
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('Preparation limit must be 1..50')
    input_path, output_path = Path(input_path), Path(output_path)
    if input_path.resolve() == output_path.resolve():
        raise ValueError('Keep source snapshot separate from preparation output')
    source_bytes = input_path.read_bytes()
    payload = json.loads(source_bytes)
    rows = payload.get('candidates')
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('Bounded candidate snapshot required')
    scoped = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Candidate record required')
        pid, sku = str(row.get('product_id') or ''), str(row.get('sku_id') or '')
        if not pid.isascii() or not pid.isdigit() or not sku or len(sku) > 128 or any(ord(c) < 32 for c in sku):
            raise ValueError('Actual product and selected SKU identifiers required')
        scoped.setdefault((pid, sku), []).append({'keyword': row.get('keyword'), 'niche': row.get('niche')})
    researcher = ProductResearcher(supplier, ebay, config=config)
    candidates = []
    for (pid, sku), provenance in list(scoped.items())[:limit]:
        observed = datetime.now(timezone.utc).isoformat()
        try:
            details = supplier.get_product_details(pid)
            if not isinstance(details, dict) or str(details.get('product_id')) != pid:
                raise ValueError('Mismatched supplier product identity')
            if hasattr(supplier, '_request'):
                try:
                    raw = supplier._request('aliexpress.ds.product.get', {'product_id': pid, 'ship_to_country': 'DE', 'target_currency': 'EUR', 'target_language': 'de'})['result']
                    details['provider_facts'] = collect_provider_facts(pid, raw)
                except Exception as error:
                    details['provider_facts'] = {'status': 'unavailable', 'error_type': type(error).__name__, 'safety_compliance_verified': False}
            item = researcher._candidate(details, str(provenance[0].get('keyword') or ''), selected_sku_id=sku)
            item['provider_facts'] = details.get('provider_facts', {'status': 'unavailable', 'reason': 'Provider fact capability unavailable'})
            refresh = {'status': 'ok', 'observed_at': observed, 'source': 'aliexpress.ds.product.get',
                       'product_id': pid, 'sku_id': sku, 'identity_matched': True,
                       'selected_sku_matched': str(item.get('sku_id')) == sku,
                       'facts_level': 'Current provider response, not independent product safety verification'}
        except Exception as error:
            # Old cached facts must not become current evidence on API failure.
            item = researcher._candidate({'product_id': pid}, str(provenance[0].get('keyword') or ''), selected_sku_id=sku)
            refresh = {'status': 'unavailable', 'observed_at': observed, 'source': 'aliexpress.ds.product.get',
                       'product_id': pid, 'sku_id': sku, 'error_type': type(error).__name__}
        item.update(requested_sku_id=sku, provenance=provenance, source_refresh=refresh)
        item.setdefault('provider_facts', {'status': 'unavailable', 'reason': 'Provider refresh failed', 'safety_compliance_verified': False})
        from src.listing_assets import selected_listing_assets
        try:
            assets=selected_listing_assets({'sku':'AE-'+pid,'source_product_id':pid,'source_sku_id':sku})
            item['image_assets']=assets
            item['image_preparation_status']='selected_sku_matched' if assets else 'not_in_selected_image_set'
            if assets and item.get('listing_draft'):
                item['listing_draft']['local_image_files']=[a['file'] for a in assets]
        except (ValueError,OSError,KeyError,TypeError):
            item['image_assets']=[]
            item['image_preparation_status']='blocked_missing_or_ambiguous_selected_sku_image'
            item['blockers']=list(dict.fromkeys(item['blockers']+['selected_sku_image_unverified']))
            item['ready_to_publish']=False
            item['preparation_state']='draft_ready' if item.get('listing_draft') else 'needs_source_data'
            item['missing_evidence'].append({'requirement':'selected_sku_image_unverified','status':'missing_or_unverified','owner':'agent','product_id':pid,'sku_id':sku})
        candidates.append(item)
    report = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'read_only': True, 'remote_mutations_performed': False,
              'source_fingerprint': source_fingerprint(),
              'input_snapshot': input_path.name, 'input_sha256': hashlib.sha256(source_bytes).hexdigest(),
              'input_use': 'Identifiers/provenance only; historical prices/readiness are not reused',
              'candidate_count': len(candidates), 'unique_product_count': len({c['product_id'] for c in candidates}),
              'draft_ready_count': sum(c['draft_ready'] for c in candidates),
              'publish_ready_count': sum(c['ready_to_publish'] for c in candidates),
              'source_refresh_success_count': sum(c['source_refresh']['status'] == 'ok' for c in candidates),
              'candidates': candidates,
              'evidence_ingestion': 'External true flags are not accepted. Supplier terms/documents and completed demand/account verifications are not currently available to this bounded read-only path.',
              'note': 'Draft readiness is local content preparation, not sourcing approval, profitable demand, publication, payment or unattended-commerce readiness. First purchase remains supervised.'}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(output_path)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only candidate preparation; no sale, order or payment')
    parser.add_argument('--input', type=Path, default=PROJECT_ROOT / 'data/niche_research_combined.json')
    parser.add_argument('--output', type=Path, default=PROJECT_ROOT / 'data/product_preparation.json')
    parser.add_argument('--limit', type=int, default=5)
    args = parser.parse_args(argv)
    enable_read_only()
    from src.api.aliexpress_client import AliExpressAPIClient
    from src.api.ebay_client import eBayAPIClient
    try:
        report = prepare_report(args.input, args.output, supplier=AliExpressAPIClient(),
                                ebay=eBayAPIClient(), config=read_config(), limit=args.limit)
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'read_only': True}))
        return 1
    print(json.dumps({key: report[key] for key in ('candidate_count', 'draft_ready_count',
        'publish_ready_count', 'source_refresh_success_count', 'read_only', 'source_fingerprint')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
