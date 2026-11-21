"""
Telegram Alerting System
Send real-time alerts to Telegram
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path

from monitoring.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    ALERT_COOLDOWN_SECONDS,
    is_telegram_enabled
)


class TelegramAlerter:
    """
    Send alerts to Telegram
    """
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.cooldown_file = Path('data/alert_cooldowns.json')
        self.cooldowns = self._load_cooldowns()
    
    def _load_cooldowns(self) -> Dict:
        """Load alert cooldown timestamps"""
        if self.cooldown_file.exists():
            try:
                with open(self.cooldown_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cooldowns(self):
        """Save alert cooldown timestamps"""
        self.cooldown_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cooldown_file, 'w') as f:
            json.dump(self.cooldowns, f, indent=2)
    
    def _is_cooled_down(self, alert_key: str) -> bool:
        """Check if alert is in cooldown period"""
        if alert_key not in self.cooldowns:
            return True  # Not in cooldown
        
        last_sent = datetime.fromisoformat(self.cooldowns[alert_key])
        cooldown_until = last_sent + timedelta(seconds=ALERT_COOLDOWN_SECONDS)
        
        return datetime.now() > cooldown_until
    
    def _set_cooldown(self, alert_key: str):
        """Set cooldown for alert"""
        self.cooldowns[alert_key] = datetime.now().isoformat()
        self._save_cooldowns()
    
    def send_message(
        self,
        message: str,
        alert_key: Optional[str] = None,
        parse_mode: str = 'Markdown',
        disable_notification: bool = False
    ) -> bool:
        """
        Send a message to Telegram
        
        Args:
            message: Message text
            alert_key: Unique key for cooldown (None = no cooldown)
            parse_mode: 'Markdown' or 'HTML'
            disable_notification: Silent notification
        
        Returns:
            True if sent successfully
        """
        
        if not is_telegram_enabled():
            print(f"⚠️  Telegram not configured")
            print(f"   Message: {message}")
            return False
        
        # Check cooldown
        if alert_key and not self._is_cooled_down(alert_key):
            print(f"⏳ Alert {alert_key} in cooldown - skipping")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': disable_notification
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                # Set cooldown
                if alert_key:
                    self._set_cooldown(alert_key)
                
                print(f"✅ Telegram alert sent: {alert_key or 'instant'}")
                return True
            else:
                print(f"❌ Telegram API error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Telegram send failed: {e}")
            return False
    
    def alert_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict = None
    ):
        """
        Send an error alert
        
        Args:
            error_type: Type of error (e.g., 'API_FAIL', 'LISTING_FAIL')
            error_message: Error description
            context: Additional context
        """
        
        alert_key = f"error_{error_type}"
        
        # Build message
        message = f"🚨 *ERROR ALERT*\n\n"
        message += f"*Type:* {error_type}\n"
        message += f"*Message:* {error_message}\n"
        message += f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if context:
            message += f"\n*Context:*\n"
            for key, value in context.items():
                message += f"  • {key}: {value}\n"
        
        self.send_message(message, alert_key=alert_key)
    
    def alert_stock_out(
        self,
        product_id: int,
        product_title: str,
        sku: str,
        ebay_item_id: str = None
    ):
        """
        Alert when product goes out of stock
        
        Args:
            product_id: Product database ID
            product_title: Product title
            sku: SKU that went out of stock
            ebay_item_id: eBay listing ID
        """
        
        alert_key = f"stock_out_{product_id}_{sku}"
        
        message = f"📦 *STOCK OUT ALERT*\n\n"
        message += f"*Product:* {product_title[:50]}\n"
        message += f"*SKU:* {sku}\n"
        message += f"*Product ID:* {product_id}\n"
        
        if ebay_item_id:
            message += f"*eBay:* https://www.ebay.de/itm/{ebay_item_id}\n"
        
        message += f"\n⚠️ Listing withdrawn automatically"
        
        self.send_message(message, alert_key=alert_key, disable_notification=True)
    
    def alert_listing_success(
        self,
        product_id: int,
        product_title: str,
        ebay_item_id: str,
        skus_count: int
    ):
        """
        Alert when listing is published successfully
        
        Args:
            product_id: Product database ID
            product_title: Product title
            ebay_item_id: eBay listing ID
            skus_count: Number of SKUs/variations
        """
        
        message = f"✅ *NEW LISTING PUBLISHED*\n\n"
        message += f"*Product:* {product_title[:50]}\n"
        message += f"*Product ID:* {product_id}\n"
        message += f"*eBay ID:* {ebay_item_id}\n"
        message += f"*Variations:* {skus_count}\n"
        message += f"\n🔗 https://www.ebay.de/itm/{ebay_item_id}"
        
        self.send_message(message, disable_notification=True)
    
    def alert_listing_failed(
        self,
        product_id: int,
        product_title: str,
        error_message: str
    ):
        """
        Alert when listing fails
        
        Args:
            product_id: Product database ID
            product_title: Product title
            error_message: Error description
        """
        
        alert_key = f"listing_fail_{product_id}"
        
        message = f"❌ *LISTING FAILED*\n\n"
        message += f"*Product:* {product_title[:50]}\n"
        message += f"*Product ID:* {product_id}\n"
        message += f"*Error:* {error_message[:200]}\n"
        
        self.send_message(message, alert_key=alert_key)
    
    def alert_stock_sync_complete(
        self,
        products_synced: int,
        variations_updated: int,
        withdrawn: int,
        reactivated: int,
        failed: int
    ):
        """
        Alert after stock sync completes
        
        Args:
            products_synced: Number of products synced
            variations_updated: Number of variations updated
            withdrawn: Number of listings withdrawn
            reactivated: Number of listings reactivated
            failed: Number of failures
        """
        
        # Only send if there are significant changes or failures
        if variations_updated == 0 and failed == 0:
            return  # Skip if nothing changed
        
        message = f"📊 *STOCK SYNC COMPLETE*\n\n"
        message += f"*Products synced:* {products_synced}\n"
        message += f"*Variations updated:* {variations_updated}\n"
        
        if withdrawn > 0:
            message += f"⚠️ *Withdrawn:* {withdrawn}\n"
        
        if reactivated > 0:
            message += f"✅ *Reactivated:* {reactivated}\n"
        
        if failed > 0:
            message += f"❌ *Failed:* {failed}\n"
        
        message += f"\n*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message, alert_key='stock_sync_complete', disable_notification=True)
    
    def alert_health_check(
        self,
        status: str,
        checks: Dict[str, bool],
        issues: list = None
    ):
        """
        Alert health check results
        
        Args:
            status: 'healthy', 'warning', 'critical'
            checks: Dict of check results
            issues: List of issue descriptions
        """
        
        # Only alert if not healthy
        if status == 'healthy':
            return
        
        emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🚨'
        }
        
        message = f"{emoji.get(status, '⚠️')} *HEALTH CHECK: {status.upper()}*\n\n"
        
        for check_name, passed in checks.items():
            status_icon = '✅' if passed else '❌'
            message += f"{status_icon} {check_name}\n"
        
        if issues:
            message += f"\n*Issues:*\n"
            for issue in issues:
                message += f"  • {issue}\n"
        
        message += f"\n*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message, alert_key=f'health_{status}')


# Global instance
alerter = TelegramAlerter()


# Convenience functions
def alert_error(error_type: str, error_message: str, context: Dict = None):
    """Send error alert"""
    alerter.alert_error(error_type, error_message, context)


def alert_stock_out(product_id: int, product_title: str, sku: str, ebay_item_id: str = None):
    """Send stock out alert"""
    alerter.alert_stock_out(product_id, product_title, sku, ebay_item_id)


def alert_listing_success(product_id: int, product_title: str, ebay_item_id: str, skus_count: int):
    """Send listing success alert"""
    alerter.alert_listing_success(product_id, product_title, ebay_item_id, skus_count)


def alert_listing_failed(product_id: int, product_title: str, error_message: str):
    """Send listing failed alert"""
    alerter.alert_listing_failed(product_id, product_title, error_message)
