"""Conservative DE/EUR planning and local cash ledger; never tax filing or commerce writes."""
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING
import json
from pathlib import Path
import sqlite3

D=Decimal
CENT=D('.01')
RESERVE_PER_UNIT=D('2.00')
FEE_SOURCE='https://www.ebay.de/help/selling/fees-credits-invoices/gebuhren-fur-gewerbliche-verkaufer?id=4809'
# New goods, standard/above-standard seller, eBay.de commercial forecast.
RULES={
 '11700':{'name':'Möbel & Wohnen','rate':D('.14'),'above_990':D('.14')},
 '26395':{'name':'Beauty & Gesundheit (non-electrical)','rate':D('.12'),'above_990':D('.03')},
 '3187':{'name':'Heimwerker','rate':D('.13'),'above_990':D('.13')},
 '9815':{'name':'Büro & Schreibwaren','rate':D('.14'),'above_990':D('.14')},
}


def number(value):
    if isinstance(value,bool): raise ValueError('Boolean is not money')
    try: value=D(str(value))
    except (ValueError,TypeError,InvalidOperation): raise ValueError('Valid money required') from None
    if not value.is_finite() or not 0<=value<=D('10000000'): raise ValueError('Money out of range')
    return value


def money(value): return number(value).quantize(CENT,rounding=ROUND_HALF_UP)


def fee_quote(total_gross, category_root, *, fee_vat_percent='19'):
    total=money(total_gross)
    if category_root not in RULES: raise ValueError('No verified tariff for this category family')
    vat=number(fee_vat_percent)/100
    if vat>1: raise ValueError('Invalid fee VAT scenario')
    rule=RULES[category_root]
    fixed=D('.45') if total>D('10') else D('.35')
    net=(min(total,D('990'))*rule['rate']+max(D('0'),total-D('990'))*rule['above_990']+fixed).quantize(CENT,rounding=ROUND_HALF_UP)
    fee_vat=(net*vat).quantize(CENT,rounding=ROUND_HALF_UP)
    return {'net_fee':net,'fee_vat':fee_vat,'gross_fee':net+fee_vat,'fixed_fee':fixed,
            'rate':rule['rate'],'fee_model':'commercial_forecast_not_actual_private_account_charge',
            'fee_vat_is_scenario':True,'source':FEE_SOURCE}


def plan_order(total_gross,unit_source,shipping_total,category_root,*,quantity=1,
               additional_import_cost=None,marketplace_vat_percent='19',fee_vat_percent='19'):
    if type(quantity) is not int or not 1<=quantity<=10000: raise ValueError('Positive unit quantity required')
    gross=money(total_gross); cost=money(unit_source)*quantity; shipping=money(shipping_total)
    rate=number(marketplace_vat_percent)/100
    if rate>1: raise ValueError('Invalid marketplace VAT scenario')
    # Gross is the buyer TOTAL including any marketplace-collected VAT, not seller payout.
    marketplace_vat=(gross*rate/(1+rate)).quantize(CENT,rounding=ROUND_HALF_UP)
    fee=fee_quote(gross,category_root,fee_vat_percent=fee_vat_percent)
    reserve=RESERVE_PER_UNIT*quantity
    known=gross-marketplace_vat-fee['gross_fee']-cost-shipping-reserve
    import_cost=money(additional_import_cost) if additional_import_cost is not None else None
    return dict(fee,buyer_gross=gross,source_total=cost,shipping_total=shipping,marketplace_vat=marketplace_vat,
                tax_reserve=reserve,known_surplus_after_reserve=known,
                import_cost=import_cost,net_after_reserve=known-import_cost if import_cost is not None else None,
                costs_complete=import_cost is not None,tax_liability_calculated=False,
                actual_after_tax_profit_verified=False,
                note='Scenario only; unknown import costs are not zero. 2 EUR/unit is a reserve, not assessed tax.')


def price_floor(unit_source,shipping_total,category_root,*,quantity=1,target_profit='25',
                target_margin='.25',marketplace_vat_percent='19',fee_vat_percent='19'):
    target=number(target_profit); margin=number(target_margin)
    if margin>=1: raise ValueError('Invalid margin')
    def good(price):
        r=plan_order(price,unit_source,shipping_total,category_root,quantity=quantity,
                     marketplace_vat_percent=marketplace_vat_percent,fee_vat_percent=fee_vat_percent)
        profit=r['known_surplus_after_reserve']
        return profit>=target and profit>=price*margin
    low=D('0'); high=D('100')
    while not good(high):
        high*=2
        if high>D('100000'): raise ValueError('Target cannot be planned within bounds')
    for _ in range(60):
        mid=(low+high)/2
        if good(mid): high=mid
        else: low=mid
    candidate=high.quantize(CENT,rounding=ROUND_CEILING)
    while not good(candidate): candidate+=CENT
    return candidate


