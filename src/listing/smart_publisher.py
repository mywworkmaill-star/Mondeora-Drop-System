"""
Smart eBay Publisher
Integrates validation, auto-fix, and retry logic
"""

import sys
sys.path.insert(0, 'src')

from src.validators.ebay_listing_validator import eBayListingValidator
from src.validators.ebay_error_parser import eBayErrorParser
from src.validators.auto_fix_engine import AutoFixEngine
import json


class SmarteBayPublisher:
    """
    Smart eBay publisher with validation and auto-fix
    
    Features:
    - Pre-flight validation
    - Auto-fix common issues
    - Parse eBay errors
    - Retry with fixes
    - Detailed logging
    """
    
    def __init__(self, ebay_client, db_conn=None):
        self.ebay = ebay_client
        self.db = db_conn
        self.validator = eBayListingValidator()
        self.parser = eBayErrorParser()
        self.fixer = AutoFixEngine(db_conn)
    
    def publish_product(self, product_id):
        """
        Smart publish with full validation and auto-fix
        
        Args:
            product_id: Database product ID
            
        Returns:
            {
                'success': bool,
                'listing_id': str (if success),
                'offer_id': str (if success),
                'stage': str,
                'validation_score': int,
                'fixes_applied': list,
                'errors': list
            }
        """
        
        print('🚀 SMART EBAY PUBLISHER')
        print('=' * 80)
        print(f'Product ID: {product_id}')
        print()
        
        # STAGE 1: Get product from database
        print('Stage 1: Loading product...')
        product = self._get_product(product_id)
        
        if not product:
            return {
                'success': False,
                'stage': 'load',
                'error': 'Product not found in database'
            }
        
        print(f'✅ Loaded: {product["title"][:60]}')
        print()
        
        # STAGE 2: Pre-flight validation
        print('Stage 2: Pre-flight validation...')
        validation = self.validator.validate(product)
        
        print(f'   Score: {validation["score"]}/100')
        
        if validation['errors']:
            print(f'   ❌ {len(validation["errors"])} error(s):')
            for err in validation['errors'][:3]:
                print(f'      - {err}')
        
        if validation['warnings']:
            print(f'   ⚠️  {len(validation["warnings"])} warning(s)')
        
        print()
        
        all_fixes = []
        
        # STAGE 3: Apply validation fixes
        if validation['fixes']:
            print('Stage 3: Applying validation fixes...')
            fix_result = self.fixer.apply_validation_fixes(product, validation)
            
            if fix_result['fixed']:
                for change in fix_result['changes']:
                    print(f'   ✅ Fixed {change["field"]}')
                    all_fixes.append(change)
                
                product = fix_result['product']
                
                # Re-validate
                validation = self.validator.validate(product)
                print(f'   New score: {validation["score"]}/100')
            
            print()
        
        # STAGE 4: Auto-enrich if needed
        if validation['score'] < 80:
            print('Stage 4: Auto-enrichment...')
            enrich_result = self.fixer.auto_enrich_product(product)
            
            if enrich_result['enriched']:
                for change in enrich_result['changes']:
                    print(f'   ✅ {change}')
                    all_fixes.append({'change': change})
                
                product = enrich_result['product']
                
                # Re-validate
                validation = self.validator.validate(product)
                print(f'   Final score: {validation["score"]}/100')
            
            print()
        
        # Check if still invalid
        if not validation['valid']:
            print('❌ Product still invalid after fixes!')
            print()
            print('Remaining errors:')
            for err in validation['errors']:
                print(f'   - {err}')
            
            return {
                'success': False,
                'stage': 'validation',
                'validation_score': validation['score'],
                'errors': validation['errors'],
                'fixes_applied': all_fixes
            }
        
        # STAGE 5: Prepare eBay data
        print('Stage 5: Preparing eBay data...')
        inventory_data, offer_data = self._prepare_ebay_data(product)
        print('✅ Data prepared')
        print()
        
        # STAGE 6: Create inventory item
        print('Stage 6: Creating inventory item...')
        sku = f'AE{product["aliexpress_product_id"]}'
        
        try:
            self.ebay._request('PUT', 
                f'/sell/inventory/v1/inventory_item/{sku}',
                json=inventory_data)
            print('✅ Inventory item created')
            print()
            
        except Exception as e:
            print(f'❌ Error: {str(e)[:100]}')
            
            # Parse error
            error_info = self.parser.parse(str(e), 400)
            print()
            print(self.parser.format_error_report(error_info))
            print()
            
            if error_info.get('auto_fixable'):
                print('Attempting auto-fix...')
                fix_result = self.fixer.apply_error_fix(
                    product, inventory_data, offer_data, error_info)
                
                if fix_result.get('fixed'):
                    print('✅ Applied fixes:')
                    for change in fix_result['changes']:
                        print(f'   - {change}')
                    
                    all_fixes.extend(fix_result['changes'])
                    
                    # Retry
                    print()
                    print('Retrying...')
                    try:
                        self.ebay._request('PUT',
                            f'/sell/inventory/v1/inventory_item/{sku}',
                            json=fix_result['inventory_data'])
                        print('✅ Success after fix!')
                        print()
                    except Exception as e2:
                        print(f'❌ Still failed: {str(e2)[:100]}')
                        return {
                            'success': False,
                            'stage': 'inventory_creation',
                            'error': str(e2)[:200],
                            'fixes_applied': all_fixes
                        }
                else:
                    return {
                        'success': False,
                        'stage': 'inventory_creation',
                        'error': error_info,
                        'fixes_applied': all_fixes
                    }
            else:
                return {
                    'success': False,
                    'stage': 'inventory_creation',
                    'error': error_info,
                    'fixes_applied': all_fixes
                }
        
        # STAGE 7: Create offer
        print('Stage 7: Creating offer...')
        
        try:
            result = self.ebay._request('POST', '/sell/inventory/v1/offer', 
                json=offer_data)
            offer_id = result.get('offerId')
            print(f'✅ Offer created: {offer_id}')
            print()
            
        except Exception as e:
            print(f'❌ Error: {str(e)[:100]}')
            
            # Parse and try to fix
            error_info = self.parser.parse(str(e), 400)
            
            if error_info.get('auto_fixable'):
                fix_result = self.fixer.apply_error_fix(
                    product, inventory_data, offer_data, error_info)
                
                if fix_result.get('fixed'):
                    # Retry
                    try:
                        result = self.ebay._request('POST', '/sell/inventory/v1/offer',
                            json=fix_result['offer_data'])
                        offer_id = result.get('offerId')
                        print(f'✅ Success after fix: {offer_id}')
                        all_fixes.extend(fix_result['changes'])
                    except:
                        return {
                            'success': False,
                            'stage': 'offer_creation',
                            'error': error_info
                        }
            else:
                return {
                    'success': False,
                    'stage': 'offer_creation',
                    'error': error_info
                }
        
        # STAGE 8: Publish offer
        print('Stage 8: Publishing to eBay...')
        
        try:
            result = self.ebay._request('POST',
                f'/sell/inventory/v1/offer/{offer_id}/publish')
            listing_id = result.get('listingId')
            
            print('✅ PUBLISHED!')
            print(f'   eBay Item ID: {listing_id}')
            print(f'   URL: https://www.ebay.de/itm/{listing_id}')
            print()
            
            # Update database
            if self.db:
                self._update_database(product_id, listing_id, offer_id)
                print('✅ Database updated')
            
            print()
            print('=' * 80)
            print('SUCCESS!')
            print('=' * 80)
            print(f'Validation Score: {validation["score"]}/100')
            print(f'Fixes Applied:    {len(all_fixes)}')
            print(f'eBay Item ID:     {listing_id}')
            print('=' * 80)
            
            return {
                'success': True,
                'listing_id': listing_id,
                'offer_id': offer_id,
                'validation_score': validation['score'],
                'fixes_applied': all_fixes
            }
            
        except Exception as e:
            print(f'❌ Publish error: {str(e)[:100]}')
            
            error_info = self.parser.parse(str(e), 400)
            print()
            print(self.parser.format_error_report(error_info))
            
            return {
                'success': False,
                'stage': 'publish',
                'error': error_info,
                'offer_id': offer_id
            }
    
    def _get_product(self, product_id):
        """Get product from database"""
        if not self.db:
            return None
        
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Get column names
        cursor.execute('PRAGMA table_info(products)')
        columns = [col[1] for col in cursor.fetchall()]
        
        return dict(zip(columns, row))
    
    def _prepare_ebay_data(self, product):
        """Prepare inventory and offer data for eBay"""
        
        # Parse images
        images = []
        if product.get('image_url'):
            images = [i.strip() for i in str(product['image_url']).split(',') if i.strip()]
        
        # Parse aspects
        aspects = {}
        if product.get('aspects'):
            try:
                aspects = json.loads(product['aspects']) if isinstance(product['aspects'], str) else product['aspects']
            except:
                pass
        
        # Inventory item
        inventory_data = {
            'product': {
                'title': product['title'],
                'description': product.get('description', 'Produktbeschreibung'),
                'imageUrls': images[:12],
                'aspects': aspects
            },
            'condition': 'NEW',
            'availability': {
                'shipToLocationAvailability': {
                    'quantity': product.get('current_stock') or 100
                }
            }
        }
        
        # Offer
        offer_data = {
            'sku': f'AE{product["aliexpress_product_id"]}',
            'marketplaceId': 'EBAY_DE',
            'format': 'FIXED_PRICE',
            'listingDescription': product.get('description', 'Produktbeschreibung'),
            'listingPolicies': {
                'fulfillmentPolicyId': '263035514017',
                'paymentPolicyId': '263035507017',
                'returnPolicyId': '263035512017'
            },
            'categoryId': product.get('category_id', '43504'),
            'pricingSummary': {
                'price': {
                    'value': str(round(float(product['ebay_price']), 2)),
                    'currency': 'EUR'
                }
            },
            'quantityLimitPerBuyer': 10,
            'merchantLocationKey': 'WAREHOUSE_DE_1'
        }
        
        return inventory_data, offer_data
    
    def _update_database(self, product_id, listing_id, offer_id):
        """Update product in database with eBay IDs"""
        if not self.db:
            return
        
        cursor = self.db.cursor()
        cursor.execute('''
            UPDATE products
            SET ebay_item_id = ?,
                ebay_offer_id = ?,
                is_listed = 1,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (listing_id, offer_id, product_id))
        
        self.db.commit()
