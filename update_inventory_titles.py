#!/usr/bin/env python3
"""
4 sorunlu başlığı Inventory API ile güncelle
"""
import sys
import os
import requests
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

# Yeni başlıklar (görsel doğrulama sonrası, ebay-de-keyword-titles kurallarına uygun)
updates = {
    '860138359448': {
        'item_group_key': 'GRP-1005010184187117',
        'new_title': 'Müll-Tüten-Halter Wandmontage Aufbewahrung Küche Bad Organizer Spender'
    },
    '860139500259': {
        'item_group_key': 'GRP-1005010033725224',
        'new_title': 'Kabelbinder Aufbewahrungsbox mit Karabiner Tasche Organizer Halterung'
    },
    '860139539563': {
        'item_group_key': 'GRP-1005005193534554',
        'new_title': 'Toocki Kabelmanagement Klettband zerreißbar Kabel Organizer USB-Kabel'
    },
    '860139545709': {
        'item_group_key': 'GRP-1005007370571569',
        'new_title': 'Wandhaken selbstklebend Besenhalter Mophalter Gerätehalter ohne Bohren'
    }
}

def update_item_group_title(item_group_key, new_title):
    """Inventory API ile item_group başlığını güncelle"""
    token = os.getenv('EBAY_ACCESS_TOKEN')
    
    # Önce mevcut item_group'u al
    url = f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{item_group_key}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print(f"GET {url}")
    response = requests.get(url, headers=headers, timeout=(10, 30))
    
    if response.status_code != 200:
        print(f"✗ GET failed: {response.status_code} {response.text[:500]}")
        return False
    
    group_data = response.json()
    
    # Title'ı güncelle
    group_data['title'] = new_title
    
    # PUT ile güncelle
    print(f"PUT {url}")
    headers['Content-Language'] = 'de-DE'
    response = requests.put(url, headers=headers, json=group_data, timeout=(10, 30))
    
    if response.status_code in [200, 204]:
        print(f"✓ SUCCESS: Title updated (HTTP {response.status_code})")
        return True
    else:
        print(f"✗ PUT failed: {response.status_code} {response.text[:500]}")
        return False

if __name__ == '__main__':
    for listing_id, data in updates.items():
        print(f"\n{'='*80}")
        print(f"Listing: {listing_id}")
        print(f"Item Group: {data['item_group_key']}")
        print(f"New Title ({len(data['new_title'])} chars): {data['new_title']}")
        print(f"{'='*80}")
        
        success = update_item_group_title(data['item_group_key'], data['new_title'])
        
        if not success:
            print("STOPPING due to error")
            break
