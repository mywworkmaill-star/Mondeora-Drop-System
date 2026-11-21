#!/usr/bin/env python3
"""
AliExpress Variation Scraper - PRODUCTION VERSION
Extracts product variants from AliExpress product pages via CDP Network Monitoring
"""

from playwright.sync_api import sync_playwright
import json
import re
import time

def extract_variants_from_network(product_url: str, timeout_seconds: int = 30):
    """
    Extract product variants by monitoring network requests
    Captures mtop.aliexpress.pdp.pc.query JSONP response
    
    Args:
        product_url: AliExpress product URL (e.g., https://www.aliexpress.com/item/1005005193534554.html)
        timeout_seconds: Max time to wait for page load
    
    Returns:
        dict: Raw JSON data from AliExpress API or None if failed
    """
    
    print("🚀 Starting Playwright with Network Monitoring...")
    
    captured_data = None
    
    def handle_response(response):
        """Capture JSONP responses containing variant data"""
        nonlocal captured_data
        
        # Check if this is the product details API call
        if 'mtop.aliexpress.pdp.pc.query' in response.url:
            try:
                # Get response text
                body = response.text()
                
                # Try to extract JSON from JSONP
                # Format: mtop_jsonp_1(...JSON...)
                json_match = re.search(r'mtop[^(]*\((.*)\)', body)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                    
                    # Verify it has the data structure we need
                    if 'data' in data and 'result' in data['data']:
                        captured_data = data
                        print(f"✅ Captured product data from: {response.url[:80]}...")
                
            except Exception as e:
                # Silently ignore parse errors (some responses are not relevant)
                pass
    
    with sync_playwright() as p:
        # Launch browser with stealth settings
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context with realistic settings
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='de-DE',
            timezone_id='Europe/Berlin',
            extra_http_headers={
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
        )
        
        # Remove webdriver flag
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        
        # Listen for responses
        page.on('response', handle_response)
        
        print(f"📄 Opening: {product_url}")
        
        try:
            # Navigate with domcontentloaded (faster than networkidle)
            page.goto(product_url, wait_until='domcontentloaded', timeout=timeout_seconds * 1000)
            
            print(f"✅ Page loaded, waiting for API response...")
            
            # Wait for data to be captured (up to 10 seconds)
            for i in range(10):
                if captured_data:
                    break
                time.sleep(1)
            
            if captured_data:
                print(f"✅ Variant data captured successfully!")
            else:
                print("⚠️  No variant data captured - page may have bot detection")
            
        except Exception as e:
            print(f"⚠️  Navigation error: {e}")
        
        finally:
            browser.close()
    
    return captured_data

