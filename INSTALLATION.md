# 🎯 MONDEORA DROPSHIPPING - COMPLETE INSTALLATION & USAGE GUIDE

## 📦 SYSTEM STATUS

✅ **Installation Complete**
- All files generated and organized
- Database schema ready
- APIs configured
- Automation engine operational

---

## 🚀 QUICK START

### Option 1: Full Automation (Recommended)
```bash
cd C:\Users\Administrator\Desktop\Mondeora-Drop-System
python main.py
# Select: 1 (Start full automation)
# Opens: http://localhost:5000
```

### Option 2: Automation Only (Background)
```bash
python main.py
# Select: 2 (Start automation only)
```

### Option 3: Dashboard Only
```bash
python main.py
# Select: 3 (Start dashboard only)
# Opens: http://localhost:5000
```

### Option 4: Initial Product Sync
```bash
python main.py
# Select: 4 (Run initial product sync)
```

### Option 5: Test APIs
```bash
python main.py
# Select: 5 (Test API connections)
```

---

## 📁 PROJECT STRUCTURE

```
Mondeora-Drop-System/
│
├── 🔧 CONFIGURATION FILES
│   ├── .env                    # ✅ API keys & settings (CONFIGURED)
│   ├── requirements.txt        # ✅ Python dependencies (READY)
│   ├── README.md              # Documentation
│   └── INSTALLATION.md        # This file
│
├── 🐍 PYTHON CODE
│   ├── main.py                # Main entry point
│   ├── setup.py               # Setup automation
│   │
│   └── src/
│       ├── api/
│       │   ├── ebay_client.py        # eBay API integration
│       │   └── aliexpress_client.py  # AliExpress API integration
│       │
│       ├── database/
│       │   └── models.py             # Database schema
│       │
│       ├── automation/
│       │   └── engine.py             # Automation engine
│       │
│       └── dashboard.py              # Web interface (Flask)
│
├── 📊 DATA & LOGS
│   ├── data/
│   │   └── dropshipping.db          # SQLite database (created)
│   │   └── backups/                 # Database backups
│   │
│   └── logs/
│       └── system.log               # System logs
│
├── 🎮 STARTUP SCRIPTS
│   ├── START_SYSTEM.bat        # Windows shortcut
│   └── start_system.sh         # Linux/Mac shortcut
│
└── 📚 DOCUMENTATION
    ├── README.md              # Main documentation
    └── INSTALLATION.md        # This file
```

---

## ✅ CHECKLIST: What's Already Configured

- [x] eBay API credentials loaded
- [x] AliExpress API credentials loaded
- [x] Database schema created
- [x] Logging system configured
- [x] Flask dashboard setup
- [x] Automation scheduler ready
- [x] Error handling & recovery
- [x] Price optimization logic
- [x] Order automation logic
- [x] Inventory sync logic

---

## 🔐 API CREDENTIALS (In .env)

```
eBay:
  APP_ID: [REDACTED - set EBAY_APP_ID in .env]
  DEV_ID: [REDACTED - set EBAY_DEV_ID in .env]
  CERT_ID: [REDACTED - set EBAY_CERT_ID in .env]
  ACCESS_TOKEN: <EBAY_TOKEN_PLACEHOLDER> (compressed format)

AliExpress:
  APP_KEY: [REDACTED - set ALIEXPRESS_APP_KEY in .env]
  APP_SECRET: [REDACTED - set ALIEXPRESS_APP_SECRET in .env]
  ACCESS_TOKEN: [REDACTED - set ALIEXPRESS_ACCESS_TOKEN in .env]
  REFRESH_TOKEN: [REDACTED - set ALIEXPRESS_REFRESH_TOKEN in .env]
  SELLER_ID: [REDACTED]
  ACCOUNT: [REDACTED - see .env]

Target Market:
  MARKET: Germany (DE)
  CURRENCY: EUR
  MIN_MARGIN: 25%
```

---

## 🎯 HOW THE AUTOMATION WORKS

### Phase 1: Product Sync (Hourly)
```
1. Search AliExpress for top products
2. Check profit margin > 25%
3. Calculate eBay price
4. List on eBay Germany
5. Store product info in database
6. Wait 1 hour → Repeat
```

### Phase 2: Order Automation (Every 15 minutes)
```
1. Check eBay for new orders
2. Extract buyer information
3. Get product details from database
4. Place order on AliExpress
5. Record order mapping
6. Wait 15 minutes → Repeat
```

### Phase 3: Inventory Management (Every 30 minutes)
```
1. Check stock levels on AliExpress
2. Update eBay inventory
3. End listings when out of stock
4. Track stock changes
5. Wait 30 minutes → Repeat
```

