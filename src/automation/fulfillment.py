"""Conservative supplier status reconciliation; never purchases or pays.

Contracts: AliExpress DS trade order lookup (API 60455), and eBay Sell
Fulfillment v1 getOrder/getShippingFulfillments/createShippingFulfillment.
Only a proven single-child/single-shipment mapping is automated. Unknown
statuses, multi-child shipments, variant-level attribution and delivery are
not inferred. Receipts are local evidence, not a replacement for provider reads.
"""
import json
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Any

from sqlalchemy import Column, Integer, String, Text
from src.database.models import Base, OrderLine, Product
from src.runtime import writes_allowed


class FulfillmentReceipt(Base):
    __tablename__ = 'fulfillment_receipts'
    id = Column(Integer, primary_key=True)
    order_line_id = Column(Integer, nullable=False, unique=True)
    state = Column(String(50), nullable=False, default='hold')
    supplier_state = Column(String(80))
    tracking_number = Column(String(200))
    carrier = Column(String(80))
    upload_state = Column(String(50), nullable=False, default='not_uploaded')
    external_fulfillment_id = Column(String(200))
    error_message = Column(Text)


def _items(data, name, child):
    value = data.get(name)
    if isinstance(value, dict):
        value = value.get(child)
    if not isinstance(value, list) or not value or not all(isinstance(v, dict) for v in value):
        raise ValueError('unsupported_supplier_schema')
    return value


def _tracking(result, line, product, config):
    if str(result.get('order_id')) != line.aliexpress_order_id:
        raise ValueError('supplier_identity_mismatch')
    if result.get('order_status') != 'WAIT_BUYER_ACCEPT_GOODS' or result.get('logistics_status') != 'SELLER_SEND_GOODS':
        raise ValueError('shipment_not_proven')
    children = _items(result, 'child_order_list', 'ae_child_order_info')
    if (len(children) != 1 or product is None
            or type(line.quantity) is not int or line.quantity <= 0
            or type(children[0].get('product_count')) is not int
            or str(children[0].get('product_id')) != product.aliexpress_product_id
            or children[0].get('product_count') != line.quantity):
        raise ValueError('supplier_child_mismatch')
    shipments = _items(result, 'logistics_info_list', 'ae_order_logistics_info')
    if len(shipments) != 1:
        raise ValueError('multiple_shipments_unsupported')
    shipment = shipments[0]
    tracking = shipment.get('logistics_no')
    mapping = config.get('TRACKING_CARRIER_MAP', {})
    if isinstance(mapping, str):
        mapping = json.loads(mapping)
    carrier = mapping.get(shipment.get('logistics_service')) if isinstance(mapping, dict) else None
    if not isinstance(tracking, str) or not isinstance(carrier, str):
        raise ValueError('tracking_or_carrier_unknown')
    tracking, carrier = tracking.strip(), carrier.strip()
    if not tracking or not carrier or len(tracking) > 200 or len(carrier) > 80 or any(c.isspace() or ord(c) < 32 for c in tracking + carrier):
        raise ValueError('tracking_or_carrier_unknown')
    return tracking, carrier


def _reconcile(ebay, path, line, receipt):
    result = ebay._request('GET', path + '/shipping_fulfillment')
    fulfillments = result['fulfillments']
    if not isinstance(fulfillments, list):
        raise ValueError('unsupported_ebay_fulfillments')
    relevant = []
    for item in fulfillments:
        if not isinstance(item, dict) or not isinstance(item.get('lineItems'), list):
            raise ValueError('unsupported_ebay_fulfillments')
        for reference in item['lineItems']:
            if not isinstance(reference, dict) or not reference.get('lineItemId'):
                raise ValueError('unsupported_ebay_fulfillments')
        if any(v['lineItemId'] == line.ebay_line_item_id for v in item['lineItems']):
            relevant.append(item)
    if not relevant:
        return False
    if len(relevant) != 1:
        raise ValueError('ambiguous_ebay_fulfillment')
    item = relevant[0]
    references = item['lineItems']
    if (item.get('shipmentTrackingNumber') != receipt.tracking_number
            or item.get('shippingCarrierCode') != receipt.carrier
            or len(references) != 1
            or type(references[0].get('quantity')) is not int
            or references[0]['quantity'] != line.quantity
            or not isinstance(item.get('fulfillmentId'), str) or not item['fulfillmentId']):
        raise ValueError('conflicting_ebay_fulfillment')
    receipt.external_fulfillment_id = item['fulfillmentId']
    receipt.upload_state = 'uploaded'
    return True


