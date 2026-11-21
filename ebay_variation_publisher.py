"""
eBay Variation Listing Publisher with Transaction Rollback
Publishes products with multiple variations (color, size, length, etc.)

Flow:
1. Load variations from database (variation_manager)
2. Create inventory item for each SKU
3. Create offer for each SKU
4. Create inventory item group (variation spec)
5. Publish listing

NEW: Automatic rollback on failure - deletes all created resources if publish fails

Result: 1 eBay listing with multiple selectable options
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
from variation_manager import VariationManager
from extract_product_aspects import build_product_specific_aspects
from generate_product_description import generate_product_description
import sqlite3
from typing import Dict, List
import time


class VariationListingPublisher:
    """
    Publishes eBay variation listings with automatic rollback on failure
    """
    
    def __init__(self):
        self.ebay = eBayAPIClient()
        self.var_manager = VariationManager()
    
    def _rollback_created_resources(
        self,
        created_skus: List[str],
        created_offers: List[str],
        created_group: str = None
    ):
        """
        Delete all created eBay resources (rollback)
        
        Args:
            created_skus: List of SKU strings
            created_offers: List of offer IDs
            created_group: Group key (if created)
        """
        
        print(f"\n🔄 ROLLING BACK CREATED RESOURCES...")
        print(f"   SKUs to delete: {len(created_skus)}")
        print(f"   Offers to delete: {len(created_offers)}")
        if created_group:
            print(f"   Group to delete: {created_group}")
        
        rollback_results = {
            'skus_deleted': 0,
            'offers_deleted': 0,
            'group_deleted': False,
            'errors': []
        }
        
        # Step 1: Delete inventory item group (if created)
        if created_group:
            try:
                self.ebay._request(
                    'DELETE',
                    self.ebay.inventory_path + '/inventory_item_group/' + created_group
                )
                rollback_results['group_deleted'] = True
                print(f"   ✅ Deleted group: {created_group}")
            except Exception as e:
                error_msg = f"Failed to delete group {created_group}: {str(e)}"
                rollback_results['errors'].append(error_msg)
                print(f"   ⚠️  {error_msg}")
        
        # Step 2: Delete offers (in reverse order)
        for offer_id in reversed(created_offers):
            try:
                self.ebay._request(
                    'DELETE',
                    self.ebay.inventory_path + '/offer/' + offer_id
                )
                rollback_results['offers_deleted'] += 1
                print(f"   ✅ Deleted offer: {offer_id}")
            except Exception as e:
                error_msg = f"Failed to delete offer {offer_id}: {str(e)}"
                rollback_results['errors'].append(error_msg)
                print(f"   ⚠️  {error_msg}")
        
        # Step 3: Delete inventory items (in reverse order)
        for sku in reversed(created_skus):
            try:
                self.ebay._request(
                    'DELETE',
                    self.ebay.inventory_path + '/inventory_item/' + sku
                )
                rollback_results['skus_deleted'] += 1
                print(f"   ✅ Deleted SKU: {sku}")
            except Exception as e:
                error_msg = f"Failed to delete SKU {sku}: {str(e)}"
                rollback_results['errors'].append(error_msg)
                print(f"   ⚠️  {error_msg}")
        
        print(f"\n🔄 ROLLBACK COMPLETE:")
        print(f"   SKUs deleted: {rollback_results['skus_deleted']}/{len(created_skus)}")
        print(f"   Offers deleted: {rollback_results['offers_deleted']}/{len(created_offers)}")
        print(f"   Group deleted: {'Yes' if rollback_results['group_deleted'] else 'No/N/A'}")
        
        if rollback_results['errors']:
            print(f"   ⚠️  {len(rollback_results['errors'])} errors during rollback")
        
        return rollback_results
    
    def publish_variation_listing(
        self,
        product_id: int,
        category_id: str = "43504",
        merchant_location: str = "WAREHOUSE_DE_1"
    ) -> Dict:
        """
        Publish variation listing to eBay with automatic rollback on failure
        
        Args:
            product_id: Database product ID
            category_id: eBay category
            merchant_location: Fulfillment location
        
        Returns:
            {
                'success': bool,
                'listing_id': str,
                'group_key': str,
                'skus_created': int,
                'offers_created': int,
                'rollback': dict (if failed)
            }
        """
        
        print(f"\n{'='*70}")
        print(f"🎨 PUBLISHING VARIATION LISTING - PRODUCT {product_id}")
        print(f"{'='*70}")
        
        # Track created resources for rollback
        created_skus = []
        created_offers = []
        created_group = None
        
        # Get product data
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            columns = [desc[0] for desc in cursor.description]
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return {'success': False, 'error': 'Product not found'}
            
            product = dict(zip(columns, result))
            
            # Check if variation product
            if not product.get('is_variation_product'):
                conn.close()
                return {'success': False, 'error': 'Product is not marked as variation product'}
            
            # Get variations
            variations = self.var_manager.get_variations(product_id)
            
            if not variations:
                conn.close()
                return {'success': False, 'error': 'No variations found'}
        
            print(f"\n📦 PRODUCT:")
            print(f"   Title: {product['title'][:60]}")
            print(f"   Variations: {len(variations)}")
            
            # Analyze dimensions
            analysis = self.var_manager.analyze_variation_dimensions(product_id)
            
            print(f"\n📊 VARIATION ANALYSIS:")
            print(f"   Dimensions: {analysis['dimensions']}")
            for dim, values in analysis['values'].items():
                print(f"   {dim}: {values}")
            
            # Generate group key
            group_key = f"VAR-{product_id}-{int(time.time())}"
            
            # Build base aspects
            template_aspects = {
                'Produktart': ['Organizer'],
                'Marke': ['Markenlos'],
                'Zustand': ['Neu']
            }
            
            aspects = build_product_specific_aspects(
                product['title'],
                template_aspects
            )
            
            # Generate description
            produktart = aspects.get('Produktart', ['Organizer'])[0]
            zimmer = aspects.get('Zimmer', ['Universell'])[0]
            kapazitaet = aspects.get('Kapazität', ['Siehe Beschreibung'])[0]
            besonderheiten = aspects.get('Besonderheiten', ['Praktisch'])[0]
            
            description = generate_product_description(
                product['title'],
                produktart,
                zimmer,
                kapazitaet,
                besonderheiten
            )
            
            print(f"\n1️⃣ CREATING INVENTORY ITEMS...")
            
            # Get product images for fallback
            product_images = []
            if product.get('image_url'):
                product_images = [product['image_url']]
            
            for i, var in enumerate(variations, 1):
                # Build variation-specific title
                var_title = product['title']
                if var.get('variation_name'):
                    var_title += f" - {var['variation_name']}"
                
                # Get images (variation-specific or product default)
                var_images = []
                if var.get('image_url'):
                    var_images = [var['image_url']]
                elif product_images:
                    var_images = product_images
                
                # eBay requires at least 1 image
                if not var_images:
                    print(f"   ⚠️  Variation {var['sku']} has no images - skipping")
                    continue
                
                # Build variation-specific aspects
                var_aspects = dict(aspects)  # Copy base aspects
                
                # Add variation dimensions (use ENGLISH names for eBay!)
                if var.get('color'):
                    var_aspects['Color'] = [var['color']]
                if var.get('length'):
                    var_aspects['Length'] = [var['length']]
                if var.get('size'):
                    var_aspects['Size'] = [var['size']]
                if var.get('material'):
                    var_aspects['Material'] = [var['material']]
                
                MAX_LISTED_QUANTITY = 20  # safety cap: uncapped variant stock (e.g. raw
                    # AliExpress stock of hundreds) multiplied by price across many
                    # variants can exceed eBay's monthly selling limit in a single
                    # listing — confirmed real incident (2026-11-20, product ID107).
                safe_qty = min(var.get('stock', 10) or 10, MAX_LISTED_QUANTITY)
                inventory_data = {
                    'product': {
                        'title': var_title[:80],
                        'aspects': var_aspects,
                        'description': description,
                        'imageUrls': var_images
                    },
                    'condition': 'NEW',
                    'availability': {
                        'shipToLocationAvailability': {
                            'quantity': safe_qty
                        }
                    },
                    # Without packageWeightAndSize eBay's International Shipping
                    # Program assumes a worst-case heavy/large package and quotes
                    # shipping cost higher than the item price itself (confirmed
                    # live incident 2026-11-20). No per-variant verified dims flow
                    # through this path yet, so use the same conservative generic
                    # fallback as the single-SKU path (orchestra step_7).
                    'packageWeightAndSize': {
                        'packageType': 'PACKAGE_THICK_ENVELOPE',
                        'weight': {'value': 300, 'unit': 'GRAM'}
                    }
                }
                
                # API call: PUT /inventory_item/{sku}
                self.ebay._request(
                    'PUT',
                    self.ebay.inventory_path + '/inventory_item/' + var['sku'],
                    json=inventory_data
                )
                
                created_skus.append(var['sku'])
                print(f"   {i}. {var['sku']} - {var.get('variation_name', 'N/A')}")
            
            print(f"   ✅ {len(created_skus)} inventory items created")
            
            # Step 2: Create offers
            print(f"\n2️⃣ CREATING OFFERS...")
            
            for i, var in enumerate(variations, 1):
                # Skip if SKU was not created
                if var['sku'] not in created_skus:
                    continue
                
                offer_data = {
                    'sku': var['sku'],
                    'marketplaceId': 'EBAY_DE',
                    'format': 'FIXED_PRICE',
                    'listingDuration': 'GTC',
                    'categoryId': category_id,
                    'merchantLocationKey': merchant_location,
                    'listingPolicies': {
                        'fulfillmentPolicyId': '263035514017',
                        'paymentPolicyId': '263035507017',
                        'returnPolicyId': '269022691017'  # 2026-11-20: switched from
                            # 263035512017 — eBay froze that policy's buyer-facing
                            # display at "Keine Rückgabe" even though its own terms
                            # said returnsAccepted=true; a fresh policy ID forced a
                            # correct resync. Never revert to the old ID.
                    },
                    'pricingSummary': {
                        'price': {
                            'value': str(var['sell_price']),
                            'currency': 'EUR'
                        }
                    }
                }
                
                # API call: POST /offer
                offer_response = self.ebay._request(
                    'POST',
                    self.ebay.inventory_path + '/offer',
                    json=offer_data
                )
                
                offer_id = offer_response.get('offerId')
                created_offers.append(offer_id)
                
                # Update database
                cursor.execute('''
                    UPDATE product_variations
                    SET ebay_offer_id = ?
                    WHERE sku = ?
                ''', (offer_id, var['sku']))
                
                print(f"   {i}. {var['sku']} → {offer_id}")
            
            conn.commit()
            
            print(f"   ✅ {len(created_offers)} offers created")
            
            # Step 3: Create inventory item group
            print(f"\n3️⃣ CREATING INVENTORY ITEM GROUP...")
            
            # Build variesBy specifications
            varies_by_specs = []
            
            for dim in analysis['dimensions']:
                varies_by_specs.append({
                    'name': dim,
                    'values': analysis['values'][dim]
                })
            
            group_data = {
                'title': product['title'][:80],
                'description': description,
                'aspects': aspects,
                'imageUrls': [product.get('image_url')] if product.get('image_url') else [],
                'variantSKUs': created_skus,
                'variesBy': {
                    'specifications': varies_by_specs
                }
            }
            
            # API call: PUT /inventory_item_group/{key}
            self.ebay.create_inventory_item_group(group_key, group_data)
            created_group = group_key  # Track for rollback
            
            print(f"   ✅ Group created: {group_key}")
            print(f"   Specifications: {varies_by_specs}")
            
            # Step 4: Publish (THE RISKY PART - wrap in try-except for rollback)
            print(f"\n4️⃣ PUBLISHING LISTING...")
            
            try:
                # API call: POST /offer/publish_by_inventory_item_group
                publish_result = self.ebay.publish_offer_by_inventory_item_group(group_key)
                listing_id = publish_result.get('listing_id')
                
            except Exception as publish_error:
                # Publish failed - trigger rollback
                print(f"\n❌ PUBLISH FAILED: {publish_error}")
                
                rollback_result = self._rollback_created_resources(
                    created_skus,
                    created_offers,
                    created_group
                )
                
                conn.close()
                
                return {
                    'success': False,
                    'error': f'Publish failed: {str(publish_error)}',
                    'rollback': rollback_result
                }
            
            # Publish succeeded - update database
            cursor.execute('''
                UPDATE products
                SET 
                    ebay_item_id = ?,
                    is_listed = 1,
                    variation_group_id = ?
                WHERE id = ?
            ''', (listing_id, group_key, product_id))
            
            conn.commit()
            conn.close()
            
            print(f"   ✅ Published: {listing_id}")
            print(f"   Link: https://www.ebay.de/itm/{listing_id}")
            
            if publish_result.get('warnings'):
                print(f"\n⚠️  Warnings:")
                for warning in publish_result['warnings']:
                    print(f"   - {warning}")
            
            print(f"\n{'='*70}")
            print(f"🎉 SUCCESS - VARIATION LISTING PUBLISHED!")
            print(f"{'='*70}")
            print(f"   Listing ID: {listing_id}")
            print(f"   Group Key: {group_key}")
            print(f"   SKUs: {len(created_skus)}")
            print(f"   Offers: {len(created_offers)}")
            print(f"   Variations: {len(variations)}")
            
            return {
                'success': True,
                'listing_id': listing_id,
                'group_key': group_key,
                'skus_created': len(created_skus),
                'offers_created': len(created_offers)
            }
        
        except Exception as e:
            # Unexpected error during Steps 1-3 - trigger rollback
            print(f"\n❌ UNEXPECTED ERROR: {e}")
            
            rollback_result = self._rollback_created_resources(
                created_skus,
                created_offers,
                created_group
            )
            
            conn.close()
            
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'rollback': rollback_result
            }


# CLI usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ebay_variation_publisher.py <product_id>")
        sys.exit(1)
    
    product_id = int(sys.argv[1])
    
    publisher = VariationListingPublisher()
    result = publisher.publish_variation_listing(product_id)
    
    if not result['success']:
        print(f"\n❌ ERROR: {result.get('error', 'Unknown error')}")
        if 'rollback' in result:
            print(f"🔄 Rollback performed: {result['rollback']}")
        sys.exit(1)
    
    sys.exit(0)
