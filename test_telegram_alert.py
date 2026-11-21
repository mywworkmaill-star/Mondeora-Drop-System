#!/usr/bin/env python3
"""
Test Telegram Alerting System
"""

import sys
sys.path.insert(0, 'src')

from monitoring.telegram_alerter import (
    TelegramAlerter,
    alert_error,
    alert_listing_success,
    alert_stock_out
)

print("="*70)
print("🧪 TESTING TELEGRAM ALERTING SYSTEM")
print("="*70)

alerter = TelegramAlerter()

# Check configuration
from monitoring.config import is_telegram_enabled

if not is_telegram_enabled():
    print("\n❌ Telegram not configured!")
    print("\n📋 Setup Instructions:")
    print("   1. Create bot with @BotFather on Telegram")
    print("   2. Get bot token")
    print("   3. Send message to bot and get chat ID")
    print("   4. Add to .env:")
    print("      TELEGRAM_BOT_TOKEN=your_token")
    print("      TELEGRAM_CHAT_ID=your_chat_id")
    print("\nSee MONITORING_SETUP_GUIDE.md for details")
    sys.exit(1)

print("\n✅ Telegram configured")
print(f"   Bot token: {alerter.bot_token[:20]}...")
print(f"   Chat ID: {alerter.chat_id}")

# Test 1: Simple message
print("\n1️⃣ TEST: Simple message")
success = alerter.send_message(
    "🧪 *Test Message*\n\nThis is a test from Mondeora monitoring system",
    alert_key=None  # No cooldown for test
)

if success:
    print("   ✅ Message sent! Check your Telegram")
else:
    print("   ❌ Failed to send message")

# Test 2: Error alert
print("\n2️⃣ TEST: Error alert")
alert_error(
    error_type='TEST_ERROR',
    error_message='This is a test error message',
    context={'test': True, 'product_id': 999}
)

# Test 3: Listing success alert
print("\n3️⃣ TEST: Listing success alert")
alert_listing_success(
    product_id=999,
    product_title='Test Product - Kabel-Organizer (Test)',
    ebay_item_id='123456789012',
    skus_count=6
)

# Test 4: Stock out alert
print("\n4️⃣ TEST: Stock out alert")
alert_stock_out(
    product_id=999,
    product_title='Test Product - Kabel-Organizer (Test)',
    sku='TEST-SKU-001',
    ebay_item_id='123456789012'
)

print("\n" + "="*70)
print("✅ TESTS COMPLETE")
print("="*70)
print("\n📱 Check your Telegram for 4 messages:")
print("   1. Test message")
print("   2. Error alert")
print("   3. Listing success alert")
print("   4. Stock out alert")
print("\nNote: Alerts may be in cooldown if run multiple times")
