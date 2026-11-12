"""Refresh real read-only observations; never submit orders, images or payments."""
import json
from datetime import datetime,timezone
from pathlib import Path
import sys
ROOT=Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
sys.path.insert(0,str(ROOT))
from src.readiness import build_report,probe_supplier_product
from src.api.ebay_client import eBayAPIClient
from src.api.aliexpress_client import AliExpressAPIClient
observations={'observed_at':datetime.now(timezone.utc).isoformat(),'api_reads':{},'read_only':True}
for key,path in (('ebay_inventory','/sell/inventory/v1/inventory_item'),('ebay_orders','/sell/fulfillment/v1/order')):
    try:
        result=eBayAPIClient()._request('GET',path,params={'limit':1})
        observations['api_reads'][key]=isinstance(result,dict) and not result.get('errors')
    except Exception as e:
        observations['api_reads'][key]=False
        observations.setdefault('error_types',{})[key]=type(e).__name__
try:
    selection=json.loads((ROOT/'data/listing_asset_selection_v2.json').read_text(encoding='utf-8'))['entries'][0]
    result=probe_supplier_product(AliExpressAPIClient(),selection['product_id'],selection['sku_id'])
    observations['api_reads']['aliexpress_selected_sku']=result.get('passed') is True
except Exception as e:
    observations['api_reads']['aliexpress_selected_sku']=False
    observations.setdefault('error_types',{})['aliexpress_selected_sku']=type(e).__name__
(ROOT/'data/completion_monitor_observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf-8')
report=build_report(live=False)
(ROOT/'data/completion_readiness_offline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({'api_reads':observations['api_reads'],'error_types':observations.get('error_types',{}),'readiness_check_names':[c['name'] for c in report['checks']]},ensure_ascii=True))
