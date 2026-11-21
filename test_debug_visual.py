#!/usr/bin/env python3
"""
Debug: Test with visible browser to see what's happening
"""

from playwright.sync_api import sync_playwright
import time

product_url = "https://www.aliexpress.com/item/1005005193534554.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Visible browser
    
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    
    page = context.new_page()
    
    # Track network
    captured = []
    
    def handle_response(response):
        if 'aliexpress' in response.url:
            captured.append(response.url)
            if 'mtop' in response.url:
                print(f"🎯 MTOP: {response.url[:100]}")
    
    page.on('response', handle_response)
    
    print("Opening page...")
    page.goto(product_url, timeout=60000)
    
    print(f"Waiting 10 seconds...")
    time.sleep(10)
    
    print(f"\nCaptured {len(captured)} responses")
    print(f"MTOP responses: {len([u for u in captured if 'mtop' in u])}")
    
    input("\nPress Enter to close...")
    browser.close()
