import sys
sys.path.insert(0, '.')
import src.jobs as j
from src.listing_quality import rank_audit
from src.database.models import Product, get_session, init_database
import json

e = j._engine()
db = init_database()

results = []
with get_session(db) as session:
    products = session.query(Product).filter_by(status='active').all()
    
    for p in products:
        pid = p.aliexpress_product_id
        print(f"Analyzing {pid} - {p.title[:50]}...", file=sys.stderr)
        
        row = {
            'title': p.title, 
            'category_id': p.category_id, 
            'ebay_price': p.ebay_price,
            'aliexpress_price': p.aliexpress_price, 
            'shipping_cost': p.shipping_cost,
            'description': p.description, 
            'ebay_item_id': p.ebay_item_id
        }
        
        try:
            result = rank_audit.audit_listing(e.aliexpress_client, e.ebay_client, row, pid)
            result['product_id'] = pid
            result['ebay_item_id'] = p.ebay_item_id
            result['title'] = p.title
            results.append(result)
        except Exception as ex:
            print(f"ERROR {pid}: {ex}", file=sys.stderr)
            results.append({
                'product_id': pid,
                'ebay_item_id': p.ebay_item_id,
                'title': p.title,
                'error': str(ex)
            })

print(json.dumps(results, indent=2, ensure_ascii=False))
