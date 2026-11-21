# Monitoring & Alerting Setup Guide

## 🎯 Overview

Mondeora monitoring system provides:
1. **Sentry:** Error tracking and performance monitoring (optional)
2. **Telegram Alerts:** Real-time notifications for critical events
3. **Health Checks:** System status monitoring

---

## 🔧 Setup

### 1. Sentry (Optional - Recommended for Production)

**Step 1: Create Sentry Account**
- Go to https://sentry.io
- Sign up for free account
- Create new project: "Mondeora Dropshipping"
- Copy DSN (looks like: `https://...@sentry.io/...`)

**Step 2: Add to .env**
```bash
# Add to Mondeora-Drop-System/.env
SENTRY_DSN=https://your-dsn@sentry.io/your-project-id
ENVIRONMENT=production
```

**Step 3: Initialize in Your Scripts**
```python
from monitoring.sentry_client import init_sentry

# At the start of your application
init_sentry()
```

**Cost:** FREE for 5,000 events/month

---

### 2. Telegram Alerts (Recommended - Easy & Free)

**Step 1: Create Telegram Bot**

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions:
   - Bot name: "Mondeora Alerts"
   - Username: `mondeora_alerts_bot` (or any available)
4. Copy Bot Token (looks like: `123456:ABC-DEF...`)

**Step 2: Get Chat ID**

1. Start a chat with your new bot
2. Send any message to it
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id":123456789}` - copy this ID

**Step 3: Add to .env**
```bash
# Add to Mondeora-Drop-System/.env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

**Step 4: Test**
```bash
python test_telegram_alert.py
```

**Cost:** FREE forever! 🎉

---

## 📋 Usage Examples

### Basic Error Tracking

```python
from monitoring.sentry_client import capture_exception, capture_message

try:
    # Your code
    result = risky_operation()
except Exception as e:
    # Automatic error tracking
    capture_exception(e, context={'operation': 'listing', 'product_id': 123})
    raise  # Re-raise after tracking
```

### Telegram Alerts

```python
from monitoring.telegram_alerter import (
    alert_error,
    alert_listing_success,
    alert_stock_out
)

# Alert on error
alert_error(
    error_type='API_FAIL',
    error_message='eBay API returned 503',
    context={'product_id': 123}
)

# Alert on listing success
alert_listing_success(
    product_id=48,
    product_title='Toocki Kabel-Organizer...',
    ebay_item_id='860156291620',
    skus_count=6
)

# Alert on stock out
alert_stock_out(
    product_id=48,
    product_title='Toocki Kabel-Organizer...',
    sku='VAR-48-001',
    ebay_item_id='860156291620'
)
```

### Decorator for Auto-Tracking

```python
from monitoring.sentry_client import track_errors

@track_errors(context={'operation': 'variation_publish'})
def publish_variation_listing(product_id):
    # Your code
    # Errors automatically tracked!
    pass
```

---

## 🔗 Integration Points

### 1. Variation Publisher

**Add to `ebay_variation_publisher.py`:**

```python
from monitoring.sentry_client import init_sentry, capture_exception
from monitoring.telegram_alerter import alert_listing_success, alert_listing_failed

# At module start
init_sentry()

class VariationListingPublisher:
    
    def publish_variation_listing(self, product_id, ...):
        try:
            # ... existing code ...
            
            # Success - alert
            alert_listing_success(
                product_id=product_id,
                product_title=product['title'],
                ebay_item_id=listing_id,
                skus_count=len(created_skus)
            )
            
            return {'success': True, ...}
            
        except Exception as e:
            # Failure - track and alert
            capture_exception(e, context={'product_id': product_id})
            alert_listing_failed(
                product_id=product_id,
                product_title=product['title'],
                error_message=str(e)
            )
            raise
```

---

### 2. Stock Sync Job

**Add to `src/jobs/stock_sync_job.py`:**

```python
from monitoring.sentry_client import init_sentry
from monitoring.telegram_alerter import (
    alert_stock_out,
    alert_stock_sync_complete
)

# At module start
init_sentry()

class StockSyncJob:
    
    def sync_product_stock(self, product):
        # ... existing code ...
        
        for var in product['variations']:
            # ... stock check ...
            
            # Out of stock - alert
            if new_stock == 0 and var['ebay_active']:
                alert_stock_out(
                    product_id=product['id'],
                    product_title=product['title'],
                    sku=var['sku'],
                    ebay_item_id=product['ebay_item_id']
                )
    
    def run_sync(self, max_age_minutes):
        # ... existing code ...
        
        # After sync complete
        alert_stock_sync_complete(
            products_synced=len(products),
            variations_updated=total_updated,
            withdrawn=total_withdrawn,
            reactivated=total_reactivated,
            failed=failed
        )
