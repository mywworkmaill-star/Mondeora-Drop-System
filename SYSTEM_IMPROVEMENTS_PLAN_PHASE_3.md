# System Improvements Plan - Phase 3: Error-Free System

## 🎯 GOAL: 100% Hatasız Otomatik Dropshipping Sistemi

**Date:** 2026-11-18  
**Current Status:** Phase 1 & 2 Complete (Quality Gate, Link Validator, Variation Listings)  
**Remaining Issues:** 8 kritik/orta/düşük seviye sorun

---

## 📊 DISCOVERED ISSUES & SOLUTIONS

### 🔴 HIGH PRIORITY (3 issues)

---

#### 1. MANUAL VARIATION INPUT ONLY

**Problem:**
- User must manually enter each variation (color, size, length)
- AliExpress API `sku_property_values` field is empty
- 10+ variations = 10 manual entries = error-prone & time-consuming

**Research Findings:**
- **Apify AliExpress Scraper:** Paid service ($49/month) extracts variants, stock, shipping
- **Browser CDP Network Log:** `mtop.aliexpress.pdp.pc.query` JSONP response contains all SKU data
- **Playwright Stealth:** Bypass bot detection with stealth plugin

**Solution:** Browser Automation Variant Extractor

```python
# src/scrapers/aliexpress_variant_scraper.py
from playwright.sync_api import sync_playwright

def extract_variants_from_product_page(product_url: str) -> List[Dict]:
    """
    Extract variants from AliExpress product page via CDP
    
    Returns:
        [
            {'color': 'Black', 'size': 'S', 'price': 18.25, 'stock': 100},
            {'color': 'Black', 'size': 'M', 'price': 19.99, 'stock': 50},
            ...
        ]
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)...'
        )
        
        # Listen for JSONP response
        variants_data = None
        
        def handle_response(response):
            if 'mtop.aliexpress.pdp.pc.query' in response.url:
                try:
                    body = response.json()
                    # Extract SKU properties
                    skus = body['data']['skuModule']['skuPriceList']
                    # Parse variants
                    # ...
                except:
                    pass
        
        page = context.new_page()
        page.on('response', handle_response)
        page.goto(product_url, wait_until='networkidle')
        
        return variants_data
```

**Dependencies:**
```bash
pip install playwright
playwright install chromium
pip install playwright-stealth  # Optional: bypass detection
```

**Time:** 2 days  
**Impact:** Eliminates 90% manual work for variation products  
**Risk:** AliExpress anti-bot measures (use proxies + stealth)

---

#### 2. NO CLEANUP ON FAILED PUBLISH

**Problem:**
- If `publish_offer_by_inventory_item_group` fails (Step 4), inventory items (Step 1) and offers (Step 2) remain in eBay
- Orphaned SKUs accumulate in eBay Inventory
- Manual cleanup required

**Research Findings:**
- eBay API best practice: Validate before publish (`operationMode: VALIDATE`)
- Transaction pattern: Try-Except-Rollback
- Delete via DELETE `/inventory_item/{sku}` cascades to offers

**Solution:** Transaction-Like Rollback System

```python
# ebay_variation_publisher.py - Updated publish method

def publish_variation_listing_safe(self, product_id):
    """
    Publish with automatic rollback on failure
    """
    created_skus = []
    created_offers = []
    created_group = None
    
    try:
        # Step 1: Create inventory items
        for var in variations:
            self.ebay._request('PUT', f'/inventory_item/{sku}', ...)
            created_skus.append(sku)
        
        # Step 2: Create offers
        for var in variations:
            offer_id = self.ebay._request('POST', '/offer', ...)
            created_offers.append((sku, offer_id))
        
        # Step 3: Create group
        self.ebay.create_inventory_item_group(group_key, ...)
        created_group = group_key
        
        # Step 4: Publish (THE RISKY PART)
        result = self.ebay.publish_offer_by_inventory_item_group(group_key)
        
        return {'success': True, 'listing_id': result['listing_id']}
        
    except Exception as e:
        print(f"❌ PUBLISH FAILED: {e}")
        print(f"🔄 ROLLING BACK...")
        
        # Rollback: Delete in reverse order
        if created_group:
            try:
                self.ebay._request('DELETE', f'/inventory_item_group/{created_group}')
                print(f"   ✅ Deleted group: {created_group}")
            except:
                pass
        
        for sku, offer_id in reversed(created_offers):
            try:
                self.ebay._request('DELETE', f'/offer/{offer_id}')
                print(f"   ✅ Deleted offer: {offer_id}")
            except:
                pass
        
        for sku in reversed(created_skus):
            try:
                self.ebay._request('DELETE', f'/inventory_item/{sku}')
                print(f"   ✅ Deleted SKU: {sku}")
            except:
                pass
        
        print(f"🔄 ROLLBACK COMPLETE")
        
        return {'success': False, 'error': str(e), 'rollback': 'complete'}
```

