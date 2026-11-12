#!/usr/bin/env python
"""
SMART PRODUCT SCORER
AliExpress satış verisinden blue ocean ürünleri bulur
"""

import sys
import os
sys.path.insert(0, '.')

class SmartProductScorer:
    """
    Scores products based on AliExpress data to find blue ocean opportunities
    """
    
    def __init__(self):
        pass
    
    def calculate_blue_ocean_score(self, product_data):
        """
        Calculate blue ocean score based on product metrics
        
        Args:
            product_data: dict with keys:
                - order_count: total orders on AliExpress
                - rating: product rating (4.0-5.0)
                - review_count: number of reviews
                - price: product price
                - seller_level: seller reputation
        
        Returns:
            dict: {
                'score': int (0-100),
                'category': 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR',
                'reasons': list,
                'is_blue_ocean': bool
            }
        """
        
        order_count = product_data.get('order_count', 0)
        rating = product_data.get('rating', 0)
        review_count = product_data.get('review_count', 0)
        price = product_data.get('price', 0)
        
        score = 50  # Base score
        reasons = []
        
        # === BLUE OCEAN INDICATORS ===
        
        # 1. MODERATE ORDERS (not too high, not too low)
        # Too high = too much competition on eBay
        # Too low = no demand
        if 100 <= order_count <= 1000:
            score += 25
            reasons.append(f"✅ SWEET SPOT orders ({order_count}) - proven demand, low saturation")
        elif 1000 < order_count <= 5000:
            score += 15
            reasons.append(f"⚠️  Good orders ({order_count}) but might have competition")
        elif order_count > 5000:
            score -= 15
            reasons.append(f"❌ TOO POPULAR ({order_count} orders) - probably saturated on eBay")
        else:
            score -= 10
            reasons.append(f"⚠️  Low orders ({order_count}) - unproven demand")
        
        # 2. HIGH RATING (quality product)
        if rating >= 4.5:
            score += 15
            reasons.append(f"✅ Excellent rating ({rating:.1f}★)")
        elif rating >= 4.0:
            score += 8
            reasons.append(f"⚠️  Good rating ({rating:.1f}★)")
        else:
            score -= 10
            reasons.append(f"❌ Low rating ({rating:.1f}★)")
        
        # 3. MODERATE REVIEWS (social proof but not oversaturated)
        if 50 <= review_count <= 500:
            score += 15
            reasons.append(f"✅ Perfect review count ({review_count}) - trusted but not mainstream")
        elif 500 < review_count <= 2000:
            score += 5
            reasons.append(f"⚠️  Many reviews ({review_count}) - getting popular")
        elif review_count > 2000:
            score -= 10
            reasons.append(f"❌ Too many reviews ({review_count}) - oversaturated")
        else:
            score += 5
            reasons.append(f"⚠️  Few reviews ({review_count}) - less proof")
        
        # 4. GOOD PROFIT MARGIN POTENTIAL
        if price >= 3 and price <= 15:
            score += 10
            reasons.append(f"✅ Perfect price range (${price:.2f}) - good margin potential")
        elif price > 15:
            score += 5
            reasons.append(f"⚠️  Higher price (${price:.2f}) - might be harder to sell")
        else:
            score -= 5
            reasons.append(f"⚠️  Very low price (${price:.2f}) - thin margins")
        
        # === BLUE OCEAN CLASSIFICATION ===
        # Blue Ocean = moderate orders, high quality, not oversaturated
        is_blue_ocean = (
            100 <= order_count <= 1000 and
            rating >= 4.3 and
            review_count >= 30 and
            review_count <= 1000
        )
        
        if is_blue_ocean:
            score += 20
            reasons.append("🌊 BLUE OCEAN! Perfect combo: demand proven, low saturation!")
        
        # Final score
        final_score = max(0, min(100, score))
        
        # Category
        if final_score >= 80:
            category = 'EXCELLENT'
        elif final_score >= 65:
            category = 'GOOD'
        elif final_score >= 50:
            category = 'FAIR'
        else:
            category = 'POOR'
        
        return {
            'score': final_score,
            'category': category,
            'reasons': reasons,
            'is_blue_ocean': is_blue_ocean
        }
    
    def filter_blue_ocean_products(self, products):
        """
        Filter products to find best blue ocean opportunities
        
        Args:
            products: list of product dicts
        
        Returns:
            list: filtered and sorted products (best first)
        """
        
        scored_products = []
        
        for product in products:
            score_result = self.calculate_blue_ocean_score(product)
            
            product_with_score = {
                **product,
                'blue_ocean_score': score_result['score'],
                'blue_ocean_category': score_result['category'],
                'blue_ocean_reasons': score_result['reasons'],
                'is_blue_ocean': score_result['is_blue_ocean']
            }
            
            scored_products.append(product_with_score)
        
        # Sort by score (best first)
        scored_products.sort(key=lambda x: x['blue_ocean_score'], reverse=True)
        
        return scored_products


if __name__ == "__main__":
    # Test
    scorer = SmartProductScorer()
    
    test_products = [
        {
            'title': 'Product A - Oversaturated',
            'order_count': 10000,
            'rating': 4.8,
            'review_count': 5000,
            'price': 8.50
        },
        {
            'title': 'Product B - Blue Ocean!',
            'order_count': 500,
            'rating': 4.6,
            'review_count': 200,
            'price': 6.00
        },
        {
            'title': 'Product C - Unproven',
            'order_count': 20,
            'rating': 4.2,
            'review_count': 5,
            'price': 3.00
        },
        {
            'title': 'Product D - Perfect Sweet Spot',
            'order_count': 800,
            'rating': 4.7,
            'review_count': 350,
            'price': 9.00
        }
    ]
    
    print()
    print("=" * 70)
    print("🌊 SMART PRODUCT SCORER - BLUE OCEAN FINDER")
    print("=" * 70)
    print()
    
    results = scorer.filter_blue_ocean_products(test_products)
    
    for i, product in enumerate(results, 1):
        print(f"{i}. {product['title']}")
        print(f"   Score: {product['blue_ocean_score']}/100 ({product['blue_ocean_category']})")
        print(f"   Blue Ocean: {'YES! 🌊' if product['is_blue_ocean'] else 'No'}")
        print(f"   Orders: {product['order_count']}, Rating: {product['rating']}, Reviews: {product['review_count']}")
        print()
        print("   Analysis:")
        for reason in product['blue_ocean_reasons']:
            print(f"     {reason}")
        print()
        print("-" * 70)
        print()