### Phase 4: Price Optimization (Every 2 hours)
```
1. Search eBay for competitor prices
2. Analyze price trends
3. Calculate optimal price
4. Update listings if > €2 difference
5. Maintain minimum margin (25%)
6. Wait 2 hours → Repeat
```

---

## 📊 DASHBOARD FEATURES

### Access
```
URL: http://localhost:5000
Available 24/7 when system is running
```

### Metrics Displayed
- **📊 Listed Products**: Total active listings
- **📦 Orders**: Daily & lifetime counts
- **💰 Revenue**: Today's sales total
- **📈 Profit**: Today's profit margin
- **🎯 Conversion**: Sales/Views percentage

### Control Buttons
- `Sync Products Now` - Immediate product refresh
- `Check Orders Now` - Immediate order check
- `Sync Inventory Now` - Immediate stock update
- `Optimize Prices Now` - Immediate price check

### Data Tables
- Recent products (title, price, stock, margin, status)
- Recent orders (ID, product, amount, status, date)

---

## 💾 DATABASE TABLES

### `products`
```sql
- id (primary key)
- aliexpress_product_id
- ebay_item_id
- title, description, category
- image_url
- aliexpress_price, ebay_price, margin_percent
- aliexpress_stock, current_stock
- status (active/paused/sold_out)
- is_listed (boolean)
- views, sales, conversion_rate
- timestamps (created_at, updated_at, last_synced)
```

### `orders`
```sql
- id (primary key)
- ebay_order_id, ebay_item_id
- aliexpress_product_id, aliexpress_order_id
- buyer_email, shipping_address
- quantity, ebay_price, total_amount, profit_amount
- order_status (received/processing/shipped/delivered)
- timestamps (order_date, created_at, updated_at)
```

### `sync_logs`
```sql
- id (primary key)
- sync_type (product/order/inventory)
- status (success/failed/partial)
- total_items, processed_items, failed_items
- error_message, details
- duration_seconds
```

### `price_history`
```sql
- id (primary key)
- product_id, ebay_item_id
- aliexpress_price, ebay_price, margin_percent
- reason (manual/stock_low/competitor_adjustment)
- recorded_at
```

### `competitor_analysis`
```sql
- id (primary key)
- product_category, competitor_id, competitor_url
- product_title
- competitor_price, our_price, price_difference
- analyzed_at
```

### `system_settings`
```sql
- id (primary key)
- setting_key (unique)
- setting_value
- data_type (string/integer/float/boolean)
- updated_at
```

---

## 🔧 CONFIGURATION OPTIONS

### In `.env` file:

```bash
# Product sync frequency (hours)
SYNC_INTERVAL_HOURS=1

# Minimum profit margin (percent)
MIN_MARGIN_PERCENT=25

# Maximum products to manage
MAX_PRODUCTS=500

# Target market
TARGET_MARKET=DE
CURRENCY=EUR

# Logging level
LOG_LEVEL=INFO

# Database path
DATABASE_URL=sqlite:///data/dropshipping.db

# Dashboard port
FLASK_PORT=5000
```

---

## 📈 PRICING EXAMPLE

### Calculation Formula:
```
eBay Price = AliExpress Price × 1.25 × 1.10
           = Product Cost × Margin × Platform Fees

Where:
- 1.25 = 25% profit margin
- 1.10 = 10% eBay fees + payment processing
```

### Example:
```
AliExpress: €10.00
eBay Price: €10 × 1.25 × 1.10 = €13.75

Revenue: €13.75
Cost: €10.00
Profit: €3.75
Margin: 27.3%
```

---

## 🚨 TROUBLESHOOTING

### Problem: "ModuleNotFoundError: No module named 'sqlalchemy'"
**Solution:**
```bash
pip install sqlalchemy==2.0.23
```

### Problem: "Token expired" errors
**Solution:** Tokens auto-refresh, but if stuck:
1. Copy new token from eBay/AliExpress developer console
2. Update .env file
3. Restart system

### Problem: "No products found"
**Solution:**
1. Check AliExpress API response
2. Try different search keywords
3. Verify API credentials
4. Check system logs: `logs/system.log`

### Problem: "eBay listing failed"
**Solution:**
1. Check category ID is correct (currently: 3024)
2. Verify minimum price meets eBay requirements
3. Check profit margin > 25%
4. Review eBay seller account settings

### Problem: Dashboard won't load
**Solution:**
1. Check Flask is running: `python main.py` → Option 3
2. Verify port 5000 is not in use
3. Check: http://127.0.0.1:5000 (not localhost)
4. Review logs for Flask errors

---

## 📝 VIEWING LOGS