**Time:** 4 hours  
**Impact:** No orphaned SKUs, clean error recovery  
**Risk:** None (improves reliability)

---

#### 3. NO REAL-TIME STOCK SYNC

**Problem:**
- Variations use hardcoded stock (999) or manual input
- No sync with AliExpress live stock
- **Overselling risk:** Customer orders but AliExpress out of stock

**Research Findings:**
- Poll AliExpress stock every 15-30 minutes (cron job)
- Priority queue: High-velocity products every 5 min, long-tail every 30 min
- Threshold alerts: When stock < daily_sales × shipping_days
- Auto-deactivate listings when stock = 0

**Solution:** Automated Stock Sync Job

```python
# src/jobs/stock_sync_job.py

import schedule
import time
from api.aliexpress_client import AliExpressAPIClient
from api.ebay_client import eBayAPIClient

class StockSyncJob:
    def __init__(self):
        self.ali = AliExpressAPIClient()
        self.ebay = eBayAPIClient()
    
    def sync_all_variations(self):
        """Sync stock for all variation products"""
        
        conn = sqlite3.connect('data/dropshipping.db')
        cursor = conn.cursor()
        
        # Get all variation products with eBay listings
        cursor.execute('''
            SELECT DISTINCT product_id, aliexpress_product_id
            FROM product_variations
            WHERE product_id IN (
                SELECT id FROM products 
                WHERE is_variation_product = 1 
                AND ebay_item_id IS NOT NULL
            )
        ''')
        
        products = cursor.fetchall()
        
        print(f"📊 Syncing stock for {len(products)} variation products...")
        
        for product_id, ali_id in products:
            # Get AliExpress stock
            ali_data = self.ali.get_product_details(ali_id)
            skus = ali_data.get('skus', [])
            
            # Map to our SKUs
            cursor.execute('SELECT sku, color, length FROM product_variations WHERE product_id = ?', (product_id,))
            our_skus = cursor.fetchall()
            
            for our_sku, color, length in our_skus:
                # Find matching AliExpress SKU
                matching_sku = None
                for ali_sku in skus:
                    # Match by properties
                    # (simplified - need real matching logic)
                    if matches_properties(ali_sku, color, length):
                        matching_sku = ali_sku
                        break
                
                if matching_sku:
                    new_stock = matching_sku.get('sku_available_stock', 0)
                    
                    # Update eBay if changed
                    if new_stock == 0:
                        # Out of stock - withdraw listing
                        self.ebay._request('POST', f'/offer/{offer_id}/withdraw')
                        print(f"   ⚠️  Withdrawn: {our_sku} (out of stock)")
                    else:
                        # Update quantity
                        self.ebay.update_inventory(our_sku, new_stock)
                        print(f"   ✅ Updated: {our_sku} → {new_stock} units")
                    
                    # Update database
                    cursor.execute('UPDATE product_variations SET stock = ? WHERE sku = ?', (new_stock, our_sku))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Stock sync complete")

# Scheduler
def run_stock_sync():
    job = StockSyncJob()
    
    # Every 30 minutes
    schedule.every(30).minutes.do(job.sync_all_variations)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run_stock_sync()
```

**Cron Setup:**
```bash
# Add to Hermes cron or system cron
python src/jobs/stock_sync_job.py &
```

**Dependencies:**
```bash
pip install schedule
```

**Time:** 1 day  
**Impact:** Prevents overselling, keeps stock accurate  
**Risk:** AliExpress API rate limits (use caching)

---

### 🟡 MEDIUM PRIORITY (4 issues)

---

#### 4. HARDCODED EBAY POLICY IDs

**Problem:**
- `ebay_variation_publisher.py` has hardcoded IDs (263035514017, etc.)
- Breaks if policies change or for different eBay accounts

**Solution:** Auto-Fetch & Cache Policies

```python
# src/utils/ebay_policy_cache.py

def get_or_cache_policies(ebay_client):
    """Fetch policies once, cache in database"""
    
    cache_file = 'data/ebay_policies_cache.json'
    
    # Check cache (expire after 7 days)
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
            if time.time() - data['cached_at'] < 7 * 86400:
                return data['policies']
    
    # Fetch from eBay
    fulfillment = ebay_client._request('GET', '/sell/account/v1/fulfillment_policy', params={'marketplace_id': 'EBAY_DE'})
    payment = ebay_client._request('GET', '/sell/account/v1/payment_policy', params={'marketplace_id': 'EBAY_DE'})
    return_policy = ebay_client._request('GET', '/sell/account/v1/return_policy', params={'marketplace_id': 'EBAY_DE'})
    
    policies = {
        'fulfillment_policy_id': fulfillment['fulfillmentPolicies'][0]['fulfillmentPolicyId'],
        'payment_policy_id': payment['paymentPolicies'][0]['paymentPolicyId'],
        'return_policy_id': return_policy['returnPolicies'][0]['returnPolicyId']
    }
    
    # Cache
    with open(cache_file, 'w') as f:
        json.dump({'policies': policies, 'cached_at': time.time()}, f)
    
    return policies
```

