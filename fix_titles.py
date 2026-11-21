#!/usr/bin/env python3
"""
4 sorunlu başlığı düzelt
"""
import sys
import os
sys.path.insert(0, 'src')

from api.ebay_xml_client import EbayXMLAPIClient
import json

def get_listing_info(listing_id):
    """eBay'den listing bilgilerini al"""
    client = EbayXMLAPIClient()
    result = client.get_item(listing_id)
    
    if not result.get('success'):
        print(f"ERROR: {result.get('errors')}")
        return None
    
    root = result['root']
    ns = {'ebay': 'urn:ebay:apis:eBLBaseComponents'}
    
    item = root.find('.//ebay:Item', ns)
    if not item:
        return None
    
    # Temel bilgileri çek
    info = {
        'listing_id': listing_id,
        'sku': item.find('.//ebay:SKU', ns).text if item.find('.//ebay:SKU', ns) is not None else None,
        'title': item.find('.//ebay:Title', ns).text if item.find('.//ebay:Title', ns) is not None else None,
        'picture_url': item.find('.//ebay:PictureURL', ns).text if item.find('.//ebay:PictureURL', ns) is not None else None,
        'category_id': item.find('.//ebay:PrimaryCategory/ebay:CategoryID', ns).text if item.find('.//ebay:PrimaryCategory/ebay:CategoryID', ns) is not None else None,
    }
    
    return info

if __name__ == '__main__':
    listing_ids = [
        '860138359448',  # Müll Taschen Halter
        '860139500259',  # Kabelbinder-Organizer
        '860139539563',  # Kabel-Organizer
        '860139545709'   # Mehrzweck haken
    ]
    
    for lid in listing_ids:
        print(f"\n=== {lid} ===")
        info = get_listing_info(lid)
        if info:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print("FAILED")
