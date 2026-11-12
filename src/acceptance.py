"""Verify a controlled order from local identities AND live provider evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from src.runtime import PROJECT_ROOT


def source_fingerprint():
    digest = hashlib.sha256()
    paths = [PROJECT_ROOT / 'main.py', PROJECT_ROOT / 'requirements.txt', *sorted((PROJECT_ROOT / 'src').rglob('*.py'))]
    for path in paths:
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def verify_acceptance(evidence_path=None, live=False, ebay=None, supplier=None, db_engine=None):
    path = Path(evidence_path or PROJECT_ROOT / 'data/acceptance_evidence.json')
    result = {'passed': False, 'reason': 'No controlled live order evidence exists'}
    if not path.exists():
        return result
    try:
        evidence = json.loads(path.read_text(encoding='utf-8'))
        if evidence.get('source_fingerprint') != source_fingerprint():
            return dict(result, reason='Acceptance belongs to a different runtime revision')
        names = ('ebay_order_id', 'ebay_line_item_id', 'aliexpress_order_id', 'tracking_number', 'carrier_code')
        if any(not isinstance(evidence.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', evidence[key]) for key in names):
            return dict(result, reason='Missing or invalid acceptance resource identifiers')
        recorded = datetime.fromisoformat(evidence['recorded_at'].replace('Z', '+00:00'))
        if recorded.tzinfo is None or recorded > datetime.now(timezone.utc):
            return dict(result, reason='Invalid acceptance timestamp')
        if not live:
            return dict(result, reason='Provider verification requires a live read-only check')
        from src.database.models import init_database, get_session, OrderLine, Product
        own_db = db_engine is None
        db = db_engine if db_engine is not None else init_database()
        try:
            with get_session(db) as session:
                line = session.query(OrderLine).filter_by(ebay_order_id=evidence['ebay_order_id'], ebay_line_item_id=evidence['ebay_line_item_id'], aliexpress_order_id=evidence['aliexpress_order_id']).one_or_none()
                if line is None or line.status not in ('shipped', 'delivered', 'tracking_uploaded'):
                    return dict(result, reason='No locally reconciled completed order line')
                product = session.get(Product, line.product_id)
                if product is None:
                    return dict(result, reason='Source product mapping unavailable')
                source_product_id, quantity = str(product.aliexpress_product_id), line.quantity
        finally:
            if own_db:
                db.dispose()
        if ebay is None:
            from src.api.ebay_client import eBayAPIClient
            ebay = eBayAPIClient()
        if supplier is None:
            from src.api.aliexpress_client import AliExpressAPIClient
            supplier = AliExpressAPIClient()
        sale = ebay._request('GET', '/sell/fulfillment/v1/order/' + evidence['ebay_order_id'])
        if (sale.get('orderId') != evidence['ebay_order_id'] or sale.get('orderPaymentStatus') != 'PAID' or sale.get('orderFulfillmentStatus') != 'FULFILLED' or sale.get('cancelStatus', {}).get('cancelState', 'NONE_REQUESTED') != 'NONE_REQUESTED'):
            return dict(result, reason='Sales order payment or fulfillment not confirmed')
        matching_lines = [r for r in sale.get('lineItems', []) if r.get('lineItemId') == evidence['ebay_line_item_id'] and r.get('quantity') == quantity and r.get('sku') == 'AE-' + source_product_id]
        if len(matching_lines) != 1:
            return dict(result, reason='Sales line identity or quantity does not match')
        order = supplier.get_order(evidence['aliexpress_order_id'])
        if str(order.get('order_id')) != evidence['aliexpress_order_id'] or order.get('order_status') not in ('WAIT_BUYER_ACCEPT_GOODS', 'FINISH'):
            return dict(result, reason='Supplier payment and dispatch not evidenced')
        from src.automation.fulfillment import _items
        from src.runtime import read_config
        children=_items(order,'child_order_list','ae_child_order_info')
        if (len(children)!=1 or str(children[0].get('product_id'))!=source_product_id
                or type(children[0].get('product_count')) is not int or children[0]['product_count']!=quantity):
            return dict(result,reason='Supplier child product/quantity not matched')
        logistics=_items(order,'logistics_info_list','ae_order_logistics_info')
        if len(logistics)!=1 or logistics[0].get('logistics_no')!=evidence['tracking_number']:
            return dict(result, reason='Supplier tracking not matched')
        carrier_map=read_config().get('TRACKING_CARRIER_MAP',{})
        if isinstance(carrier_map,str):carrier_map=json.loads(carrier_map)
        if not isinstance(carrier_map,dict) or carrier_map.get(logistics[0].get('logistics_service'))!=evidence['carrier_code']:
            return dict(result,reason='Supplier carrier mapping not verified')
        shipments = ebay._request('GET', '/sell/fulfillment/v1/order/' + evidence['ebay_order_id'] + '/shipping_fulfillment').get('fulfillments', [])
        for shipment in shipments:
            if shipment.get('shipmentTrackingNumber') == evidence['tracking_number'] and shipment.get('shippingCarrierCode') == evidence['carrier_code'] and any(r.get('lineItemId') == evidence['ebay_line_item_id'] and r.get('quantity') == quantity for r in shipment.get('lineItems', [])):
                return {'passed': True, 'reason': 'Controlled source payment/dispatch and sales tracking verified by live reads'}
        return dict(result, reason='Sales tracking fulfillment not matched')
    except Exception as error:
        return dict(result, reason='Acceptance verification failed', error_type=type(error).__name__)