def parse_variants(data):
    """
    Parse variant information from captured AliExpress data
    
    Args:
        data: Raw JSON data from AliExpress API
    
    Returns:
        dict: Parsed variants with structure:
            {
                'dimensions': {
                    'Color': {'id': 14, 'values': [...]},
                    'Ships From': {'id': 200007763, 'values': [...]}
                },
                'variants': [
                    {
                        'sku_id': '12000035196348614',
                        'properties': {'Color': 'Red 5M'},
                        'price': 2.44,
                        'stock': 1,
                        'image': 'https://...'
                    },
                    ...
                ]
            }
    """
    
    if not data or 'data' not in data:
        print("❌ Invalid data structure")
        return None
    
    try:
        result = data.get('data', {}).get('result', {})
        
        # Get SKU module
        sku_module = result.get('SKU', {})
        if not sku_module:
            print("❌ No SKU module found")
            return None
        
        # Get PRICE module
        price_module = result.get('PRICE', {})
        price_map = price_module.get('skuPriceInfoMap', {})
        
        # Get IMAGE module
        image_module = result.get('HEADER_IMAGE_PC', {})
        sku_images_map = image_module.get('skuImagesMap', {})
        
        # Get QUANTITY module
        quantity_module = result.get('QUANTITY_PC', {})
        sku_quantity_map = quantity_module.get('allSkuQuantityView', {})
        
        # Extract dimension definitions
        sku_properties = sku_module.get('skuProperties', [])
        dimensions = {}
        
        for prop in sku_properties:
            prop_id = prop.get('skuPropertyId')
            prop_name = prop.get('skuPropertyName')
            
            if prop_name and prop_id:
                # Get property values from skuPropertyValues if exists
                prop_values = prop.get('skuPropertyValues', [])
                values_list = []
                
                for val in prop_values:
                    values_list.append({
                        'id': val.get('propertyValueId'),
                        'name': val.get('propertyValueDisplayName'),
                        'image': val.get('skuPropertyImagePath')
                    })
                
                dimensions[prop_name] = {
                    'id': prop_id,
                    'values': values_list
                }
        
        print(f"📊 Found {len(dimensions)} dimension(s)")
        
        # Extract variants
        sku_paths = sku_module.get('skuPaths', [])
        variants = []
        
        for sku_path in sku_paths:
            sku_id_str = str(sku_path.get('skuId', ''))
            sku_attr = sku_path.get('skuAttr', '')
            sku_stock = sku_path.get('skuStock', 0)
            salable = sku_path.get('salable', False)
            
            # Parse properties from skuAttr (e.g., "14:366#Red 5M")
            properties = {}
            if '#' in sku_attr:
                parts = sku_attr.split('#')
                if len(parts) == 2:
                    prop_path, prop_value = parts
                    # Find dimension name from prop_path
                    if ':' in prop_path:
                        prop_id = prop_path.split(':')[0]
                        # Match with dimensions
                        for dim_name, dim_data in dimensions.items():
                            if str(dim_data['id']) == prop_id:
                                properties[dim_name] = prop_value
                                break
                    else:
                        # Fallback: use attr as-is
                        properties['Variant'] = prop_value
            
            # Get price
            price = None
            if sku_id_str in price_map:
                price_info = price_map[sku_id_str]
                price_str = price_info.get('salePriceString', '')
                # Extract number from price string (e.g., "2,44€" → 2.44)
                price_match = re.search(r'([\d,\.]+)', price_str)
                if price_match:
                    price_text = price_match.group(1).replace(',', '.')
                    try:
                        price = float(price_text)
                    except:
                        pass
            
            # Get image
            image = None
            if sku_id_str in sku_images_map:
                images_list = sku_images_map[sku_id_str]
                if images_list and len(images_list) > 0:
                    image = images_list[0]
            
            # Get accurate stock from quantity module
            stock = sku_stock  # Default from skuPath
            if sku_id_str in sku_quantity_map:
                quantity_info = sku_quantity_map[sku_id_str]
                max_buy_count = quantity_info.get('maxBuyCount')
                if max_buy_count is not None:
                    stock = max_buy_count
            
            variants.append({
                'sku_id': sku_id_str,
                'properties': properties,
                'price': price,
                'stock': stock,
                'salable': salable,
                'image': image
            })
        
        print(f"🎯 Extracted {len(variants)} variant(s)")
        
        return {
            'dimensions': dimensions,
            'variants': variants
        }
        
    except Exception as e:
        print(f"❌ Parse error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_extraction():
    """Test extraction on product ID 1005005193534554"""
    
    product_url = "https://www.aliexpress.com/item/1005005193534554.html"
    
    print("="*70)
    print("🧪 TESTING ALIEXPRESS VARIANT EXTRACTION v2")
    print("="*70)
    
    # Extract raw data
    raw_data = extract_variants_from_network(product_url)
    
    if raw_data:
        # Save raw data for inspection
        with open('debug_aliexpress_raw_v2.json', 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Raw data saved to debug_aliexpress_raw_v2.json")
        
        # Parse variants
        result = parse_variants(raw_data)
        
        if result:
            print("\n" + "="*70)
            print("📊 EXTRACTION RESULTS:")
            print("="*70)
            
            print(f"\n🎨 DIMENSIONS ({len(result['dimensions'])} total):")
            for dim_name, dim_data in result['dimensions'].items():
                print(f"  - {dim_name} (ID: {dim_data['id']}): {len(dim_data['values'])} values")
                if dim_data['values']:
                    for val in dim_data['values'][:3]:  # Show first 3
                        print(f"    • {val['name']}")
                    if len(dim_data['values']) > 3:
                        print(f"    ... and {len(dim_data['values']) - 3} more")
            
            print(f"\n🎯 VARIANTS ({len(result['variants'])} total):")
            for i, var in enumerate(result['variants'][:20], 1):  # Show first 20
                props_str = ', '.join([f"{k}: {v}" for k, v in var['properties'].items()])
                price_str = f"€{var['price']:.2f}" if var['price'] else "N/A"
                salable_str = "✅" if var['salable'] else "❌"
                print(f"  {i}. {props_str} → {price_str} | Stock: {var['stock']} | Salable: {salable_str}")
            
            if len(result['variants']) > 20:
                print(f"  ... and {len(result['variants']) - 20} more variants")
            
            # Save parsed result
            with open('debug_aliexpress_parsed_v2.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Parsed data saved to debug_aliexpress_parsed_v2.json")
            
            print("\n✅ EXTRACTION COMPLETE!")
            return result
        
    else:
        print("\n❌ EXTRACTION FAILED - No data captured")
        print("   Possible causes:")
        print("   - AliExpress bot detection")
        print("   - Network timeout")
        print("   - Product page structure changed")
        return None

if __name__ == "__main__":
    test_extraction()
