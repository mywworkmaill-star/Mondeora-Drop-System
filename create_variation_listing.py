"""
eBay Variation Listings Implementation
Creates one listing with multiple SKUs (color, size, length variations)

API Flow:
1. createOrReplaceInventoryItem (for each SKU)
2. createOffer (for each SKU)
3. createOrReplaceInventoryItemGroup (define variations)
4. publishOfferByInventoryItemGroup (publish listing)

Example: Kabel-Organizer
- Schwarz, 1m → €19.99 (SKU-1)
- Schwarz, 2m → €24.99 (SKU-2)
- Weiß, 1m → €19.99 (SKU-3)
- Weiß, 2m → €24.99 (SKU-4)
→ 1 eBay listing with 4 selectable options
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient
from api.aliexpress_client import AliExpressAPIClient
import sqlite3
import json
import time
from typing import Dict, List


class eBayVariationListingManager:
    """
    Manages eBay variation (multi-SKU) listings
    """
    
    def __init__(self):
        self.ebay = eBayAPIClient()
        self.ali = AliExpressAPIClient()
    
    def get_aliexpress_variations(self, aliexpress_product_id: str) -> List[Dict]:
        """
        Get all variations/SKUs from AliExpress product
        
        Returns:
            [
                {
                    'sku_id': '12000035196348614',
                    'properties': [{'name': 'Color', 'value': 'Black'}],
                    'price': 18.25,
                    'stock': 100,
                    'image': 'https://...'
                },
                ...
            ]
        """
        try:
            product = self.ali.get_product_details(aliexpress_product_id)
            
            if not product:
                print("   ❌ Product not found")
                return []
            
            skus = product.get('skus', [])
            
            if not skus:
                print("   ⚠️ No SKUs found (single-variation product)")
                return []
            
            # Parse SKUs
            variations = []
            
            for sku in skus:
                sku_id = sku.get('sku_id', '')
                price = sku.get('sku_price', 0)
                stock = sku.get('sku_available_stock', 0)
                image = sku.get('sku_image', '')
                
                # Get properties (color, size, length, etc)
                props = []
                for prop in sku.get('sku_property_values', []):
                    prop_name = prop.get('property_value_definition_name', '')
                    sku_value = prop.get('sku_property_value', '')
                    
                    if prop_name and sku_value:
                        props.append({
                            'name': prop_name,
                            'value': sku_value
                        })
                
                variations.append({
                    'sku_id': sku_id,
                    'properties': props,
                    'price': price,
                    'stock': stock,
                    'image': image
                })
            
            print(f"   ✅ Found {len(variations)} variations")
            return variations
            
        except Exception as e:
            print(f"   ❌ Error getting variations: {e}")
            return []
    
    def analyze_variation_dimensions(self, variations: List[Dict]) -> Dict:
        """
        Analyze variation properties to determine pivoting aspects
        
        Example:
            Input: [
                {'properties': [{'name': 'Color', 'value': 'Black'}]},
                {'properties': [{'name': 'Color', 'value': 'White'}]}
            ]
            Output: {
                'dimensions': ['Color'],
                'values': {
                    'Color': ['Black', 'White']
                }
            }
        """
        dimension_values = {}
        
        for variation in variations:
            for prop in variation.get('properties', []):
                prop_name = prop['name']
                prop_value = prop['value']
                
                if prop_name not in dimension_values:
                    dimension_values[prop_name] = set()
                
                dimension_values[prop_name].add(prop_value)
        
        # Convert sets to sorted lists
        result = {
            'dimensions': list(dimension_values.keys()),
            'values': {k: sorted(list(v)) for k, v in dimension_values.items()}
        }
        
        return result
    
    def create_variation_listing(
        self,
        product_id: int,
        base_title: str,
        variations: List[Dict],
        category_id: str = "43504",
        description: str = "",
        aspects: Dict = None
    ) -> Dict:
        """
        Create eBay variation listing
        
        Steps:
        1. Create inventory items (one per SKU)
        2. Create offers (one per SKU)
        3. Create inventory item group (defines variations)
        4. Publish listing
        
        Returns:
            {
                'success': bool,
                'listing_id': str,
                'sku_count': int
            }
        """
        
        print(f"\n📦 CREATING VARIATION LISTING")
        print(f"   Product ID: {product_id}")
        print(f"   Variations: {len(variations)}")
        
        # Analyze variation dimensions
        analysis = self.analyze_variation_dimensions(variations)
        
        print(f"\n📊 VARIATION ANALYSIS:")
        print(f"   Dimensions: {analysis['dimensions']}")
        for dim, values in analysis['values'].items():
            print(f"   {dim}: {values[:5]}{'...' if len(values) > 5 else ''}")
        
        # Generate group ID
        group_id = f"VAR-{product_id}-{int(time.time())}"
        
        # Step 1: Create inventory items
        print(f"\n1️⃣ CREATING INVENTORY ITEMS...")
        
        variant_skus = []
        
        for i, variation in enumerate(variations):
            sku = f"{group_id}-SKU-{i}"
            variant_skus.append(sku)
            
            # Build variation-specific title
            var_title = base_title
            for prop in variation['properties']:
                var_title += f" {prop['value']}"
            
            inventory_item = {
                "product": {
                    "title": var_title[:80],
                    "aspects": aspects or {},
                    "description": description,
                    "imageUrls": [variation['image']] if variation['image'] else []
                },
                "condition": "NEW",
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": int(variation['stock']) if variation['stock'] else 10
                    }
                }
            }
            
            # TODO: Call eBay createOrReplaceInventoryItem API
            # self.ebay.create_inventory_item(sku, inventory_item)
            
            print(f"   {i+1}. SKU: {sku}")
        
        print(f"   ✅ {len(variant_skus)} inventory items created")
        
        # Step 2: Create offers
        print(f"\n2️⃣ CREATING OFFERS...")
        
        for i, (sku, variation) in enumerate(zip(variant_skus, variations)):
            offer = {
                "sku": sku,
                "marketplaceId": "EBAY_DE",
                "format": "FIXED_PRICE",
                "listingDuration": "GTC",
                "categoryId": category_id,
                "pricingSummary": {
                    "price": {
                        "value": str(variation['price'] * 2.5),  # 2.5x markup
                        "currency": "EUR"
                    }
                },
                "merchantLocationKey": "WAREHOUSE_DE_1"
            }
            
            # TODO: Call eBay createOffer API
            # self.ebay.create_offer(offer)
            
            print(f"   {i+1}. Offer: {sku} - €{variation['price'] * 2.5:.2f}")
        
        print(f"   ✅ {len(variant_skus)} offers created")
        
        # Step 3: Create inventory item group
        print(f"\n3️⃣ CREATING INVENTORY ITEM GROUP...")
        
        # Build variesBy specifications
        varies_by_specs = []
        
        for dim in analysis['dimensions']:
            varies_by_specs.append({
                "name": dim,
                "values": analysis['values'][dim]
            })
        
        item_group = {
            "aspects": aspects or {},
            "title": base_title[:80],
            "description": description,
            "variantSKUs": variant_skus,
            "variesBy": {
                "specifications": varies_by_specs
            }
        }
        
        # TODO: Call eBay createOrReplaceInventoryItemGroup API
        # self.ebay.create_inventory_item_group(group_id, item_group)
        
        print(f"   ✅ Group created: {group_id}")
        
        # Step 4: Publish
        print(f"\n4️⃣ PUBLISHING LISTING...")
        
        # TODO: Call eBay publishOfferByInventoryItemGroup API
        # listing_id = self.ebay.publish_inventory_item_group(group_id)
        
        listing_id = "SIMULATED-" + group_id
        
        print(f"   ✅ Published: {listing_id}")
        
        return {
            'success': True,
            'listing_id': listing_id,
            'group_id': group_id,
            'sku_count': len(variant_skus)
        }


# Test
if __name__ == "__main__":
    print("🧪 TESTING VARIATION LISTING SYSTEM")
    print("=" * 70)
    
    manager = eBayVariationListingManager()
    
    # Test with ID 48 (Toocki Kabel-Organizer - 10 variants)
    test_product_id = 48
    ali_product_id = "1005005193534554"
    
    print(f"\n📦 Product: ID {test_product_id}")
    print(f"   AliExpress: {ali_product_id}")
    
    # Get variations from AliExpress
    variations = manager.get_aliexpress_variations(ali_product_id)
    
    if not variations:
        print("\n⚠️ No variations found - this is a single-variation product")
        print("   Use standard listing instead")
    else:
        # Analyze
        analysis = manager.analyze_variation_dimensions(variations)
        
        print(f"\n✅ VARIATION SYSTEM READY")
        print(f"   Dimensions: {len(analysis['dimensions'])}")
        print(f"   Total combinations: {len(variations)}")
        
        # Simulate creation (TODO: integrate with real eBay API)
        # result = manager.create_variation_listing(
        #     product_id=test_product_id,
        #     base_title="Toocki Kabel-Organizer",
        #     variations=variations,
        #     description="Test description",
        #     aspects={}
        # )
