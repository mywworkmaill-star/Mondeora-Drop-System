#!/usr/bin/env python3
"""
Browse API ile başlıkları doğrula
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

def verify_browse_title(listing_id):
    """Browse API ile başlığı doğrula"""
    token = os.getenv('EBAY_ACCESS_TOKEN')
    
    item_group_id = item_groups[listing_id]
    
    url = f'https://api.ebay.com/buy/browse/v1/item/get_items_by_item_group'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_DE'
    }
    params = {'item_group_id': item_group_id}
    
    response = requests.get(url, headers=headers, params=params, timeout=(10, 30))
    
    if response.status_code == 200:
        data = response.json()
        # get_items_by_item_group commonDescriptions altında title döner
        browse_title = data.get('commonDescriptions', [{}])[0].get('title', 'NOT FOUND')
        return browse_title
    else:
        return f"ERROR: {response.status_code} {response.text[:200]}"

if __name__ == '__main__':
    print("\\n" + "="*80)
    print("BROWSE API VERIFICATION")
    print("="*80)
    
    all_verified = True
    
    for lid in item_groups.keys():
        browse_title = verify_browse_title(lid)
        expected = expected_titles[lid]
        
        if browse_title == expected:
            print(f"\\n✓ {lid}")
            print(f"  Title: {browse_title}")
        else:
            print(f"\\n✗ {lid}")
            print(f"  Expected: {expected}")
            print(f"  Got:      {browse_title}")
            all_verified = False
    
    print("\\n" + "="*80)
    if all_verified:
        print("✓ ALL VERIFIED - All titles updated successfully!")
    else:
        print("✗ VERIFICATION FAILED - Some titles don't match")
    print("="*80)