**Time:** 2 hours  
**Impact:** Portable across eBay accounts  

---

#### 5. NO VARIATION PRE-PUBLISH VALIDATION

**Problem:**
- Quality Gate only validates single listings
- Variation listings skip validation
- Bad variation data can reach eBay API

**Solution:** Extend Quality Gate for Variations

```python
# src/quality/listing_validator.py - Add method

def validate_variation_listing(self, variations: List[Dict], base_aspects: Dict) -> Dict:
    """
    Validate all variations before publish
    
    Checks:
    - Every SKU has required dimensions (Color, Length, etc.)
    - Prices are consistent and logical
    - Stock is non-negative
    - Images exist for all SKUs
    """
    errors = []
    warnings = []
    score = 100
    
    # Check 1: All SKUs have variation-specific aspects
    for var in variations:
        if not var.get('color') and not var.get('size') and not var.get('length'):
            errors.append(f"❌ SKU {var['sku']} has no variation dimensions")
            score -= 20
    
    # Check 2: Price consistency
    prices = [v['sell_price'] for v in variations]
    if max(prices) / min(prices) > 3.0:
        warnings.append(f"⚠️  Price range too wide: €{min(prices):.2f} - €{max(prices):.2f}")
    
    # Check 3: Stock
    for var in variations:
        if var.get('stock', 0) < 0:
            errors.append(f"❌ SKU {var['sku']} has negative stock")
            score -= 10
    
    # Check 4: Images
    no_image_count = sum(1 for v in variations if not v.get('image_url'))
    if no_image_count > 0:
        warnings.append(f"⚠️  {no_image_count}/{len(variations)} SKUs have no images")
    
    return {
        'status': 'FAIL' if score < 80 else 'PASS',
        'score': score,
        'errors': errors,
        'warnings': warnings
    }
```

**Time:** 3 hours  
**Impact:** Catches variation errors before eBay publish  

---

#### 6. NO AUTOMATED PRICE OPTIMIZATION

**Problem:**
- Prices are manual or simple 2.5× markup
- No competitor analysis
- May price too high (lose sales) or too low (lose profit)

**Solution:** eBay Competitor Price Scraper

```python
# src/pricing/competitor_analyzer.py

def get_competitor_prices(title: str, category_id: str) -> Dict:
    """
    Search eBay for similar products and analyze prices
    
    Returns:
        {
            'min': 15.99,
            'max': 35.99,
            'median': 24.99,
            'recommended': 23.99
        }
    """
    # Use eBay Browse API
    ebay_rest = eBayRESTClient()
    
    # Search similar products
    results = ebay_rest.search_products(
        keyword=title[:50],  # First 50 chars
        category=category_id,
        limit=50
    )
    
    # Extract prices
    prices = []
    for item in results:
        price = item.get('price', {}).get('value')
        if price:
            prices.append(float(price))
    
    if not prices:
        return None
    
    prices.sort()
    
    return {
        'min': prices[0],
        'max': prices[-1],
        'median': prices[len(prices)//2],
        'recommended': prices[int(len(prices) * 0.4)]  # 40th percentile (competitive)
    }
```

**Time:** 4 hours  
**Impact:** Data-driven pricing, maximize profit & sales  

---

#### 7. MANUAL CATEGORY SELECTION

**Problem:**
- Category ID hardcoded (43504)
- Wrong category = poor SEO

**Solution:** Use eBay Taxonomy API + Keyword Matching

```python
def suggest_category(title: str) -> str:
    """
    Suggest eBay category from title keywords
    """
    keywords = {
        'kabel': '43504',  # Cable organizer
        'werkzeug': '11700',  # Tool storage
        'küche': '20668',  # Kitchen organization
        'bad': '20492',  # Bathroom
        # etc.
    }
    
    for keyword, category_id in keywords.items():
        if keyword in title.lower():
            return category_id
    
    return '43504'  # Default
```

**Time:** 2 hours  
**Impact:** Better SEO, correct categorization  

---

### 🟢 LOW PRIORITY (1 issue)

#### 8. NO DUPLICATE VARIATION CHECK

**Solution:** Check before `add_variations()`

