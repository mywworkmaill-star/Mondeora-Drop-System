"""Read-only authenticated-browser checkout bridge. No JSON observation import.

Only an already open, single-item German AliExpress checkout is read. Never
navigates, clicks, changes an address, creates an order or initiates payment.
Unrecognized DOM/layout/amount semantics remain source_unavailable.
Run python -m src.checkout_evidence --help for the bounded capture entrypoint.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit, parse_qs
import requests


class SourceUnavailable(ValueError):
    pass


CHECKOUT_PATHS = {'/p/trade/confirm.html', '/p/order/index.html', '/trade/confirm_order.htm'}

# Extract rendered text, not embedded application state, scripts or caller JSON.
# The parser supports semantic dt/dd, table rows, and two-leaf summary rows only.
DOM_EXPRESSION = r'''(() => {
 const visible=e=>!!(e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
 const text=e=>e.innerText.trim();
 const rows=[];
 for(const e of document.querySelectorAll('dt,tr,div')) {
   if(!visible(e))continue;
   if(e.tagName==='DT'&&e.nextElementSibling?.tagName==='DD')
     rows.push([text(e),text(e.nextElementSibling)]);
   else {const c=Array.from(e.children).filter(visible);
     if(c.length===2&&c.every(x=>x.children.length===0)&&text(e).length<200)
       rows.push(c.map(text));}
 }
 return {url:location.href,lang:document.documentElement.lang,
   title:document.title,body:document.body.innerText.slice(0,60000),
   links:Array.from(document.querySelectorAll('a[href]')).filter(visible).map(e=>e.href).slice(0,500),
   addresses:Array.from(document.querySelectorAll('address')).filter(visible).map(text),
   quantities:Array.from(document.querySelectorAll('input[type="number"]')).filter(visible).map(e=>e.value),
   rows:rows.slice(0,500)};
})()'''


def _origin(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in {'de.aliexpress.com','www.aliexpress.com'} or p.path not in CHECKOUT_PATHS:
        raise SourceUnavailable('authenticated_checkout_page_not_open_product_pages_are_not_checkout')
    return p


def read_browser(cdp_http='http://127.0.0.1:9222', scope=None):
    """GET targets then Runtime.evaluate only, through a local existing browser.

    CDP itself has privileged browser access; allow loopback endpoints only. No
    credentials, remote debugger proxy, target creation or browser launch here.
    """
    p=urlsplit(cdp_http)
    if p.scheme!='http' or p.hostname not in {'127.0.0.1','localhost','::1'} or p.username or p.password or p.path not in {'','/'}:
        raise SourceUnavailable('loopback_cdp_endpoint_required')
    try:
        response=requests.get(cdp_http.rstrip('/')+'/json/list',timeout=4)
        response.raise_for_status()
        targets=response.json()
        candidates=[]
        for target in targets:
            if target.get('type')!='page':continue
            try:_origin(target.get('url',''))
            except SourceUnavailable:continue
            candidates.append(target)
        if not 1<=len(candidates)<=5:
            raise SourceUnavailable('one_to_five_existing_checkout_tabs_required')
        observed=[]
        for target in candidates:
            ws=target.get('webSocketDebuggerUrl','')
            w=urlsplit(ws)
            if w.scheme!='ws' or w.hostname not in {'127.0.0.1','localhost','::1'}:
                raise SourceUnavailable('local_checkout_debugger_access_required')
            value=_read_cdp(ws)
            if len(candidates)==1:return value
            if scope is not None:
                try:parse_checkout(value,scope)
                except (ValueError, TypeError, KeyError, AttributeError):continue
                observed.append(value)
        if len(observed)==1:return observed[0]
        raise SourceUnavailable('unique_matching_checkout_scope_not_available')
    except SourceUnavailable:raise
    except ImportError:raise SourceUnavailable('browser_bridge_aiohttp_dependency_missing') from None
    except Exception:raise SourceUnavailable('browser_session_access_unavailable') from None


def _read_cdp(ws):
    """Use the existing declared aiohttp dependency; one read-only CDP command."""
    import asyncio
    import aiohttp
    async def read():
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.ws_connect(ws,max_msg_size=2**20) as socket:
                await socket.send_json({'id':1,'method':'Runtime.evaluate','params':{
                    'expression':DOM_EXPRESSION,'returnByValue':True,'timeout':4000}})
                for _ in range(30):
                    message=await socket.receive_json(timeout=5)
                    if message.get('id')==1:
                        value=message.get('result',{}).get('result',{}).get('value')
                        if not isinstance(value,dict):raise SourceUnavailable('checkout_dom_read_not_available')
                        return value
        raise SourceUnavailable('checkout_dom_read_not_available')
    return asyncio.run(read())


def collect(scope, *, cdp_http='http://127.0.0.1:9222'):
    try:
        observed=read_browser(cdp_http,scope)
        record=parse_checkout(observed,scope)
        return {'status':'observed','read_only':True,'engine_evidence_written':False,
                'record':record,'capture_sha256':_digest(observed)}
    except SourceUnavailable as error:
        return {'status':'source_unavailable','read_only':True,'engine_evidence_written':False,
                'blocker':str(error),'software_implemented':True}
    except (ValueError, TypeError, KeyError, AttributeError):
        return {'status':'source_unavailable','read_only':True,'engine_evidence_written':False,
                'blocker':'checkout_dom_schema_not_supported','software_implemented':True}


def _digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def parse_checkout(observed, scope):
    """Strict German single-item semantic checkout; unsupported layouts hold.

    Missing SKU-bearing item href, number quantity control, semantic address,
    independent VAT/import row or explicit VAT inclusion is NOT inferred.
    """
    from decimal import Decimal
    from src.finance import money
    _origin(observed.get('url',''))
    if observed.get('lang') not in {'de','de-DE'}:
        raise SourceUnavailable('german_checkout_locale_required')
    qty=scope.get('quantity')
    if type(qty) is not int or not 1<=qty<=10000:
        raise SourceUnavailable('positive_integer_quantity_required')
    ids=set()
    for link in observed.get('links',[]):
        p=urlsplit(link)
        match=re.fullmatch(r'/item/([0-9]+)\.html',p.path)
        if p.hostname in {'de.aliexpress.com','www.aliexpress.com'} and match:
            sku=parse_qs(p.query).get('sku_id',[])
            if len(sku)!=1:raise SourceUnavailable('selected_sku_not_exposed_by_checkout_dom')
            ids.add((match[1],sku[0]))
    if ids!={(scope.get('product_id'),scope.get('sku_id'))}:
        raise SourceUnavailable('unique_selected_checkout_product_sku_mismatch')
    if observed.get('quantities')!=[str(qty)]:
        raise SourceUnavailable('unique_checkout_quantity_mismatch')
    addresses=observed.get('addresses',[])
    postcode=scope.get('ship_to_postal_code')
    if (not isinstance(postcode,str) or not re.fullmatch(r'[0-9]{5}',postcode)
            or len(addresses)!=1 or 'Deutschland' not in addresses[0]
            or re.findall(r'(?<!\d)\d{5}(?!\d)',addresses[0])!=[postcode]):
        raise SourceUnavailable('exact_germany_checkout_postcode_not_observed')
    rows=observed.get('rows',[])
    if not isinstance(rows,list) or len(rows)>500:
        raise SourceUnavailable('bounded_semantic_checkout_rows_required')
    def amount(labels):
        hits=[row[1] for row in rows if isinstance(row,list) and len(row)==2 and row[0] in labels]
        if len(hits)!=1:raise SourceUnavailable('independent_checkout_amount_missing_or_ambiguous')
        value=hits[0]
        if not isinstance(value,str) or not re.fullmatch(r'(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+),[0-9]{2}\s*(?:€|EUR)',value):
            raise SourceUnavailable('explicit_german_eur_amount_required')
        return money(re.sub(r'\s*(?:€|EUR)$','',value).replace('.','').replace(',','.'))
    subtotal=amount({'Zwischensumme','Artikelbetrag'})
    shipping=amount({'Versand','Versandkosten'})
    vat=amount({'MwSt.','Mehrwertsteuer'})
    # A customs-duty-only row does not establish all additional import costs.
    imports=amount({'Einfuhrabgaben','Importgebühren'})
    total=amount({'Gesamt','Gesamtsumme'})
    body=observed.get('body','')
    included='Preis inkl. MwSt.' in body
    excluded='Preis exkl. MwSt.' in body
    if included==excluded:raise SourceUnavailable('source_vat_inclusion_not_explicit')
    tax=Decimal('0') if included else vat
    if vat>subtotal+shipping or subtotal<=0 or subtotal+shipping+tax+imports!=total:
        raise SourceUnavailable('checkout_breakdown_does_not_reconcile_or_unrecognized_adjustments')
    unit=subtotal/qty
    if unit!=money(unit):raise SourceUnavailable('exact_unit_price_not_available')
    return dict(product_id=scope['product_id'],sku_id=scope['sku_id'],quantity=qty,
                currency='EUR',ship_to_country='DE',ship_to_postal_code=postcode,
                unit_source=str(money(unit)),shipping_total=str(shipping),
                source_tax_total=str(money(tax)),source_vat_observed=str(vat),
                additional_import_cost=str(imports),supplier_checkout_total=str(total),
                source_vat_semantics=('included_in_unit_source' if included else 'excluded_from_unit_source_explicit_tax_total'),
                import_cost_scope='all_additional_import_costs_explicit',
                observed_at=datetime.now(timezone.utc).isoformat(),cost_source='supplier_checkout',
                cost_evidence_reference='browser-dom-sha256:'+_digest(observed))


def read_category(category_id, category_root, cfg):
    """Read official EBAY_DE tree and verify the leaf under the configured family."""
    from src.finance import RULES
    if (category_root not in RULES or not isinstance(category_id,str)
            or not re.fullmatch(r'[0-9]+',category_id)):
        raise SourceUnavailable('supported_confirmed_category_required')
    token=cfg.get('EBAY_ACCESS_TOKEN')
    if not token:raise SourceUnavailable('ebay_taxonomy_authenticated_access_required')
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    base='https://api.ebay.com/commerce/taxonomy/v1'
    try:
        reply=requests.get(base+'/get_default_category_tree_id',params={'marketplace_id':'EBAY_DE'},headers=headers,timeout=15)
        reply.raise_for_status();tree=reply.json()['categoryTreeId']
        if not isinstance(tree,str) or not re.fullmatch(r'[0-9]+',tree):raise ValueError()
        reply=requests.get(base+'/category_tree/'+tree+'/get_category_subtree',
                           params={'category_id':category_root},headers=headers,timeout=20)
        reply.raise_for_status();payload=reply.json()
        node=payload['categorySubtreeNode']
        if node['category']['categoryId']!=category_root:raise ValueError()
        stack=[node];matches=[];count=0
        while stack:
            node=stack.pop();count+=1
            if count>100000:raise ValueError()
            if node.get('category',{}).get('categoryId')==category_id:matches.append(node)
            stack.extend(node.get('childCategoryTreeNodes',[]))
        if len(matches)!=1 or matches[0].get('leafCategoryTreeNode') is not True:
            raise SourceUnavailable('category_leaf_not_in_verified_tariff_family')
        return dict(category_id=category_id,category_root=category_root,
                    category_source='verified_ebay_category_mapping',
                    category_evidence_reference='ebay-taxonomy-sha256:'+_digest(payload))
    except SourceUnavailable:raise
    except Exception:raise SourceUnavailable('ebay_taxonomy_read_unavailable') from None


def verify_record(record, cfg):
    """Do not trust a hash, user JSON or verified flag: read exact live sources again."""
    from src.finance_evidence import _fresh
    if not isinstance(record,dict) or record.get('collector')!='aliexpress_german_dom_v1':
        raise SourceUnavailable('automatic_browser_capture_required_no_manual_json_authority')
    _fresh(record.get('observed_at'))
    fresh=collect(record,cdp_http=cfg.get('CHECKOUT_CDP_HTTP','http://127.0.0.1:9222'))
    if fresh['status']!='observed':raise SourceUnavailable(fresh['blocker'])
    keys=('product_id','sku_id','quantity','currency','ship_to_country','ship_to_postal_code',
          'unit_source','shipping_total','source_tax_total','source_vat_observed',
          'additional_import_cost','supplier_checkout_total','source_vat_semantics','import_cost_scope')
    if any(record.get(key)!=fresh['record'][key] for key in keys):
        raise SourceUnavailable('checkout_current_source_changed_recapture_required')
    category=read_category(record.get('category_id'),record.get('category_root'),cfg)
    if any(record.get(key)!=value for key,value in category.items()):
        raise SourceUnavailable('category_current_source_changed_recapture_required')
    return {'passed':True,'source_authenticated':True,'read_only':True}


def capture_to_file(path, scope, *, category_id, category_root, cfg):
    """Atomic exact-scope writer. No input file/import or verified flag accepted."""
    from pathlib import Path
    import os, tempfile
    result=collect(scope,cdp_http=cfg.get('CHECKOUT_CDP_HTTP','http://127.0.0.1:9222'))
    if result['status']!='observed':return result
    try:category=read_category(category_id,category_root,cfg)
    except SourceUnavailable as error:
        return dict(status='source_unavailable',blocker=str(error),read_only=True,engine_evidence_written=False)
    record=dict(result['record'],**category,collector='aliexpress_german_dom_v1')
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_name(path.name+'.finance-evidence.lock');temporary=None
    try:descriptor=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise SourceUnavailable('evidence_writer_busy_or_interrupted_lock_requires_review') from None
    try:
        os.close(descriptor)
        payload=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'records':[],'order_records':[]}
        rows=payload['records']
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('invalid_finance_records')
        identity=lambda r:tuple(r.get(k) for k in ('product_id','sku_id','quantity','ship_to_country','ship_to_postal_code'))
        rows=[r for r in rows if identity(r)!=identity(record)]+[record]
        payload['records']=sorted(rows,key=lambda r:str(identity(r)))
        descriptor,temporary=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            json.dump(payload,stream,ensure_ascii=False,sort_keys=True,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path);temporary=None
    finally:
        if temporary:Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return dict(status='captured',read_only=True,engine_evidence_written=True,records_written=1)


def _ebay_get(path, cfg, params=None):
    token=cfg.get('EBAY_ACCESS_TOKEN')
    if not token:raise SourceUnavailable('authenticated_ebay_order_access_required')
    try:
        response=requests.get('https://api.ebay.com'+path,params=params,
                              headers={'Authorization':'Bearer '+token,'Accept':'application/json'},timeout=20)
        response.raise_for_status();payload=response.json()
        if not isinstance(payload,dict) or payload.get('errors'):raise ValueError()
        return payload
    except Exception:raise SourceUnavailable('ebay_order_expense_read_unavailable') from None


def read_order_expenses(order_id, lines, cfg):
    """GET existing exact order, actual fees and collected VAT; never a fee forecast.

    Contract: Fulfillment getOrder fieldGroups=TAX_BREAKDOWN and documented
    totalMarketplaceFee (cumulative expenses already including the fixed charge).
    No provider fixed-charge split is exposed: retain None, not an invented zero.
    """
    from decimal import Decimal
    from urllib.parse import quote
    from src.finance import money
    if not isinstance(order_id,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}',order_id):
        raise SourceUnavailable('exact_existing_ebay_order_id_required')
    raw=_ebay_get('/sell/fulfillment/v1/order/'+quote(order_id,safe=''),cfg,{'fieldGroups':'TAX_BREAKDOWN'})
    if raw.get('orderId')!=order_id or raw.get('orderPaymentStatus')!='PAID':
        raise SourceUnavailable('paid_ebay_order_identity_mismatch')
    if raw.get('cancelStatus',{}).get('cancelState') not in (None,'NONE_REQUESTED'):
        raise SourceUnavailable('cancelled_order_expenses_require_reconciliation')
    def amount(value):
        if not isinstance(value,dict) or value.get('currency')!='EUR':
            raise SourceUnavailable('actual_eur_order_expense_missing')
        try:return money(value.get('value'))
        except ValueError:raise SourceUnavailable('actual_order_amount_unknown') from None
    gross=amount(raw.get('pricingSummary',{}).get('total'))
    fee=amount(raw.get('totalMarketplaceFee'))
    actual=raw.get('lineItems')
    if not isinstance(actual,list) or not actual or len(actual)!=len(lines):
        raise SourceUnavailable('exact_order_expense_lines_required')
    expected={r['line_item_id']:r for r in lines}
    if len(expected)!=len(lines):raise SourceUnavailable('unique_order_expense_lines_required')
    seen=set();vat=Decimal('0')
    for item in actual:
        key=item.get('lineItemId');row=expected.get(key)
        if (row is None or key in seen or item.get('sku') != 'AE-'+row['product_id']
                or type(item.get('quantity')) is not int
                or item['quantity']!=row['quantity'] or amount(item.get('lineItemCost'))!=money(row['line_gross'])):
            raise SourceUnavailable('live_order_expense_line_scope_mismatch')
        seen.add(key)
        taxes=item.get('ebayCollectAndRemitTaxes')
        if taxes is None:
            if raw.get('ebayCollectAndRemitTax') is not False:
                raise SourceUnavailable('marketplace_collected_tax_not_explicit')
            taxes=[]
        if not isinstance(taxes,list):raise SourceUnavailable('marketplace_tax_breakdown_invalid')
        for tax in taxes:
            if tax.get('taxType')!='VAT':raise SourceUnavailable('unsupported_collected_tax_type')
            vat+=amount(tax.get('amount'))
    if gross<=0 or vat>gross or fee>gross:raise SourceUnavailable('actual_order_expenses_inconsistent')
    return dict(order_id=order_id,currency='EUR',source='verified_order_expenses',
                observed_at=datetime.now(timezone.utc).isoformat(),
                evidence_reference='ebay-getOrder-sha256:'+_digest(raw),
                buyer_gross=str(gross),marketplace_vat=str(vat.quantize(Decimal('.01'))),
                gross_fee=str(fee),fixed_fee=None,lines=lines,
                fixed_fee_semantics='included_once_in_actual_total_no_provider_split')


def main(argv=None):
    import argparse
    from src.runtime import read_config,enable_read_only
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('product-id','sku-id','postal-code','category-id','category-root','output'):
        parser.add_argument('--'+name)
    parser.add_argument('--quantity',type=int,default=1)
    parser.add_argument('--cdp-http',default='http://127.0.0.1:9222')
    args=parser.parse_args(argv);enable_read_only()
    cfg=read_config();cfg['CHECKOUT_CDP_HTTP']=args.cdp_http
    scope=dict(product_id=args.product_id,sku_id=args.sku_id,quantity=args.quantity,ship_to_postal_code=args.postal_code)
    # Probe real browser access even when no selected scope exists; no navigation.
    if not all((args.product_id,args.sku_id,args.postal_code,args.category_id,args.category_root,args.output)):
        result=collect(scope,cdp_http=args.cdp_http)
        if result['status']=='observed':result=dict(status='source_unavailable',blocker='exact_product_category_destination_output_scope_required',engine_evidence_written=False)
    else:
        try:result=capture_to_file(args.output,scope,category_id=args.category_id,category_root=args.category_root,cfg=cfg)
        except (OSError,ValueError,TypeError,KeyError):result=dict(status='source_unavailable',blocker='evidence_writer_or_scope_invalid',engine_evidence_written=False)
    # Never emit checkout address, raw page, cookies, tokens or account identity.
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get('engine_evidence_written') else 2


if __name__=='__main__':
    raise SystemExit(main())
