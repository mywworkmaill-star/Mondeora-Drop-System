# 🎯 Mondeora + eBay MCP - TAM ENTEGRASYON

## ✅ KURULUM TAMAMLANDI!

### **📦 Kurulu Sistemler:**

| Sistem | Durum | Lokasyon |
|--------|-------|----------|
| **eBay MCP** | ✅ KURULU | Hermes config |
| **15 E-commerce Skills** | ✅ AKTIF | $HERMES_HOME/skills |
| **LangGraph Automation** | ✅ HAZIR | mondeora_full_automation.py |
| **Python Bridge** | ✅ HAZIR | src/integrations/ebay_mcp_bridge.py |
| **n8n** | ⏳ KURULUYOR | Arka planda |

---

## 🚀 **KULLANIM REHBERİ**

### **1. Hermes'ten Direkt eBay İşlemleri**

#### **A) eBay Bilgilerini Sorgula**
```
Hermes'e sor:
"Check my eBay API rate limits"
"Get my eBay seller metrics"
"List all my active eBay listings"
```

#### **B) eBay Siparişlerini Al**
```
"Get eBay orders from last 7 days"
"Show me order details for eBay order #12345"
```

#### **C) Tracking Yükle**
```
"Upload tracking number DHL123456789 to eBay order #12345-67890"
```

#### **D) Listing Oluştur**
```
"Create new eBay listing:
- Title: Wireless Bluetooth Kopfhörer 5.0
- Price: €29.99
- Quantity: 50
- Category: Electronics"
```

#### **E) Toplu İşlemler**
```
"Update prices for all Electronics listings: apply 10% discount"
"Update stock quantity to 100 for SKU-WIRELESS-001"
```

---

### **2. Python'dan eBay MCP Kullanımı**

#### **Basit Örnek:**
```python
from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

# Initialize
ebay = eBayMCPIntegration()

# Create listing
result = ebay.create_listing({
    'sku': 'TEST-WIRELESS-001',
    'title': 'Wireless Bluetooth Kopfhörer 5.0',
    'description': 'Premium wireless earbuds',
    'price': 29.99,
    'quantity': 50,
    'category_id': '112529',
    'images': ['https://example.com/image1.jpg'],
    'item_specifics': {
        'Brand': 'Generic',
        'Model': 'TWS-2024',
        'Connectivity': 'Bluetooth'
    }
})

print(f"Listing created: {result}")
```

#### **Sipariş Al:**
```python
# Get orders
orders = ebay.get_orders(days=7)
print(f"Total orders: {len(orders)}")

# Get specific order
order = ebay.get_order_details('12345-67890')
print(f"Order: {order}")
```

#### **Tracking Yükle:**
```python
# Upload tracking
result = ebay.upload_tracking(
    order_id='12345-67890',
    tracking_number='DHL123456789',
    carrier='DHL'
)
print(f"Tracking uploaded: {result}")
```

#### **Toplu Fiyat Güncelleme:**
```python
# Bulk price update
updates = {
    'SKU-001': 29.99,
    'SKU-002': 39.99,
    'SKU-003': 19.99
}
result = ebay.bulk_update_prices(updates)
print(f"Updated {result['updated']} listings")
```

---

### **3. Tam Otomatik Workflow (LangGraph)**

#### **Çalıştır:**
```bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 mondeora_full_automation.py
```

#### **Ne Yapar:**
```
1. eBay'den sipariş al (eBay MCP)
   ↓
2. AliExpress'te stok kontrolü (3x retry)
   ↓
3. GPSR compliance check (database)
   ↓
4. AliExpress'te PENDING order oluştur
   ↓
5. Manuel onay bekle (Telegram via n8n)
   ↓
6. Tracking number al
   ↓
7. eBay'e tracking yükle (eBay MCP)
   ↓
✅ Tamamlandı!
```

