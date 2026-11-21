# Mondeora Drop System - Complete Memory Index

## System Architecture
**Location:** C:/Users/Administrator/Desktop/Mondeora-Drop-System/
**Type:** AliExpress → eBay Dropshipping Automation
**Status:** Fully Operational (November 2026)

## Core Components

### 1. API Integrations
- **eBay API**: Inventory, Orders, Fulfillment (REST + Trading API)
- **AliExpress API**: Product sourcing, Order creation (Dropshipping API)
- **eBay MCP**: 379 tools via Hermes (ebay-mondeora server)

### 2. Automation System
**Main Scheduler:** `autonomous_scheduler_FULL.py`
**Cron Jobs (11):**
1. listing_prepare: Prepare products for listing
2. listing_pipeline: Publish to eBay
3. orders_poll: Check new eBay orders
4. orders_fulfill: Process orders
5. inventory_sync: Sync stock
6. tracking_upload: Upload tracking numbers
7. token_refresh: Refresh API tokens
8. performance_optimize: Optimize listings
9. customer_communication: Handle messages
10. social_media: Post updates
11. database_sync: Real-time sync

### 3. Database Structure
**Main DB:** `data/mondeora.db` (SQLite)
**Tables:**
- products: AliExpress products
- ebay_listings: eBay listings
- orders: Order records
- tracking: Tracking numbers
- automation_runs: Job execution logs

**GPSR DB:** `data/listing_ready.sqlite`
**Tables:**
- product_evidence: GPSR compliance evidence
- readiness_state: Product readiness tracking

### 4. File Structure
```
Mondeora-Drop-System/
├── src/
│   ├── api/
│   │   ├── ebay_client.py          # eBay API wrapper
│   │   └── aliexpress_client.py    # AliExpress API wrapper
│   ├── jobs/
│   │   ├── listing_prepare.py      # Prepare listings
│   │   ├── listing_pipeline.py     # Publish listings
│   │   ├── orders_poll.py          # Poll orders
│   │   └── orders_fulfill.py       # Fulfill orders
│   ├── listing_quality/
│   │   ├── ready_plan.py           # GPSR planning
│   │   ├── ready_workflow.py       # GPSR workflow
│   │   └── ready_launch.py         # GPSR launch
│   └── integrations/
│       └── ebay_mcp_bridge.py      # eBay MCP bridge
├── autonomous_scheduler_FULL.py     # Main scheduler
├── mondeora_full_automation.py      # LangGraph workflow
├── langgraph_advanced.py            # LangGraph order flow
└── data/
    ├── mondeora.db                  # Main database
    └── listing_ready.sqlite         # GPSR database
```

### 5. Environment Variables (.env)
**eBay:**
- EBAY_APP_ID: Mondeora-drop-PRD-41addb012-8a42183e
- EBAY_CERT_ID: PRD-8094df1add7c-4acb-468e-8f04-b090
- EBAY_ACCESS_TOKEN: (OAuth token)
- EBAY_REFRESH_TOKEN: (OAuth refresh)
- EBAY_PAYMENT_POLICY_ID: 263035507017
- EBAY_FULFILLMENT_POLICY_ID: 263035514017
- EBAY_RETURN_POLICY_ID: 263035512017

**AliExpress:**
- ALIEXPRESS_APP_KEY: (App key)
- ALIEXPRESS_APP_SECRET: (App secret)
- ALIEXPRESS_ACCESS_TOKEN: (OAuth token)

## LangGraph Workflow

**File:** `mondeora_full_automation.py`

**Workflow Steps:**
1. **fetch_ebay_order**: Get eBay order via eBay MCP
2. **check_stock**: Check AliExpress stock (retry 3x)
3. **check_gpsr**: GPSR compliance check (database)
4. **create_ali_order**: Create AliExpress PENDING order
5. **manual_approval**: Wait for Telegram approval (n8n)
6. **upload_tracking**: Upload tracking to eBay (eBay MCP)

**State Tracking:**
- Order IDs, SKUs, tracking numbers
- Stock availability, GPSR compliance
- Retry counts, error states

**Conditional Routing:**
- Stock unavailable → retry 3x → error
- GPSR non-compliant → manual review
- All steps logged

## eBay MCP Integration

**Bridge File:** `src/integrations/ebay_mcp_bridge.py`

**Available Methods:**
- `create_listing(product_data)`: Create eBay listing
- `get_listing(sku)`: Get listing details
- `update_listing_price(sku, price)`: Update price
- `update_listing_quantity(sku, qty)`: Update stock
- `get_orders(days)`: Get eBay orders
- `get_order_details(order_id)`: Get order details
- `upload_tracking(order_id, tracking)`: Upload tracking
- `bulk_update_prices(sku_price_map)`: Bulk price update
- `bulk_update_quantities(sku_qty_map)`: Bulk stock update

