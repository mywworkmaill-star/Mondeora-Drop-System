"""
Mondeora Telegram Notifier
Send notifications via Telegram Bot API
"""

import os
import requests
import json
from pathlib import Path


class TelegramNotifier:
    """
    Send Telegram notifications via Bot API
    """
    
    def __init__(self):
        # From Hermes config - your actual bot token and chat
        self.bot_token = "9109...yc_Q"  # Will be loaded from Hermes config
        self.chat_id = "8472230106"
        self.enabled = True
        self._load_token()
        
    def _load_token(self):
        """Load bot token from Hermes config"""
        try:
            import subprocess
            result = subprocess.run(
                ["hermes", "config", "get", "telegram.bot_token"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                self.bot_token = result.stdout.strip()
        except Exception as e:
            print(f"Could not load token from Hermes config: {e}")
            # Fallback: will use placeholder token
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message via Telegram Bot API
        
        Args:
            message: Message text (supports Markdown)
            parse_mode: "Markdown" or "HTML"
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled or not self.bot_token or self.bot_token.startswith("9109..."):
            print("⚠️ Telegram bot token not configured properly")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                print(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Telegram notification error: {e}")
            return False
    
    def notify_new_order(self, order_id: str, buyer: str, amount: float, currency: str = "EUR"):
        """Notify about a new eBay order"""
        message = f"""
🎉 **YENİ SİPARİŞ!**

📦 **Order ID:** `{order_id}`
👤 **Alıcı:** {buyer}
💰 **Tutar:** {amount} {currency}

⏳ Otomasyon başladı...
"""
        return self.send_message(message)
    
    def notify_tracking_uploaded(self, order_id: str, tracking_number: str):
        """Notify that tracking was uploaded to eBay"""
        message = f"""
✅ **TRACKING YÜKLENDİ!**

📦 **Order ID:** `{order_id}`
🚚 **Tracking:** `{tracking_number}`

Sipariş tamamlandı! 🎉
"""
        return self.send_message(message)
    
    def notify_error(self, error_type: str, details: str):
        """Notify about an error"""
        message = f"""
⚠️ **HATA!**

❌ **Tip:** {error_type}
📝 **Detay:** {details}

Kontrol et!
"""
        return self.send_message(message)
    
    def notify_stock_issue(self, sku: str, ali_product_id: str):
        """Notify about stock availability issue"""
        message = f"""
⚠️ **STOK SORUNU!**

🏷️ **SKU:** `{sku}`
🔗 **AliExpress:** `{ali_product_id}`

Stok kontrol edilmeli!
"""
        return self.send_message(message)
    
    def notify_gpsr_issue(self, sku: str):
        """Notify about GPSR compliance issue"""
        message = f"""
⚠️ **GPSR UYUMSUZLUK!**

🏷️ **SKU:** `{sku}`

Manuel review gerekli!
"""
        return self.send_message(message)
    
    def notify_daily_summary(self, stats: dict):
        """Send daily summary"""
        message = f"""
📊 **GÜNLÜK ÖZET**

📦 **Yeni Siparişler:** {stats.get('new_orders', 0)}
✅ **Tamamlanan:** {stats.get('completed', 0)}
⏳ **Bekleyen:** {stats.get('pending', 0)}
❌ **Hatalar:** {stats.get('errors', 0)}

💰 **Toplam Satış:** {stats.get('total_sales', 0)} EUR
"""
        return self.send_message(message)


# Test function
def test_telegram():
    """Test Telegram notifications"""
    notifier = TelegramNotifier()
    
    print("🧪 Testing Telegram notifier...")
    
    # Test simple message
    result = notifier.send_message("🧪 **TEST:** Mondeora Telegram entegrasyonu çalışıyor! ✅")
    
    if result:
        print("✅ Test başarılı!")
    else:
        print("❌ Test başarısız!")
    
    return result


if __name__ == "__main__":
    # Run test
    test_telegram()