def allocate_money(total, weights):
    """Largest-remainder cent allocation; input order breaks ties deterministically."""
    total = number(total)
    if total != money(total):
        raise ValueError('Exact cent total required')
    weights = [number(value) for value in weights]
    if not weights or sum(weights) <= 0:
        raise ValueError('Positive allocation weights required')
    from decimal import ROUND_FLOOR
    raw = [total * 100 * weight / sum(weights) for weight in weights]
    cents = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
    remainder = int(total * 100) - sum(cents)
    for index in sorted(range(len(raw)), key=lambda i: (-(raw[i] - cents[i]), i))[:remainder]:
        cents[index] += 1
    return [D(value) / 100 for value in cents]


def open_ledger(path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, order_id TEXT NOT NULL UNIQUE, paid_date TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS paid_sale_reserves (order_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute("CREATE TRIGGER IF NOT EXISTS no_reserve_update BEFORE UPDATE ON paid_sale_reserves BEGIN SELECT RAISE(ABORT,'Append-only reserve ledger'); END")
        db.execute("CREATE TRIGGER IF NOT EXISTS no_reserve_delete BEFORE DELETE ON paid_sale_reserves BEGIN SELECT RAISE(ABORT,'Append-only reserve ledger'); END")
        db.execute("CREATE TRIGGER IF NOT EXISTS no_sale_update BEFORE UPDATE ON sales BEGIN SELECT RAISE(ABORT,'Append-only ledger'); END")
        db.execute("CREATE TRIGGER IF NOT EXISTS no_sale_delete BEFORE DELETE ON sales BEGIN SELECT RAISE(ABORT,'Append-only ledger'); END")
        db.commit()


def append_sale(path, sale):
    if not isinstance(sale,dict): raise ValueError('Sale record required')
    order_id=sale.get('order_id')
    if not isinstance(order_id,str) or not order_id.strip() or len(order_id)>100 or any(ord(c)<32 for c in order_id):
        raise ValueError('Actual order ID required')
    try: paid=date.fromisoformat(sale['paid_date'])
    except (ValueError,TypeError,KeyError): raise ValueError('Actual ISO payment date required') from None
    if paid>date.today(): raise ValueError('Future payments cannot be booked as received')
    quantity=sale.get('quantity')
    if type(quantity) is not int or not 1<=quantity<=10000: raise ValueError('Positive sold unit count required')
    product=sale.get('product','')
    if not isinstance(product,str) or len(product)>500: raise ValueError('Bounded product summary required')
    record={'order_id':order_id,'paid_date':paid.isoformat(),'product':product,'quantity':quantity,
            'currency':'EUR','tax_reserve':str(RESERVE_PER_UNIT*quantity),'tax_liability':None,
            'source':'manual_actual_order_input','ship_from_country':None,'ship_from_evidence':'unknown'}
    required=('buyer_gross','marketplace_vat','ebay_fees_actual','source_total','shipping_total','other_total')
    for field in required:
        if sale.get(field) in (None,''): raise ValueError('Actual amount required: '+field)
        record[field]=str(money(sale[field]))
    if D(record['marketplace_vat'])>D(record['buyer_gross']): raise ValueError('Marketplace tax exceeds buyer payment')
    import_value=sale.get('import_total')
    record['import_total']=str(money(import_value)) if import_value not in (None,'') else None
    known=D(record['buyer_gross'])-sum(D(record[k]) for k in ('marketplace_vat','ebay_fees_actual','source_total','shipping_total','other_total','tax_reserve'))
    record['known_surplus_after_reserve']=str(known)
    record['net_after_reserve']=str(known-D(record['import_total'])) if record['import_total'] is not None else None
    record['costs_complete']=record['import_total'] is not None
    record['created_at']=datetime.now(timezone.utc).isoformat()
    # Do not invent private customer details or guessed order fees.
    open_ledger(path)
    try:
        with closing(sqlite3.connect(path)) as db:
            db.execute('BEGIN IMMEDIATE')
            reserved = db.execute('SELECT payload FROM paid_sale_reserves WHERE order_id=?', (order_id,)).fetchone()
            if reserved:
                prior = json.loads(reserved[0])
                if any(prior.get(k) != record[k] for k in ('quantity', 'paid_date', 'buyer_gross', 'currency')):
                    raise ValueError('Actual sale conflicts with existing paid reserve; reconcile manually')
            db.execute('INSERT INTO sales(order_id,paid_date,created_at,payload) VALUES (?,?,?,?)',
                       (order_id,record['paid_date'],record['created_at'],json.dumps(record,ensure_ascii=False)))
            db.commit()
    except sqlite3.IntegrityError: raise ValueError('This order is already recorded; do not duplicate it') from None
    return record


def record_paid_order_reserve(path, order):
    """Book only a verified received eBay payment, never forecast actual expenses.

    A separate append-only event keeps incomplete paid sales out of the complete
    actual-cost sales ledger. Order identity deduplicates both entry routes.
    """
    if not isinstance(order, dict) or order.get('orderPaymentStatus') != 'PAID':
        raise ValueError('Actual paid order required')
    if order.get('cancelStatus', {}).get('cancelState') not in (None, 'NONE_REQUESTED'):
        raise ValueError('Cancelled order requires reconciliation')
    order_id = order.get('orderId')
    if (not isinstance(order_id, str) or not order_id.strip() or len(order_id) > 100
            or any(ord(c) < 32 for c in order_id)):
        raise ValueError('Actual order identity required')
    lines = order.get('lineItems')
    if not isinstance(lines, list) or not lines:
        raise ValueError('Paid sale lines required')
    identities = set()
    quantity = 0
    for line in lines:
        if not isinstance(line, dict): raise ValueError('Paid sale line required')
        identity, units = line.get('lineItemId'), line.get('quantity')
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError('Unique paid sale line identity required')
        if type(units) is not int or not 1 <= units <= 10000:
            raise ValueError('Positive sold unit count required')
        identities.add(identity)
        quantity += units
    if quantity > 10000: raise ValueError('Sold unit count out of bounds')
    total = order.get('pricingSummary', {}).get('total', {})
    if total.get('currency') != 'EUR': raise ValueError('Actual EUR buyer total required')
    gross = money(total.get('value'))
    if gross <= 0: raise ValueError('Positive received payment required')
    payments = order.get('paymentSummary', {}).get('payments')
    if not isinstance(payments, list) or not payments:
        raise ValueError('Actual payment date and amount evidence required')
    dates, received = [], D('0')
    for payment in payments:
        if not isinstance(payment, dict) or payment.get('paymentStatus') != 'PAID':
            raise ValueError('Received payment evidence required')
        try: paid = datetime.fromisoformat(payment['paymentDate'].replace('Z', '+00:00'))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ValueError('Actual timezone-aware payment date required') from None
        if paid.tzinfo is None or paid.utcoffset() is None or paid > datetime.now(timezone.utc):
            raise ValueError('Actual past payment date required')
        amount = payment.get('paymentAmount', {})
        if amount.get('currency') != 'EUR': raise ValueError('Actual EUR payment required')
        received += money(amount.get('value'))
        dates.append(paid.astimezone(timezone.utc))
    if received != gross: raise ValueError('Received payments must match buyer total')
    record = dict(order_id=order_id, paid_date=max(dates).date().isoformat(), quantity=quantity,
                  currency='EUR', buyer_gross=str(gross), tax_reserve=str(RESERVE_PER_UNIT * quantity),
                  source='ebay_paid_order_payment_evidence', ebay_fees_actual=None,
                  net_after_reserve=None, costs_complete=False, tax_liability=None,
                  created_at=datetime.now(timezone.utc).isoformat())
    open_ledger(path)
    with closing(sqlite3.connect(path)) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT payload FROM sales WHERE order_id=?', (order_id,)).fetchone()
        if existing is None:
            existing = db.execute('SELECT payload FROM paid_sale_reserves WHERE order_id=?', (order_id,)).fetchone()
        if existing:
            prior = json.loads(existing[0])
            if any(prior.get(k) != record[k] for k in ('quantity', 'paid_date', 'buyer_gross', 'currency')):
                raise ValueError('Paid sale conflicts with existing reserve; reconcile manually')
            return prior
        db.execute('INSERT INTO paid_sale_reserves(order_id,payload) VALUES (?,?)',
                   (order_id, json.dumps(record)))
        db.commit()
    return record


def reserve_rows(path):
    """One reserve per actual order, preferring the complete actual-cost record.

    This read does not create a database or migrate an older ledger.
    """
    path = Path(path)
    if not path.exists(): return []
    with closing(sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rows = {}
        for table in ('paid_sale_reserves', 'sales'):
            if table in tables:
                for (payload,) in db.execute('SELECT payload FROM ' + table):  # nosec B608 - table from fixed whitelist
                    record = json.loads(payload)
                    rows[record['order_id']] = record
        return sorted(rows.values(), key=lambda r: (r['paid_date'], r['order_id']))


def ledger_rows(path):
    path=Path(path)
    if not path.exists(): return []
    with closing(sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True)) as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM sales ORDER BY paid_date,id')]