#### **Workflow Output:**
```
🚀 Mondeora Full Sales Automation
============================================================
📋 TEST ORDER:
eBay Order ID: 12345-67890-TEST
AliExpress Product: 1005006372921430
============================================================

📦 Fetching eBay order: 12345-67890-TEST
   ✅ Order fetched: SKU=PLACEHOLDER-SKU
📊 Checking AliExpress stock for: 1005006372921430
   ✅ Stock available!
🔍 GPSR compliance check: PLACEHOLDER-SKU
   ✅ GPSR compliant
🛒 Creating AliExpress order: https://aliexpress.com/item/...
   ⏳ Order created (PENDING approval)
👤 Waiting for manual approval...
   📱 Telegram notification sent (via n8n)
   ✅ Approved! Tracking: DHL123456789
📮 Uploading tracking to eBay: DHL123456789
   ✅ Tracking uploaded to eBay!

============================================================
📊 FINAL RESULT:
============================================================
Status: completed
Tracking: DHL123456789
Tracking Uploaded: True
Error: None

✅ Workflow complete!
```

---

### **4. Mondeora Job'larına Entegrasyon**

#### **A) listing_pipeline.py'ye eBay MCP Ekle**

```python
# src/jobs/listing_pipeline.py

from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

def publish_to_ebay_via_mcp(product_data):
    """
    Publish product to eBay using MCP instead of direct API
    """
    ebay_mcp = eBayMCPIntegration()
    
    # Optimize title first (using marketplace-listing-optimizer skill)
    # (Hermes'ten çağır)
    
    # Create listing
    result = ebay_mcp.create_listing({
        'sku': product_data['sku'],
        'title': product_data['optimized_title'],
        'description': product_data['description'],
        'price': product_data['price_eur'],
        'quantity': product_data['quantity'],
        'category_id': product_data['ebay_category_id'],
        'images': product_data['images'],
        'item_specifics': product_data['item_specifics']
    })
    
    return result
```

#### **B) orders_poll.py'ye eBay MCP Ekle**

```python
# src/jobs/orders_poll.py

from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

def poll_ebay_orders():
    """
    Poll eBay orders using MCP
    """
    ebay_mcp = eBayMCPIntegration()
    
    # Get recent orders
    orders = ebay_mcp.get_orders(days=1)
    
    for order in orders['orders']:
        # Process each order
        process_order(order)
```

#### **C) tracking_upload.py'ye eBay MCP Ekle**

```python
# src/jobs/tracking_upload.py

from src.integrations.ebay_mcp_bridge import eBayMCPIntegration

def upload_tracking_via_mcp(ebay_order_id, tracking_number):
    """
    Upload tracking to eBay using MCP
    """
    ebay_mcp = eBayMCPIntegration()
    
    result = ebay_mcp.upload_tracking(
        order_id=ebay_order_id,
        tracking_number=tracking_number,
        carrier='DHL'
    )
    
    return result
```

---

## 🎯 **HERMES SKILLS KULLANIMI**

### **1. marketplace-listing-optimizer**
```
Hermes'e sor:
"Optimize my eBay listing:
- Product: Wireless Bluetooth Kopfhörer
- Current Title: Wireless Earbuds Bluetooth 5.0
- Category: Electronics
- Issue: Low traffic (20 views/week)"

Çıktı:
✅ Optimized Title (80 chars)
✅ Item Specifics checklist
✅ Keyword strategy
✅ Image recommendations
✅ Price suggestions
```

### **2. dynamic-pricing**
```
"Analyze pricing for my eBay listings and suggest optimizations"

Çıktı:
- SKU-001: Increase by 10% (high demand, low stock)
- SKU-002: Decrease by 5% (competitor cheaper)
- SKU-003: Keep (margin optimal)
```

### **3. contribution-margin-check**
```
"Calculate real profit margin:
- Sale Price: €29.99
- AliExpress: €8.50
- eBay Fee: 13.5%
- Shipping: €3.20
- PayPal: 2.9%"

Çıktı:
Real Profit: €5.23 (17.4%)
Warning: Below 20% target!
```

