#!/usr/bin/env python3
"""
Simple Playwright Test - Open AliExpress and check page loads
"""

from playwright.sync_api import sync_playwright
import time

def test_simple_page_load():
    """Test if we can open AliExpress product page"""
    
    product_url = "https://www.aliexpress.com/item/1005005193534554.html"
    
    print("🚀 Starting Playwright...")
    
    with sync_playwright() as p:
        # Launch browser (headless=False to see what's happening)
        browser = p.chromium.launch(headless=False)
        
        # Create context with user agent
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        print(f"📄 Opening: {product_url}")
        
        # Navigate to page
        page.goto(product_url, wait_until='networkidle', timeout=60000)
        
        print(f"✅ Page loaded successfully")
        
        # Get page title
        title = page.title()
        print(f"📋 Title: {title}")
        
        # Wait a bit to see the page
        time.sleep(3)
        
        # Check if product title exists
        try:
            product_title = page.locator('h1').first.text_content()
            print(f"🎯 Product Title: {product_title}")
        except:
            print("⚠️  Could not find product title")
        
        print("✅ Test complete!")
        
        browser.close()

if __name__ == "__main__":
    test_simple_page_load()
