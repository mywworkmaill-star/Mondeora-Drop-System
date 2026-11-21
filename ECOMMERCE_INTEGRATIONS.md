# 🎯 E-Commerce Entegrasyonları - Mondeora

## ✅ Kurulum Tamamlananlar

### 1. **11 Hermes Skills (Hazır)**
Konum: `%HERMES_HOME%/skills/ecommerce-imported/`

| Skill | Kullanım |
|-------|----------|
| **dropshipping-integration** | AliExpress → eBay/Shopify entegrasyonu |
| **dynamic-pricing** | Otomatik fiyat optimizasyonu (demand-based) |
| **order-fulfillment-workflow** | Sipariş işleme workflow'u |
| **inventory-tracking** | Stok takibi ve senkronizasyon |
| **low-stock-alerts** | Düşük stok uyarıları |
| **checkout-friction-finder** | Checkout sorunlarını tespit et |
| **product-page-conversion-review** | Ürün sayfası optimizasyonu |
| **returns-reason-miner** | İade sebeplerini analiz et |
| **contribution-margin-check** | Kar marjı analizi |
| **shipping-economics-review** | Kargo maliyeti analizi |
| **inventory-risk-brief** | Stok riski raporu |

**Kullanım:**
```
Hermes otomatik yükler. Skill'i aktive etmek için trigger kelimesini kullan:
"dynamic pricing optimization for my eBay listings"
```

---

### 2. **MCP Server'lar (Aktif)**

#### **A) DSers Dropshipping MCP**
- **Ne yapar:** AliExpress ürünlerini Shopify/Wix'e import eder
- **Kullanım:**
```bash
# İlk kurulum (bir kez)
dsers-mcp login

# Hermes'ten kullan:
"Import this AliExpress product to Shopify: [URL]"
```

**Config'e eklendi:**
```yaml
mcp_servers:
  dsers-dropshipping:
    command: npx
    args: ["-y", "@akacoder404/dsers-mcp"]
    description: DSers AliExpress to Shopify/Wix automation
```

#### **B) CJ Dropshipping Product Scout**
- **Ne yapar:** CJDropshipping ürün araması ve freight hesaplama
- **Kullanım:**
```
Hermes'e sor:
"Search CJDropshipping for wireless earbuds under $5"
"Calculate freight cost for this product to Germany"
```

**Config'e eklendi:**
```yaml
mcp_servers:
  dropshipping-product-scout:
    type: http
    url: https://mcp.youxiu.shop/mcp
    description: CJ Dropshipping product scout
```

---

### 3. **MedusaJS (Kuruluyor)**
Konum: `C:\Users\Administrator\Desktop\mondeora-medusa`

**Ne yapar:**
- Kendi e-ticaret backend'in (Shopify alternatifi)
- Headless commerce platform
- Multi-channel satış (eBay + kendi site)

**Kurulum bitince:**
```bash
cd C:\Users\Administrator\Desktop\mondeora-medusa
npm run dev
# Admin panel: http://localhost:9000/app
```

---

## 🚀 Mondeora'ya Entegrasyon

### **Senaryo 1: AliExpress → eBay Otomasyonu (Şu Anki)**
```python
# src/jobs/listing_pipeline.py
# Mevcut akış:
1. AliExpress API → Ürün verisi
2. GPSR evidence generation
3. eBay listing

# İyileştirme (LangGraph ile):
from langgraph_order_flow import build_order_workflow

app = build_order_workflow()
result = app.invoke({
    "product_id": ali_product_id,
    "target_platform": "ebay_de",
    ...
})
```

### **Senaryo 2: Dynamic Pricing**
```python
# Hermes skill'i kullan
from hermes_tools import delegate_task

result = delegate_task(
    goal="Optimize pricing for all active eBay listings using dynamic-pricing skill",
    context="Current eBay listings in data/mondeora.db"
)
```