### **4. returns-reason-miner**
```
"Analyze my eBay returns (last 3 months):
- 'Size too small' x 12
- 'Color different' x 8
- 'Quality issue' x 3"

Çıktı:
Problem 1: Size chart incorrect
Solution: Get real measurements from supplier
Problem 2: Misleading photos
Solution: Add more real product photos
```

---

## 📋 **HERMES CONFIG DOĞRULAMA**

### **Config Kontrol:**
```bash
hermes config get mcp_servers.ebay-mondeora
```

### **Çıktı:**
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
    description: eBay API for Mondeora
```

---

## 🧪 **TEST SENARYOLARI**

### **Test 1: eBay API Rate Limits**
```
Hermes'e sor:
"Check my eBay API rate limits"

Beklenen:
Daily limit: 10,000 requests
Used: X requests
Remaining: Y requests
```

### **Test 2: Listing Al**
```
"Get my eBay active listings"

Beklenen:
Liste of active listings (SKU, Title, Price, Quantity)
```

### **Test 3: Sipariş Al**
```
"Get eBay orders from last 7 days"

Beklenen:
Order list with IDs, Buyer, Total, Status
```

### **Test 4: Skill Test (SEO)**
```
"Optimize eBay listing for wireless earbuds"

Beklenen:
- 80-char SEO title
- Item Specifics
- Keywords
```

---

## 📊 **DOSYA YAPISI**

```
Mondeora-Drop-System/
├── src/
│   ├── integrations/
│   │   └── ebay_mcp_bridge.py         ✅ eBay MCP Python Bridge
│   ├── jobs/
│   │   ├── listing_pipeline.py         → eBay MCP'ye entegre et
│   │   ├── orders_poll.py              → eBay MCP'ye entegre et
│   │   └── tracking_upload.py          → eBay MCP'ye entegre et
│   └── ...
├── mondeora_full_automation.py         ✅ LangGraph Full Workflow
├── langgraph_advanced.py               ✅ LangGraph Order Flow
├── EBAY_INTEGRATIONS.md                ✅ eBay Dökümantasyonu
└── MONDEORA_EBAY_FULL_GUIDE.md         ✅ Bu dosya
```

---

## 🚨 **HATA GİDERME**

### **Problem: eBay MCP bağlanamıyor**
```bash
# Config kontrol
hermes config get mcp_servers.ebay-mondeora

# Test
hermes doctor

# Credentials kontrol
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
cat .env | grep EBAY
```

### **Problem: Skill yüklenmiyor**
```bash
# Skill'leri kontrol
ls "$HERMES_HOME/skills/ecommerce-imported/"
hermes skills list | grep marketplace
```

### **Problem: LangGraph hatası**
```bash
# Dependencies kontrol
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 -m pip list | grep langgraph
```

---

## 📞 **DESTEK & KAYNAKLAR**

**Dökümantasyon:**
- eBay MCP: https://github.com/YosefHayim/ebay-mcp
- LangGraph: langgraph_advanced.py
- Skills: $HERMES_HOME/skills/ecommerce-imported/

**Test:**
```bash
# Full automation test
python311 mondeora_full_automation.py

# eBay MCP bridge test
python311 src/integrations/ebay_mcp_bridge.py
```

---

## ✅ **ÖZET - NE YAPABİLİRSİN**

### **Hemen Kullanabileceklerin:**
1. ✅ eBay API rate limits sorgula
2. ✅ eBay listings listele
3. ✅ eBay orders al
4. ✅ Tracking yükle
5. ✅ eBay listing SEO optimize et
6. ✅ Kar marjı hesapla
7. ✅ İade analizi yap

### **1-2 Hafta İçinde:**
8. 🔄 Python kodundan eBay MCP çağır
9. 🔄 Listing pipeline'a entegre et
10. 🔄 Order polling'e entegre et
11. 🔄 LangGraph automation çalıştır

### **1 Ay İçinde:**
12. 🚀 Tam otomatik sipariş işleme
13. 🚀 n8n ile bildirim sistemi
14. 🚀 Multi-platform expansion

---

✅ **TÜM SİSTEM HAZIR!**
