#!/usr/bin/env python3
"""
AliExpress Variation Scraper with CDP Network Monitoring
"""

from playwright.sync_api import sync_playwright
import json
import re
import time

def extract_variants_from_network(product_url: str):
    """
    Extract product variants by monitoring network requests
    Captures mtop.aliexpress.pdp.pc.query JSONP response
    """
    
    print("🚀 Starting Playwright with Network Monitoring...")
    
    captured_data = None
    
    def handle_response(response):
        """Capture JSONP responses containing variant data"""
        nonlocal captured_data
        
        # Check if this is the product details API call
        if 'mtop.aliexpress' in response.url and 'pdp' in response.url:
            try:
                print(f"📡 Captured: {response.url[:100]}...")
                
                # Get response text
                body = response.text()
                
                # Try to extract JSON from JSONP
                # Format: mtop_jsonp_1(...JSON...)
                json_match = re.search(r'mtop[^(]*\((.*)\)', body)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                    
                    # Look for SKU data
                    if 'data' in data:
                        captured_data = data
                        print(f"✅ Captured product data!")
                
            except Exception as e:
                print(f"⚠️  Failed to parse response: {e}")
    
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
            # Navigate with shorter timeout and domcontentloaded
            page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
            
            print(f"✅ Page loaded, waiting for network responses...")
            
            # Wait for data to be captured (up to 10 seconds)
            for i in range(10):
                if captured_data:
                    break
                time.sleep(1)
                print(f"⏳ Waiting... ({i+1}/10)")
            
            if not captured_data:
                print("❌ No variant data captured from network")
                # Try to scroll and trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)
            
        except Exception as e:
            print(f"⚠️  Navigation error: {e}")
        
        finally:
            browser.close()
    
    return captured_data

def parse_variants(data):
    """Parse variant information from captured data"""
    
    if not data or 'data' not in data:
        return None
    
    try:
        # Navigate to SKU module
        sku_module = data.get('data', {}).get('skuModule', {})
        
        if not sku_module:
            print("⚠️  No skuModule found in data")
            return None
        
        # Get SKU property list (color, size, etc.)
        sku_properties = sku_module.get('productSKUPropertyList', [])
        
        # Get price list per SKU
        sku_price_list = sku_module.get('skuPriceList', [])
        
        print(f"📊 Found {len(sku_properties)} property dimensions")
        print(f"💰 Found {len(sku_price_list)} SKU prices")
        
        # Extract dimension names
        dimensions = {}
        for prop in sku_properties:
            prop_name = prop.get('skuPropertyName')  # e.g., "Color", "Ships From"
            prop_id = prop.get('skuPropertyId')
            values = prop.get('skuPropertyValues', [])
            
            dimension_values = []
            for val in values:
                dimension_values.append({
                    'name': val.get('propertyValueDisplayName'),
                    'id': val.get('propertyValueId'),
                    'image': val.get('skuPropertyImagePath')
                })
            
            dimensions[prop_name] = {
                'id': prop_id,
                'values': dimension_values
            }
        
        # Extract variants (combinations)
        variants = []
        for sku_item in sku_price_list:
            sku_id = sku_item.get('skuId')
            sku_prop_ids = sku_item.get('skuPropIds')  # e.g., "14:193#Black;200000182:201336106#1m"
            sku_val = sku_item.get('skuVal', {})
            
            price = sku_val.get('skuActivityAmount', {}).get('value')
            if not price:
                price = sku_val.get('skuAmount', {}).get('value')
            
            stock = sku_val.get('availQuantity', 0)
            
            # Parse property IDs to names
            props = {}
            if sku_prop_ids:
                pairs = sku_prop_ids.split(';')
                for pair in pairs:
                    if '#' in pair:
                        prop_id, val_id = pair.split('#')
                        # Find matching dimension name
                        for dim_name, dim_data in dimensions.items():
                            if str(dim_data['id']) == prop_id:
                                # Find value name
                                for val in dim_data['values']:
                                    if str(val['id']) == val_id:
                                        props[dim_name] = val['name']
            
            variants.append({
                'sku_id': sku_id,
                'properties': props,
                'price': float(price) if price else None,
                'stock': stock
            })
        
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
    print("🧪 TESTING ALIEXPRESS VARIANT EXTRACTION")
    print("="*70)
    
    # Extract raw data
    raw_data = extract_variants_from_network(product_url)
    
    if raw_data:
        # Save raw data for inspection
        with open('debug_aliexpress_raw.json', 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Raw data saved to debug_aliexpress_raw.json")
        
        # Parse variants
        result = parse_variants(raw_data)
        
        if result:
            print("\n" + "="*70)
            print("📊 EXTRACTION RESULTS:")
            print("="*70)
            
            print(f"\n🎨 DIMENSIONS ({len(result['dimensions'])} total):")
            for dim_name, dim_data in result['dimensions'].items():
                print(f"  - {dim_name}: {len(dim_data['values'])} values")
                for val in dim_data['values'][:3]:  # Show first 3
                    print(f"    • {val['name']}")
                if len(dim_data['values']) > 3:
                    print(f"    ... and {len(dim_data['values']) - 3} more")
            
            print(f"\n🎯 VARIANTS ({len(result['variants'])} total):")
            for i, var in enumerate(result['variants'][:10], 1):  # Show first 10
                props_str = ', '.join([f"{k}: {v}" for k, v in var['properties'].items()])
                print(f"  {i}. {props_str} → €{var['price']} (Stock: {var['stock']})")
            
            if len(result['variants']) > 10:
                print(f"  ... and {len(result['variants']) - 10} more variants")
            
            # Save parsed result
            with open('debug_aliexpress_parsed.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Parsed data saved to debug_aliexpress_parsed.json")
            
            print("\n✅ EXTRACTION COMPLETE!")
            return result
        
    else:
        print("\n❌ EXTRACTION FAILED - No data captured")
        return None

if __name__ == "__main__":
    test_extraction()
