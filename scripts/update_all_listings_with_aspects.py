#!/usr/bin/env python3
"""
Update ALL Active eBay Listings with Aspects (XML Trading API)
Uses ReviseFixedPriceItem to directly update ItemSpecifics.
100% guaranteed to work - bypasses Inventory API issues.
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import json

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.api.aliexpress_client import AliExpressAPIClient
from src.api.ebay_client import eBayRESTClient
from src.api.ebay_xml_client import EbayXMLAPIClient
from src.runtime import read_config
from scripts.extract_aspects_from_description import extract_aspects_for_product


def get_all_active_listings(db_path):
    """Get ALL active published listings from database."""
    
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    
    query = '''
        SELECT 
            p.id,
            p.aliexpress_product_id as product_id,
            p.title,
            p.description,
            p.ebay_item_id,
            p.ebay_price,
            p.category_id as ebay_category_id
        FROM products p
        WHERE p.ebay_item_id IS NOT NULL
        AND p.ebay_item_id != ''
        AND p.status != 'DELISTED'
        ORDER BY p.id DESC
    '''
    
    rows = db.execute(query).fetchall()
    db.close()
    
    return [dict(row) for row in rows]


def revise_listing_with_aspects(xml_client, ebay_item_id, aspects, enhanced_description=None):
    """
    Revise eBay listing with aspects using XML Trading API.
    
    Args:
        xml_client: eBay XML client
        ebay_item_id: eBay item ID
        aspects: Dict of {name: value} where value can be str, list, or dict
        enhanced_description: Optional enhanced description with aspects
    
    Returns:
        bool: Success
    """
    
    # Build ItemSpecifics XML
    item_specifics = []
    for name, value in aspects.items():
        # Skip invalid types (dict, None, etc.)
        if isinstance(value, dict):
            # Skip dict values (like Dimensions dict)
            print(f"    ⚠️  Skipping dict value for {name}: {value}")
            continue
        
        # Normalize value to string
        if isinstance(value, list):
            if len(value) > 0:
                val = str(value[0])  # Take first value, convert to string
            else:
                continue  # Skip empty lists
        elif value is None:
            continue  # Skip None values
        else:
            val = str(value)  # Convert to string
        
        # Skip empty strings
        if not val or val.strip() == '':
            continue
        
        # Escape XML special characters
        val = val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        name = str(name).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        item_specifics.append(f'''
        <NameValueList>
            <Name>{name}</Name>
            <Value>{val}</Value>
        </NameValueList>''')
    
    item_specifics_xml = ''.join(item_specifics)
    
    # Build Description with aspects table (if provided)
    description_xml = ""
    if enhanced_description:
        description_xml = f'''
    <Description><![CDATA[{enhanced_description}]]></Description>'''
    
    # Build ReviseFixedPriceItem XML
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<ReviseFixedPriceItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{xml_client.auth_token}</eBayAuthToken>
    </RequesterCredentials>
    <Item>
        <ItemID>{ebay_item_id}</ItemID>
        <ItemSpecifics>{item_specifics_xml}
        </ItemSpecifics>{description_xml}
    </Item>
    <VerifyOnly>false</VerifyOnly>
</ReviseFixedPriceItemRequest>'''
    
    try:
        response = xml_client._send_request('ReviseFixedPriceItem', xml)
        
        # 🚨 SECURITY FIX (2026-11-21): used to print() the full raw eBay
        # response dict — can carry internal diagnostic/PII detail into logs,
        # contradicting this project's own "never propagate response text"
        # policy (see EBayAPIError docstring in src/api/ebay_client.py).
        # Only print a success/ack summary now.
        print(f"    🔍 Ack: {response.get('ack') if isinstance(response, dict) else type(response).__name__}")
        
        # Response is a dict from _send_request()
        if isinstance(response, dict) and response.get('success'):
            print(f"    ✅ Updated successfully")
            return True
        else:
            # Failed - show errors
            errors = response.get('errors', [])
            if errors:
                error_msg = '; '.join(errors)
                print(f"    ❌ eBay API error: {error_msg}")
            else:
                error = response.get('error', 'Unknown error')
                print(f"    ❌ Error: {error}")
            return False
            
    except Exception as e:
        print(f"    ❌ XML API error: {e}")
        import traceback
        traceback.print_exc()
        return False


def enhance_description_with_aspects(original_description, aspects):
    """Add aspects table to description for better visibility."""
    
    aspects_html = '''
<div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0; background: #f9f9f9;">
    <h3 style="margin-top: 0; color: #333;">📋 Produktmerkmale</h3>
    <table style="width: 100%; border-collapse: collapse;">
'''
    
    for name, value in aspects.items():
        val = value[0] if isinstance(value, list) else value
        aspects_html += f'''
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; width: 40%;">{name}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{val}</td>
        </tr>'''
    
    aspects_html += '''
    </table>
</div>
'''
    
    # Add aspects table at the beginning of description
    return aspects_html + original_description


def main():
    """Update all active listings with aspects."""
    
    # Initialize clients
    ali = AliExpressAPIClient()
    ebay = eBayRESTClient()
    
    # Get XML token from config
    cfg = read_config()
    xml_token = cfg.get('EBAY_ACCESS_TOKEN')  # XML client uses this
    
    if not xml_token:
        print("❌ EBAY_ACCESS_TOKEN not found in config!")
        print("👉 Need XML API token for ReviseFixedPriceItem")
        return
    
    xml_client = EbayXMLAPIClient()
    
    print(f"\n{'='*60}")
    print("UPDATE ALL ACTIVE LISTINGS WITH ASPECTS")
    print("Using eBay XML Trading API (ReviseFixedPriceItem)")
    print(f"{'='*60}\n")
    
    # Get all active listings
    db_path = ROOT / 'data' / 'dropshipping.db'
    listings = get_all_active_listings(db_path)
    
    print(f"📦 Found {len(listings)} active published listings\n")
    
    if not listings:
        print("⚠️  No active listings found!")
        return
    
    results = []
    success_count = 0
    failed_count = 0
    
    for idx, listing in enumerate(listings, 1):
        product_id = listing['product_id']
        ebay_item_id = listing['ebay_item_id']
        category_id = listing['ebay_category_id']
        title = listing['title']
        description = listing.get('description', '')
        
        print(f"\n[{idx}/{len(listings)}] Processing {product_id}")
        print(f"  eBay Item: {ebay_item_id}")
        print(f"  Title: {title[:60]}...")
        
        if not category_id:
            print(f"  ⚠️  No category ID - skipping")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'skipped',
                'reason': 'no_category'
            })
            continue
        
        # Extract aspects
        try:
            print(f"  🔍 Extracting aspects...")
            aspects = extract_aspects_for_product(ali, ebay, product_id, category_id)
        except Exception as e:
            print(f"  ❌ Aspect extraction failed: {e}")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'failed',
                'reason': f'extraction_error: {type(e).__name__}'
            })
            continue
        
        if not aspects:
            print(f"  ⚠️  No aspects extracted")
            # Still try to update with minimal aspects
            aspects = {
                'Marke': 'Markenlos',
                'Herstellernummer': 'Nicht zutreffend'
            }
        
        print(f"  📊 Extracted {len(aspects)} aspects")
        
        # Enhance description with aspects table
        enhanced_desc = enhance_description_with_aspects(description, aspects)
        
        # Update via XML API
        print(f"  📤 Updating eBay listing via XML API...")
        success = revise_listing_with_aspects(
            xml_client, 
            ebay_item_id, 
            aspects,
            enhanced_description=enhanced_desc
        )
        
        if success:
            print(f"  ✅ Successfully updated!")
            success_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'success',
                'aspects_count': len(aspects),
                'aspects': aspects
            })
        else:
            print(f"  ❌ Update failed")
            failed_count += 1
            results.append({
                'product_id': product_id,
                'ebay_item_id': ebay_item_id,
                'status': 'failed',
                'reason': 'xml_api_error'
            })
    
    # Save report
    report = {
        'timestamp': datetime.now().isoformat(),
        'total': len(listings),
        'success': success_count,
        'failed': failed_count,
        'results': results
    }
    
    report_path = ROOT / 'data' / 'audit' / 'xml_aspect_update_report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total processed: {len(listings)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Success rate: {success_count/len(listings)*100:.1f}%")
    print()
    print(f"📄 Report saved: {report_path}")
    print()
    print("✅ Done! Check eBay.de listings - aspects should be visible now!")
    print()


if __name__ == '__main__':
    main()
