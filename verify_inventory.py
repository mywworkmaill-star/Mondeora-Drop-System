#!/usr/bin/env python3
"""
Inventory API üzerinden başlıkları doğrula
"""
import sys
import os
import requests
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

item_groups = {
    '860138359448': 'GRP-1005010184187117',
    '860139500259': 'GRP-1005010033725224',
    '860139539563': 'GRP-1005005193534554',
    '860139545709': 'GRP-1005007370571569'
}

expected_titles = {
    '860138359448': 'Müll-Tüten-Halter Wandmontage Aufbewahrung Küche Bad Organizer Spender',
    '860139500259': 'Kabelbinder Aufbewahrungsbox mit Karabiner Tasche Organizer Halterung',
    '860139539563': 'Toocki Kabelmanagement Klettband zerreißbar Kabel Organizer USB-Kabel',
    '860139545709': 'Wandhaken selbstklebend Besenhalter Mophalter Gerätehalter ohne Bohren'
}

def verify_inventory_title(listing_id, item_group_key):
    """Inventory API ile başlığı doğrula"""
    token = os.getenv('EBAY_ACCESS_TOKEN')
    
    url = f'https://api.ebay.com/sell/inventory/v1/inventory_item_group/{item_group_key}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    response = requests.get(url, headers=headers, timeout=(10, 30))
    
    if response.status_code == 200:
        data = response.json()
        return data.get('title', 'NOT FOUND')
    else:
        return f"ERROR: {response.status_code}"

if __name__ == '__main__':
    print("\n" + "="*80)
    print("INVENTORY API VERIFICATION")
    print("="*80)
    
    all_verified = True
    
    for lid, grp_key in item_groups.items():
        inventory_title = verify_inventory_title(lid, grp_key)
        expected = expected_titles[lid]
        
        if inventory_title == expected:
            print(f"\n✓ {lid} ({grp_key})")
            print(f"  Title: {inventory_title}")
            print(f"  Length: {len(inventory_title)} chars")
        else:
            print(f"\n✗ {lid} ({grp_key})")
            print(f"  Expected: {expected}")
            print(f"  Got:      {inventory_title}")
            all_verified = False
    
    print("\n" + "="*80)
    if all_verified:
        print("✓ ALL VERIFIED - All titles updated successfully in Inventory API!")
    else:
        print("✗ VERIFICATION FAILED - Some titles don't match")
    print("="*80)
