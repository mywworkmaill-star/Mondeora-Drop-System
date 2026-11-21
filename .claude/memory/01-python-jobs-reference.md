# Mondeora Python Jobs Reference

## Job Execution Commands

### Via Autonomous Scheduler
```bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 autonomous_scheduler_FULL.py
```

### Individual Jobs
```bash
# Listing preparation
python311 -m src.jobs.listing_prepare

# Listing pipeline (publish to eBay)
python311 -m src.jobs.listing_pipeline

# Orders poll
python311 -m src.jobs.orders_poll

# Orders fulfill
python311 -m src.jobs.orders_fulfill

# Inventory sync
python311 -m src.jobs.inventory_sync

# Tracking upload
python311 -m src.jobs.tracking_upload
```

## Key Python Modules

### src/api/ebay_client.py
**eBayAPIClient class:**
- `refresh_access_token()`: Refresh OAuth token
- `create_inventory_item()`: Create listing
- `get_inventory_item()`: Get listing
- `update_inventory_item()`: Update listing
- `get_orders()`: Get orders
- `create_shipping_fulfillment()`: Upload tracking

### src/api/aliexpress_client.py
**AliExpressClient class:**
- `ds_text_search()`: Search products
- `ds_product_get()`: Get product details
- `ds_freight_query()`: Get shipping cost
- `ds_order_create()`: Create order
- `ds_order_tracking_get()`: Get tracking

### src/integrations/ebay_mcp_bridge.py
**eBayMCPIntegration class:**
- `create_listing(product_data)`: Create via MCP
- `get_orders(days)`: Get orders via MCP
- `upload_tracking(order_id, tracking)`: Upload via MCP
- `bulk_update_prices(sku_price_map)`: Bulk updates

## Database Queries

### SQLite Main DB (data/mondeora.db)
```python
import sqlite3
conn = sqlite3.connect('data/mondeora.db')
cursor = conn.cursor()

# Get all products
cursor.execute("SELECT * FROM products")

# Get active eBay listings
cursor.execute("SELECT * FROM ebay_listings WHERE status='active'")

# Get recent orders
cursor.execute("SELECT * FROM orders WHERE created_at > datetime('now', '-7 days')")
```

### GPSR DB (data/listing_ready.sqlite)
```python
conn = sqlite3.connect('data/listing_ready.sqlite')
cursor = conn.cursor()

# Get products with evidence
cursor.execute("SELECT * FROM product_evidence WHERE readiness='ready'")
```

## Common Automation Patterns

### Pattern 1: Create Listing
```python
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

ebay = eBayMCPIntegration()
result = ebay.create_listing({
    'sku': 'PRODUCT-001',
    'title': 'Product Title (80 chars)',
    'description': 'Product description',
    'price': 29.99,
    'quantity': 50,
    'category_id': '112529',
    'images': ['url1', 'url2'],
    'item_specifics': {
        'Brand': 'Generic',
        'Model': 'ABC123'
    }
})
```

### Pattern 2: Process Orders
```python
ebay = eBayMCPIntegration()

# Get orders
orders = ebay.get_orders(days=7)

for order in orders['orders']:
    order_id = order['orderId']
    
    # Create AliExpress order
    # ... (AliExpress API call)
    
    # Upload tracking
    ebay.upload_tracking(order_id, tracking_number='DHL123')
```

### Pattern 3: Bulk Updates
```python
ebay = eBayMCPIntegration()

# Bulk price update
price_map = {
    'SKU-001': 29.99,
    'SKU-002': 39.99,
    'SKU-003': 19.99
}
ebay.bulk_update_prices(price_map)

# Bulk quantity update
qty_map = {
    'SKU-001': 100,
    'SKU-002': 50,
    'SKU-003': 75
}
ebay.bulk_update_quantities(qty_map)
```

## Error Handling

### Token Refresh
```python
from src.api.ebay_client import eBayAPIClient

ebay_client = eBayAPIClient()

try:
    result = ebay_client.some_api_call()
except Exception as e:
    if 'token' in str(e).lower():
        # Refresh token
        ebay_client.refresh_access_token(force=True)
        # Retry
        result = ebay_client.some_api_call()
```

### Retry Logic
```python
def retry_api_call(func, max_retries=3):
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i == max_retries - 1:
                raise
            time.sleep(2 ** i)  # Exponential backoff
```

## LangGraph Integration

### Full Automation Workflow
```python
from mondeora_full_automation import MondeoraSalesAutomation

automation = MondeoraSalesAutomation()
app = automation.build_workflow()

# Run workflow
result = app.invoke({
    "ebay_order_id": "12345-67890",
    "ali_product_id": "1005006372921430",
    "sku": "PRODUCT-001",
    "retry_count": 0,
    "max_retries": 3
})

print(f"Status: {result['status']}")
print(f"Tracking: {result['tracking_number']}")
```

## Hermes Integration

### Call eBay MCP via Hermes
```python
# In production, use Hermes API
# For now, direct eBay MCP calls
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

ebay = eBayMCPIntegration()
result = ebay.hermes_call('ebay_get_rate_limits', {})
```

### Skill Triggers
```python
# Hermes skills activate automatically
# Trigger via conversation:
# "Optimize my eBay listing for wireless earbuds"
# "Calculate profit margin for this product"
# "Analyze return reasons"
```

## Monitoring & Logs

### Check Automation Logs
```python
import sqlite3

conn = sqlite3.connect('data/mondeora.db')
cursor = conn.cursor()

# Get recent automation runs
cursor.execute("""
    SELECT job_name, status, started_at, completed_at, error
    FROM automation_runs
    ORDER BY started_at DESC
    LIMIT 20
""")

for row in cursor.fetchall():
    print(row)
```

### Check API Rate Limits
```python
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

ebay = eBayMCPIntegration()
limits = ebay.get_rate_limits()
print(f"Daily limit: {limits['daily_limit']}")
print(f"Used: {limits['used']}")
print(f"Remaining: {limits['remaining']}")
```

## Critical Python Paths
- Python 3.11: `/c/Program Files/Python311/python.exe`
- Not 3.14: Default Python 3.14.9 is incompatible
- Always use: `python311` command
