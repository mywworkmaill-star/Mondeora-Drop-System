# Mondeora eBay & Hermes Integration Reference

## eBay MCP Tools (379 Available)

### Inventory Tools (57)
- ebay_create_inventory_item
- ebay_get_inventory_item
- ebay_update_inventory_item
- ebay_delete_inventory_item
- ebay_bulk_create_or_replace_inventory_item
- ebay_bulk_get_inventory_item
- ebay_bulk_update_price_quantity
- ebay_create_offer
- ebay_update_offer
- ebay_publish_offer
- ebay_withdraw_offer
- ebay_get_offers
- ebay_get_listing_fees

### Order Tools (45)
- ebay_get_orders
- ebay_get_order
- ebay_issue_refund
- ebay_get_payment_dispute
- ebay_create_shipping_fulfillment
- ebay_get_shipping_fulfillment
- ebay_delete_shipping_fulfillment

### Marketing Tools (32)
- ebay_get_ad_rate
- ebay_create_ad
- ebay_delete_ad
- ebay_get_ads_by_inventory_reference
- ebay_bulk_create_ads_by_inventory_reference
- ebay_bulk_delete_ads_by_inventory_reference
- ebay_update_bid
- ebay_get_campaigns
- ebay_create_campaign
- ebay_delete_campaign
- ebay_suggest_keywords
- ebay_suggest_items

### Analytics Tools (28)
- ebay_get_traffic_reports
- ebay_get_seller_standards_profile
- ebay_get_rate_limits
- ebay_find_listing_recommendations

### Finance Tools (21)
- ebay_get_payout_summary
- ebay_get_payout
- ebay_get_payouts
- ebay_get_seller_transaction
- ebay_get_seller_transactions
- ebay_get_total_balances

### Taxonomy & Catalog Tools (18)
- ebay_get_category_tree
- ebay_get_category_subtree
- ebay_get_category_suggestions
- ebay_get_item_aspects_for_category
- ebay_get_product
- ebay_search_products

## Hermes Skills Usage

### marketplace-listing-optimizer
```
Trigger: "optimize ebay listing", "ebay seo", "cassini optimization"

Input:
- Marketplace: eBay
- Product: Product name
- Current title: Existing title
- Category: Electronics
- Issue: Low traffic / Low conversion

Output:
- 80-char SEO title
- Item Specifics checklist
- Keyword strategy (primary, secondary, long-tail)
- Description structure
- Image recommendations
- Conversion fixes
```

### dynamic-pricing
```
Trigger: "dynamic pricing", "price optimization", "competitor pricing"

Input:
- Current prices
- Competitor prices
- Inventory levels
- Sales velocity

Output:
- Price recommendations per SKU
- Increase/decrease percentages
- Margin protection rules
```

### contribution-margin-check
```
Trigger: "profit margin", "real profit", "margin calculation"

Input:
- Sale price
- Product cost
- eBay fee (13.5%)
- Shipping cost
- Payment processing (2.9%)

Output:
- Real profit amount
- Profit margin percentage
- Warning if below target (20%)
```

### returns-reason-miner
```
Trigger: "return analysis", "return reasons", "return patterns"

Input:
- Return exports (CSV or list)
- Return reasons
- Time period

Output:
- Top return reasons
- Patterns identified
- Actionable fixes (size chart, photos, description)
- Priority ranking
```

## Hermes MCP Servers Configuration

### ebay-mondeora
```yaml
mcp_servers:
  ebay-mondeora:
    command: npx
    args:
      - -y
      - ebay-mcp
    env:
      EBAY_CLIENT_ID: Mondeora-drop-PRD-41addb012-8a42183e
      EBAY_CLIENT_SECRET: PRD-8094df1add7c-4acb-468e-8f04-b090
      EBAY_ENVIRONMENT: production
      EBAY_MARKETPLACE_ID: EBAY_DE
      EBAY_CONTENT_LANGUAGE: de-DE
    description: eBay API for Mondeora - Inventory, Orders, Fulfillment
```

### dropshipping-product-scout
```yaml
mcp_servers:
  dropshipping-product-scout:
    type: http
    url: https://mcp.youxiu.shop/mcp
    description: CJ Dropshipping product scout and freight calculator
```

### dsers-dropshipping
```yaml
mcp_servers:
  dsers-dropshipping:
    command: npx
    args:
      - -y
      - "@akacoder404/dsers-mcp"
    description: DSers AliExpress to Shopify/Wix product import
```

## Hermes Usage Examples

### Direct eBay Queries
```
"Check my eBay API rate limits"
→ Shows daily limit, used, remaining

"Get my eBay active listings"
→ Lists all active listings with SKU, title, price

"Get eBay orders from last 7 days"
→ Lists recent orders with order ID, buyer, total

"Show me order details for eBay order #12345-67890"
→ Full order details including line items

"Upload tracking number DHL123456789 to eBay order #12345-67890"
→ Uploads tracking to eBay
```

