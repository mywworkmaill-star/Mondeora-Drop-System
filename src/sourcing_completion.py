"""Finite read-only sourcing pass. No publication, purchases or assumed demand.

Run once: python -m src.sourcing_completion
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from src.automation.research import ProductResearcher, semantic_relevance
from src.runtime import PROJECT_ROOT, enable_read_only, read_config

NICHES = {
    'office_monitor': ('bamboo monitor stand drawer', 'monitor stand drawer'),
    'office_desk': ('desk shelf', 'desk riser'),
    'home_garden': ('plant stand', 'plant trellis'),
}


def select_sku(product):
    """A deterministic proposal, not approval; unit cap excludes freight/tax."""
    valid = []
    for sku in product.get('skus') or [product]:
        cost = ProductResearcher.number(sku.get('sale_price'), positive=True)
        stock = ProductResearcher.number(sku.get('warehouse_count'))
        if (sku.get('sku_id') and sku.get('currency', product.get('currency')) == 'EUR'
                and cost is not None and cost <= Decimal('40') and stock is not None
                and stock >= 1 and stock == stock.to_integral_value()):
            valid.append((cost, -stock, str(sku['sku_id']), sku))
    return min(valid, key=lambda row: row[:3])[3] if valid else None


class ReadCounter:
    """Count attempted business API reads, including enrichment inside searches."""
    def __init__(self, **clients):
        self.clients = clients
        self.originals = []
        self.counts = {}

    def __enter__(self):
        for platform, client in self.clients.items():
            if client is None or not hasattr(client, '_request'):
                continue
            original = client._request
            def counted(*args, _platform=platform, _original=original, **kwargs):
                operation = str(args[0]) if _platform == 'supplier' else str(args[0])+' '+str(args[1])
                if _platform == 'marketplace' and str(args[0]) != 'GET':
                    raise ValueError('Read-only sourcing requires GET')
                if _platform == 'supplier' and operation not in {'aliexpress.ds.text.search', 'aliexpress.ds.product.get', 'aliexpress.ds.freight.query'}:
                    raise ValueError('Unsupported read-only sourcing operation')
                key = _platform+':'+operation
                self.counts[key] = self.counts.get(key, 0)+1
                return _original(*args, **kwargs)
            self.originals.append((client, original))
            client._request = counted
        return self

    def __exit__(self, *args):
        for client, original in self.originals:
            client._request = original


def source_candidates(supplier, ebay, output_path, *, config=None, researcher=None, niches=None, limit=6):
    enable_read_only()
    if type(limit) is not int or not 1 <= limit <= 6:
        raise ValueError('Candidate cap must be 1..6')
    niches = NICHES if niches is None else niches
    if not isinstance(niches, dict) or not 1 <= len(niches) <= 10 or any(not 1 <= len(queries) <= 2 for queries in niches.values()):
        raise ValueError('Bounded niches required')
    researcher = researcher or ProductResearcher(supplier, ebay, config=config)
    products, provenance, niche_results, errors = {}, {}, [], []
    with ReadCounter(supplier=supplier, marketplace=ebay) as reads:
        # All six bounded searches finish before any overall candidate truncation.
        for niche, queries in niches.items():
            result = {'niche': niche, 'queries': [], 'allocation': 2}
            for query in queries:
                try:
                    batch = supplier.search_products(query, page_num=1, page_size=10)
                    if not isinstance(batch, list):
                        raise ValueError('Invalid discovery schema')
                    result['queries'].append({'query': query, 'returned_count': len(batch[:10]), 'status': 'ok'})
                    for product in batch[:10]:
                        pid = str(product.get('product_id') or '')
                        if not pid.isascii() or not pid.isdigit():
                            continue
                        products.setdefault(pid, product)
                        tag = {'niche': niche, 'keyword': query}
                        if tag not in provenance.setdefault(pid, []):
                            provenance[pid].append(tag)
                except Exception as error:
                    result['queries'].append({'query': query, 'status': 'unavailable', 'error_type': type(error).__name__})
                    errors.append({'stage': 'search', 'niche': niche, 'error_type': type(error).__name__})
            niche_results.append(result)
        candidates, selected_ids, rejected = [], set(), []
        for niche_result in niche_results:
            niche = niche_result['niche']
            eligible = []
            for pid, product in products.items():
                tags = [p for p in provenance[pid] if p['niche'] == niche]
                if not tags or pid in selected_ids:
                    continue
                sku = select_sku(product)
                title = str(product.get('product_title') or '')
                matching = [p for p in tags if semantic_relevance(title+' '+str((sku or {}).get('sku_attr') or ''), p['keyword'])]
                reason = ('no_in_stock_eur_sku_within_40' if not sku else
                          'risk_policy_excluded' if ProductResearcher.risk_flags(title) else
                          'query_concepts_not_supported' if not matching else None)
                if reason:
                    rejected.append({'product_id': pid, 'niche': niche, 'reason': reason, 'provenance': tags})
                    continue
                # Prefer substantive higher-value products to low-ticket accessories.
                eligible.append((-Decimal(str(sku['sale_price'])), pid, sku, matching[0]))
            chosen = sorted(eligible, key=lambda row: row[:2])[:min(2, max(0, limit-len(candidates)))]
            niche_result['selected_product_ids'] = [row[1] for row in chosen]
            for _, pid, sku, tag in chosen:
                selected_ids.add(pid)
                product = dict(products[pid])
                if hasattr(supplier, '_request'):
                    try:
                        raw = supplier._request('aliexpress.ds.product.get', {'product_id': pid, 'ship_to_country': 'DE', 'target_currency': 'EUR', 'target_language': 'de'})['result']
                        from src.product_preparation import collect_provider_facts
                        product['provider_facts'] = collect_provider_facts(pid, raw)
                    except Exception as error:
                        product['provider_facts'] = {'status': 'unavailable', 'error_type': type(error).__name__}
                item = researcher._candidate(product, tag['keyword'], selected_sku_id=sku['sku_id'])
                item.update(niche=niche, provenance=provenance[pid], provider_facts=product.get('provider_facts', {'status': 'unavailable'}))
                screen = item.get('finance', {}).get('commercial_screen')
                item['shortlist_status'] = ('rejected_at_observed_related_asking_prices' if screen == 'do_not_source_at_sampled_asking_prices'
                    else 'rejected' if any(b in item.get('blockers', []) for b in ('risk_policy_excluded', 'source_unit_budget_exceeded', 'search_relevance_unverified'))
                    else 'hold_demand_and_complete_costs_unknown')
                item['profitable_verified'] = False
                candidates.append(item)
    report = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'read_only': True, 'remote_mutations_performed': False, 'source_frozen_after_run': True,
        'bounds': {'niches': 3, 'queries_per_niche': 2, 'hits_per_query': 10, 'candidates_per_niche': 2, 'global_candidate_cap': 6},
        'minimum_profit_eur': '25', 'minimum_net_margin': '0.25', 'source_unit_cap_eur': '40', 'source_cap_excludes_freight_tax': True,
        'niche_results': niche_results, 'unique_discovered_product_count': len(products),
        'search_read_count': sum(len(r['queries']) for r in niche_results),
        'business_api_read_attempts': dict(reads.counts), 'total_read_count': sum(reads.counts.values()),
        'read_count_scope': 'Business API attempts including search/detail/freight/taxonomy/Browse; excludes internal OAuth/network retries',
        'candidate_count': len(candidates), 'candidates': candidates, 'discovery_rejections': rejected,
        'profitable_verified_count': 0, 'shortlist_status': 'no_verified_profitable_candidate', 'errors': errors,
        'demand_status': 'unknown_no_recent_ebay_sold_proof',
        'note': 'Scenario price floors are proposals, not achievable prices. Related asks and supplier aggregate sales never establish eBay DE recent sold demand.'}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(output_path)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT_ROOT/'data/production_sourcing_candidates.json')
    args = parser.parse_args(argv)
    enable_read_only()
    from src.api.aliexpress_client import AliExpressAPIClient
    from src.api.ebay_client import eBayAPIClient
    report = source_candidates(AliExpressAPIClient(), eBayAPIClient(), args.output, config=read_config())
    print(json.dumps({key: report[key] for key in ('candidate_count', 'unique_discovered_product_count', 'total_read_count', 'profitable_verified_count', 'shortlist_status')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
