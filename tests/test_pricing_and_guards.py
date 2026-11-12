from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from src import runtime
from src.automation.engine import AutamationEngine

CFG = {'EBAY_FEE_PERCENT': '13.5', 'MIN_PROFIT_EUR': '25', 'MIN_MARGIN_PERCENT': '25',
       'TAX_RESERVE_PERCENT': '0', 'EBAY_FIXED_FEE_EUR': '0'}


def engine(**over):
    return AutamationEngine(ebay_client=object(), aliexpress_client=object(),
                            db_engine=create_engine('sqlite://'), config={**CFG, **over})


@pytest.mark.parametrize('cost,ship', [(0.6, 0), (1.29, 0), (5, 0), (25.79, 0), (39.99, 5)])
def test_price_always_earns_minimum_profit(cost, ship):
    price = engine()._calculate_ebay_price(cost, ship)
    net = price * (1 - Decimal('0.135')) - Decimal(str(cost)) - Decimal(str(ship))
    assert net >= Decimal('25') - Decimal('0.01')


def test_price_rejects_bad_input():
    e = engine()
    for bad in (-1, 'nan', 'abc', None):
        with pytest.raises(ValueError):
            e._calculate_ebay_price(bad, 0)


def test_fee_must_be_configured_and_total_below_100():
    with pytest.raises(ValueError):
        engine(EBAY_FEE_PERCENT='')._calculate_ebay_price(5, 0)
    with pytest.raises(ValueError):
        engine(EBAY_FEE_PERCENT='60', MIN_MARGIN_PERCENT='50')._calculate_ebay_price(5, 0)


def test_writes_fail_closed():
    assert not runtime.writes_allowed({})
    assert not runtime.writes_allowed({'AUTOMATION_LIVE_WRITES': 'true'})
    assert runtime.writes_allowed({'AUTOMATION_LIVE_WRITES': 'true', 'SUPPLIER_AGREEMENT_CONFIRMED': 'true'})
    runtime.enable_read_only()
    assert not runtime.writes_allowed({'AUTOMATION_LIVE_WRITES': 'true', 'SUPPLIER_AGREEMENT_CONFIRMED': 'true'})


def test_engine_blocks_write_jobs_when_read_only():
    runtime.enable_read_only()
    e = engine(AUTOMATION_LIVE_WRITES='true', SUPPLIER_AGREEMENT_CONFIRMED='true')
    assert e._run('products', lambda s: {'status': 'ok'}, write=True)['status'] == 'blocked'
