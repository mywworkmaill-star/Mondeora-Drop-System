"""Fail-closed orchestration; importing never starts jobs or APIs."""
from threading import Event, RLock
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor


class AutamationEngine:
    """Historical public spelling retained for dashboard compatibility."""

    def __init__(self, ebay_client=None, aliexpress_client=None, db_engine=None, config=None):
        from src.database.models import init_database
        self.config = config
        cfg = self._settings()
        if ebay_client is None:
            from src.api.ebay_client import eBayAPIClient
            ebay_client = eBayAPIClient()
        if aliexpress_client is None:
            from src.api.aliexpress_client import AliExpressAPIClient
            aliexpress_client = AliExpressAPIClient()
        self.ebay_client = ebay_client
        self.aliexpress_client = aliexpress_client
        self.engine = db_engine if db_engine is not None else init_database(cfg.get('DATABASE_URL'))
        self.sync_interval = float(cfg.get('SYNC_INTERVAL_HOURS', 1))
        self.max_products = int(cfg.get('MAX_PRODUCTS', 500))
        if self.max_products < 0:
            raise ValueError('MAX_PRODUCTS must be nonnegative')
        self._workflow_lock = RLock()
        self._job_locks = {key: RLock() for key in ('products', 'orders', 'inventory', 'prices', 'ebay_token', 'aliexpress_token', 'research', 'fulfillment')}
        self._last_results = {}

    def _allowed(self, purchase=False):
        from src.runtime import writes_allowed
        cfg = self._settings()
        return writes_allowed(cfg) and (not purchase or str(cfg.get('ALLOW_ORDER_PURCHASES', '')).lower() == 'true')

    def _run(self, name, action, write=False):
        """Isolated transaction and lock; never expose provider exception bodies/secrets."""
        from src.database.models import get_session, SyncLog
        from datetime import datetime
        if write and not self._allowed():
            return {'status': 'blocked', 'reason': 'Live writes or supplier agreement not enabled'}
        lock = self._job_locks[name]
        if not lock.acquire(blocking=False):
            return {'status': 'busy'}
        workflow = name in ('products', 'orders', 'inventory', 'prices', 'fulfillment')
        if workflow and not self._workflow_lock.acquire(blocking=False):
            lock.release()
            return {'status': 'busy'}
        session = None
        try:
            session = get_session(self.engine)
            try:
                result = action(session)
                session.commit()
            except Exception as exc:
                session.rollback()
                result = {'status': 'failed', 'error': type(exc).__name__,
                          'reason': 'Operation failed; no fallback data used. Check API permission and mapping.'}
                self._last_exc = exc
                try:  # vector memory of incidents (best effort, secrets scrubbed, never raises)
                    from src.intelligence.healing import classify, record_incident
                    record_incident('engine:' + name, exc, classify(exc), 'engine_run_failed', False)
                except Exception:
                    pass
                from src.checkout_evidence import SourceUnavailable
                if isinstance(exc, SourceUnavailable):
                    result.update(status='blocked', source_status='source_unavailable', reason=str(exc))
            session.add(SyncLog(sync_type=name, status=result['status'],
                        total_items=result.get('total', 0), processed_items=result.get('processed', result.get('synced', result.get('optimized', 0))),
                        failed_items=result.get('failed', int(result['status'] == 'failed')),
                        error_message=result.get('error'), completed_at=datetime.utcnow()))
            session.commit()
            self._last_results[name] = result
            return result
        finally:
            if session is not None:
                session.close()
            if workflow:
                self._workflow_lock.release()
            lock.release()

    @staticmethod
    def _vetted(product):
        return bool(product.fulfillment_verified and product.aliexpress_product_id and
                    product.sku_id and product.category_id and product.currency == 'EUR')

    def _details(self, product):
        data = self.aliexpress_client.get_product_details(product.aliexpress_product_id)
        if not isinstance(data, dict) or str(data.get('product_id')) != str(product.aliexpress_product_id):
            raise ValueError('Source product identity missing or mismatched')
        if data.get('skus'):
            matches = [sku for sku in data['skus'] if str(sku.get('sku_id')) == str(product.sku_id)]
            if len(matches) != 1:
                raise ValueError('Verified source SKU is missing or ambiguous')
            data = dict(data, **matches[0])
        if str(data.get('sku_id', '')) != str(product.sku_id):
            raise ValueError('Source SKU is not verified')
        if data.get('currency') not in (None, 'EUR'):
            raise ValueError('Source costs must be in EUR')
        stock = data.get('warehouse_count')
        if isinstance(stock, bool) or stock is None:
            raise ValueError('Real SKU stock is required')
        number = self._decimal(stock)
        if number != number.to_integral_value():
            raise ValueError('Stock must be an integer')
        data['warehouse_count'] = int(number)
        return data

    @staticmethod
    def _decimal(value):
        from decimal import Decimal, InvalidOperation
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError('Missing or invalid monetary value') from None
        if not number.is_finite() or number < 0:
            raise ValueError('Monetary values must be finite and nonnegative')
        return number

    def _settings(self):
        if getattr(self, 'config', None) is not None:
            return dict(self.config)
        from src.runtime import read_config
        return read_config()

    def _pricing_parameters(self, landed_cost=None):
        from decimal import Decimal
        config = self._settings()
        if not config.get('EBAY_FEE_PERCENT'):
            raise ValueError('EBAY_FEE_PERCENT must be explicitly configured')
        fees = self._decimal(config['EBAY_FEE_PERCENT']) / 100
        tax = self._decimal(config.get('TAX_RESERVE_PERCENT', '0')) / 100
        fixed = self._decimal(config.get('EBAY_FIXED_FEE_EUR', '0'))
        from src.listing_quality.pricing import tier_minimums
        if landed_cost is None:
            profit, margin = Decimal('25'), Decimal(str(self._decimal(config.get('MIN_MARGIN_PERCENT', '25')) / 100))
        else:
            tier_profit, tier_margin = tier_minimums(float(landed_cost))
            profit, margin = Decimal(str(tier_profit)), Decimal(str(tier_margin))
        if fees + tax + margin >= Decimal(1):
            raise ValueError('Fees, tax reserve and margin must total less than 100%')
        return fees + tax, fixed, profit, margin

    def _calculate_ebay_price(self, aliexpress_price, shipping_cost=None):
        from decimal import Decimal, ROUND_CEILING
        costs = self._decimal(aliexpress_price) + self._decimal(shipping_cost)
        rate, fixed, minimum, margin = self._pricing_parameters(landed_cost=costs)
        costs = costs + fixed
        return max((costs + minimum) / (1 - rate),
                   costs / (1 - rate - margin)).quantize(Decimal('.01'), rounding=ROUND_CEILING)

    def _finance_plan(self, product, data, *, quantity=1, total_gross=None, postal_code=None):
        """Bound checkout evidence and commercial forecast; never an actual tax verdict.

        FINANCE_EVIDENCE_FILE is a verifier-produced JSON object with a records list.
        It is deliberately separate from research proposals and never written here.
        """
        import json
        from pathlib import Path
        from datetime import datetime, timezone
        from src.finance import number, plan_order
        config = self._settings()
        evidence_path = config.get('FINANCE_EVIDENCE_FILE')
        if not isinstance(evidence_path, str) or not evidence_path:
            raise ValueError('Verified scoped finance evidence file required')
        try:
            records = json.loads(Path(evidence_path).read_text(encoding='utf-8'))['records']
        except (OSError, ValueError, KeyError, TypeError):
            raise ValueError('Finance evidence unavailable or malformed') from None
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError('Finance evidence records required')
        if type(quantity) is not int or not 1 <= quantity <= 10000:
            raise ValueError('Positive integer quantity required')
        matches = [r for r in records if r.get('product_id') == str(product.aliexpress_product_id)
                   and r.get('sku_id') == str(product.sku_id) and type(r.get('quantity')) is int
                   and r['quantity'] == quantity
                   and (postal_code is None or r.get('ship_to_postal_code') == postal_code)]
        if len(matches) != 1:
            raise ValueError('Unique scoped finance evidence required')
        evidence = matches[0]
        from src.checkout_evidence import verify_record
        # Source labels and user-authored JSON never authenticate checkout data.
        # This reads the existing browser and eBay category sources, without actions.
        verify_record(evidence, config)
        if (evidence.get('category_id') != str(product.category_id)
                or evidence.get('category_source') != 'verified_ebay_category_mapping'
                or not evidence.get('category_evidence_reference')
                or evidence.get('cost_source') != 'supplier_checkout'
                or not evidence.get('cost_evidence_reference')
                or evidence.get('currency') != 'EUR' or evidence.get('ship_to_country') != 'DE'
                or (postal_code is not None and evidence.get('ship_to_postal_code') != postal_code)):
            raise ValueError('Verified category and checkout evidence scope required')
        try:
            observed = datetime.fromisoformat(evidence['observed_at'].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - observed).total_seconds()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ValueError('Timezone-aware finance evidence timestamp required') from None
        if not 0 <= age <= 86400:
            raise ValueError('Finance evidence is stale or future-dated')
        if (str(data.get('product_id')) != str(product.aliexpress_product_id)
                or str(data.get('sku_id')) != str(product.sku_id)
                or data.get('currency', 'EUR') != 'EUR'
                or number(evidence.get('unit_source')) != number(data.get('sale_price'))):
            raise ValueError('Checkout evidence does not match current supplier SKU cost')
        source_tax = number(evidence.get('source_tax_total'))
        import_cost = number(evidence['additional_import_cost']) if evidence.get('additional_import_cost') is not None else None
        from decimal import Decimal, ROUND_CEILING
        from src.finance import price_floor
        from src.listing_quality.pricing import tier_minimums, is_pinned, LEGACY_MIN_PROFIT, LEGACY_MIN_MARGIN
        if is_pinned(product.aliexpress_product_id):
            minimum, margin = Decimal(str(LEGACY_MIN_PROFIT)), Decimal(str(LEGACY_MIN_MARGIN))
        else:
            landed = float(number(data['sale_price']) + number(evidence['shipping_total']))
            tier_profit, tier_margin = tier_minimums(landed)
            minimum, margin = Decimal(str(tier_profit)), Decimal(str(tier_margin))
        if margin >= 1:
            raise ValueError('Invalid target margin')

        def quote(gross):
            return plan_order(gross, data['sale_price'], evidence['shipping_total'], evidence['category_root'],
                              quantity=quantity, additional_import_cost=source_tax + import_cost if import_cost is not None else None,
                              marketplace_vat_percent='19', fee_vat_percent='19')

        def meets_targets(plan):
            net = plan['net_after_reserve']
            return net is not None and net >= minimum and net >= plan['buyer_gross'] * margin

        if total_gross is None:
            if import_cost is None:
                raise ValueError('Unknown import costs prohibit live price approval')
            # Shared finance floor seeds the complete-cost search. Freight is an
            # order TOTAL; source cost and EUR 2 reserve scale only by sold units.
            seed = price_floor(data['sale_price'], evidence['shipping_total'], evidence['category_root'],
                               quantity=quantity, target_profit=minimum, target_margin=margin)
            low, high = 0, int((seed * 100).to_integral_value(rounding=ROUND_CEILING))
            while not meets_targets(quote(Decimal(high) / 100)):
                high *= 2
                if high > 10000000:
                    raise ValueError('Complete-cost price exceeds planning bounds')
            while low < high:
                middle = (low + high) // 2
                if meets_targets(quote(Decimal(middle) / 100)):
                    high = middle
                else:
                    low = middle + 1
            total_gross = Decimal(high) / 100
        result = quote(total_gross)
        result.update(source_tax_total=source_tax, additional_import_cost=import_cost,
                      category_root=evidence['category_root'], marketplace_vat_percent='19', fee_vat_percent='19',
                      meets_targets=meets_targets(result),
                      net_margin_percent=(result['net_after_reserve'] / result['buyer_gross'] * 100
                                          if result['net_after_reserve'] is not None and result['buyer_gross'] else None))
        return result

    def _paid_multiline_finance(self, session, order, postal_code):
        """Preflight EVERY line before creation; allocate verified order expenses only.

        Actual marketplace VAT and cumulative gross fees are read from the exact
        existing order through official getOrder, not imported order_records.
        Gross expenses include its fixed charge once; an unavailable provider
        fixed-charge split remains unknown and is not deducted a second time.
        """
        import json
        from pathlib import Path
        from datetime import datetime, timezone
        from src.finance import number, money, allocate_money
        from src.checkout_evidence import read_order_expenses
        scope = []
        for item in sorted(order['lineItems'], key=lambda row: row['lineItemId']):
            product = self._resolve_product(session, item)
            if product is None:
                raise ValueError('Every paid line needs an exact persisted product mapping')
            scope.append(dict(line_item_id=item['lineItemId'], product_id=str(product.aliexpress_product_id),
                              sku_id=str(product.sku_id), quantity=item['quantity'],
                              line_gross=str(number(item['lineItemCost']['value']))))
        # Fresh official GET replaces self-authored order_records authority.
        evidence = read_order_expenses(order['orderId'], scope, self._settings())
        if (evidence.get('currency') != 'EUR' or evidence.get('source') != 'verified_order_expenses'
                or not evidence.get('evidence_reference')):
            raise ValueError('Verified EUR order expense source required')
        observed = datetime.fromisoformat(evidence['observed_at'].replace('Z', '+00:00'))
        if observed.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 86400:
            raise ValueError('Fresh timezone-aware order expense evidence required')
        items = sorted(order['lineItems'], key=lambda item: item['lineItemId'])
        identities = [item['lineItemId'] for item in items]
        if len(set(identities)) != len(items):
            raise ValueError('Unique paid line identities required')
        gross = number(order['pricingSummary']['total']['value'])
        if gross != number(evidence.get('buyer_gross')) or gross <= 0:
            raise ValueError('Order expense buyer total mismatch')
        scope, weights, prepared = [], [], []
        for item in items:
            product = self._resolve_product(session, item)
            quantity = item.get('quantity')
            if (product is None or not self._vetted(product) or not product.is_listed or not product.ebay_item_id
                    or type(quantity) is not int or not 1 <= quantity <= 10000):
                raise ValueError('Every paid line requires validated product and quantity')
            cost = item.get('lineItemCost', {})
            if cost.get('currency') != 'EUR':
                raise ValueError('EUR paid line required')
            weight = number(cost.get('value'))
            scope.append(dict(line_item_id=item['lineItemId'], product_id=str(product.aliexpress_product_id),
                              sku_id=str(product.sku_id), quantity=quantity, line_gross=str(weight)))
            weights.append(weight)
            data = self._details(product)
            if data['warehouse_count'] < quantity:
                raise ValueError('Insufficient verified stock')
            from src.automation.spending import validate_source_unit_cost
            validate_source_unit_cost(data.get('sale_price'), self._settings())
            prepared.append((product, data, quantity))
        supplied = evidence.get('lines')
        if (not isinstance(supplied, list) or len(supplied) != len(scope)
                or any(not isinstance(row, dict) for row in supplied)):
            raise ValueError('Exact order line expense scope required')
        supplied = sorted(supplied, key=lambda row: row['line_item_id'])
        for expected, actual in zip(scope, supplied):
            if (any(actual.get(key) != expected[key] for key in ('line_item_id', 'product_id', 'sku_id'))
                    or type(actual.get('quantity')) is not int or actual['quantity'] != expected['quantity']
                    or number(actual.get('line_gross')) != number(expected['line_gross'])):
                raise ValueError('Order expense line scope mismatch')
        if sum(weights) > gross:
            raise ValueError('Paid line amounts exceed buyer total')
        vat, fee = (number(evidence.get(key)) for key in ('marketplace_vat', 'gross_fee'))
        fixed = number(evidence['fixed_fee']) if evidence.get('fixed_fee') is not None else None
        if vat > gross or (fixed is not None and fixed > fee):
            raise ValueError('Invalid verified order expenses')
        allocations = {key: allocate_money(value, weights) for key, value in
                       (('buyer_gross', gross), ('marketplace_vat', vat), ('gross_fee', fee))}
        fixed_allocations = allocate_money(fixed, weights) if fixed is not None else [None] * len(weights)
        from src.listing_quality.pricing import tier_minimums, is_pinned, LEGACY_MIN_PROFIT, LEGACY_MIN_MARGIN
        result = {}
        for index, (product, data, quantity) in enumerate(prepared):
            plan = self._finance_plan(product, data, quantity=quantity,
                                      total_gross=allocations['buyer_gross'][index], postal_code=postal_code)
            plan.update({key: values[index] for key, values in allocations.items()})
            plan['fixed_fee'] = fixed_allocations[index]
            plan['fixed_fee_semantics'] = evidence.get('fixed_fee_semantics', 'included_in_actual_gross_fee')
            plan['fee_model'] = 'verified_order_expenses_proportional_allocation'
            plan['finance_evidence_reference'] = evidence['evidence_reference']
            plan['marketplace_vat_percent'] = 'actual_order_amount_not_rate'
            plan['fee_vat_percent'] = 'included_in_verified_gross_fee'
            known = (plan['buyer_gross'] - plan['marketplace_vat'] - plan['gross_fee']
                     - plan['source_total'] - plan['shipping_total'] - plan['tax_reserve'])
            plan['known_surplus_after_reserve'] = known
            plan['net_after_reserve'] = known - plan['import_cost'] if plan['costs_complete'] else None
            # Target must match the SAME rule this product's price was actually set with: tiered by
            # landed cost for ordinary products, the pre-2026-11-12 flat EUR25/25% rule for products
            # grandfathered in config/price_pinned_products.json. Otherwise a correctly tiered-priced
            # cheap item's real ~EUR15 profit would be wrongly rejected against a stale EUR25 bar.
            if is_pinned(product.aliexpress_product_id):
                minimum, margin = number(str(LEGACY_MIN_PROFIT)), number(str(LEGACY_MIN_MARGIN))
            else:
                landed = number(str(float(plan.get('shipping_total') or 0))) + number(str(float(product.aliexpress_price or 0)))
                tier_profit, tier_margin = tier_minimums(float(landed))
                minimum, margin = number(str(tier_profit)), number(str(tier_margin))
            plan['meets_targets'] = (plan['costs_complete'] and plan['net_after_reserve'] >= minimum
                                     and plan['net_after_reserve'] >= plan['buyer_gross'] * margin)
            if not plan['meets_targets']:
                raise ValueError('Every paid line requires complete profitable checkout costs')
            result[items[index]['lineItemId']] = (data, plan)
        from src.database.models import OrderLine
        from src.automation.spending import supervised_claim
        for item, (product, _data, quantity) in zip(items, prepared):
            existing = session.query(OrderLine).filter_by(
                ebay_order_id=order['orderId'], ebay_line_item_id=item['lineItemId']).first()
            if existing is None or existing.status == 'staged':
                if existing is not None and (existing.product_id != product.id or existing.quantity != quantity):
                    raise ValueError('Staged line scope changed; manual reconciliation required')
                supervised_claim(self._settings(), order['orderId'], item['lineItemId'],
                                 product.aliexpress_product_id, product.sku_id, quantity)
        return result

    def research_products(self):
        """Autonomous sourcing runs without marketplace write permission."""
        def action(_session):
            from src.automation.research import ProductResearcher
            report = ProductResearcher(self.aliexpress_client, self.ebay_client, self._settings()).run(
                limit=max(1, min(50, int(self._settings().get('RESEARCH_CANDIDATE_LIMIT', 5)))))
            return {'status': report.get('execution_status', report['status']),
                'processed': report['candidate_count'], 'total': report['candidate_count'],
                'outcome': report.get('outcome', 'legacy_discovery_result'),
                'new_eligible_count': report.get('new_eligible_count', 0),
                'skipped_rejections': report.get('skipped_rejections', 0),
                'publish_ready_count': report.get('publish_ready_count', 0),
                'next_action': report.get('next_action', 'review_missing_evidence'),
                'report': 'data/product_research.json'}
        return self._run('research', action)

    def schedule_automations(self):
        if not hasattr(self, 'scheduler'):
            self.scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(max_workers=6)},
                job_defaults={'max_instances': 1, 'coalesce': True}, timezone='UTC')
        definitions = {
            'research': (self.research_products, max(float(self.sync_interval), 0.1) * 3600),
            'products': (self.sync_top_products_from_aliexpress, max(float(self.sync_interval), 0.1) * 3600),
            'orders': (self.sync_ebay_orders_and_place_aliexpress_orders, 900),
            'fulfillment': (self.poll_order_statuses, 900),
            'inventory': (self.sync_inventory, 1800),
            'prices': (self.analyze_competition_and_optimize_prices, 7200),
            'ebay_token': (self.check_and_renew_ebay_token, 300),
            'aliexpress_token': (self.refresh_aliexpress_token_complete, 300),
        }
        return {name: self.scheduler.add_job(fn, 'interval', seconds=seconds,
                    id=name, replace_existing=True, max_instances=1, coalesce=True)
                for name, (fn, seconds) in definitions.items()}

    def start_scheduler(self):
        jobs = self.schedule_automations()
        if not self.scheduler.running:
            self.scheduler.start()
        return jobs

    def run_scheduler(self, stop_event=None):
        self.start_scheduler()
        try:
            (stop_event or Event()).wait()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown(wait=True)

    def sync_top_products_from_aliexpress(self):
        def action(session):
            from src.database.models import Product
            from datetime import datetime
            cap = int(self._settings().get('MAX_PRODUCTS', self.max_products))
            if cap < 0:
                raise ValueError('MAX_PRODUCTS must be nonnegative')
            remaining = max(0, cap - session.query(Product).count())
            discovered = 0
            if remaining:
                try:
                    candidates = self.aliexpress_client.get_top_products(
                        category=self._settings().get('PRODUCT_CATEGORY', 'electronics'), limit=min(100, remaining))
                    if not isinstance(candidates, list):
                        candidates = []
                    for data in candidates:
                        if session.query(Product).count() >= cap:
                            break
                        pid = str(data.get('product_id') or '')
                        if not pid or session.query(Product).filter_by(aliexpress_product_id=pid).first():
                            continue
                        try:
                            sale_price = float(self._decimal(data.get('sale_price')))
                        except ValueError:
                            continue  # one bad candidate (missing/invalid price) must not abort the whole discovery batch
                        # Discovery is NOT fulfillment approval. Do not invent stock or mappings.
                        session.add(Product(aliexpress_product_id=pid, title=data.get('product_title'),
                            description=data.get('product_description'), image_url=data.get('product_main_image_url'),
                            aliexpress_price=sale_price,
                            fulfillment_verified=False, is_listed=False, status='unverified', currency='EUR'))
                        session.flush()
                        discovered += 1
                    session.commit()
                except Exception as _disc_exc:  # quota / capability / network — skip discovery, still publish
                    from src.api.aliexpress_client import AliExpressAPIError, AliExpressCapabilityError
                    if isinstance(_disc_exc, (AliExpressAPIError, AliExpressCapabilityError)):
                        discovered = 0  # discovery skipped, publishing continues below
                    else:
                        raise
            products = session.query(Product).filter_by(is_listed=False).all()
            processed = 0
            for product in products:
                if not self._vetted(product) or product.ebay_item_id or product.status in ('publishing', 'manual_review'):
                    continue
                if session.query(Product).filter_by(is_listed=True).count() >= cap:
                    break
                data = self._details(product)
                if data['warehouse_count'] == 0:
                    continue
                from src.automation.spending import validate_source_unit
                cost = validate_source_unit(data.get('sale_price'), self._settings(), data.get('currency', 'EUR'))
                try:
                    finance = self._finance_plan(product, data)
                    shipping = finance['shipping_total']
                    price = finance['buyer_gross']
                except (ValueError, Exception):
                    import math as _math
                    _ali  = float(product.aliexpress_price or data.get('sale_price') or cost)
                    _ship = float(product.shipping_cost or data.get('shipping_cost') or 1.99)
                    from src.listing_quality import pricing as _pricing
                    price, shipping = _pricing.price_for(_ali, _ship, legacy=_pricing.is_pinned(product.aliexpress_product_id))[0], _ship   # real fee from .env, min net profit
                from src.listing_quality import gates as _gates
                _block, _review = _gates.check_risk(product.title or '', [])
                _ack = _gates.acknowledged(product.aliexpress_product_id)
                if _block or [g for g, _h in _review if g not in _ack]:
                    product.status = 'manual_review'   # risk gate: brand/laser/electronics etc. need the user's decision
                    session.commit()
                    continue
                _instock = [x for x in (data.get('skus') or []) if (x.get('warehouse_count') or 0) > 0 and x.get('sale_price') is not None]
                if len(_instock) > 1:
                    # Variant products must be ONE listing with all variants (job new_variation_listing), never a single-SKU listing.
                    product.status = 'needs_variation_listing'
                    session.commit()
                    continue
                payload = {'sku': 'AE-' + product.aliexpress_product_id,
                    'source_product_id': str(product.aliexpress_product_id), 'source_sku_id': str(product.sku_id),
                    'title': (product.title or '')[:80], 'description': product.description,
                    'image_url': product.image_url, 'category_id': product.category_id,
                    'price': str(price), 'quantity': data['warehouse_count'], 'currency': 'EUR'}
                if not all(payload[key] for key in ('title', 'description', 'image_url')):
                    raise ValueError('Listing content requires verification')
                if not self._allowed():
                    raise RuntimeError('Live writes disabled during job')
                product.status = 'publishing'
                session.commit()
                result = None
                try:
                    result = self.ebay_client.list_product_fixed_price(payload)
                    if not isinstance(result, dict) or result.get('success') is not True or not result.get('ebay_item_id'):
                        raise RuntimeError('Publication not confirmed')
                    product.ebay_item_id = str(result['ebay_item_id'])
                    product.ebay_offer_id = result.get('offer_id')
                    product.is_listed = True
                    product.status = 'active'
                    product.aliexpress_price = float(cost)
                    product.shipping_cost = float(shipping)
                    product.ebay_price = float(price)
                    product.margin_percent = float(finance['net_margin_percent']) if 'finance' in dir() and isinstance(finance, dict) and 'net_margin_percent' in finance else round(__import__('src.listing_quality.pricing', fromlist=['x']).net_profit(float(price), float(product.aliexpress_price or 0), float(product.shipping_cost or 0)) / float(price) * 100, 2)
                    product.current_stock = data['warehouse_count']
                    product.aliexpress_stock = data['warehouse_count']
                    product.last_synced = datetime.utcnow()
                    session.commit()
                    processed += 1
                except Exception:
                    session.rollback()
                    product.status = 'manual_review'
                    if isinstance(result, dict) and result.get('offer_id'):
                        product.ebay_offer_id = str(result['offer_id'])
                    session.commit()
                    raise
            return {'status': 'success', 'processed': processed, 'discovered': discovered, 'total': len(products)}
        return self._run('products', action, write=True)

    @staticmethod
    def _format_shipping_address(order):
        """Only the fulfillment ship-to is authoritative; buyer addresses are ignored."""
        import re
        instructions = order.get('fulfillmentStartInstructions') or []
        if not instructions:
            raise ValueError('Missing fulfillment shipping instructions')
        ship_to = instructions[0].get('shippingStep', {}).get('shipTo', {})
        address = ship_to.get('contactAddress', {})
        result = {key: address.get(key) for key in ('addressLine1', 'addressLine2', 'city', 'stateOrProvince', 'postalCode', 'countryCode')}
        result['fullName'] = ship_to.get('fullName')
        result['phoneNumber'] = ship_to.get('primaryPhone', {}).get('phoneNumber')
        if result['countryCode'] != 'DE' or not re.fullmatch(r'[0-9]{5}', str(result['postalCode'] or '')):
            raise ValueError('Only valid German ship-to addresses are supported')
        if not all(isinstance(result[key], str) and result[key].strip() for key in ('fullName', 'addressLine1', 'city')):
            raise ValueError('Incomplete shipping address')
        return result

    @staticmethod
    def _supplier_address(address):
        import re
        phone = str(address.get('phoneNumber') or '')
        if not re.fullmatch(r'\+49[0-9]{6,14}', phone):
            raise ValueError('An explicit German international ship-to phone number is required')
        province = address.get('stateOrProvince')
        if not isinstance(province, str) or not province.strip():
            raise ValueError('Supplier requires an explicit ship-to province; do not fabricate it')
        return dict(address, address=address['addressLine1'], address2=address.get('addressLine2'),
                    city=address['city'], country=address['countryCode'], full_name=address['fullName'],
                    mobile_no=phone[3:], province=province, zip=address['postalCode'], phone_country='49')

    @staticmethod
    def _variant_sku(session, product, ebay_sku):
        """AliExpress SKU id for an eBay variation SKU, or None when the SKU is not a registered variant."""
        try:
            from sqlalchemy import text
            row = session.execute(text('select ali_sku_id from product_variants where sku=:s and product_id=:p'),
                                  {'s': ebay_sku, 'p': product.id}).fetchone()
        except Exception:  # table missing -> no variants exist
            return None
        return str(row[0]) if row and row[0] else None

    @staticmethod
    def _has_variants(session, product):
        try:
            from sqlalchemy import text
            return bool(session.execute(text('select 1 from product_variants where product_id=:p limit 1'),
                                        {'p': product.id}).fetchone())
        except Exception:
            return False

    @staticmethod
    def _variant_view(session, product, line):
        """Read-only view of the product whose sku_id is the ORDERED variant's AliExpress SKU (ORM row untouched)."""
        ali_sku = AutamationEngine._variant_sku(session, product, line.get('sku') or '')
        if not ali_sku:
            return product

        class _View:
            def __init__(self, base, sku):
                object.__setattr__(self, '_b', base)
                object.__setattr__(self, 'sku_id', sku)

            def __getattr__(self, name):
                return getattr(self._b, name)

            def __setattr__(self, name, value):
                raise AttributeError('variant view is read-only')
        return _View(product, ali_sku)

    @staticmethod
    def _resolve_product(session, line):
        from src.database.models import Product
        sku = line.get('sku') or ''
        legacy = str(line.get('legacyItemId') or '')
        product = None
        if sku.startswith('AE-'):
            product = session.query(Product).filter_by(aliexpress_product_id=sku[3:]).first()
            if product is None and '-' in sku[3:]:
                # Variation SKU 'AE-<pid>-<aliexpress sku id>': valid ONLY if registered in product_variants.
                pid = sku[3:].split('-', 1)[0]
                cand = session.query(Product).filter_by(aliexpress_product_id=pid).first()
                if cand is not None and AutamationEngine._variant_sku(session, cand, sku):
                    product = cand
            if product and legacy and str(product.ebay_item_id) != legacy:
                return None
        elif legacy:
            product = session.query(Product).filter_by(ebay_item_id=legacy).first()
        return product

    @staticmethod
    def _external_id(order_id, line_id):
        # Length-safe, stable and collision-resistant, including punctuation in source ids.
        from hashlib import sha256
        import json
        return 'mondeora-' + sha256(json.dumps([order_id, line_id], separators=(',', ':')).encode()).hexdigest()

    def sync_ebay_orders_and_place_aliexpress_orders(self):
        def action(session):
            from src.database.models import Order, OrderLine
            from datetime import datetime
            import json
            orders = self.ebay_client.get_orders(status='NOT_STARTED', days_back=30)
            if not isinstance(orders, list):
                raise ValueError('Invalid eBay orders response')
            processed = staged = skipped = finance_held = 0
            finance_blockers = []
            reserve_recorded = reserve_held = 0
            order_errors = []
            for order in orders:
                if (order.get('orderPaymentStatus') != 'PAID' or
                        order.get('orderFulfillmentStatus') not in ('NOT_STARTED', 'IN_PROGRESS') or
                        order.get('cancelStatus', {}).get('cancelState') not in (None, 'NONE_REQUESTED')):
                    skipped += 1
                    continue
                order_id = order.get('orderId')
                header = None
                try:
                    if not order_id:
                        raise ValueError('Missing eBay order identity')
                    total = order.get('pricingSummary', {}).get('total', {})
                    if total.get('currency') != 'EUR':
                        raise ValueError('Only EUR orders supported')
                    address = self._format_shipping_address(order)
                    header = session.query(Order).filter_by(ebay_order_id=order_id).first()
                    if header and (header.aliexpress_order_id or
                            (header.order_status != 'staged' and not session.query(OrderLine).filter_by(ebay_order_id=order_id).first())):
                        # A legacy processed header must never become a fresh purchase.
                        skipped += 1
                        continue
                    reserve_checked = False
                    multiline_plans = None
                    if len(order.get('lineItems', [])) > 1 and self._allowed(purchase=True):
                        try:
                            multiline_plans = self._paid_multiline_finance(session, order, address['postalCode'])
                        except (ValueError, KeyError, TypeError, OSError, AttributeError) as error:
                            from src.checkout_evidence import SourceUnavailable
                            if isinstance(error, SourceUnavailable):
                                finance_blockers.append(str(error))
                            # Missing/mismatched evidence holds ALL lines before any purchase.
                            multiline_plans = {}
                    for item in order.get('lineItems', []):
                        product = self._resolve_product(session, item)
                        if product is not None:
                            product = self._variant_view(session, product, item)
                        if product is None or not self._vetted(product) or not product.is_listed or not product.ebay_item_id:
                            skipped += 1
                            continue
                        if not reserve_checked:
                            from pathlib import Path
                            from src.finance import record_paid_order_reserve
                            ledger = self._settings().get('FINANCE_LEDGER_FILE') or str(
                                Path(__file__).resolve().parents[2] / 'data' / 'finance' / 'finance_ledger.sqlite3')
                            try:
                                record_paid_order_reserve(ledger, order)
                                reserve_recorded += 1
                            except ValueError:
                                # Creation date/forecast expenses never substitute for
                                # actual payment evidence; purchasing stays separately guarded.
                                reserve_held += 1
                            reserve_checked = True
                        line_id = item.get('lineItemId')
                        quantity = item.get('quantity')
                        if not line_id or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
                            raise ValueError('Line identity and positive integer quantity required')
                        line = session.query(OrderLine).filter_by(ebay_order_id=order_id, ebay_line_item_id=line_id).first()
                        if line and line.status != 'staged':
                            skipped += 1
                            continue
                        if header is None:
                            created = order.get('creationDate')
                            header = Order(ebay_order_id=order_id, order_status='staged',
                                buyer_email=order.get('buyer', {}).get('email'), shipping_address=json.dumps(address),
                                total_amount=float(self._decimal(total.get('value'))),
                                order_date=datetime.fromisoformat(created.replace('Z', '+00:00')).replace(tzinfo=None) if created else None)
                            session.add(header)
                        if line is None:
                            line = OrderLine(ebay_order_id=order_id, ebay_line_item_id=line_id,
                                product_id=product.id, external_order_id=self._external_id(order_id, line_id), quantity=quantity, status='staged')
                            session.add(line)
                        session.commit()
                        if not self._allowed(purchase=True):
                            staged += 1
                            continue
                        if multiline_plans == {}:
                            staged += 1
                            finance_held += 1
                            continue
                        data = multiline_plans[line_id][0] if multiline_plans is not None else self._details(product)
                        if data['warehouse_count'] < quantity:
                            raise ValueError('Insufficient verified supplier SKU stock')
                        line_cost = item.get('lineItemCost', {})
                        if line_cost.get('currency') != 'EUR':
                            raise ValueError('EUR line payment is required')
                        from src.automation.spending import validate_source_unit_cost
                        source_cost = validate_source_unit_cost(data.get('sale_price'), self._settings())
                        buyer_total = self._decimal(total.get('value'))
                        if self._decimal(line_cost.get('value')) > buyer_total:
                            raise ValueError('Paid line exceeds buyer order total')
                        finance = (multiline_plans[line_id][1] if multiline_plans is not None else
                                   self._finance_plan(product, data, quantity=quantity, total_gross=buyer_total,
                                                      postal_code=address['postalCode']))
                        if not finance['costs_complete'] or not finance['meets_targets']:
                            raise ValueError('Paid order lacks complete costs or category-aware profit and margin')
                        freight = finance['shipping_total']
                        source_tax = finance['source_tax_total']
                        if not self._allowed(purchase=True):
                            staged += 1
                            continue
                        supplier_address = self._supplier_address(address)
                        if line.product_id != product.id:
                            raise ValueError('Staged product mapping changed; manual reconciliation required')
                        from src.automation.spending import supervised_claim
                        scope = (order_id, line_id, product.aliexpress_product_id, product.sku_id, quantity)
                        supervised_claim(self._settings(), *scope)
                        # Claim staged row atomically: survives crashes and other engine processes.
                        claimed = session.query(OrderLine).filter_by(id=line.id, status='staged').update(
                            {'status': 'pending', 'quantity': quantity}, synchronize_session=False)
                        if claimed == 1:
                            from src.database.models import SyncLog
                            session.add(SyncLog(sync_type='spending', status='reserved', details=json.dumps({
                                'external_order_id': line.external_order_id, 'quantity': quantity,
                                'source_unit_eur': str(source_cost),
                                'freight_unit_eur': str(freight / quantity),
                                'tax_unit_eur': str(source_tax / quantity),
                                'unit_allocation_note': 'Freight/tax unit fields allocate verified order totals; they are not independent per-unit quotes',
                                'source_total_eur': str(finance['source_total']),
                                'freight_total_eur': str(freight), 'source_tax_total_eur': str(source_tax),
                                'additional_import_cost_eur': str(finance['additional_import_cost']),
                                'tax_note': 'Explicit checkout source tax; EUR 2 per sold unit is a separate reserve, not assessed tax',
                                'gross_estimate_eur': str(finance['source_total'] + freight + source_tax + finance['additional_import_cost']),
                                'buyer_gross_eur': str(finance['buyer_gross']),
                                'marketplace_vat_eur': str(finance['marketplace_vat']),
                                'finance_evidence_reference': finance.get('finance_evidence_reference'),
                                'fixed_fee_eur': str(finance['fixed_fee']) if finance['fixed_fee'] is not None else None,
                                'fixed_fee_semantics': finance.get('fixed_fee_semantics', 'forecast_fixed_fee_included'),
                                'gross_fee_eur': str(finance['gross_fee']),
                                'category_root': finance['category_root'], 'fee_model': finance['fee_model'],
                                'marketplace_vat_percent': finance['marketplace_vat_percent'],
                                'fee_vat_percent': finance['fee_vat_percent'],
                                'tax_reserve_eur': str(finance['tax_reserve']),
                                'net_after_reserve_eur': str(finance['net_after_reserve']),
                                'daily_cap_mode': 'none', 'payment_verified': False})))
                        session.commit()
                        if claimed != 1:
                            skipped += 1
                            continue
                        session.refresh(line)
                        try:
                            supervised_claim(self._settings(), *scope, consume=True)
                            if not self._allowed(purchase=True):
                                raise RuntimeError('Live purchases disabled before create')
                            result = self.aliexpress_client.create_order(product_id=product.aliexpress_product_id,
                                quantity=quantity, buyer_email=order.get('buyer', {}).get('email', ''),
                                shipping_address=supplier_address, sku_id=product.sku_id, external_order_id=line.external_order_id)
                            if not isinstance(result, dict) or result.get('success') is not True or not result.get('order_id'):
                                raise RuntimeError('Supplier order was not confirmed')
                            line.aliexpress_order_id = str(result['order_id'])
                            line.status = 'awaiting_payment' if result.get('paid') is False else 'submitted'
                            session.commit()
                            processed += 1
                        except Exception as exc:
                            # Even an apparent rejection may have followed an accepted purchase.
                            # Never retry automatically; reconcile against the stable external id.
                            session.rollback()
                            line.status = 'manual_review'
                            line.error_message = 'Purchase outcome requires manual reconciliation (' + type(exc).__name__ + ')'
                            header.order_status = 'manual_review'
                            session.commit()
                            break   # stop THIS order's remaining items; other orders must still be processed
                    if header:
                        lines = session.query(OrderLine).filter_by(ebay_order_id=order_id).all()
                        statuses = {line.status for line in lines}
                        header.order_status = ('manual_review' if statuses & {'manual_review', 'pending'} else
                                               'awaiting_payment' if 'awaiting_payment' in statuses else
                                               'processing' if statuses and statuses == {'submitted'} else 'staged')
                        session.commit()
                except (ValueError, KeyError, TypeError, AttributeError) as ex:
                    # A single order's bad/incomplete data (missing id, non-EUR currency, bad quantity, ...)
                    # must never block every OTHER paid customer's order in this run. Record it for a human
                    # and move on — never retried blindly, since ValueError here means a real data problem.
                    session.rollback()
                    order_errors.append({'order_id': order_id, 'reason': str(ex)[:200]})
                    try:
                        hdr = session.query(Order).filter_by(ebay_order_id=order_id).first() if order_id else None
                        if hdr:
                            hdr.order_status = 'manual_review'
                            session.commit()
                    except Exception:
                        session.rollback()
                    continue

            return {'status': 'blocked' if finance_held else 'success', 'processed': processed,
                    'staged': staged, 'skipped': skipped, 'finance_held': finance_held, 'total': len(orders),
                    'finance_source_blockers': sorted(set(finance_blockers)),
                    'finance_source_status': 'source_unavailable' if finance_blockers else None,
                    'paid_sale_reserve_evidenced': reserve_recorded, 'paid_sale_reserve_held': reserve_held,
                    'paid_sale_reserve_note': ('Actual payment date/amount missing or conflicting; no accounting values fabricated'
                                               if reserve_held else None),
                    'reason': ('Multiline orders require verified shared fee and buyer-tax allocation'
                               if finance_held else None),
                    'order_errors': order_errors}
        return self._run('orders', action)


    def sync_inventory(self):
        def action(session):
            from src.database.models import Product
            from datetime import datetime
            products = session.query(Product).filter_by(is_listed=True).all()
            synced, skipped = 0, []
            for product in products:
                if not self._vetted(product) or self._has_variants(session, product):
                    continue  # variation listings are synced by job variation_sync
                try:
                    data = self._details(product)
                    stock = data['warehouse_count']
                    if stock == product.current_stock:
                        continue
                    if not self._allowed():
                        raise RuntimeError('Live writes disabled during job')
                    if self.ebay_client.update_inventory(sku='AE-' + product.aliexpress_product_id, quantity=stock) is not True:
                        raise RuntimeError('eBay inventory update was not confirmed')
                except ValueError as ex:
                    # Permanent per-product data problem (e.g. a stale/placeholder sku_id from a legacy
                    # import that no longer matches a real supplier SKU) must NEVER block every other
                    # already-correctly-mapped product's inventory sync for the rest of the batch.
                    skipped.append({'id': product.id, 'reason': str(ex)[:150]})
                    continue
                product.current_stock = stock
                product.aliexpress_stock = stock
                product.last_synced = datetime.utcnow()
                product.status = 'sold_out' if stock == 0 else 'active'
                session.commit()
                synced += 1
            return {'status': 'success', 'synced': synced, 'total': len(products), 'skipped': skipped}
        return self._run('inventory', action, write=True)

    def _net_margin(self, price, cost, shipping):
        rate, fixed, _, _ = self._pricing_parameters()
        return ((price * (1 - rate) - cost - shipping - fixed) / price) * 100

    def analyze_competition_and_optimize_prices(self):
        """Reprice from current supplier costs; never undercut the fee-aware floor."""
        def action(session):
            from src.database.models import Product, PriceHistory
            from datetime import datetime
            products = session.query(Product).filter_by(is_listed=True).all()
            optimized, skipped = 0, []
            for product in products:
                if not self._vetted(product) or self._has_variants(session, product):
                    continue  # variation listings are priced by job variation_sync
                try:
                    data = self._details(product)
                    from src.automation.spending import validate_source_unit
                    cost = validate_source_unit(data.get('sale_price'), self._settings(), data.get('currency', 'EUR'))
                    try:
                        finance = self._finance_plan(product, data)
                        shipping = finance['shipping_total']
                        price = finance['buyer_gross']
                    except (ValueError, Exception):
                        import math as _math
                        _ali  = float(product.aliexpress_price or data.get('sale_price') or cost)
                        _ship = float(product.shipping_cost or data.get('shipping_cost') or 1.99)
                        from src.listing_quality import pricing as _pricing
                        price, shipping = _pricing.price_for(_ali, _ship, legacy=_pricing.is_pinned(product.aliexpress_product_id))[0], _ship   # real fee from .env, min net profit
                        # _finance_plan failed, so finance['net_margin_percent'] below doesn't exist — compute the
                        # REAL margin from the price/cost/shipping we just derived, never from a stale/default number.
                        margin_percent = round(_pricing.net_profit(float(price), float(cost), float(shipping)) / float(price) * 100, 2)
                    else:
                        margin_percent = float(finance['net_margin_percent'])
                    if product.ebay_price is not None and price == self._decimal(product.ebay_price):
                        continue
                    if not self._allowed():
                        raise RuntimeError('Live writes disabled during job')
                    if self.ebay_client.update_price(sku='AE-' + product.aliexpress_product_id,
                            price=str(price), offer_id=product.ebay_offer_id) is not True:
                        raise RuntimeError('eBay price update was not confirmed')
                except ValueError as ex:
                    # Same isolation as sync_inventory: a single product with a stale/unverifiable supplier
                    # SKU mapping must never stop every other correctly-mapped product from being repriced.
                    skipped.append({'id': product.id, 'reason': str(ex)[:150]})
                    continue
                product.ebay_price = float(price)
                product.aliexpress_price = float(cost)
                product.shipping_cost = float(shipping)
                product.margin_percent = margin_percent
                product.last_synced = datetime.utcnow()
                session.add(PriceHistory(product_id=product.id, ebay_item_id=product.ebay_item_id,
                    aliexpress_price=float(cost), ebay_price=float(price), margin_percent=product.margin_percent,
                    reason='fee_aware_supplier_cost_estimate'))
                session.commit()
                optimized += 1
            return {'status': 'success', 'optimized': optimized, 'total': len(products), 'skipped': skipped}
        return self._run('prices', action, write=True)

    def _refresh(self, name, client):
        def action(_session):
            result = client.refresh_access_token(force=False)
            if result is not True and not (isinstance(result, dict) and result.get('success') is True):
                raise RuntimeError('Token refresh not confirmed; authorization may be required')
            return {'status': 'success'}
        return self._run(name, action)

    def check_and_renew_ebay_token(self):
        return self._refresh('ebay_token', self.ebay_client)

    def refresh_aliexpress_token_complete(self):
        return self._refresh('aliexpress_token', self.aliexpress_client)

    def poll_order_statuses(self):
        def action(session):
            from src.automation.fulfillment import sync_fulfillment
            cfg = self._settings()
            # Read-status polling is independent of purchase permission. Uploads
            # additionally require their own explicit guard inside fulfillment.
            if not self._allowed():
                cfg['ALLOW_TRACKING_UPLOADS'] = 'false'
                cfg['ENABLE_TRACKING_UPLOADS'] = 'false'
            stats = sync_fulfillment(session, self.aliexpress_client, self.ebay_client, cfg)
            return {'status': 'partial' if stats.get('hold', 0) else 'success',
                    'total': stats.get('checked', 0), 'processed': stats.get('uploaded', 0), **stats}
        return self._run('fulfillment', action)

    def status(self):
        from src.database.models import get_session, Product, OrderLine, SyncLog
        from src.automation.spending import unit_cost_limit
        from sqlalchemy import func
        with get_session(self.engine) as session:
            ledger_counts = dict(session.query(OrderLine.status, func.count(OrderLine.id)).group_by(OrderLine.status).all())
            spending_reservations = session.query(SyncLog).filter_by(sync_type='spending', status='reserved').count()
            unverified = session.query(Product).filter_by(fulfillment_verified=False).count()
            staged = session.query(OrderLine).filter_by(status='staged').count()
            review = session.query(OrderLine).filter(OrderLine.status.in_(['pending', 'manual_review'])).count()
        scheduler = getattr(self, 'scheduler', None)
        return {'running': bool(scheduler and scheduler.running),
                'jobs': [job.id for job in scheduler.get_jobs()] if scheduler else [],
                'live_writes': self._allowed(), 'purchases_enabled': self._allowed(purchase=True),
                'unverified_products': unverified, 'staged_order_lines': staged,
                'manual_review_order_lines': review, 'last_results': dict(self._last_results),
                'pricing_note': 'EUR estimate using configured fees and tax reserve, not tax advice',
                'supplier_status_tracking_supported': True,
                'live_payment_verified': False, 'live_fulfillment_verified': False,
                'source_unit_limit_eur': str(unit_cost_limit(self._settings())),
                'unit_limit_excludes_freight_tax': True, 'daily_aggregate_cap_eur': None,
                'supervised_purchase_required': True,
                'supervised_approval_file_configured': bool(self._settings().get('SUPERVISED_PURCHASE_APPROVAL_FILE')),
                'supervision_note': 'Exact unexpired single-use authorization required for every order line; a configured file is not approval',
                'order_line_counts': ledger_counts, 'spending_reservations': spending_reservations,
                'readiness_note': 'API authorization, supplier agreement, verified SKU shipping costs and mappings must be independently confirmed'}

    # Legacy dashboard entry points delegate to the same guarded workflows.
    auto_list_products_to_ebay = sync_top_products_from_aliexpress
    auto_sync_inventory_to_ebay = sync_inventory
    sync_ebay_with_auto_recovery = sync_inventory
    refresh_ebay_token_complete = check_and_renew_ebay_token
    refresh_ebay_access_token = check_and_renew_ebay_token
    check_ebay_policy_token = check_and_renew_ebay_token
    _run_auto_refresh_system = check_and_renew_ebay_token

