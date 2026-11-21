# 🎯 eBay Entegrasyonları - Mondeora

## ✅ Kurulum Tamamlananlar

### 1. **Hermes Skills (13 Adet - Hazır)**

| Skill | Kullanım | Kategori |
|-------|----------|----------|
| **marketplace-listing-optimizer** | eBay/Amazon/Etsy listing SEO, Cassini optimization | eBay SEO ⭐ |
| dropshipping-integration | AliExpress → eBay/Shopify entegrasyonu | Fulfillment |
| dynamic-pricing | Otomatik fiyat optimizasyonu | Pricing |
| order-fulfillment-workflow | Sipariş işleme workflow'u | Operations |
| inventory-tracking | Stok takibi ve senkronizasyon | Inventory |
| low-stock-alerts | Düşük stok uyarıları | Inventory |
| checkout-friction-finder | Checkout sorunlarını tespit et | Conversion |
| product-page-conversion-review | Ürün sayfası optimizasyonu | Conversion |
| returns-reason-miner | İade sebeplerini analiz et | Analytics |
| contribution-margin-check | Kar marjı analizi | Finance |
| shipping-economics-review | Kargo maliyeti analizi | Shipping |
| inventory-risk-brief | Stok riski raporu | Risk |

**Yeni Eklenen:**
- ✅ **marketplace-listing-optimizer** - eBay Cassini SEO optimization

**Kullanım:**
```
Hermes'e sor:
"Optimize my eBay listing for this product"
"Write an eBay SEO title (80 chars) for wireless earbuds"
"Complete eBay Item Specifics for better Cassini ranking"
```

---

### 2. **eBay MCP Server'lar (4 Adet)**

#### **A) ebay-mcp (YosefHayim) - TAM KAPSAMLI ⭐⭐⭐**
- **379 tools** covering ALL eBay Sell, Commerce, Developer APIs
- **Kapsamı:**
  - ✅ Inventory (ürün ekleme, güncelleme, varyantlar)
  - ✅ Fulfillment (sipariş yönetimi, tracking)
  - ✅ Marketing (Promoted Listings, kampanyalar)
  - ✅ Analytics (satış raporları, metrikler)
  - ✅ Finance (ödeme, faturalar)
  - ✅ Messaging (alıcı mesajları)
  - ✅ Taxonomy (kategori ağacı)
  - ✅ Legacy Trading API

**Config'e eklendi:**
```yaml
mcp_servers:
  ebay-full:
    command: npx
    args: ["-y", "ebay-mcp"]
    description: Full eBay API MCP - 379 tools
```

**Kurulum:**
```bash
# İlk setup (OAuth)
npx ebay-mcp setup

# Env variables (config'den veya .env)
EBAY_CLIENT_ID=your_app_id
EBAY_CLIENT_SECRET=your_cert_id
EBAY_ENVIRONMENT=sandbox  # veya production
EBAY_REDIRECT_URI=your_runame
EBAY_USER_REFRESH_TOKEN=auto_generated
```

**Kullanım:**
```
Hermes'ten:
"Check my eBay API rate limits"
"List all my active eBay listings"
"Create a new eBay listing for this product"
"Get eBay order details for order #12345"
"Upload tracking number to eBay order"
```

---

#### **B) @ebay/npm-public-api-mcp - RESMİ eBay MCP ⭐⭐**
- **Resmi eBay MCP server** (OpenAPI support)
- **Kullanım:** Public API'ler için (Browse, Taxonomy, Catalog)

**Config'e eklendi:**
```yaml
mcp_servers:
  ebay-official:
    command: npx
    args: ["-y", "@ebay/npm-public-api-mcp"]
    description: Official eBay MCP with OpenAPI
```

---

#### **C) DSers Dropshipping MCP**
- **AliExpress → Shopify/Wix** import automation
- **Kullanım:** DSers hesabı üzerinden ürün import

**Config'e eklendi:**
```yaml
mcp_servers:
  dsers-dropshipping:
    command: npx
    args: ["-y", "@akacoder404/dsers-mcp"]
```

---

#### **D) CJ Dropshipping Product Scout**
- **CJDropshipping** ürün araması + freight calculator
- **Remote MCP:** https://mcp.youxiu.shop/mcp