### Skill-Based Queries
```
"Optimize my eBay listing for wireless earbuds"
→ marketplace-listing-optimizer skill activates
→ Returns SEO title, keywords, Item Specifics

"Calculate profit margin for:
- Sale: €29.99
- Cost: €8.50
- Shipping: €3.20"
→ contribution-margin-check skill activates
→ Returns real profit and margin percentage

"Analyze my eBay returns (last 3 months):
- Size too small: 12
- Color different: 8
- Quality issue: 3"
→ returns-reason-miner skill activates
→ Returns patterns and actionable fixes
```

### Bulk Operations
```
"Update prices for all Electronics listings: apply 10% discount"
→ Bulk price update via eBay MCP

"Update stock quantity to 100 for SKU-WIRELESS-001"
→ Single SKU update via eBay MCP
```

## Python + Hermes Integration

### Call eBay MCP from Python
```python
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

# Initialize
ebay = eBayMCPIntegration()

# Create listing
result = ebay.create_listing({
    'sku': 'PRODUCT-001',
    'title': 'Wireless Bluetooth Kopfhörer 5.0',
    'price': 29.99,
    'quantity': 50
})

# The bridge calls eBay MCP via Hermes
# hermes_call('ebay_create_inventory_item', params)
```

### Trigger Skills from Python
```python
# In production, call Hermes API
# For now, documented for future integration

# Example: Optimize listing
# hermes_api.query("Optimize eBay listing for: " + product_title)

# Example: Calculate margin
# hermes_api.query(f"Calculate profit margin: Sale {price}, Cost {cost}")
```

## LangGraph + eBay MCP + Hermes

### Full Workflow Integration
```python
# File: mondeora_full_automation.py

class MondeoraSalesAutomation:
    def __init__(self):
        self.ebay_mcp = eBayMCPIntegration()
    
    def fetch_ebay_order(self, state):
        # Call eBay MCP
        order = self.ebay_mcp.get_order_details(state['ebay_order_id'])
        return state
    
    def upload_tracking_to_ebay(self, state):
        # Call eBay MCP
        result = self.ebay_mcp.upload_tracking(
            order_id=state['ebay_order_id'],
            tracking_number=state['tracking_number']
        )
        return state
```

## Verification Commands

### Check eBay MCP Status
```bash
hermes config get mcp_servers.ebay-mondeora
hermes doctor
```

### Check Skills
```bash
hermes skills list | grep ecommerce
ls "$HERMES_HOME/skills/ecommerce-imported/"
```

### Test eBay MCP
```
Hermes query: "Check my eBay API rate limits"
Expected: Daily limit, used, remaining counts
```

## Common Workflows

### Workflow 1: Create Listing
```
1. Hermes: "Optimize eBay listing for: [product]"
   → marketplace-listing-optimizer returns SEO title

2. Python: ebay_mcp.create_listing(optimized_data)
   → eBay MCP creates listing

3. Python: Store listing_id in database
```

### Workflow 2: Process Order
```
1. Python: ebay_mcp.get_orders(days=1)
   → Fetch new orders

2. LangGraph: Run order workflow
   → Check stock, GPSR, create AliExpress order

3. Python/Hermes: Get tracking number
   → Manual approval via Telegram (n8n)

4. Python: ebay_mcp.upload_tracking(order_id, tracking)
   → Upload to eBay
```

### Workflow 3: Bulk Price Optimization
```
1. Hermes: "Analyze pricing for my eBay listings"
   → dynamic-pricing skill returns recommendations

2. Python: ebay_mcp.bulk_update_prices(price_map)
   → Apply recommended prices

3. Monitor: Check conversion rates
```

## Troubleshooting

### eBay MCP Not Connecting
```bash
# Check config
hermes config get mcp_servers.ebay-mondeora

# Check credentials
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
cat .env | grep EBAY

# Test connection
hermes query: "Check my eBay API rate limits"
```

### Skill Not Loading
```bash
# List skills
hermes skills list

# Check skill directory
ls "$HERMES_HOME/skills/ecommerce-imported/"

# Reload skills
hermes reload-skills
```

### Python Bridge Error
```bash
# Test bridge
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 src/integrations/ebay_mcp_bridge.py

# Check environment
python311 -c "import os; print(os.getenv('EBAY_APP_ID'))"
```

## Integration Status
- ✅ eBay MCP: Configured in Hermes
- ✅ 15 Skills: Active in Hermes
- ✅ Python Bridge: src/integrations/ebay_mcp_bridge.py
- ✅ LangGraph: mondeora_full_automation.py
- ⏳ Full Python Integration: In progress
- ⏳ n8n Notifications: Installing