```python
def add_variations(self, product_id, ...):
    # Check if already has variations
    existing = self.get_variations(product_id)
    if existing:
        raise ValueError(f"Product {product_id} already has {len(existing)} variations. Delete first.")
    # ...
```

**Time:** 30 min  

---

## 🧪 TESTING & MONITORING FRAMEWORK

### Automated Testing (Pytest)

```bash
pip install pytest pytest-playwright allure-pytest
```

**Test Structure:**
```
tests/
├── test_variation_manager.py
├── test_variation_publisher.py
├── test_stock_sync.py
├── test_quality_gate.py
└── test_ebay_api_integration.py
```

**Example Test:**
```python
# tests/test_variation_publisher.py

def test_rollback_on_failed_publish(mock_ebay_api):
    """Test that SKUs are deleted if publish fails"""
    
    # Mock publish to fail
    mock_ebay_api.publish_offer_by_inventory_item_group.side_effect = Exception("eBay error")
    
    publisher = VariationListingPublisher()
    result = publisher.publish_variation_listing_safe(48)
    
    assert result['success'] == False
    assert result['rollback'] == 'complete'
    
    # Verify SKUs were deleted
    # ...
```

---

### Error Monitoring (Sentry)

```bash
pip install sentry-sdk
```

```python
# src/__init__.py

import sentry_sdk

sentry_sdk.init(
    dsn="https://your-dsn@sentry.io/project-id",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# Automatic error tracking for all uncaught exceptions
```

**Features:**
- Real-time error alerts (Slack/Email)
- Stack traces with context
- Performance monitoring
- Release tracking

---

### Application Monitoring (Prometheus + Grafana)

**Metrics to Track:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
listings_created = Counter('listings_created_total', 'Total listings created')
listings_failed = Counter('listings_failed_total', 'Total listing failures')

# Gauges
active_listings = Gauge('active_listings', 'Current active listings')
out_of_stock_products = Gauge('out_of_stock_products', 'Products out of stock')

# Histograms
listing_duration = Histogram('listing_duration_seconds', 'Time to create listing')
```

**Dashboard Panels:**
1. Listing Success Rate (last 24h)
2. Average Listing Time
3. Stock Sync Status
4. Error Rate by Type
5. Active Products by Category

---

## 📅 IMPLEMENTATION TIMELINE

### Week 1 (Critical - 5 days)
- **Day 1-2:** AliExpress Variant Scraper (Playwright + CDP)
- **Day 3:** Transaction Rollback System
- **Day 4-5:** Stock Sync Job + Cron Setup

### Week 2 (Medium - 5 days)
- **Day 1:** Policy Auto-Fetch & Cache
- **Day 2:** Variation Pre-Publish Validation
- **Day 3:** Competitor Price Analyzer
- **Day 4:** Category Auto-Selection
- **Day 5:** Testing Framework Setup

### Week 3 (Monitoring - 3 days)
- **Day 1:** Sentry Integration
- **Day 2:** Prometheus Metrics
- **Day 3:** Grafana Dashboards

**Total:** 13 days (~2 weeks)

---

## 🎯 EXPECTED RESULTS

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Manual Variation Input** | 100% | 10% | -90% |
| **Orphaned SKUs** | High | Zero | -100% |
| **Overselling Risk** | High | Low | -80% |
| **Error Detection Time** | Manual | Real-time | ∞ |
| **System Uptime** | Unknown | Monitored | +100% |
| **Price Optimization** | None | Automated | ∞ |

---

## 💰 COST ANALYSIS

| Component | Cost | Notes |
|-----------|------|-------|
| Playwright | Free | Open-source |
| Sentry | $26/month | 50K events/month |
| Prometheus + Grafana | Free | Self-hosted |
| Stock Sync Cron | Free | Local scheduler |
| eBay API Calls | Free | Included in fees |
| **Total** | **~$26/month** | **Minimal cost** |

---

## ✅ SUCCESS CRITERIA

**Phase 3 is complete when:**
1. ✅ Variation products can be created without manual input (scraper working)
2. ✅ Zero orphaned SKUs after failed publishes (rollback working)
3. ✅ Stock syncs every 30 minutes automatically (cron job running)
4. ✅ Errors reported to Sentry in real-time (monitoring working)
5. ✅ 90% test coverage with Pytest (testing framework complete)

---

## 📚 DEPENDENCIES

```bash
# requirements.txt additions
playwright==1.40.0
playwright-stealth==1.0.6
schedule==1.2.0
sentry-sdk==1.38.0
pytest==7.4.3
pytest-playwright==0.4.3
allure-pytest==2.13.2
prometheus-client==0.19.0
```

---

**Author:** Claude (Hermes Agent)  
**Date:** 2026-11-18  
**Phase:** 3 / 3  
**Priority:** HIGH (Error-Free System)
