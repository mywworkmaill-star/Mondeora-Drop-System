#!/usr/bin/env python3
"""Enrich eBay listings with detailed item specifics."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.ebay_client import eBayRESTClient
from src.api.aliexpress_client import AliExpressAPIClient
from src.listing_quality import categories, source
from src.runtime import read_config
import sqlite3


def enrich_aspects(product_id, category_id):
    cfg = read_config()
    
    ali = AliExpressAPIClient(cfg['ALIEXPRESS_APP_KEY'], cfg['ALIEXPRESS_APP_SECRET'])
    ali.access_token = cfg['ALIEXPRESS_ACCESS_TOKEN']
    
    ebay = eBayRESTClient(cfg['EBAY_ACCESS_TOKEN'])  # Changed from EBAY_OAUTH_TOKEN
    
    raw = ali.get_product_details(product_id)
    props = source.properties(raw)
    
    meta = categories.aspects_for(ebay, category_id)
    aspects, missing = categories.fill_aspects(meta, props)
    
    # Add package dimensions if available
    base = raw.get('ae_item_base_info_dto', {})
    h = base.get('package_height')
    l = base.get('package_length')
    w = base.get('package_width')
    
    if h and l and w:
        for m in meta:
            if 'abmessung' in m['name'].lower() and m['name'] not in aspects:
                aspects[m['name']] = [f'{l}x{w}x{h} cm']
                break
    
    return aspects, missing, len(props)


if __name__ == '__main__':
    db = sqlite3.connect(ROOT / 'data' / 'dropshipping.db')
    
    rows = db.execute('''
        SELECT aliexpress_product_id, ebay_item_id, category
        FROM products
        WHERE ebay_item_id IN ('860143527490', '860143527923')
    ''').fetchall()
    
    print('LISTING CONTENT ENRICHMENT')
    print('='*60)
    
    for ali_id, ebay_id, category in rows:
        print(f'\nProduct: {ali_id}')
        print(f'eBay: {ebay_id}')
        
        category = category or '175672'
        
        try:
            aspects, missing, total_props = enrich_aspects(ali_id, category)
            
            print(f'AliExpress properties: {total_props}')
            print(f'Mapped aspects: {len(aspects)}')
            print(f'Missing required: {len(missing)}')
            
            print('\nAspects:')
            for name, values in list(aspects.items())[:15]:
                print(f'  {name}: {values[0] if values else ""}')
            
            if missing:
                print(f'\nMissing: {", ".join(missing)}')
                
        except Exception as e:
            print(f'ERROR: {e}')
    
    db.close()