**Config'e eklendi:**
```yaml
mcp_servers:
  dropshipping-product-scout:
    type: http
    url: https://mcp.youxiu.shop/mcp
```

---

### 3. **LangGraph Order Workflow**
Konum: `C:\Users\Administrator\Desktop\Mondeora-Drop-System\langgraph_advanced.py`

**Ne yapar:**
- Conditional logic (if/else akışları)
- Retry mekanizması (API hataları için)
- Manuel onay noktaları (Telegram entegrasyonu)
- State tracking (sipariş hangi aşamada?)

**Test:**
```bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 langgraph_advanced.py
```

---

## 🚀 Kullanım Senaryoları

### **Senaryo 1: eBay Listing SEO Optimization**
```
Hermes'e sor:
"Optimize this eBay listing for better Cassini ranking:
Title: Wireless Bluetooth Earbuds
Category: Electronics > Headphones
Current traffic: Low
Current conversion: 2%"

Output:
1. ✅ Keyword research (primary, secondary, long-tail)
2. ✅ Optimized 80-char title
3. ✅ Item Specifics checklist
4. ✅ Description structure
5. ✅ Image plan
6. ✅ Conversion fixes (price, shipping, returns)
```

---

### **Senaryo 2: Full eBay Automation (ebay-mcp)**
```bash
# 1. İlk setup
npx ebay-mcp setup

# 2. Hermes'ten kullan
Hermes: "List all my eBay active listings"
Hermes: "Create a new eBay listing:
  - Title: Wireless Earbuds
  - Price: $29.99
  - Quantity: 100
  - Category: Electronics"

Hermes: "Upload tracking UPS123456789 to eBay order #12345"
```

---

### **Senaryo 3: Mondeora + eBay MCP Entegrasyonu**
```python
# src/jobs/ebay_automation_langgraph.py

from langgraph_advanced import build_advanced_workflow
# ebay-mcp Hermes'te aktif olacak

# Workflow:
# 1. eBay sipariş geldi (ebay-mcp: get order)
# 2. AliExpress'te stok kontrolü (LangGraph node)
# 3. GPSR compliance check (database)
# 4. AliExpress pending order oluştur
# 5. Manuel onay (Telegram via n8n)
# 6. Tracking eBay'e yükle (ebay-mcp: upload tracking)
```

---

## 📊 eBay Cassini SEO Checklist

### **Kullanım (marketplace-listing-optimizer skill):**
```
Hermes'e sor:
"Audit my eBay listing for Cassini optimization"
```

### **Çıktı:**
- [ ] **Title:** 70-80 chars, keyword-rich, no spam
- [ ] **Item Specifics:** 100% complete (mandatory + recommended)
- [ ] **Category:** Exact match to eBay taxonomy
- [ ] **Images:** 12 photos (main on white, infographics, lifestyle)
- [ ] **Description:** 300+ words HTML
- [ ] **Shipping:** Free/Fast shipping (boosts ranking)
- [ ] **Returns:** 30-day free returns (trust signal)
- [ ] **Price:** Competitive (Best Match factor)
- [ ] **Seller Metrics:** Positive feedback, fast shipping

---

## 🔧 eBay MCP Setup (ebay-mcp)

### **1. eBay Developer Hesabı Oluştur**
https://developer.ebay.com/

**Gerekli bilgiler:**
- **App ID (Client ID)**
- **Cert ID (Client Secret)**
- **RuName (Redirect URI)**

---

### **2. Setup Wizard Çalıştır**
```bash
npm install -g ebay-mcp
npx ebay-mcp setup
```

**Wizard:**
1. ✅ Client ID/Secret gir
2. ✅ Tarayıcıda eBay OAuth login
3. ✅ Authorization code'u yapıştır
4. ✅ Hermes config'e otomatik ekle

---

### **3. Test Et**
```
Hermes'e sor:
"Check my eBay API rate limits"

Çıktı:
Daily limit: 10,000 requests (user token)
Used: 234 requests
Remaining: 9,766 requests
```

---

## 📋 Available eBay Tools (379 Adet)