### **Senaryo 3: Multi-Platform Expansion (Gelecek)**
```
AliExpress → Mondeora → eBay + Shopify + Kendi Site (MedusaJS)
                      ↓
              [LangGraph Workflow]
                      ↓
              [n8n Notifications]
```

---

## 📋 Diğer Repolar (İnceleme Aşamasında)

| Repo | Durum | Kullanım |
|------|-------|----------|
| **DropShipping-AI-Agent** | 🔍 İnceleniyor | Tam AI dropshipping sistemi (FastAPI) |
| **ecommerce-skills (Cart API)** | 🔍 İnceleniyor | Competitor intelligence |
| **Awesome-Automated-Dropshipping** | ℹ️ Referans | Curated list (kod yok) |

---

## 🎯 Hemen Kullanabileceğin Komutlar

### 1. **Skill'leri Listele**
```bash
hermes skills list | grep ecommerce
```

### 2. **Dynamic Pricing Analizi**
```
Hermes'e sor:
"Analyze my eBay listings and suggest dynamic pricing strategy"
```

### 3. **DSers Import (Shopify için)**
```bash
# İlk kurulum
dsers-mcp login

# Hermes'ten
"Import these 5 AliExpress products to Shopify:
[URL1]
[URL2]
..."
```

### 4. **LangGraph Order Flow Test**
```bash
cd /c/Users/Administrator/Desktop/Mondeora-Drop-System
python311 langgraph_advanced.py
```

---

## 🔧 Troubleshooting

### **Problem: Skill yüklenmiyor**
```bash
# Skill'leri reload et
hermes config get skills
ls "$HERMES_HOME/skills/ecommerce-imported/"
```

### **Problem: MCP server bağlanamıyor**
```bash
# MCP server'ları kontrol et
hermes config get mcp_servers
hermes doctor
```

### **Problem: DSers login süresi doldu**
```bash
dsers-mcp logout
dsers-mcp login
```

---

## 📊 Öncelik Sırası

**ŞİMDİ:**
1. ✅ 11 Skill'i test et (Hermes'te aktif)
2. ✅ LangGraph order flow'u Mondeora'ya entegre et
3. ⏳ n8n kurulumu bitsin → Telegram notifications

**SONRA (1-2 hafta):**
4. 🔄 Dynamic pricing skill'ini eBay'e uygula
5. 🔄 DSers MCP ile Shopify expansion
6. 🔄 MedusaJS ile kendi site kur

**GELECEKİ (1-2 ay):**
7. 📈 Multi-platform orchestration (eBay + Shopify + Site)
8. 📈 AI-powered competitor intelligence
9. 📈 Tam otomasyon (zero-touch fulfillment)

---

## 💡 Öneriler

1. **İlk önce mevcut Mondeora'yı stabilize et**
   - eBay + AliExpress akışı %100 çalışsın
   - GPSR compliance tamam olsun

2. **LangGraph'ı order fulfillment'a ekle**
   - Retry mekanizması
   - Manual approval workflow

3. **n8n ile bildirim sistemi kur**
   - Telegram alerts
   - Error notifications

4. **Dynamic pricing'i test et**
   - 5-10 ürünle başla
   - Kar marjını koru

5. **Shopify expansion hazırlıkları**
   - DSers hesabı aç
   - Shopify store kur
   - DSers MCP test et

---

## 📞 Destek

**Skill kullanımı:**
```
Hermes'e sor: "Show me how to use the dynamic-pricing skill"
```

**MCP server sorunları:**
```bash
hermes doctor
hermes config get mcp_servers
```

**Repo'lar:**
- awesome-ecommerce-skills: https://github.com/finsilabs/awesome-ecommerce-skills
- dsers-mcp: https://github.com/AkaCoder404/dsers-mcp
- MedusaJS: https://docs.medusajs.com

---

✅ **Tüm kaynaklar hazır, test edip kullanabilirsin!**
