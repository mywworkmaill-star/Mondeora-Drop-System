"""
SİPARİŞ BİLDİRİM SİSTEMİ
Yeni eBay siparişi geldiğinde veya pending AliExpress siparişi olduğunda bildirim gönderir
"""
import json
import smtplib
import os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class OrderNotifier:
    def __init__(self):
        self.pending_orders_file = Path('data/pending_aliexpress_orders.jsonl')
        self.notification_log = Path('data/notifications_sent.jsonl')
        
    def check_pending_orders(self):
        """Bekleyen siparişleri kontrol et"""
        if not self.pending_orders_file.exists():
            return []
        
        pending = []
        with open(self.pending_orders_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    pending.append(json.loads(line))
        
        return pending
    
    def send_console_notification(self, pending_orders):
        """Konsol bildirimi (her zaman çalışır)"""
        print("\n" + "="*70)
        print("🔔 YENİ SİPARİŞ BİLDİRİMİ!")
        print("="*70)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📦 Bekleyen Sipariş Sayısı: {len(pending_orders)}")
        print()
        
        for i, order in enumerate(pending_orders[-5:], 1):  # Son 5 sipariş
            print(f"Sipariş #{i}:")
            print(f"  🔗 AliExpress: {order['order_url']}")
            print(f"  📍 Adres: {order['shipping_address'][:50]}...")
            print(f"  ⏱️  {order['timestamp']}")
            print()
        
        print("="*70)
        print("⚠️  AKSİYON GEREKLİ:")
        print("   1. data/pending_aliexpress_orders.jsonl dosyasını aç")
        print("   2. Her sipariş için AliExpress linkini aç")
        print("   3. Adresi kopyala ve siparişi tamamla")
        print("="*70)
        print()
    
    def send_file_notification(self, pending_orders):
        """Masaüstüne HTML notification dosyası oluştur"""
        desktop = Path.home() / 'Desktop'
        notification_file = desktop / f'MONDEORA_SIPARIS_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mondeora Sipariş Bildirimi</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 20px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
        }}
        .order-card {{
            background: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .order-card h3 {{
            color: #667eea;
            margin-top: 0;
        }}
        .btn {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 10px;
        }}
        .btn:hover {{
            background: #764ba2;
        }}
        .address {{
            background: #f8f9fa;
            padding: 15px;
            border-left: 4px solid #667eea;
            margin: 10px 0;
            white-space: pre-wrap;
            font-family: monospace;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔔 Mondeora Sipariş Bildirimi</h1>
        <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <h2>{len(pending_orders)} Bekleyen Sipariş</h2>
    </div>
    
    <div class="warning">
        <strong>⚠️ AKSİYON GEREKLİ:</strong>
        <p>Aşağıdaki siparişleri manuel olarak AliExpress'te tamamlamanız gerekiyor.</p>
    </div>
"""
        
        for i, order in enumerate(pending_orders, 1):
            html_content += f"""
    <div class="order-card">
        <h3>📦 Sipariş #{i}</h3>
        <p><strong>Ürün ID:</strong> {order['product_id']}</p>
        <p><strong>Miktar:</strong> {order['quantity']}</p>
        <p><strong>Zaman:</strong> {order['timestamp']}</p>
        
        <a href="{order['order_url']}" class="btn" target="_blank">🔗 AliExpress'te Aç</a>
        
        <h4>📍 Teslimat Adresi:</h4>
        <div class="address">{order['shipping_address']}</div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(notification_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Masaüstüne bildirim dosyası oluşturuldu:")
        print(f"   {notification_file}")
        
        return notification_file
    
    def log_notification(self, notification_type, details):
        """Gönderilen bildirimleri logla"""
        self.notification_log.parent.mkdir(exist_ok=True)
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': notification_type,
            'details': details
        }
        
        with open(self.notification_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def run(self):
        """Ana bildirim döngüsü"""
        print("\n🔔 Sipariş bildirim sistemi başlatıldı...")
        
        pending = self.check_pending_orders()
        
        if not pending:
            print("📭 Bekleyen sipariş yok")
            return 0
        
        print(f"📦 {len(pending)} bekleyen sipariş bulundu!")
        
        # Konsol bildirimi
        self.send_console_notification(pending)
        
        # Masaüstü HTML dosyası
        notification_file = self.send_file_notification(pending)
        
        # Log kaydet
        self.log_notification('pending_orders', {
            'count': len(pending),
            'notification_file': str(notification_file)
        })
        
        return len(pending)


if __name__ == "__main__":
    notifier = OrderNotifier()
    notifier.run()
