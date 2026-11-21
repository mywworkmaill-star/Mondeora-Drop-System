#!/usr/bin/env python3
"""
Test Competitor Aspect Integration
===================================

Tests that competitor scraping works in the full listing pipeline.

USAGE:
    python scripts/test_competitor_integration.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.api.aliexpress_client import AliExpressAPIClient
from scripts.extract_aspects_from_description import extract_aspects_for_product


def main():
    """Test competitor integration."""
    
    print(f"\n{'='*60}")
    print(f"COMPETITOR ASPECT INTEGRATION TEST")
    print(f"{'='*60}\n")
    
    # Initialize
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    # Test products
    test_cases = [
        {
            'product_id': '1005012707841792',
            'category_id': '20741',
            'name': 'Müllbeutelhalter'
        },
        {
            'product_id': '1005009030953454',
            'category_id': '3285',
            'name': 'Pop-Up Maus'
        }
    ]
    
    for idx, tc in enumerate(test_cases, 1):
        print(f"\n[{idx}/{len(test_cases)}] Testing: {tc['name']}")
        print(f"  Product ID: {tc['product_id']}")
        print(f"  Category: {tc['category_id']}")
        
        # WITH competitor scraping
        print(f"\n  🏆 WITH COMPETITORS:")
        aspects_with = extract_aspects_for_product(
            ali, ebay, 
            tc['product_id'], 
            tc['category_id'],
            include_competitors=True
        )
        
        # WITHOUT competitor scraping
        print(f"\n  ❌ WITHOUT COMPETITORS:")
        aspects_without = extract_aspects_for_product(
            ali, ebay, 
            tc['product_id'], 
            tc['category_id'],
            include_competitors=False
        )
        
        # Compare
        print(f"\n  📊 COMPARISON:")
        print(f"    With competitors: {len(aspects_with)} aspects")
        print(f"    Without competitors: {len(aspects_without)} aspects")
        print(f"    Improvement: +{len(aspects_with) - len(aspects_without)} aspects")
        
        # Show competitor-only aspects
        competitor_only = set(aspects_with.keys()) - set(aspects_without.keys())
        if competitor_only:
            print(f"\n  🏆 Competitor-only aspects ({len(competitor_only)}):")
            for name in competitor_only:
                val = aspects_with[name]
                val_str = val[0] if isinstance(val, list) else val
                print(f"    ✅ {name}: {val_str}")
    
    print(f"\n{'='*60}")
    print(f"✅ TEST COMPLETE")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
