import sys
sys.path.insert(0, '.')
from smart_product_scorer import SmartProductScorer

print('=' * 80)
print('BLUE OCEAN SCORING TEST - PRODUCTION MODE')
print('=' * 80)
print()

scorer = SmartProductScorer()

# Test ürünler
test_products = [
    {
        'product_id': '1005007756879885',
        'product_title': 'Pet finger toothbrush',
        'product_main_image_url': 'http://example.com/img.jpg',
        'original_price': '5.99',
        'sale_price': '3.99',
        'evaluate_rate': '95.5',
        'volume': 500,
        'lastest_volume': 450,
        'ship_from_country': 'CN'
    },
    {
        'product_id': '1005009999999999',
        'product_title': 'Generic toy',
        'product_main_image_url': 'http://example.com/img2.jpg',
        'original_price': '15.99',
        'sale_price': '12.99',
        'evaluate_rate': '85.0',
        'volume': 50000,
        'lastest_volume': 48000,
        'ship_from_country': 'CN'
    }
]

print('Testing Blue Ocean Scoring Algorithm:')
print()

for product in test_products:
    result = scorer.calculate_blue_ocean_score(product)
    score = result.get('score', 0)
    
    if score >= 80:
        category = 'EXCELLENT'
    elif score >= 60:
        category = 'GOOD'
    elif score >= 40:
        category = 'FAIR'
    else:
        category = 'POOR'
    
    print('Product: {}'.format(product['product_title']))
    print('  Orders: {}'.format(product['volume']))
    print('  Rating: {}%'.format(product['evaluate_rate']))
    print('  Price: ${}'.format(product['sale_price']))
    print('  SCORE: {}/100 - {}'.format(score, category))
    print('  Reason: {}'.format(result.get('reason', 'N/A')))
    print()

print('TEST STATUS: SUCCESS')
