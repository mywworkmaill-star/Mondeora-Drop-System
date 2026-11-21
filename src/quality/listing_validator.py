"""
Pre-listing Quality Gate Validator
Prevents bad listings before eBay publish
"""

from typing import Dict, List, Tuple


class ListingQualityGate:
    """
    Automated quality validation before eBay publish
    Score: 0-100 (80+ = PASS, <80 = FAIL)
    """
    
    RULES = {
        'images': {'min': 6, 'max': 12, 'weight': 15, 'critical': True},
        'description': {'min': 2000, 'max': 5000, 'weight': 10, 'critical': False},
        'aspects': {'min': 15, 'max': 30, 'weight': 15, 'critical': True},
        'produktart_match': {'weight': 20, 'critical': True},
        'dimensions': {'weight': 10, 'critical': False},
        'niche': {'weight': 15, 'critical': True},
        'title_quality': {'weight': 15, 'critical': False}
    }
    
    NICHE_KEYWORDS = [
        'aufbewahrung', 'organizer', 'storage', 'box', 'halter',
        'holder', 'rack', 'stand', 'container', 'behälter', 'regal'
    ]
    
    def validate(self, listing_data: dict) -> dict:
        """
        Validate listing before eBay publish
        
        Args:
            listing_data: {
                'title': str,
                'description': str,
                'images': List[str],
                'aspects': Dict[str, List[str]],
                'price': float
            }
        
        Returns:
            {
                'score': 0-100,
                'status': 'PASS' | 'FAIL',
                'errors': List[str],
                'warnings': List[str],
                'details': Dict
            }
        """
        score = 100
        errors = []
        warnings = []
        details = {}
        
        # Rule 1: Images (CRITICAL)
        images = listing_data.get('images', [])
        image_count = len(images)
        
        if image_count < self.RULES['images']['min']:
            msg = f"❌ Images: {image_count} < {self.RULES['images']['min']} (CRITICAL)"
            errors.append(msg)
            score -= self.RULES['images']['weight']
        elif image_count > self.RULES['images']['max']:
            msg = f"⚠️ Images: {image_count} > {self.RULES['images']['max']} (eBay limit 12)"
            warnings.append(msg)
        else:
            details['images'] = f"✅ {image_count} images"
        
        # Rule 2: Description length
        description = listing_data.get('description', '')
        desc_len = len(description)
        
        if desc_len < self.RULES['description']['min']:
            msg = f"⚠️ Description: {desc_len} < {self.RULES['description']['min']} chars"
            warnings.append(msg)
            score -= self.RULES['description']['weight']
        else:
            details['description'] = f"✅ {desc_len} chars"
        
        # Rule 3: Aspects count (CRITICAL)
        aspects = listing_data.get('aspects', {})
        aspect_count = len(aspects)
        
        if aspect_count < self.RULES['aspects']['min']:
            msg = f"❌ Aspects: {aspect_count} < {self.RULES['aspects']['min']} (CRITICAL)"
            errors.append(msg)
            score -= self.RULES['aspects']['weight']
        else:
            details['aspects'] = f"✅ {aspect_count} aspects"
        
        # Rule 4: Produktart matches title (CRITICAL)
        title = listing_data.get('title', '').lower()
        produktart = aspects.get('Produktart', [''])[0].lower()
        
        # Extract base word from Produktart (remove -organizer, -box, -halter)
        produktart_base = produktart.replace('-organizer', '').replace('-halter', '').replace('-box', '').replace('organizer', '').replace('box', '').replace('halter', '').strip()
        
        # Also check singular/plural variations
        # "küchen" → "küche", "badezimmer" → "bad"
        base_variations = [
            produktart_base,
            produktart_base.rstrip('n'),  # "küchen" → "küche"
            produktart_base.rstrip('s'),  # "boxes" → "boxe"
        ]
        
        # Check if ANY variation is in title
        match_found = any(var in title for var in base_variations if var)
        
        if produktart_base and not match_found:
            msg = f"❌ Produktart '{produktart}' NOT in title (CRITICAL)"
            errors.append(msg)
            score -= self.RULES['produktart_match']['weight']
        else:
            details['produktart'] = f"✅ '{produktart}' matches title"
        
        # Rule 5: Dimensions populated
        required_dims = ['Breite', 'Höhe', 'Länge']
        empty_dims = []
        
        for dim in required_dims:
            value = aspects.get(dim, [''])[0]
            if value in ['Nicht angegeben', 'Siehe Beschreibung', '']:
                empty_dims.append(dim)
        
        if len(empty_dims) == 3:
            msg = f"⚠️ All dimensions empty: {empty_dims}"
            warnings.append(msg)
            score -= self.RULES['dimensions']['weight']
        elif len(empty_dims) > 0:
            details['dimensions'] = f"⚠️ {len(empty_dims)}/3 dimensions empty"
        else:
            details['dimensions'] = f"✅ All dimensions populated"
        
        # Rule 6: Niche compliance (CRITICAL)
        if not any(kw in title for kw in self.NICHE_KEYWORDS):
            msg = f"❌ Niche: No Home Organization keywords in title (CRITICAL)"
            errors.append(msg)
            score -= self.RULES['niche']['weight']
        else:
            matched_keywords = [kw for kw in self.NICHE_KEYWORDS if kw in title]
            details['niche'] = f"✅ Niche match: {matched_keywords[:2]}"
        
        # Rule 7: Title quality
        if len(title) < 40:
            msg = f"⚠️ Title too short: {len(title)} chars (recommend 60-80)"
            warnings.append(msg)
            score -= self.RULES['title_quality']['weight']
        elif len(title) > 80:
            msg = f"❌ Title too long: {len(title)} chars (eBay limit 80)"
            errors.append(msg)
            score -= self.RULES['title_quality']['weight']
        else:
            details['title'] = f"✅ {len(title)} chars"
        
        # 🔍 BONUS: Vision confidence (NEW!)
        vision_confidence = listing_data.get('vision_confidence', 0)
        if vision_confidence >= 80:
            bonus = 5
            score += bonus
            details['vision'] = f"🔍 +{bonus} vision bonus ({vision_confidence}% confidence)"
        elif vision_confidence > 0:
            details['vision'] = f"⚠️ Vision: {vision_confidence}% (below 80% threshold)"
        
        # Final score
        final_score = max(0, min(100, score))  # Cap at 100
        status = 'PASS' if final_score >= 80 else 'FAIL'
        
        return {
            'score': final_score,
            'status': status,
            'errors': errors,
            'warnings': warnings,
            'details': details
        }
    
    def print_report(self, result: dict):
        """Print formatted validation report"""
        print(f"\n{'='*70}")
        print(f"🔍 LISTING QUALITY GATE VALIDATION")
        print(f"{'='*70}")
        print()
        
        # Score
        status_emoji = "✅" if result['status'] == 'PASS' else "❌"
        print(f"{status_emoji} SCORE: {result['score']}/100 ({result['status']})")
        print()
        
        # Details
        if result['details']:
            print("📊 DETAILS:")
            for key, value in result['details'].items():
                print(f"   {value}")
            print()
        
        # Errors (critical)
        if result['errors']:
            print("❌ CRITICAL ERRORS:")
            for error in result['errors']:
                print(f"   {error}")
            print()
        
        # Warnings
        if result['warnings']:
            print("⚠️ WARNINGS:")
            for warning in result['warnings']:
                print(f"   {warning}")
            print()
        
        # Recommendation
        if result['status'] == 'FAIL':
            print("🛑 RECOMMENDATION: DO NOT PUBLISH - Fix critical errors first")
        else:
            print("✅ RECOMMENDATION: OK TO PUBLISH")
        
        print(f"{'='*70}")


# Example usage
if __name__ == "__main__":
    # Test data
    test_listing = {
        'title': 'Küchen-Organizer Aufbewahrungsbox 30x20x10cm',
        'description': 'A' * 2500,  # 2500 chars
        'images': ['img1.jpg', 'img2.jpg', 'img3.jpg', 'img4.jpg', 'img5.jpg', 'img6.jpg'],
        'aspects': {
            'Produktart': ['Küchen-Organizer'],
            'Breite': ['20 cm'],
            'Höhe': ['10 cm'],
            'Länge': ['30 cm'],
            'Material': ['Kunststoff'],
            'Farbe': ['Weiß'],
            'Zimmer': ['Küche'],
            'Marke': ['Markenlos'],
            'Zustand': ['Neu']
            # 9 aspects total
        },
        'price': 44.99
    }
    
    gate = ListingQualityGate()
    result = gate.validate(test_listing)
    gate.print_report(result)
