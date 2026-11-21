"""
FIND CORRECT EBAY DE CATEGORY
Search for 'Aufbewahrung' (Storage) categories on eBay Germany
"""

import sys
sys.path.insert(0, 'src')

from api.ebay_client import eBayAPIClient

ebay = eBayAPIClient()

print("=" * 80)
print("🔍 EBAY DE CATEGORY SEARCH")
print("=" * 80)
print()

try:
    # Search for Storage/Organization categories on eBay DE
    print("Searching for 'Aufbewahrung' categories...")
    
    # Get category suggestions
    # Try Taxonomy API category search
    response = ebay._request('GET', '/commerce/taxonomy/v1/category_tree/77/get_category_suggestions', params={
        'q': 'Aufbewahrung Organizer Batterie'
    })
    
    if response and 'categorySuggestions' in response:
        print(f"\n✅ Found {len(response['categorySuggestions'])} suggestions:\n")
        
        for i, cat in enumerate(response['categorySuggestions'][:10], 1):
            cat_id = cat.get('category', {}).get('categoryId', 'Unknown')
            cat_name = cat.get('category', {}).get('categoryName', 'Unknown')
            cat_tree = cat.get('categoryTreeNodeAncestors', [])
            
            # Build full path
            path = " > ".join([anc.get('categoryName', '') for anc in cat_tree])
            if path:
                path += f" > {cat_name}"
            else:
                path = cat_name
            
            print(f"{i}. ID: {cat_id}")
            print(f"   Path: {path}")
            print()
    else:
        print("❌ No suggestions found")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("=" * 80)
print("💡 MANUAL SEARCH RECOMMENDATION")
print("=" * 80)
print()
print("If API fails, manually check eBay DE:")
print("1. Go to: https://www.ebay.de")
print("2. Search: 'batterie organizer'")
print("3. Click on a similar listing")
print("4. Check 'Kategorie' in item specifics")
print("5. Note the category path")
