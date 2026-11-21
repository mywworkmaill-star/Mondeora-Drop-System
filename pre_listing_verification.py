"""
ORCHESTRA v5.1 - PRE-LISTING ALIEXPRESS VERIFICATION
Before publishing, fetch and verify ALL product details from AliExpress
"""

import sys
sys.path.insert(0, 'src')

from api.aliexpress_client import AliExpressAPIClient

def verify_aliexpress_product(ali_product_id):
    """
    Fetch complete product details from AliExpress BEFORE listing.
    
    Returns dict with verified data:
    - color (actual color from SKU)
    - material (from title/description parsing)
    - size/dimensions (from properties)
    - variants (all available SKUs)
    - images (all variant images)
    - price (current sale price)
    - stock (availability)
    """
    
    ali = AliExpressAPIClient()
    
    print("=" * 80)
    print("🔍 PRE-LISTING ALIEXPRESS VERIFICATION")
    print("=" * 80)
    print(f"Product ID: {ali_product_id}")
    print()
    
    try:
        # Get full product details
        details = ali.get_product_details(ali_product_id)
        
        if not details:
            return None
        
        # Extract verified data
        verified = {
            'title': details.get('product_title', ''),
            'price': details.get('sale_price', 0),
            'stock': details.get('warehouse_count', 0),
            'images': [],
            'color': None,
            'variants': [],
            'properties': {}
        }
        
        # Parse images
        image_urls = details.get('image_urls', '')
        if image_urls:
            verified['images'] = [img.strip() for img in image_urls.split(';') if img.strip()]
        
        # Parse SKUs/Variants
        sku_infos = details.get('ae_item_sku_info_dtos', {}).get('ae_item_sku_info_d_t_o', [])
        
        for sku_info in sku_infos:
            sku_id = sku_info.get('sku_id', '')
            sku_price = sku_info.get('offer_sale_price', 0)
            sku_stock = sku_info.get('sku_available_stock', 0)
            
            variant = {
                'sku_id': sku_id,
                'price': float(sku_price) if sku_price else 0,
                'stock': sku_stock,
                'properties': {}
            }
            
            # Parse properties (color, size, etc.)
            props = sku_info.get('ae_sku_property_dtos', {}).get('ae_sku_property_d_t_o', [])
            
            for prop in props:
                prop_name = prop.get('sku_property_name', '')  # e.g., "Farbe", "Größe"
                prop_value = prop.get('property_value_definition_name', '')  # e.g., "Black", "Large"
                prop_image = prop.get('sku_image', '')
                
                variant['properties'][prop_name] = {
                    'value': prop_value,
                    'image': prop_image
                }
                
                # Extract main color (first SKU's color)
                if prop_name.lower() in ['farbe', 'color', 'colour'] and not verified['color']:
                    verified['color'] = prop_value
                    
                    # Add variant image to main images if not already there
                    if prop_image and prop_image not in verified['images']:
                        verified['images'].append(prop_image)
            
            verified['variants'].append(variant)
        
        # Print verification result
        print("✅ VERIFICATION RESULTS:")
        print("=" * 80)
        print(f"Title: {verified['title'][:70]}...")
        print(f"Price: €{verified['price']}")
        print(f"Stock: {verified['stock']} available")
        print(f"Images: {len(verified['images'])} found")
        print(f"Color: {verified['color'] or 'NOT FOUND'}")
        print(f"Variants: {len(verified['variants'])} SKU(s)")
        print()
        
        if verified['variants']:
            print("VARIANT DETAILS:")
            for i, var in enumerate(verified['variants'], 1):
                print(f"\nVariant {i}:")
                print(f"  SKU ID: {var['sku_id']}")
                print(f"  Price: €{var['price']}")
                print(f"  Stock: {var['stock']}")
                if var['properties']:
                    print(f"  Properties:")
                    for k, v in var['properties'].items():
                        print(f"    • {k}: {v['value']}")
        
        return verified
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    # Test with ID 137
    test_id = "1005010494395563"
    result = verify_aliexpress_product(test_id)
    
    if result:
        print()
        print("=" * 80)
        print("✅ PRE-LISTING VERIFICATION COMPLETED")
        print("=" * 80)
        print()
        print("🎯 KEY FINDINGS:")
        print(f"  Color: {result['color']} (USE THIS, NOT 'Mehrfarbig'!)")
        print(f"  Images: {len(result['images'])} (ALL available)")
        print(f"  Variants: {len(result['variants'])} SKU(s)")
        print()
        print("💡 RECOMMENDATION:")
        print("  • Use verified color in eBay listing")
        print("  • Include all variant images")
        print("  • Set correct price from AliExpress")
        print("  • Check stock before publishing")
