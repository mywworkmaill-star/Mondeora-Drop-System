#!/usr/bin/env python
"""
BLUE OCEAN PRODUCT FINDER
Rakip az ama alıcısı çok ürünler bulur!
Low competition + High demand = ALTIN!
"""

import sys
import os
sys.path.insert(0, '.')

import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import quote_plus

class BlueOceanFinder:
    """
    Finds products with low competition but high demand
    """
    
    def __init__(self):
        self.ebay_search_url = "https://www.ebay.de/sch/i.html"
        
    def check_ebay_competition(self, product_title, category_id=20741):
        """
        Check how many sellers have this product on eBay
        
        Returns:
            dict: {
                'competition_count': int,
                'competition_level': 'low' | 'medium' | 'high',
                'search_volume_estimate': int
            }
        """
        
        try:
            # Search eBay for similar products
            search_query = self._extract_keywords(product_title)
            
            params = {
                '_nkw': search_query,
                '_sacat': category_id,
                'LH_ItemCondition': 1000  # New only
            }
            
            # Make request with user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(
                self.ebay_search_url,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get total results count
                results_count_elem = soup.find('h1', class_='srp-controls__count-heading')
                
                if results_count_elem:
                    # Extract number from text like "1.234 Ergebnisse"
                    text = results_count_elem.get_text()
                    count_str = ''.join(filter(str.isdigit, text.split('Ergebnisse')[0]))
                    
                    if count_str:
                        competition_count = int(count_str)
                    else:
                        competition_count = 0
                else:
                    competition_count = 0
                
                # Determine competition level
                if competition_count < 50:
                    competition_level = 'low'  # ALTIN!
                elif competition_count < 200:
                    competition_level = 'medium'  # İyi
                else:
                    competition_level = 'high'  # Rekabet çok
                
                # Estimate search volume (simplified)
                # More results usually means more demand
                # But we want LOW competition, so this is tricky
                search_volume_estimate = min(competition_count * 10, 10000)
                
                return {
                    'competition_count': competition_count,
                    'competition_level': competition_level,
                    'search_volume_estimate': search_volume_estimate,
                    'is_blue_ocean': competition_count < 50,  # Less than 50 sellers = BLUE OCEAN!
                    'search_query': search_query
                }
            else:
                return {
                    'competition_count': -1,
                    'competition_level': 'unknown',
                    'search_volume_estimate': 0,
                    'is_blue_ocean': False,
                    'error': f'HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {
                'competition_count': -1,
                'competition_level': 'unknown',
                'search_volume_estimate': 0,
                'is_blue_ocean': False,
                'error': str(e)
            }
    
    def _extract_keywords(self, title):
        """Extract main keywords from product title"""
        # Remove common words
        stopwords = ['und', 'für', 'mit', 'das', 'der', 'die', 'von', 'zu', 'auf']
        
        # Clean title
        words = title.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        
        # Take first 3-4 meaningful words
        return ' '.join(keywords[:4])
    
    def evaluate_product_potential(self, product_title, aliexpress_price, category_id=20741):
        """
        Evaluate if product is a good blue ocean opportunity
        
        Returns:
            dict: {
                'score': int (0-100),
                'recommendation': 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR',
                'reasons': list
            }
        """
        
        print(f"🔍 Evaluating: {product_title[:50]}...")
        
        competition = self.check_ebay_competition(product_title, category_id)
        
        score = 50  # Base score
        reasons = []
        
        # Competition scoring
        if competition['competition_level'] == 'low':
            score += 30
            reasons.append(f"✅ LOW competition ({competition['competition_count']} sellers) - BLUE OCEAN!")
        elif competition['competition_level'] == 'medium':
            score += 15
            reasons.append(f"⚠️  Medium competition ({competition['competition_count']} sellers)")
        else:
            score -= 20
            reasons.append(f"❌ HIGH competition ({competition['competition_count']} sellers)")
        
        # Search volume scoring (simplified)
        if competition['search_volume_estimate'] > 1000:
            score += 20
            reasons.append(f"✅ Good search volume (~{competition['search_volume_estimate']})")
        elif competition['search_volume_estimate'] > 500:
            score += 10
            reasons.append(f"⚠️  Moderate search volume (~{competition['search_volume_estimate']})")
        
        # Blue ocean bonus
        if competition.get('is_blue_ocean'):
            score += 20
            reasons.append("🌊 BLUE OCEAN OPPORTUNITY! (< 50 sellers)")
        
        # Determine recommendation
        if score >= 80:
            recommendation = 'EXCELLENT'
        elif score >= 65:
            recommendation = 'GOOD'
        elif score >= 50:
            recommendation = 'FAIR'
        else:
            recommendation = 'POOR'
        
        return {
            'score': min(score, 100),
            'recommendation': recommendation,
            'reasons': reasons,
            'competition': competition
        }


if __name__ == "__main__":
    # Test
    finder = BlueOceanFinder()
    
    # Test products
    test_products = [
        "Hundespielzeugball Interactive Pet Toy",
        "Katzenminze Spielzeug Plüsch Maus",
        "Haustier Fingerzahnbürste Dental Care"
    ]
    
    print()
    print("=" * 70)
    print("🌊 BLUE OCEAN PRODUCT FINDER - TEST")
    print("=" * 70)
    print()
    
    for product in test_products:
        result = finder.evaluate_product_potential(product, 5.0)
        
        print()
        print(f"📦 Product: {product}")
        print(f"   Score: {result['score']}/100")
        print(f"   Recommendation: {result['recommendation']}")
        print(f"   Competition: {result['competition']['competition_count']} sellers")
        print(f"   Level: {result['competition']['competition_level'].upper()}")
        print()
        print("   Reasons:")
        for reason in result['reasons']:
            print(f"     {reason}")
        print()
        print("-" * 70)
        
        time.sleep(2)  # Be nice to eBay