### All logs:
```bash
# Windows
type logs\system.log

# Linux/Mac
cat logs/system.log
```

### Last 50 lines:
```bash
# Windows
powershell -Command "Get-Content logs\system.log -Tail 50"

# Linux/Mac
tail -50 logs/system.log
```

### Search for errors:
```bash
# Windows
findstr "ERROR" logs\system.log

# Linux/Mac
grep "ERROR" logs/system.log
```

### Real-time monitoring:
```bash
# Windows
powershell -Command "Get-Content logs\system.log -Wait"

# Linux/Mac
tail -f logs/system.log
```

---

## 🌐 WEB DASHBOARD ACCESS

### Local Network:
```
http://127.0.0.1:5000
http://localhost:5000
```

### From Other Computers (Same Network):
```
http://<YOUR-IP>:5000
# Example: http://192.168.1.100:5000
```

### Production Deployment:
For production use with public IP, set in `main.py`:
```python
dashboard_app.run(host='0.0.0.0', port=5000)
```

---

## 💡 BEST PRACTICES

### ✅ Do's:
- Monitor dashboard daily
- Review logs weekly
- Test API connections monthly
- Back up database monthly
- Adjust pricing based on competition
- Maintain minimum 25% margin
- Keep API credentials secure

### ❌ Don'ts:
- Share API keys publicly
- Edit system files while running
- Set margin below 20%
- List more products than database can handle
- Ignore error messages
- Run multiple instances simultaneously
- Disable logging

---

## 🔄 MAINTENANCE

### Daily:
- Monitor dashboard
- Check new orders
- Review revenue

### Weekly:
- Review price changes
- Check inventory levels
- Analyze sales trends

### Monthly:
- Backup database
- Review API logs
- Test API credentials
- Analyze competitor prices

### Quarterly:
- Review overall performance
- Adjust automation parameters
- Plan strategy updates

---

## 📞 SUPPORT & DEBUGGING

### Enable Debug Mode:
Edit `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

### System Health Check:
```bash
python main.py
# Select option 5: Test API connections
```

### Database Check:
```bash
# View database size
ls -lh data/dropshipping.db

# Check database tables
sqlite3 data/dropshipping.db ".tables"

# Count products
sqlite3 data/dropshipping.db "SELECT COUNT(*) FROM products;"
```

---

## 🎓 LEARNING RESOURCES

### Files to Study:
1. `src/automation/engine.py` - Main automation logic
2. `src/api/ebay_client.py` - eBay API calls
3. `src/api/aliexpress_client.py` - AliExpress API calls
4. `src/database/models.py` - Database structure

### Common Modifications:
- Change sync intervals in `engine.py`
- Adjust margin calculation in `engine.py`
- Add new categories in `.env`
- Customize dashboard HTML in `dashboard.py`

---

## 📦 DEPENDENCIES INSTALLED

```
✅ ebaysdk              - eBay SDK
✅ requests             - HTTP library
✅ python-dotenv        - Environment variables
✅ sqlalchemy           - ORM & database
✅ pandas               - Data analysis
✅ schedule             - Task scheduling
✅ aiohttp              - Async HTTP
✅ Flask                - Web framework
✅ APScheduler          - Advanced scheduling
✅ cryptography         - Secure communications
✅ beautifulsoup4       - HTML parsing
✅ lxml                 - XML parsing
```

---

## 🎯 SUCCESS METRICS

Track these in the dashboard:

- **Products Listed:** Target 100-500
- **Daily Orders:** Target 10-50 (scale dependent)
- **Conversion Rate:** Target 2-5%
- **Average Margin:** Target 25-35%
- **System Uptime:** Target 99%+
- **API Success Rate:** Target 95%+

---

## 🚀 NEXT STEPS

1. **Verify Setup:**
   ```bash
   python main.py
   # Select 5: Test API connections
   ```

2. **Run Initial Sync:**
   ```bash
   python main.py
   # Select 4: Run initial product sync
   ```

3. **Start System:**
   ```bash
   python main.py
   # Select 1: Start full automation
   ```

4. **Monitor Dashboard:**
   ```
   Open: http://localhost:5000
   ```

5. **Track Performance:**
   ```bash
   tail -f logs/system.log
   ```

---

## 📞 SYSTEM STATUS

```
✅ Files Generated:     100%
✅ Database Created:    Ready
✅ APIs Configured:     Ready
✅ Dashboard Setup:     Ready
✅ Automation Ready:    Ready
✅ Logging Enabled:     Active

🚀 SYSTEM READY TO LAUNCH!
```

---

**Mondeora Dropshipping System v1.0**
*Fully Automated eBay ← → AliExpress Integration*

**Start now and grow your dropshipping business! 💼**