**Hermes Config:**
```yaml
mcp_servers:
  ebay-mondeora:
    command: npx
    args: [-y, ebay-mcp]
    env:
      EBAY_CLIENT_ID: Mondeora-drop-PRD-41addb012-8a42183e
      EBAY_CLIENT_SECRET: PRD-8094df1add7c-4acb-468e-8f04-b090
      EBAY_ENVIRONMENT: production
      EBAY_MARKETPLACE_ID: EBAY_DE
```

**379 eBay Tools Available:**
- Inventory: 57 tools
- Orders: 45 tools
- Marketing: 32 tools
- Analytics: 28 tools
- Finance: 21 tools
- Messaging: 12 tools
- Taxonomy: 18 tools
- Trading API: 166 tools

## Hermes Skills (15 Active)

**Location:** `%HERMES_HOME%/skills/ecommerce-imported/`

**Skills:**
1. marketplace-listing-optimizer: eBay SEO, Cassini optimization
2. dynamic-pricing: Auto price optimization
3. order-fulfillment-workflow: Order processing
4. inventory-tracking: Stock tracking
5. low-stock-alerts: Stock alerts
6. checkout-friction-finder: Checkout optimization
7. product-page-conversion-review: Product page audit
8. returns-reason-miner: Return analysis
9. contribution-margin-check: Profit margin calculation
10. shipping-economics-review: Shipping cost analysis
11. inventory-risk-brief: Inventory risk report
12. dropshipping-integration: AliExpress integration
13. Aliexpress: Supplier navigation
14. Amazon: Marketplace navigation
15. (Additional skills available)

## Usage Examples

### Python Usage:
```python
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

ebay = eBayMCPIntegration()

# Create listing
result = ebay.create_listing({
    'sku': 'TEST-001',
    'title': 'Wireless Bluetooth Kopfhörer 5.0',
    'price': 29.99,
    'quantity': 50,
    'category_id': '112529'
})

# Get orders
orders = ebay.get_orders(days=7)

# Upload tracking
ebay.upload_tracking('12345-67890', 'DHL123456789')
```

### Hermes Usage:
```
"Check my eBay API rate limits"
"Get my eBay active listings"
"Optimize eBay listing for wireless earbuds"
"Upload tracking DHL123 to eBay order 12345"
```

### LangGraph Usage:
```bash
python311 mondeora_full_automation.py
```

## Key Documentation Files
- MONDEORA_EBAY_FULL_GUIDE.md: Complete eBay integration guide
- EBAY_INTEGRATIONS.md: eBay MCP documentation
- ECOMMERCE_INTEGRATIONS.md: E-commerce skills documentation
- AUTOMATION_STATUS.md: Automation status report
- 100_PERCENT_AUTOMATION_COMPLETE.md: Full automation documentation

## Recent Updates (November 2026)
- ✅ eBay MCP fully integrated
- ✅ 15 e-commerce skills activated
- ✅ LangGraph workflow implemented
- ✅ Full automation with supervised trial working
- ⏳ n8n notification system (installing)
- ⏳ MedusaJS e-commerce platform (optional)

## Critical Files to Never Modify Without Backup
- .env: All credentials
- data/mondeora.db: Main database
- data/listing_ready.sqlite: GPSR evidence
- autonomous_scheduler_FULL.py: Main scheduler
- src/api/ebay_client.py: eBay API wrapper
- src/listing_quality/: GPSR system (bypasses active for supervised trial)

## Token Management
**Auto-refresh implemented:**
- AliExpress: Every 1 hour (5-min threshold)
- eBay: Every 1 hour (token expired - needs manual refresh)

**Files:**
- token_auto_refresh_complete.py: Token refresh system
- data/aliexpress_token_refresh_metadata.json: AliExpress metadata
- data/ebay_token_refresh_metadata.json: eBay metadata

## Deployment Status
- Python: 3.11 required (not 3.14)
- Database: SQLite (file-based, rm -f to reset)
- Cron: 11 jobs via autonomous_scheduler_FULL.py
- eBay: Production environment (EBAY_DE)
- AliExpress: Production environment
- Hermes: Local MCP servers configured
- Skills: 15 active e-commerce skills

## Next Steps
1. Test eBay MCP via Hermes
2. Integrate eBay MCP into Python jobs
3. Complete n8n setup for notifications
4. Deploy LangGraph workflow to production
5. Scale to multi-product automation