### **Inventory Management (57 tools)**
- Create/update/delete listings
- Bulk inventory operations
- Variant management
- Product catalog

### **Order Fulfillment (45 tools)**
- Get orders
- Update shipping
- Upload tracking
- Cancel orders

### **Marketing (32 tools)**
- Promoted Listings
- Ad campaigns
- Pricing strategies
- Performance reports

### **Analytics (28 tools)**
- Sales reports
- Traffic reports
- Conversion metrics
- Seller dashboard

### **Finance (21 tools)**
- Payouts
- Transaction history
- Fee calculations
- Invoices

### **Messaging (12 tools)**
- Customer messages
- Order inquiries
- Auto-responses

### **Taxonomy (18 tools)**
- Category tree
- Item specifics lookup
- Suggested categories

### **Legacy Trading API (166 tools)**
- Backward compatibility
- Advanced features

---

## 🎯 Mondeora Entegrasyon Planı

### **Faz 1: eBay SEO (ŞİMDİ)**
```python
# marketplace-listing-optimizer skill kullan
result = skill_optimize_listing({
    "marketplace": "ebay",
    "product": mondeora_product,
    "current_title": listing.title,
    "issues": ["low traffic", "low conversion"]
})

# Output: Optimized title, Item Specifics, Keywords
```

---

### **Faz 2: eBay MCP Integration (1-2 HAFTA)**
```python
# ebay-mcp üzerinden listing oluştur
from hermes_tools import tool_call

listing = tool_call("ebay_create_inventory_item", {
    "sku": product.sku,
    "title": optimized_title,
    "price": calculated_price,
    "quantity": stock_qty,
    "condition": "NEW",
    "category_id": ebay_category_id
})
```

---

### **Faz 3: LangGraph Order Flow (1 AY)**
```python
# Full automated order processing
app = build_order_workflow()
result = app.invoke({
    "ebay_order_id": order.id,
    "product_id": product.id,
    ...
})

# Workflow:
# eBay Order → Stock Check → GPSR → AliExpress → Tracking → eBay
```

---

## 🔐 Güvenlik & Best Practices

### **1. Environment Variables**
```bash
# .env (Mondeora-Drop-System)
EBAY_CLIENT_ID=your_app_id
EBAY_CLIENT_SECRET=your_cert_id
EBAY_ENVIRONMENT=sandbox  # Test için
EBAY_USER_REFRESH_TOKEN=auto_generated
```

### **2. Sandbox → Production Geçişi**
```bash
# Test bitince
EBAY_ENVIRONMENT=production
```

### **3. Rate Limits**
| Mode | Daily Limit |
|------|-------------|
| Client credentials | 1,000 requests |
| User token (OAuth) | 10,000-50,000 requests |

---

## 📞 Troubleshooting

### **Problem: eBay MCP bağlanamıyor**
```bash
# OAuth token'ı yenile
npx ebay-mcp setup

# Config'i kontrol et
hermes config get mcp_servers
```

### **Problem: Skill yüklenmiyor**
```bash
# Skill'leri kontrol et
ls "$HERMES_HOME/skills/ecommerce-imported/"
hermes skills list | grep marketplace
```

### **Problem: API rate limit aşıldı**
```
Hermes'e sor:
"Check my eBay API rate limits"

# Çözüm: User token kullan (OAuth setup)
```

---

## 📚 Kaynaklar

**eBay MCP Documentation:**
- https://github.com/YosefHayim/ebay-mcp
- https://www.npmjs.com/package/ebay-mcp
- https://yosefhayim.github.io/ebay-mcp/

**eBay Developer:**
- https://developer.ebay.com/
- https://developer.ebay.com/api-docs/

**Skills:**
- marketplace-listing-optimizer: `$HERMES_HOME/skills/ecommerce-imported/marketplace-listing-optimizer/SKILL.md`

**Mondeora Integration:**
- LangGraph: `C:\Users\Administrator\Desktop\Mondeora-Drop-System\langgraph_advanced.py`
- E-commerce Skills: `C:\Users\Administrator\Desktop\Mondeora-Drop-System\ECOMMERCE_INTEGRATIONS.md`

---

✅ **Tüm eBay araçları hazır! Hemen kullanabilirsin.**
