#!/usr/bin/env python3
"""
Test: eBay Browse API with Free Proxy
"""

import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Free proxy list
FREE_PROXIES = [
    "http://8.219.97.248:80",
    "http://47.74.152.29:8888",
    "http://103.167.135.110:80",
]

def test_ebay_with_proxy(proxy_url):
    """Test eBay Browse API with proxy"""
    
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Test simple eBay search
    url = "https://www.ebay.de/sch/i.html?_nkw=aufbewahrungstasche"
    
    try:
        print(f"\n🔍 Testing proxy: {proxy_url}")
        
        response = requests.get(
            url,
            proxies=proxies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS! Status: {response.status_code}")
            print(f"   📄 Content length: {len(response.text)} chars")
            return True
        else:
            print(f"   ❌ Failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ProxyError:
        print(f"   ❌ Proxy connection failed")
        return False
    except requests.exceptions.Timeout:
        print(f"   ⏱️ Timeout")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_direct_no_proxy():
    """Test WITHOUT proxy (baseline)"""
    
    url = "https://www.ebay.de/sch/i.html?_nkw=aufbewahrungstasche"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"\n🔍 Testing DIRECT (no proxy)")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"   ✅ SUCCESS! Status: {response.status_code}")
            return True
        elif response.status_code == 403:
            print(f"   ❌ BLOCKED: HTTP 403 (bot detection)")
            return False
        else:
            print(f"   ⚠️ Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("="*70)
    print("EBAY PROXY TEST")
    print("="*70)
    
    # 1. Test direct (baseline)
    direct_works = test_direct_no_proxy()
    
    # 2. Test with proxies
    working_proxies = []
    
    for proxy in FREE_PROXIES:
        if test_ebay_with_proxy(proxy):
            working_proxies.append(proxy)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Direct (no proxy): {'✅ WORKS' if direct_works else '❌ BLOCKED'}")
    print(f"Working proxies: {len(working_proxies)}/{len(FREE_PROXIES)}")
    
    if working_proxies:
        print(f"\n✅ WORKING PROXIES:")
        for p in working_proxies:
            print(f"   {p}")
    else:
        print(f"\n❌ NO WORKING PROXIES")
    
    # Recommendation
    print(f"\n💡 RECOMMENDATION:")
    if direct_works:
        print(f"   ✅ Direct access works - NO PROXY NEEDED!")
    elif working_proxies:
        print(f"   ✅ Use working proxy for scraping")
    else:
        print(f"   ⚠️ Need PAID proxy service (residential/rotating)")
        print(f"   📦 OR use template system (already working)")


if __name__ == '__main__':
    main()