```

---

## 🧪 Testing

### Test Sentry

```bash
python test_sentry.py
```

Should see:
- Console: "✅ Sentry initialized"
- Sentry dashboard: New error appears

### Test Telegram

```bash
python test_telegram_alert.py
```

Should receive Telegram message instantly!

---

## 📊 Alert Types

| Alert | When | Cooldown | Telegram | Sentry |
|-------|------|----------|----------|--------|
| **Error** | Any exception | 1 hour | ✅ | ✅ |
| **Listing Success** | eBay publish OK | None | ✅ (silent) | - |
| **Listing Failed** | eBay publish fail | 1 hour | ✅ | ✅ |
| **Stock Out** | Variation stock=0 | 1 hour | ✅ (silent) | - |
| **Stock Sync** | Sync complete | 1 hour | ✅ (if changes) | - |
| **Health Check** | System unhealthy | 1 hour | ✅ | ✅ |

**Cooldown:** Prevents spam - same alert won't send twice within cooldown period

---

## ⚙️ Configuration

### Environment Variables

```bash
# Sentry (optional)
SENTRY_DSN=https://...@sentry.io/...
ENVIRONMENT=production  # or 'development', 'staging'

# Telegram (recommended)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

### Alert Settings

**Edit `src/monitoring/config.py`:**

```python
# Alert Thresholds
ALERT_ON_ERRORS: bool = True
ALERT_ON_STOCK_OUT: bool = True
ALERT_ON_LISTING_FAIL: bool = True

# Cooldown (prevent spam)
ALERT_COOLDOWN_SECONDS: int = 3600  # 1 hour
```

---

## 🚀 Deployment Checklist

- [ ] Create Telegram bot (5 min)
- [ ] Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to .env
- [ ] Test: `python test_telegram_alert.py`
- [ ] Integrate into variation publisher
- [ ] Integrate into stock sync job
- [ ] (Optional) Create Sentry account
- [ ] (Optional) Add `SENTRY_DSN` to .env
- [ ] (Optional) Test: `python test_sentry.py`

---

## 📱 Sample Telegram Alerts

### Listing Success
```
✅ NEW LISTING PUBLISHED

Product: Toocki Kabel-Organizer...
Product ID: 48
eBay ID: 860156291620
Variations: 6

🔗 https://www.ebay.de/itm/860156291620
```

### Stock Out
```
📦 STOCK OUT ALERT

Product: Toocki Kabel-Organizer...
SKU: VAR-48-001
Product ID: 48
eBay: https://www.ebay.de/itm/860156291620

⚠️ Listing withdrawn automatically
```

### Error
```
🚨 ERROR ALERT

Type: API_FAIL
Message: eBay API returned 503 Service Unavailable
Time: 2026-11-18 15:30:00

Context:
  • product_id: 48
  • operation: publish
```

---

## 💡 Best Practices

1. **Start with Telegram only**
   - Easy setup
   - Instant notifications
   - Free forever

2. **Add Sentry for production**
   - Better error tracking
   - Performance monitoring
   - Stack traces with context

3. **Adjust cooldowns**
   - Default: 1 hour
   - Increase for noisy alerts
   - Decrease for critical alerts

4. **Use silent notifications**
   - For informational alerts (stock sync, listing success)
   - `disable_notification=True`

5. **Test before deploying**
   - Always test alerts work
   - Check cooldown logic
   - Verify message format

---

## 🆘 Troubleshooting

### "Telegram not configured"
- Check `.env` has `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Verify values are correct (no quotes, no spaces)

### "Sentry not configured"
- Check `.env` has `SENTRY_DSN`
- Verify DSN is correct format
- Try without Sentry first (optional)

### Alerts not received
- Check bot token is valid
- Check chat ID is correct
- Try sending test message: `python test_telegram_alert.py`
- Check alert is not in cooldown

### Too many alerts
- Increase `ALERT_COOLDOWN_SECONDS` in config
- Disable specific alert types
- Use silent notifications

---

**Setup Time:** 10 minutes (Telegram only)  
**Cost:** FREE  
**Maintenance:** None - runs automatically 🎉
