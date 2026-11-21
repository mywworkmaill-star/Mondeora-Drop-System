#!/usr/bin/env python3
"""
4 sorunlu başlığı güncelle
"""
import sys
import os
sys.path.insert(0, 'src')

from api.ebay_xml_client import EbayXMLAPIClient

# Yeni başlıklar (görsel doğrulama sonrası, ebay-de-keyword-titles kurallarına uygun)
new_titles = {
    '860138359448': 'Müll-Tüten-Halter Wandmontage Aufbewahrung Küche Bad Organizer Spender',  # 77 char
    '860139500259': 'Kabelbinder Aufbewahrungsbox mit Karabiner Tasche Organizer Halterung',  # 76 char
    '860139539563': 'Toocki Kabelmanagement Klettband zerreißbar Kabel Organizer USB-Kabel',  # 76 char
    '860139545709': 'Wandhaken selbstklebend Besenhalter Mophalter Gerätehalter ohne Bohren'   # 77 char
}

def update_title(listing_id, new_title):
    """ReviseFixedPriceItem ile başlığı güncelle"""
    import requests
    from xml.etree import ElementTree as ET
    from defusedxml.ElementTree import fromstring as _safe_fromstring
    
    client = EbayXMLAPIClient()
    
    # ReviseFixedPriceItem XML - sadece başlık güncelle
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<ReviseFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{client.auth_token}</eBayAuthToken>
    </RequesterCredentials>
    <Item>
        <ItemID>{listing_id}</ItemID>
        <Title>{new_title}</Title>
    </Item>
    <ErrorLanguage>en_US</ErrorLanguage>
</ReviseFixedPriceItemRequest>"""
    
    headers = client._get_headers('ReviseFixedPriceItem')
    response = requests.post(client.endpoint, data=xml, headers=headers, timeout=15)
    
    print(f"HTTP Status: {response.status_code}")
    print(f"Response XML:\n{response.text[:2000]}")
    
    result = client._send_request('ReviseFixedPriceItem', xml)
    return result

if __name__ == '__main__':
    for listing_id, new_title in new_titles.items():
        print(f"\n{'='*80}")
        print(f"Listing: {listing_id}")
        print(f"New Title ({len(new_title)} chars): {new_title}")
        print(f"{'='*80}")
        
        result = update_title(listing_id, new_title)
        
        if result.get('success'):
            print("✓ SUCCESS: Title updated")
        else:
            print(f"✗ FAILED")
            print(f"Result: {result}")
