"""
Auto-Fix Engine
Automatically fixes common eBay listing issues
"""

import json


class AutoFixEngine:
    """Automatically fix common listing issues"""
    
    def __init__(self, db_conn=None):
        self.db = db_conn
        self.fixes_applied = []
    
    def apply_validation_fixes(self, product, validation_result):
        """
        Apply fixes suggested by validator
        
        Args:
            product: dict with product data
            validation_result: dict from eBayListingValidator
            
        Returns:
            {
                'fixed': bool,
                'changes': list,
                'product': dict (updated)
            }
        """
        
        if not validation_result.get('fixes'):
            return {
                'fixed': False,
                'changes': [],
                'product': product
            }
        
        changes = []
        
        for field, fix_value in validation_result['fixes'].items():
            old_value = product.get(field)
            product[field] = fix_value
            
            changes.append({
                'field': field,
                'old': old_value,
                'new': fix_value,
                'reason': 'validation_fix'
            })
        
        return {
            'fixed': True,
            'changes': changes,
            'product': product
        }
    
    def apply_error_fix(self, product, inventory_data, offer_data, error_info):
        """
        Apply fix based on eBay error response
        
        Args:
            product: dict with product data
            inventory_data: dict for inventory item API
            offer_data: dict for offer API
            error_info: dict from eBayErrorParser
            
        Returns:
            {
                'fixed': bool,
                'changes': list,
                'product': dict,
                'inventory_data': dict,
                'offer_data': dict,
                'action': str
            }
        """
        
        if not error_info.get('auto_fixable'):
            return {
                'fixed': False,
                'reason': 'Not auto-fixable',
                'action': 'manual_review'
            }
        
        error_type = error_info['error_type']
        changes = []
        action = error_info.get('action', 'retry')
        
        # Apply type-specific fixes
        if error_type == 'merchant_location':
            old_loc = offer_data.get('merchantLocationKey')
            offer_data['merchantLocationKey'] = 'WAREHOUSE_DE_1'
            changes.append(f'Updated merchantLocationKey: {old_loc} → WAREHOUSE_DE_1')
        
        elif error_type == 'invalid_price':
            old_price = offer_data['pricingSummary']['price']['value']
            new_price = str(round(float(old_price), 2))
            offer_data['pricingSummary']['price']['value'] = new_price
            product['ebay_price'] = round(float(old_price), 2)
            changes.append(f'Rounded price: {old_price} → {new_price}')
        
        elif error_type == 'image_error':
            # Fix HTTP → HTTPS
            if 'imageUrls' in inventory_data.get('product', {}):
                old_imgs = inventory_data['product']['imageUrls']
                new_imgs = [img.replace('http://', 'https://') for img in old_imgs]
                inventory_data['product']['imageUrls'] = new_imgs
                
                if old_imgs != new_imgs:
                    changes.append(f'Fixed {len(old_imgs)} images to HTTPS')
                    
                    # Update product too
                    product['image_url'] = ','.join(new_imgs)
        
        elif error_type == 'title_error':
            # Truncate or clean title
            title = inventory_data['product']['title']
            
            if len(title) > 80:
                new_title = title[:77] + '...'
                inventory_data['product']['title'] = new_title
                product['title'] = new_title
                changes.append(f'Truncated title: {len(title)} → 80 chars')
            
            # Remove HTML tags if present
            import re
            clean_title = re.sub(r'<[^>]+>', '', title)
            if clean_title != title:
                inventory_data['product']['title'] = clean_title
                product['title'] = clean_title
                changes.append('Removed HTML from title')
        
        elif error_type == 'duplicate':
            # Can't fix duplicate - must skip or update existing
            return {
                'fixed': False,
                'reason': 'Duplicate listing exists',
                'action': 'skip',
                'ebay_item_id': error_info.get('ebay_item_id'),
                'changes': changes
            }
        
        elif error_type == 'policy_error':
            # Update policy IDs to known working ones
            offer_data['listingPolicies'] = {
                'fulfillmentPolicyId': '263035514017',
                'paymentPolicyId': '263035507017',
                'returnPolicyId': '263035512017'
            }
            changes.append('Updated policy IDs to defaults')
        
        return {
            'fixed': True,
            'changes': changes,
            'product': product,
            'inventory_data': inventory_data,
            'offer_data': offer_data,
            'action': action
        }
    
    def auto_enrich_product(self, product):
        """
        Auto-enrich product to meet minimum requirements
        
        Args:
            product: dict with product data
            
        Returns:
            {
                'enriched': bool,
                'changes': list,
                'product': dict (updated)
            }
        """
        
        changes = []
        
        # 1. EXTEND DESCRIPTION
        desc = product.get('description', '')
        if len(desc) < 2000:
            # Add generic useful info
            additional = '''

<h3>Versand und Lieferung:</h3>
<ul>
<li>Schneller Versand aus Deutschland</li>
<li>Sorgfältige Verpackung</li>
<li>Tracking-Nummer inklusive</li>
<li>Lieferzeit: 3-5 Werktage</li>
</ul>

<h3>Kundenservice:</h3>
<ul>
<li>30 Tage Rückgaberecht</li>
<li>Deutscher Kundensupport</li>
<li>Sichere Bezahlung</li>
<li>100% Käuferschutz</li>
</ul>

<h3>Warum bei uns kaufen?</h3>
<ul>
<li>Geprüfte Qualität</li>
<li>Faire Preise</li>
<li>Zufriedene Kunden</li>
<li>Schnelle Abwicklung</li>
</ul>

<p><strong>Bei Fragen kontaktieren Sie uns gerne!</strong></p>
'''
            new_desc = desc + additional
            product['description'] = new_desc
            changes.append(f'Extended description: {len(desc)} → {len(new_desc)} chars')
        
        # 2. ADD MORE ASPECTS (if possible)
        aspects = product.get('aspects')
        if aspects:
            try:
                aspect_dict = json.loads(aspects) if isinstance(aspects, str) else aspects
                
                # Add generic useful aspects if not present
                defaults = {
                    'Zustand': ['Neu'],
                    'Lieferumfang': ['Siehe Beschreibung'],
                    'Herstellungsland und -region': ['China'],
                }
                
                added = 0
                for key, value in defaults.items():
                    if key not in aspect_dict:
                        aspect_dict[key] = value
                        added += 1
                
                if added > 0:
                    product['aspects'] = json.dumps(aspect_dict)
                    product['aspect_count'] = len(aspect_dict)
                    changes.append(f'Added {added} generic aspects')
                    
            except:
                pass
        
        # 3. ENSURE HTTPS IMAGES
        images = product.get('image_url', '')
        if 'http://' in images:
            new_images = images.replace('http://', 'https://')
            product['image_url'] = new_images
            changes.append('Converted images to HTTPS')
        
        # 4. ROUND PRICE
        price = product.get('ebay_price')
        if price:
            rounded = round(float(price), 2)
            if abs(price - rounded) > 0.001:
                product['ebay_price'] = rounded
                changes.append(f'Rounded price: {price} → {rounded}')
        
        return {
            'enriched': len(changes) > 0,
            'changes': changes,
            'product': product
        }
    
    def save_fixes_to_db(self, product_id, changes):
        """Save applied fixes to database"""
        
        if not self.db or not product_id:
            return False
        
        try:
            cursor = self.db.cursor()
            
            # Update product
            if 'product' in changes:
                prod = changes['product']
                
                cursor.execute('''
                    UPDATE products
                    SET title = ?,
                        description = ?,
                        image_url = ?,
                        ebay_price = ?,
                        aspects = ?,
                        aspect_count = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    prod.get('title'),
                    prod.get('description'),
                    prod.get('image_url'),
                    prod.get('ebay_price'),
                    prod.get('aspects'),
                    prod.get('aspect_count'),
                    product_id
                ))
                
                self.db.commit()
                return True
        except Exception as e:
            print(f'Error saving fixes: {e}')
            return False
