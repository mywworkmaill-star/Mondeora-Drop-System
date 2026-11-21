"""
eBay Listing Pre-Flight Validator
Validates products before sending to eBay API
"""

class eBayListingValidator:
    """Validates products against eBay requirements"""
    
    REQUIRED_FIELDS = {
        'title': (10, 80),          # min, max chars
        'description': (500, 50000),
        'price': (1.0, 9999.99),
        'images': (1, 24),
        'category_id': True,
        'aspects': (3, 50),
    }
    
    def validate(self, product):
        """
        Validate product against eBay requirements
        
        Args:
            product: dict with product data from database
            
        Returns:
            {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'fixes': dict,
                'score': int (0-100)
            }
        """
        errors = []
        warnings = []
        fixes = {}
        
        # 1. TITLE VALIDATION
        title = product.get('title', '')
        if not title:
            errors.append('Title is missing')
        elif len(title) < 10:
            errors.append(f'Title too short: {len(title)} chars (min 10)')
        elif len(title) > 80:
            errors.append(f'Title too long: {len(title)} chars (max 80)')
            # Auto-fix: truncate
            fixes['title'] = title[:77] + '...'
        
        # 2. PRICE VALIDATION
        price = product.get('ebay_price')
        if not price:
            errors.append('Price is missing')
        elif price < 1.0:
            errors.append(f'Price too low: €{price} (min €1)')
        elif price > 9999.99:
            errors.append(f'Price too high: €{price} (max €9999.99)')
        
        # Round to 2 decimals
        if price:
            rounded = round(float(price), 2)
            if abs(price - rounded) > 0.001:
                warnings.append(f'Price has >2 decimals: €{price}')
                fixes['ebay_price'] = rounded
        
        # 3. IMAGES VALIDATION
        images = product.get('image_url', '')
        if not images:
            errors.append('No images')
        else:
            img_list = [i.strip() for i in str(images).split(',') if i.strip()]
            img_count = len(img_list)
            
            if img_count < 1:
                errors.append('No valid images')
            elif img_count < 7:
                warnings.append(f'Only {img_count} images (recommend 7+)')
            
            # Check HTTPS
            http_images = [i for i in img_list if i.startswith('http://')]
            if http_images:
                warnings.append(f'{len(http_images)} images use HTTP (should be HTTPS)')
                fixes['image_url'] = ','.join([
                    img.replace('http://', 'https://') for img in img_list
                ])
        
        # 4. DESCRIPTION VALIDATION
        desc = product.get('description', '')
        desc_len = len(desc) if desc else 0
        
        if desc_len < 500:
            errors.append(f'Description too short: {desc_len} chars (min 500)')
        elif desc_len < 2000:
            warnings.append(f'Description short: {desc_len} chars (recommend 2000+)')
        
        # 5. ASPECTS VALIDATION
        aspect_count = product.get('aspect_count', 0)
        if aspect_count < 3:
            errors.append(f'Too few aspects: {aspect_count} (min 3)')
        elif aspect_count < 5:
            warnings.append(f'Few aspects: {aspect_count} (recommend 5+)')
        
        # 6. CATEGORY VALIDATION
        if not product.get('category_id'):
            errors.append('Category ID is missing')
        
        # 7. SKU/ID VALIDATION
        if not product.get('aliexpress_product_id'):
            errors.append('AliExpress product ID is missing')
        
        # 8. STOCK VALIDATION
        stock = product.get('current_stock')
        if stock is not None and stock < 1:
            warnings.append(f'Low/zero stock: {stock}')
        
        # Calculate quality score
        score = self._calculate_score(errors, warnings, product)
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'fixes': fixes,
            'score': score
        }
    
    def _calculate_score(self, errors, warnings, product):
        """
        Calculate quality score (0-100)
        
        Score breakdown:
        - Start: 100
        - Each error: -20
        - Each warning: -5
        - Bonus for good metrics
        """
        score = 100
        
        # Penalties
        score -= len(errors) * 20
        score -= len(warnings) * 5
        
        # Bonuses
        if product.get('image_url'):
            img_count = len([i for i in str(product['image_url']).split(',') if i.strip()])
            if img_count >= 7:
                score += 5
            if img_count >= 10:
                score += 5
        
        desc_len = len(product.get('description', ''))
        if desc_len >= 2000:
            score += 5
        if desc_len >= 3000:
            score += 5
        
        aspect_count = product.get('aspect_count', 0)
        if aspect_count >= 5:
            score += 5
        if aspect_count >= 10:
            score += 5
        
        return max(0, min(100, score))
    
    def get_recommendation(self, validation_result):
        """
        Get recommendation based on validation
        
        Returns:
            str: 'publish', 'fix_and_publish', or 'needs_work'
        """
        score = validation_result['score']
        errors = len(validation_result['errors'])
        
        if errors > 0:
            return 'needs_work'
        elif score >= 80:
            return 'publish'
        else:
            return 'fix_and_publish'