def sync_fulfillment(session, supplier, ebay, config):
    FulfillmentReceipt.__table__.create(session.get_bind(), checkfirst=True)
    stats: dict[str, Any] = {'checked': 0, 'awaiting_payment': 0, 'uploaded': 0, 'hold': 0}
    if str(config.get('EMAIL_INGESTION_ENABLED', '')).lower() == 'true':
        from pathlib import Path
        from src.database.models import PROJECT_ROOT
        from src.email_tracking import ingest_folder, ingest_imap
        from src.gmail_ingestion import ingest_gmail
        # Gmail intake failure is separate from authoritative supplier/eBay
        # reconciliation. Transport never supplies shipment/upload permission.
        gmail = ingest_gmail(session, config)
        stats['email_ingestion'] = {'gmail': gmail,
                                    'mailbox_verified': gmail['mailbox_verified']}
        try:
            folder = Path(config.get('EMAIL_EML_FOLDER') or PROJECT_ROOT / 'data/email_tracking/inbox')
            if not folder.is_absolute():
                folder = PROJECT_ROOT / folder
            if (not config.get('EMAIL_EML_FOLDER') and not folder.is_dir()
                    and str(config.get('EMAIL_GMAIL_ENABLED', '')).lower() == 'true'):
                local = {'status': 'local_not_configured', 'rejected': 0}
            else:
                local = ingest_folder(session, folder, config)
            remote = ingest_imap(session, config,
                enabled=str(config.get('EMAIL_IMAP_ENABLED', '')).lower() == 'true')
            stats['email_ingestion'].update(local=local, imap=remote)
            stats['email_ingestion']['mailbox_verified'] = gmail['mailbox_verified'] or remote.get('status') == 'read_only'
            if local['rejected'] or remote.get('status') in ('imap_read_failed', 'mailbox_not_configured') or remote.get('rejected', 0):
                stats['email_ingestion']['status'] = 'blocked'
                stats['status'] = 'blocked'
                return stats
        except Exception:
            session.rollback()
            stats['email_ingestion'] = {'status': 'email_ingestion_failed'}
            stats['status'] = 'blocked'
            return stats
    for line in session.query(OrderLine).filter(OrderLine.aliexpress_order_id.isnot(None)).all():
        stats['checked'] += 1
        receipt = session.query(FulfillmentReceipt).filter_by(order_line_id=line.id).one_or_none()
        if receipt is None:
            receipt = FulfillmentReceipt(order_line_id=line.id)
            session.add(receipt)
        try:
            receipt.error_message = None
            result = supplier.get_order(line.aliexpress_order_id)
            receipt.supplier_state = result.get('order_status')
            if str(result.get('order_id')) == line.aliexpress_order_id and receipt.supplier_state == 'PLACE_ORDER_SUCCESS':
                receipt.state = line.status = 'awaiting_payment'
                stats['awaiting_payment'] += 1
            else:
                if session.query(OrderLine).filter_by(aliexpress_order_id=line.aliexpress_order_id).count() != 1:
                    raise ValueError('supplier_order_multiple_local_lines')
                product = session.get(Product, line.product_id)
                tracking, carrier = _tracking(result, line, product, config)
                if (receipt.upload_state in ('pending', 'uncertain', 'uploaded')
                        and (receipt.tracking_number != tracking or receipt.carrier != carrier)):
                    raise ValueError('tracking_changed_after_upload_attempt')
                receipt.tracking_number, receipt.carrier = tracking, carrier
                receipt.state = line.status = 'shipped'
                path = '/sell/fulfillment/v1/order/' + quote(line.ebay_order_id, safe='')
                order = ebay._request('GET', path)
                matches = [v for v in order['lineItems'] if v.get('lineItemId') == line.ebay_line_item_id]
                if (order.get('orderId') != line.ebay_order_id or order.get('orderPaymentStatus') != 'PAID'
                        or order.get('cancelStatus', {}).get('cancelState') != 'NONE_REQUESTED'
                        or len(matches) != 1 or matches[0].get('sku') != 'AE-' + product.aliexpress_product_id
                        or type(matches[0].get('quantity')) is not int
                        or matches[0].get('quantity') != line.quantity):
                    raise ValueError('ebay_order_mismatch')
                from src.email_tracking import reconcile_email_hints
                reconcile_email_hints(session, line, tracking, carrier)
                if not _reconcile(ebay, path, line, receipt) and receipt.upload_state in ('pending', 'uncertain', 'uploaded'):
                    receipt.upload_state = 'uncertain'
                    raise ValueError('upload_requires_manual_reconciliation')
                if receipt.upload_state != 'uploaded' and matches[0].get('lineItemFulfillmentStatus') in ('FULFILLED', 'PARTIALLY_FULFILLED'):
                    raise ValueError('ebay_already_fulfilled_without_tracking_match')
                if receipt.upload_state != 'uploaded' and writes_allowed(config) and str(config.get('ENABLE_TRACKING_UPLOADS')).lower() == 'true':
                    # Compare-and-set, not an in-memory flag: another worker may
                    # have reserved after our last read. Never steal its claim.
                    claimed = session.query(FulfillmentReceipt).filter_by(
                        id=receipt.id, upload_state='not_uploaded').update(
                            {'upload_state': 'pending'}, synchronize_session=False)
                    if claimed != 1:
                        session.expire(receipt)
                        raise ValueError('upload_already_reserved')
                    session.commit()
                    session.refresh(receipt)
                    ebay._request('POST', path + '/shipping_fulfillment', json={
                        'lineItems': [{'lineItemId': line.ebay_line_item_id, 'quantity': line.quantity}],
                        'shippedDate': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                        'shippingCarrierCode': receipt.carrier, 'trackingNumber': receipt.tracking_number})
                    if not _reconcile(ebay, path, line, receipt):
                        receipt.upload_state = 'uncertain'
                        raise ValueError('upload_not_confirmed')
                if receipt.upload_state == 'uploaded':
                    stats['uploaded'] += 1
        except Exception:
            if receipt.upload_state == 'pending':
                receipt.upload_state = 'uncertain'
            receipt.state = line.status = 'manualreview'
            receipt.error_message = 'fulfillment_evidence_or_api_failure'
            stats['hold'] += 1
        session.commit()
    return stats
