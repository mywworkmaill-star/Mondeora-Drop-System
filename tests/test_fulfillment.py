import pytest
from sqlalchemy import create_engine

from src.automation.fulfillment import FulfillmentReceipt, sync_fulfillment
from src.database.models import Base, OrderLine, Product, get_session

CONFIG = {'TRACKING_CARRIER_MAP': {'CAINIAO': 'DHL'}}


class Supplier:
    def __init__(self, order):
        self.order = order

    def get_order(self, oid):
        return self.order


class Ebay:
    def __init__(self):
        self.posts = []

    def _request(self, method, path, **kw):
        if method == 'POST':
            self.posts.append(path)
            return {}
        if path.endswith('/shipping_fulfillment'):
            return {'fulfillments': []}
        return {'orderId': 'E1', 'orderPaymentStatus': 'PAID', 'cancelStatus': {'cancelState': 'NONE_REQUESTED'},
                'lineItems': [{'lineItemId': 'L1', 'sku': 'AE-555', 'quantity': 1}]}


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    s = get_session(engine)
    p = Product(aliexpress_product_id='555', sku_id='S', category_id='1', currency='EUR', fulfillment_verified=True)
    s.add(p); s.flush()
    s.add(OrderLine(ebay_order_id='E1', ebay_line_item_id='L1', product_id=p.id, aliexpress_order_id='A1',
                    external_order_id='x', quantity=1))
    s.commit()
    return s


def shipped(**over):
    base = {'order_id': 'A1', 'order_status': 'WAIT_BUYER_ACCEPT_GOODS', 'logistics_status': 'SELLER_SEND_GOODS',
            'child_order_list': {'ae_child_order_info': [{'product_id': '555', 'product_count': 1}]},
            'logistics_info_list': {'ae_order_logistics_info': [{'logistics_no': 'TRK1', 'logistics_service': 'CAINIAO'}]}}
    base.update(over)
    return base


def test_unpaid_order_waits(session):
    stats = sync_fulfillment(session, Supplier({'order_id': 'A1', 'order_status': 'PLACE_ORDER_SUCCESS'}), Ebay(), CONFIG)
    assert stats['awaiting_payment'] == 1 and stats['hold'] == 0


def test_identity_mismatch_goes_to_manual_review(session):
    sync_fulfillment(session, Supplier(shipped(order_id='OTHER')), Ebay(), CONFIG)
    assert session.query(OrderLine).one().status == 'manualreview'


def test_unknown_carrier_goes_to_manual_review(session):
    s = shipped(logistics_info_list={'ae_order_logistics_info': [{'logistics_no': 'T', 'logistics_service': 'UNKNOWN'}]})
    sync_fulfillment(session, Supplier(s), Ebay(), CONFIG)
    assert session.query(OrderLine).one().status == 'manualreview'


def test_no_tracking_upload_without_enable_flag(session):
    ebay = Ebay()
    sync_fulfillment(session, Supplier(shipped()), ebay, CONFIG)
    assert ebay.posts == []
    assert session.query(FulfillmentReceipt).one().upload_state == 'not_uploaded'
