"""Autonomous, read-only product research. No guessed costs or seller approvals."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
import statistics
from src.runtime import PROJECT_ROOT, read_config


def semantic_relevance(title, query):
    """Require every query concept, including the domain, in EN/DE wording."""
    groups = (
        ('garden', 'garten'), ('tool', 'werkzeug', 'geräte', 'geraete'),
        ('desk', 'desktop', 'schreibtisch'),
        ('bamboo', 'bambus'), ('wood', 'holz'), ('monitor', 'bildschirm'),
        ('stand', 'ständer', 'staender', 'erhöh', 'erhoeh', 'riser'),
        ('drawer', 'schublad'), ('shelf', 'shelves', 'regal', 'ablage'),
        ('plant', 'pflanz', 'blumen'), ('trellis', 'rankgitter', 'rankhilfe'),
        ('remote', 'fernbedien'), ('control', 'fernbedien'),
        ('broom', 'besen'), ('mop', 'mopp'), ('holder', 'halter'),
        ('storage', 'aufbewahr'),
        ('metal', 'metall', 'iron', 'eisen'), ('wall', 'wand'),
        ('folding', 'foldable', 'klapp'), ('table', 'tisch'),
        ('document', 'dokument', 'file', 'akten', 'papier', 'brief'),
        ('organizer', 'organiser', 'organisator', 'aufbewahr', 'halter', 'regal'),
    )
    text, query = str(title or '').casefold(), str(query or '').casefold()
    # German compounds carry multiple requirements, not just their first noun.
    for compound, expanded in (
        ('monitorständer', 'monitor stand'), ('monitorstaender', 'monitor stand'),
        ('bildschirmständer', 'monitor stand'), ('monitorerhöhung', 'monitor stand'),
        ('pflanzenständer', 'plant stand'), ('blumenständer', 'plant stand'),
        ('schreibtischregal', 'desk shelf'), ('besenhalter', 'broom holder'),
    ):
        query = query.replace(compound, expanded)
    words = [word for word in re.findall(r'\w+', query) if word not in {'with', 'mit', 'and', 'und', 'für', 'for'}]
    requirements = []
    for word in words:
        group = next((g for g in groups if any(term in word for term in g)), None)
        requirements.append(group or (word,))
    return bool(requirements) and all(any(term in text for term in group) for group in requirements)


def product_kind_query(title):
    """One bounded related-product query; preserve differentiating concepts."""
    text = str(title or '').casefold()
    if any(t in text for t in ('wall', 'wand')) and any(t in text for t in ('fold', 'klapp')) and any(t in text for t in ('table', 'tisch')):
        return 'Wand Klapptisch'
    if any(t in text for t in ('document', 'file organizer', 'file organiser', 'akten', 'dokument', 'papierablage', 'briefablage')):
        return 'Dokumenten Organizer'
    if any(t in text for t in ('monitor', 'bildschirm')) and any(t in text for t in ('stand', 'ständ', 'staend', 'riser', 'erhöh', 'erhoeh', 'regal')):
        query = 'Monitorständer'
        if any(t in text for t in ('bamboo', 'bambus')):
            query += ' Bambus'
        if any(t in text for t in ('drawer', 'schublad')):
            query += ' Schublade'
        return query
    if any(t in text for t in ('drawer', 'schublad')) and any(t in text for t in ('storage', 'aufbewahr', 'organizer', 'schrank')):
        return 'Schubladen Organizer Holz' if any(t in text for t in ('wood', 'holz')) else 'Schubladen Organizer'
    if any(t in text for t in ('trellis', 'rankgitter', 'rankhilfe')):
        return 'Pflanzen Rankgitter'
    if any(t in text for t in ('plant stand', 'pflanzenständ', 'pflanzenstaend', 'blumenständ', 'blumenstaend')):
        return 'Pflanzenständer Metall' if any(t in text for t in ('metal', 'iron', 'eisen')) else 'Pflanzenständer'
    if any(t in text for t in ('desk shelf', 'desk riser', 'schreibtischregal', 'schreibtischerhöh')):
        return 'Schreibtisch Regal'
    if any(t in text for t in ('fernbedien', 'remote control')):
        return 'Fernbedienung Organizer'
    if any(t in text for t in ('besenhalter', 'mopp', 'broom holder', 'mop holder')):
        return 'Besenhalter'
    return str(title or '')


class ProductResearcher:
    def __init__(self, supplier, ebay=None, config=None, output_path=None):
        self.supplier, self.ebay = supplier, ebay
        self.config = read_config() if config is None else dict(config)
        self.output_path = Path(output_path or PROJECT_ROOT / 'data/product_research.json')

    @staticmethod
    def risk_flags(title):
        groups = {
            'regulated_or_safety_sensitive': ['baby', 'infant', 'toy', 'medical', 'medicine', 'cosmetic', 'supplement', 'lithium', 'battery', 'charger', 'helmet', 'pesticide', 'food', 'bebek', 'oyuncak'],
            'brand_or_ip_review': ['replica', 'compatible with', 'apple', 'ipad', 'iphone', 'xiaomi', 'samsung', 'disney', 'nike', 'lego'],
        }
        text = str(title or '').lower()
        return [group for group, terms in groups.items() if any(re.search(r'\b' + re.escape(term) + r'\b', text) for term in terms)]

    @staticmethod
    def number(value, positive=False):
        try:
            n = Decimal(str(value))
            return n if n.is_finite() and (n > 0 if positive else n >= 0) else None
        except InvalidOperation:
            return None

    def _market(self, keyword):
        if self.ebay is None:
            return {'status': 'unavailable', 'error': 'No marketplace client'}
        try:
            effective_query = keyword
            def relevant(row, query):
                text = str(row.get('title') or '')
                # Accessories and replacement parts are not whole-product asks.
                excluded = r'\b(?:ersatzteil\w*|scharnier\w*|spare\s+parts?|replacement\s+parts?|hinges?|abdeckung\w*)\b'
                return semantic_relevance(text, query) and not re.search(excluded, text, re.I)
            attempts = []
            payload = {}
            for query in dict.fromkeys((keyword, product_kind_query(keyword))):
                effective_query = query
                payload = self.ebay._request('GET', '/buy/browse/v1/item_summary/search', params={'q': query, 'limit': 10})
                rows = payload.get('itemSummaries', [])[:10]
                matched = sum(bool(relevant(row, query)) for row in rows)
                attempts.append({'query': query, 'returned_count': len(rows), 'concept_match_count': matched})
                if matched:
                    break
            prices, samples = [], []
            for row in payload.get('itemSummaries', [])[:10]:
                if not relevant(row, effective_query):
                    continue
                price = row.get('price', {})
                value = self.number(price.get('value'), positive=True)
                if price.get('currency') == 'EUR' and value is not None:
                    prices.append(value)
                    samples.append({'item_id': row.get('itemId'), 'title': row.get('title'),
                                    'asking_price_eur': str(value)})
            return {'status': 'ok', 'query': keyword, 'effective_query': effective_query, 'observed_at': datetime.now(timezone.utc).isoformat(),
                'source': 'eBay Browse item_summary/search EBAY_DE',
                'sample_count': len(prices), 'samples': samples, 'query_attempts': attempts,
                'demand': {'status': 'unknown', 'platform': 'eBay DE', 'observation_window': None,
                           'sold_metric': None, 'reason': 'Browse search supplies active asking prices, not recent sold metrics'},
                'median_asking_price_eur': str(statistics.median(prices)) if prices else None,
                'comparison_level': 'title_concept_match_not_verified_identical_product_or_variant',
                'exact_sku_comparison_verified': False, 'demand_verified': False, 'sold_count': None,
                'evidence_note': 'Current related asking prices only; not sold-price or demand evidence'}
        except Exception as error:
            return {'status': 'unavailable', 'error_type': type(error).__name__}

    def _category(self, title):
        self.category_status = {'status': 'unavailable', 'reason': 'No usable category/aspect response',
                                'observed_at': datetime.now(timezone.utc).isoformat()}
        if self.ebay is None:
            self.category_status['reason'] = 'No marketplace client'
            return None
        try:
            tree = self.ebay._request('GET', '/commerce/taxonomy/v1/get_default_category_tree_id', params={'marketplace_id': 'EBAY_DE'})
            tree_id = str(tree['categoryTreeId'])
            if not tree_id.isdigit():
                return None
            query = product_kind_query(title)
            data = self.ebay._request('GET', '/commerce/taxonomy/v1/category_tree/' + tree_id + '/get_category_suggestions', params={'q': query})
            suggestions = data.get('categorySuggestions', [])
            if not suggestions:
                return None
            category = suggestions[0]['category']
            category_id = str(category['categoryId'])
            if not category_id.isascii() or not category_id.isdigit():
                return None
            ancestors = suggestions[0].get('categoryTreeNodeAncestors', [])
            from src.finance import RULES
            roots = [str(row.get('categoryId')) for row in [category, *ancestors]
                     if str(row.get('categoryId')) in RULES]
            aspects = self.ebay._request('GET', '/commerce/taxonomy/v1/category_tree/' + tree_id + '/get_item_aspects_for_category',
                                        params={'category_id': category_id}).get('aspects')
            valid = isinstance(aspects, list) and all(isinstance(a, dict)
                and isinstance(a.get('localizedAspectName'), str)
                and type(a.get('aspectConstraint', {}).get('aspectRequired')) is bool for a in aspects)
            required = [a['localizedAspectName'] for a in aspects if a['aspectConstraint']['aspectRequired']] if valid else None
            self.category_status = {'status': 'ok' if valid else 'unavailable',
                                    'reason': 'Current taxonomy response' if valid else 'Invalid aspect schema',
                                    'observed_at': datetime.now(timezone.utc).isoformat()}
            return {'category_id': category_id, 'name': category.get('categoryName'),
                'tree_id': tree_id, 'ancestors': [{'category_id': str(a.get('categoryId')), 'name': a.get('categoryName')} for a in ancestors],
                'fee_category_root': roots[0] if roots else None,
                'source': 'eBay Taxonomy GET category suggestions and item aspects EBAY_DE',
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'requirements_fetched': valid, 'required_aspects': required,
                'aspect_constraints': aspects if valid else None,
                'missing_aspects': required, 'listing_aspects_verified': valid and not required,
                'category_fit': 'suggested_not_independently_verified'}
        except Exception as error:
            self.category_status['error_type'] = type(error).__name__
            return None

    def _candidate(self, product, keyword, market=None, *, selected_sku_id=None):
        title = str(product.get('product_title') or '')
        variants = product.get('skus') or [product]
        eligible = []
        for sku in variants:
            if selected_sku_id is not None and str(sku.get('sku_id')) != str(selected_sku_id):
                continue
            stock, cost = self.number(sku.get('warehouse_count')), self.number(sku.get('sale_price'), positive=True)
            if sku.get('sku_id') and sku.get('currency', product.get('currency')) == 'EUR' and cost is not None and stock is not None and stock == stock.to_integral_value() and stock >= 1:
                eligible.append((cost, -stock, str(sku['sku_id']), sku))
        selected = min(eligible, key=lambda v: (v[0], v[1], v[2]))[3] if eligible else {}
        blockers = []
        facts = product.get('provider_facts') or {}
        scoped_facts = (facts.get('source') == 'aliexpress.ds.product.get'
                        and str(facts.get('source_product_id')) == str(product.get('product_id')))
        attrs = facts.get('attributes', {}) if scoped_facts else {}
        attrs = attrs if isinstance(attrs, dict) else {}
        attr_text = ' '.join(str(v) for v in attrs.values() if isinstance(v, str))
        evidence_text = ' '.join((title, str(selected.get('sku_attr') or ''), attr_text))
        relevance = semantic_relevance(evidence_text, keyword)
        # Never use packaging measurements as product facts, or a global median.
        market_title = title
        for terms, suffix in ((('bamboo', 'bambus'), ' Bambus'), (('drawer', 'schublad'), ' Schublade')):
            if any(t in evidence_text.casefold() for t in terms) and not any(t in title.casefold() for t in terms):
                market_title += suffix
        market = self._market(market_title) if title else {'status': 'unavailable'}
        if not relevance:
            blockers.append('search_relevance_unverified')
        risk = self.risk_flags(title)
        if risk:
            blockers.append('risk_policy_excluded')
        if not selected:
            blockers.append('no_valid_in_stock_eur_sku')
        shipping = product.get('shipping_cost')
        quote = None
        if selected and hasattr(self.supplier, 'get_shipping_quote'):
            try:
                quote = self.supplier.get_shipping_quote(str(product['product_id']), str(selected['sku_id']), quantity=1, ship_to_country='DE')
                shipping = quote.get('cost') if isinstance(quote, dict) else None
                if not isinstance(quote, dict) or any(str(quote.get(key)) != str(value) for key, value in {
                        'product_id': product['product_id'], 'sku_id': selected['sku_id'],
                        'quantity': 1, 'ship_to_country': 'DE', 'currency': 'EUR'}.items()):
                    shipping = None
                    blockers.append('freight_scope_mismatch')
            except Exception as error:
                blockers.append('freight_' + type(error).__name__)
        if self.number(shipping) is None:
            blockers.append('freight_unverified')
        if isinstance(quote, dict) and (quote.get('is_estimate') or quote.get('transaction_ready') is not True):
            blockers.append('freight_estimate_only')
        category = self._category(title) if title and not risk else None
        if category is None:
            blockers.append('category_unresolved')
        if not category or not category.get('requirements_fetched') or not category.get('listing_aspects_verified'):
            blockers.append('listing_requirements_unverified')
        # No document/terms verifier exists here; provider booleans and .env
        # declarations are assertions, not scoped external proof.
        blockers.extend(['supplier_product_compliance_unverified', 'supplier_agreement_missing',
                         'category_fit_unverified', 'demand_unverified', 'complete_cost_profit_unverified',
                         'manufacturer_eu_responsible_person_missing', 'image_rights_unverified',
                         'dispatch_origin_unverified', 'seller_commercial_tax_status_unverified',
                         'account_policies_location_unverified'])
        floor = None
        finance = {'status': 'unavailable', 'scenarios': {}, 'market_price_verified': False,
                   'unknown_import_cost_is_zero': False, 'category_root': (category or {}).get('fee_category_root')}
        blockers.append('unknown_import_cost')
        if selected and self.number(shipping) is not None and finance['category_root']:
            try:
                from src.finance import plan_order, price_floor, number
                target_profit = max(Decimal('25'), number(self.config.get('MIN_PROFIT_EUR') or '25'))
                target_margin = max(Decimal('.25'), number(self.config.get('MIN_MARGIN_PERCENT') or '25') / 100)
                finance.update(minimum_profit_eur=str(target_profit), minimum_net_margin=str(target_margin))
                for vat in ('19', '0'):
                    planned_floor = price_floor(selected['sale_price'], shipping, finance['category_root'],
                        target_profit=str(target_profit), target_margin=str(target_margin),
                        marketplace_vat_percent=vat, fee_vat_percent='19')
                    scenario = plan_order(planned_floor, selected['sale_price'], shipping, finance['category_root'],
                                          marketplace_vat_percent=vat, fee_vat_percent='19', additional_import_cost=None)
                    finance['scenarios']['marketplace_vat_' + vat + '_percent'] = dict(
                        json.loads(json.dumps(scenario, default=str)),
                        price_floor_excluding_unknown_import_eur=str(planned_floor),
                        marketplace_vat_percent=vat, fee_vat_percent='19',
                        basis='Assumed VAT scenario, not verified seller treatment or proven achievable market price')
                    if vat == '19':
                        floor = str(planned_floor)
                finance['status'] = 'scenario_only_costs_incomplete'
                asking = self.number(market.get('median_asking_price_eur'), positive=True)
                lowest_floor = min(Decimal(s['price_floor_excluding_unknown_import_eur']) for s in finance['scenarios'].values())
                if asking is not None and asking < lowest_floor:
                    finance['commercial_screen'] = 'do_not_source_at_sampled_asking_prices'
                    blockers.append('sampled_asking_prices_below_all_scenario_floors')
                else:
                    finance['commercial_screen'] = 'hold_pending_verified_demand_and_complete_costs'
            except (ValueError, InvalidOperation, TypeError):
                blockers.append('fee_configuration_missing_or_invalid')
        else:
            blockers.append('fee_category_or_cost_unavailable')
        asking = self.number(market.get('median_asking_price_eur'), positive=True)
        if selected and asking is not None:
            # Necessary condition only: even ZERO freight/fees/tax cannot rescue
            # these sampled asks. Unknown actual costs remain unknown.
            optimistic = asking - Decimal(str(selected['sale_price']))
            finance['optimistic_profit_before_all_other_costs_eur'] = str(optimistic)
            finance['optimistic_screen_basis'] = 'Related median ask minus source only; upper bound, not actual profit or proven selling price'
            target = max(Decimal('25'), self.number(self.config.get('MIN_PROFIT_EUR')) or Decimal('25'))
            if optimistic < target:
                finance['commercial_screen'] = 'do_not_source_at_sampled_asking_prices'
                blockers.append('sampled_asking_prices_fail_even_zero_other_cost_profit_bound')
        if selected and Decimal(str(selected['sale_price'])) > Decimal('40'):
            blockers.append('source_unit_budget_exceeded')
        if market.get('status') != 'ok':
            blockers.append('market_comparison_unavailable')
        from src.product_preparation import factual_german_draft
        draft = factual_german_draft(product, selected)
        blockers = list(dict.fromkeys(blockers))
        supplier_pending = {'supplier_product_compliance_unverified', 'supplier_agreement_missing',
                            'manufacturer_eu_responsible_person_missing', 'image_rights_unverified', 'dispatch_origin_unverified'}
        missing = [{'requirement': b, 'status': 'missing_or_unverified',
                    'owner': 'external_supplier_response_pending' if b in supplier_pending else 'agent',
                    'product_id': str(product.get('product_id') or ''), 'sku_id': selected.get('sku_id'),
                    'verification': 'Requires current scoped provider/document evidence, not a manual true flag'} for b in blockers]
        policy_url = 'https://www.ebay.com/help/selling/posting-items/setting-postage-options/drop-shipping?id=4176'
        tasks = [{'product_id': str(product.get('product_id') or ''), 'sku_id': selected.get('sku_id'),
            'status': 'prepared_not_sent', 'owner': 'agent',
            'store_reference': facts.get('store') if scoped_facts else None,
            'supplier_reported_contact': facts.get('manufacturer') if scoped_facts else None,
            'contact_role_note': 'Provider-reported manufacturer contact and store identity; not a verified legal identity or contacted counterparty',
            'source_url': 'https://www.aliexpress.com/item/' + str(product.get('product_id') or '') + '.html',
            'policy_source': policy_url,
            'policy_rule': 'Wholesale direct fulfillment allowed; listing then purchasing from another retailer/marketplace to ship to the customer is prohibited. DS API access or an ordinary buyer account is not wholesale rights.',
            'request_de': 'Bitte bestätigen Sie für Produkt ' + str(product.get('product_id') or '')
                + ', SKU ' + str(selected.get('sku_id') or '')
                + ': Großhandelsvertrag und Direktversandberechtigung, tatsächliches Versandlager, Lieferzeiten, Retouren-/Erstattungsbedingungen, Bildrechte sowie Hersteller, EU-Verantwortlicher, Sicherheits-/Konformitätsunterlagen und belegte Pflichtmerkmale '
                + ', '.join((category or {}).get('missing_aspects') or []) + '. Keine Bestellung oder Zahlung autorisiert.'}]
        return {'product_id': str(product.get('product_id') or ''), 'title': title,
            'source_url': 'https://www.aliexpress.com/item/' + str(product.get('product_id') or '') + '.html',
            'keyword': keyword, 'search_relevance_verified': relevance,
            'relevance_evidence': {'title': title, 'selected_sku_id': selected.get('sku_id'),
                'selected_sku_attributes': selected.get('sku_attr'),
                'provider_attribute_source': facts.get('source') if scoped_facts else None,
                'provider_attributes': attrs, 'query': keyword,
                'evidence_level': 'provider_claim_concept_match_not_independent_product_verification'},
            'sku_id': selected.get('sku_id'), 'sku_attr': selected.get('sku_attr'),
            'source_cost_eur': selected.get('sale_price'), 'real_sku_stock': selected.get('warehouse_count'),
            'variant_selection_rule': 'Known EUR price and real positive stock; lowest price, then highest stock',
            'shipping_quote': quote, 'shipping_cost_eur': shipping,
            'price_floor_eur': floor, 'finance': finance, 'category_suggestion': category, 'market': market,
            'category_status': dict(getattr(self, 'category_status', {'status': 'not_requested'})),
            'risk_flags': risk, 'blockers': blockers, 'missing_evidence': missing,
            'listing_draft': draft, 'supplier_tasks': tasks,
            'draft_ready': draft is not None,
            'preparation_state': 'needs_source_data' if draft is None else ('publish_ready' if not blockers else 'draft_ready'),
            'ready_to_publish': draft is not None and not blockers}

    def run_actionable(self, limit=12, niches=None):
        """Finite discovery with per-query/niche allocation BEFORE dedup/detail reads.

        Search prices rank proposals only. Current SKU, freight, market and facts
        are reread; supplier aggregate orders remain separate from eBay demand.
        """
        from src.runtime import enable_read_only
        from src.sourcing_completion import ReadCounter, select_sku
        from src.product_preparation import collect_provider_facts
        enable_read_only()
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError('Actionable candidate cap must be 1..12')
        niches = niches or {
            'office': (('monitor stand', '200001108', 'monitor stand'),
                       ('document organizer', None, 'document organizer')),
            'home': (('wall folding table', None, 'wall folding table'),
                     ('storage drawer', '200043145', 'storage drawer')),
            'garden': (('metal plant stand', '200287145', 'metal plant stand'),
                       ('plant shelf', '200287145', 'plant shelf')),
        }
        if not isinstance(niches, dict) or not 1 <= len(niches) <= 10 or any(not 1 <= len(q) <= 2 for q in niches.values()):
            raise ValueError('Bounded niche queries required')
        from src.research_rotation import ResearchRotation, PAGE_CAP
        rotation = ResearchRotation(self.output_path, self.config)
        if self.output_path.parent.resolve() == (PROJECT_ROOT / 'data').resolve():
            for name in ('production_sourcing_v2.json', 'product_research.json'):
                rotation.seed_snapshot(PROJECT_ROOT / 'data' / name)
        # Keep the existing six-search maximum, including configured niches.
        niche_items = list(niches.items())
        start = (rotation.cursor // PAGE_CAP) % len(niche_items)
        niche_items = niche_items[start:] + niche_items[:start]
        niche_items = niche_items[:6]
        quota, extra = divmod(limit, len(niche_items))
        page_num = 1 + rotation.cursor % PAGE_CAP
        searches, skipped = 0, set()
        allocations, provenance, chosen, errors, rejected = [], {}, {}, [], []
        with ReadCounter(supplier=self.supplier, marketplace=self.ebay) as reads:
            for index, (niche, queries) in enumerate(niche_items):
                allowance = quota + (index < extra)
                pools, query_reports = [], []
                query_start = (rotation.cursor // PAGE_CAP) % len(queries)
                queries = queries[query_start:] + queries[:query_start]
                # Reserve at least one search for each included niche.
                queries = queries[:max(1, 6 // len(niche_items))]
                for query, category, concept in queries:
                    if searches >= 6:
                        break
                    searches += 1
                    try:
                        page = self.supplier.search_product_page(query, category_id=category, page_num=page_num, page_size=50)
                        rows = page['products'][:50]
                        query_reports.append({'query': query, 'category_id': category, 'concept_query': concept, 'page_num': page_num, 'status': 'ok', 'returned_count': len(rows), 'source_rows': rows})
                        eligible = []
                        for row in rows:
                            pid = str(row.get('itemId') or '')
                            tag = {'niche': niche, 'keyword': query, 'concept_query': concept}
                            if not pid.isascii() or not pid.isdigit():
                                continue
                            if tag not in provenance.setdefault(pid, []):
                                provenance[pid].append(tag)
                            cooldown = rotation.blocked(pid, concept)
                            if cooldown:
                                skipped.add(pid)
                                rejected.append({'product_id': pid, 'niche': niche, 'query': query,
                                    'reason': 'sampled_market_policy_cooldown', 'cooldown_evidence': cooldown})
                                continue
                            title = str(row.get('title') or '')
                            price = self.number(row.get('targetSalePrice'), positive=True)
                            reason = ('query_concepts_not_supported' if not semantic_relevance(title, concept) else
                                      'risk_policy_excluded' if self.risk_flags(title) else
                                      'search_price_not_substantive_or_over_budget' if price is None or not Decimal('8') <= price <= Decimal('40') else None)
                            if concept == 'monitor stand' and any(t in title.casefold() for t in ('vesa', 'tablet', 'armhalter', 'gelenkarm')):
                                reason = 'monitor_arm_not_desktop_riser'
                            if reason:
                                rejected.append({'product_id': pid, 'niche': niche, 'query': query, 'reason': reason})
                            else:
                                eligible.append((-price, pid, row, tag))
                        pools.append(sorted(eligible, key=lambda r: r[:2]))
                    except Exception as error:
                        query_reports.append({'query': query, 'status': 'unavailable', 'error_type': type(error).__name__})
                        errors.append({'stage': 'search', 'query': query, 'error_type': type(error).__name__})
                        pools.append([])
                # Round robin the queries within each reserved niche allocation.
                allocated = []
                while len(allocated) < allowance and any(pools):
                    for pool in pools:
                        if pool and len(allocated) < allowance:
                            row = pool.pop(0)
                            if row[1] not in [r[1] for r in allocated]:
                                allocated.append(row)
                allocations.append({'niche': niche, 'allocation': allowance, 'queries': query_reports,
                                    'allocated_product_ids': [r[1] for r in allocated]})
                for _, pid, row, tag in allocated:
                    chosen.setdefault(pid, (row, tag))
            candidates = []
            for pid, (row, tag) in chosen.items():
                try:
                    product = self.supplier.get_product_details(pid)
                    if str(product.get('product_id')) != pid:
                        raise ValueError('Supplier identity mismatch')
                    if hasattr(self.supplier, '_request'):
                        raw = self.supplier._request('aliexpress.ds.product.get', {'product_id': pid, 'ship_to_country': 'DE', 'target_currency': 'EUR', 'target_language': 'de'})['result']
                        product['provider_facts'] = collect_provider_facts(pid, raw)
                    sku = select_sku(product)
                    item = self._candidate(product, tag['concept_query'], selected_sku_id=(sku or {}).get('sku_id'))
                    item.update(niche=tag['niche'], provenance=provenance[pid], provider_facts=product.get('provider_facts', {}),
                                source_refresh={'status': 'ok', 'source': 'aliexpress.ds.product.get', 'observed_at': datetime.now(timezone.utc).isoformat()})
                    item['supplier_orders'] = {'source': 'aliexpress.ds.text.search', 'reported_aggregate': row.get('orders'),
                        'observation_window': None, 'platform': 'AliExpress', 'recent_ebay_demand': False}
                    commercial = item.get('finance', {}).get('commercial_screen')
                    item['shortlist_status'] = ('rejected_at_observed_related_asking_prices' if commercial == 'do_not_source_at_sampled_asking_prices'
                        else 'rejected' if any(b in item['blockers'] for b in ('search_relevance_unverified', 'source_unit_budget_exceeded', 'no_valid_in_stock_eur_sku', 'risk_policy_excluded'))
                        else 'hold_demand_and_complete_costs_unknown')
                    candidates.append(item)
                    rotation.remember(item, tag['concept_query'])
                except Exception as error:
                    errors.append({'stage': 'detail_or_evaluation', 'product_id': pid, 'error_type': type(error).__name__})
            eligible = [c for c in candidates if not c['shortlist_status'].startswith('rejected')]
            new_count = sum(c['product_id'] not in rotation.seen for c in eligible)
            outcome = ('new_eligible_candidates' if new_count else 'hold_pending_external_evidence' if eligible
                       else 'no_eligible_candidates' if candidates or not errors else 'discovery_unavailable')
            report = {'schema_version': 2, 'status': 'success' if candidates else 'failed',
                'execution_status': 'partial' if errors and searches > len([e for e in errors if e['stage'] == 'search']) else 'failed' if errors else 'success',
                'outcome': outcome, 'new_eligible_count': new_count,
                'eligible_count': len(eligible), 'skipped_rejections': len(skipped),
                'next_action': 'collect_verified_demand_full_costs_and_supplier_documents' if eligible else 'continue_bounded_search_rotation',
                'search_rotation': {'cursor': rotation.cursor, 'page_num': page_num, 'page_cap': PAGE_CAP,
                                    'history_status': rotation.load_status, 'search_reads': searches},
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'read_only': True, 'remote_mutations_performed': False, 'candidate_count': len(candidates),
                'unique_product_count': len({c['product_id'] for c in candidates}), 'candidates': candidates,
                'draft_ready_count': sum(c['draft_ready'] for c in candidates),
                'publish_ready_count': sum(c['ready_to_publish'] for c in candidates),
                'niche_results': allocations, 'discovery_rejections': rejected, 'errors': errors,
                'business_api_read_attempts': dict(reads.counts), 'total_read_count': sum(reads.counts.values()),
                'bounds': {'candidate_cap': limit, 'search_pages_per_query': 1, 'hits_per_query': 50,
                           'allocation_before_dedup': True, 'post_dedup_backfill': False},
                'source_unit_cap_eur': '40', 'source_cap_excludes_freight_tax': True,
                'minimum_profit_eur': '25', 'minimum_net_margin': '0.25',
                'demand_status': 'unknown_no_recent_ebay_sold_proof',
                'warehouse_origin': {'country': 'CN', 'basis': 'user_reported_not_supplier_verified'},
                'note': 'Rejected candidates are evidence, not an approved shortlist. Asks and supplier aggregate orders do not establish recent eBay sales.'}
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        temporary.replace(self.output_path)
        rotation.save(candidates)
        return report

    def run(self, limit=5):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('Research limit must be 1..50')
        from src.sourcing_completion import source_candidates
        niches = None
        if 'RESEARCH_KEYWORDS' in self.config:
            keywords = list(dict.fromkeys(k.strip() for k in str(self.config['RESEARCH_KEYWORDS']).split(',') if k.strip()))
            if not keywords:
                raise ValueError('At least one research keyword required')
            niches = {'configured_' + str(index + 1): (keyword,) for index, keyword in enumerate(keywords[:10])}
        if callable(getattr(self.supplier, 'search_product_page', None)):
            actionable_niches = ({name: tuple((q, None, q) for q in queries) for name, queries in niches.items()}
                                 if niches is not None else None)
            return self.run_actionable(limit=min(limit, 12), niches=actionable_niches)
        return source_candidates(self.supplier, self.ebay, self.output_path,
            config=self.config, researcher=self, niches=niches, limit=min(limit, 6))
