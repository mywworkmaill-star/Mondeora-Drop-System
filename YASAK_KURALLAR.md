# ⚠️ YASAK - AliExpress Ürün Listeleme Kuralları

## 🚫 KESINLIKLE YASAK

### 1. Uydurma AliExpress Linkleri
❌ **YASAK:** Rastgele ID numaralarıyla link oluşturmak
❌ **YASAK:** Doğrulanmamış ürün ID'leri kullanmak
❌ **YASAK:** 404 veren linkler

✅ **DOĞRU:** Sadece gerçek, çalışan AliExpress linkleri kullan

### 2. Sahte Ürün Bilgileri
❌ **YASAK:** Uydurma fiyatlar
❌ **YASAK:** Varsayılan fiyatlar ($0.99, $1.99 gibi)
❌ **YASAK:** Tahmini satış sayıları

✅ **DOĞRU:** Gerçek AliExpress API'den veya tarayıcıdan çekilen veriler

### 3. Sahte Ürün Görselleri
❌ **YASAK:** Unsplash fotoğrafları kullanmak
❌ **YASAK:** Placeholder görseller
❌ **YASAK:** Rastgele AliExpress CDN linkleri (ae01.alicdn.com/kf/Sxxx...)
❌ **YASAK:** BAŞKA ÜRÜNÜN GÖRSELLERİNİ KULLANMAK (iPhone case görseli köpek oyuncağında!)

✅ **DOĞRU:** Gerçek ürün sayfasından çekilen görseller

**🔒 KRİTİK KURAL - ZORUNLİ:**
```python
# ✅ DOĞRU - Her ürün KENDİ görsellerini kullanır:
product = ali.get_product_details(product_id)
images = product['image_urls'].split(';')  # O ürünün gerçek görselleri
listing['imageUrls'] = images  # Sadece bunları kullan

# ❌ YANLIŞ - Başka ürünün görselleri:
listing['imageUrls'] = PLACEHOLDER_IMAGES  # YASAK!
listing['imageUrls'] = random_stock_photos  # YASAK!
listing['imageUrls'] = previous_product_images  # YASAK!
```

**✅ HER LİSTİNG İÇİN ZORUNLU:**
1. AliExpress product_id al
2. `get_product_details(product_id)` çağır
3. `image_urls` field'ını split et
4. SADECE o görselleri kullan
5. Başka hiçbir görsel kullanma

### 4. Sahte Varyantlar
❌ **YASAK:** Tahmin edilen renkler/modeller
❌ **YASAK:** Standart model listesi (iPhone 13/14/15 vs.)

✅ **DOĞRU:** Ürün sayfasındaki gerçek varyantlar

### 5. Sahte Açıklamalar
❌ **YASAK:** Genel template açıklamalar (her ürün için aynı HTML)
❌ **YASAK:** Generic başlıklar ("Premium Qualität" her üründe)
❌ **YASAK:** Uydurma özellik listesi
❌ **YASAK:** Copy-paste açıklamalar

✅ **DOĞRU:** Her ürün için ÖZEL, ürüne özgü HTML açıklaması

**🔒 KRİTİK KURAL - ZORUNLİ:**
```python
# ❌ YANLIŞ - Generic template (her ürün aynı):
html = f"""
<h1>Premium Qualität</h1>
<p>Schneller Versand</p>
"""

# ✅ DOĞRU - Ürüne özel açıklama:
if product_type == "dog_toy":
    html = f"""
    <h1>🐕 Hunde Spielzeug Ball Set</h1>
    <p>Interaktives Kauspielzeug für aktive Hunde</p>
    <ul>
      <li>Bissfest: Naturkautschuk Material</li>
      <li>Zahnreinigung: Spezielle Rillen</li>
      <li>Schwimmfähig: Perfekt für Wasserspiele</li>
    </ul>
    """
elif product_type == "cat_feeder":
    html = f"""
    <h1>🐱 Katzen Futterautomat</h1>
    <p>4 Mahlzeiten täglich - Automatische Fütterung</p>
    <ul>
      <li>Timer: Programmierbar bis 24h</li>
      <li>Frischeschutz: Luftdichte Fächer</li>
      <li>Sprachaufnahme: Rufen Sie Ihre Katze</li>
    </ul>
    """
```

**✅ HER ÜRÜN İÇİN ZORUNLU:**
1. Ürüne özel başlık (generic değil)
2. Ürünün gerçek özelliklerini araştır
3. O ürüne özgü faydalar yaz
4. Ürünün kullanım senaryoları ekle
5. Başka hiçbir üründe kullanma

---

## ✅ DOĞRU SÜREÇ

### Adım 1: Gerçek Ürün Seçimi

**Manuel yöntem (ÖNERİLEN):**
1. Kullanıcı AliExpress.com'a gider
2. İstediği ürünü bulur (10,000+ satış, 4.5+ yıldız)
3. Ürün URL'sini kopyalar
4. Sisteme verir

**Örnek:**
```
Kullanıcı: "Bu ürünü listele: https://www.aliexpress.com/item/1005003657092883.html"
```

### Adım 2: Ürün Bilgilerini Çekme

**Yöntem 1: Browser kullan**
```python
# Browser ile sayfayı aç
# Gerçek fotoğrafları kaydet
# Gerçek fiyatı al
# Gerçek varyantları çek
# Gerçek açıklamayı kopyala
```

**Yöntem 2: Kullanıcıdan al**
```
"Bu ürünün fiyatı nedir?"
"Kaç farklı renk var?"
"Ürün açıklamasını kopyala"
```

### Adım 3: Doğrulama

**Her zaman kontrol et:**
- [ ] Link 404 vermiyor mu?
- [ ] Fotoğraflar gerçekten bu üründen mi?
- [ ] Fiyat gerçek mi?
- [ ] Varyantlar doğru mu?

---

## 📋 MANUEL LİSTELEME ŞABLONU

Kullanıcıdan şu bilgileri iste:

```
=== AliExpress Ürün Bilgileri ===

1. Ürün URL'si:
   https://www.aliexpress.com/item/XXXXXXXXXX.html

2. Ürün Başlığı:
   [Gerçek başlık buraya]

3. Fiyat (USD):
   $X.XX

4. Fotoğraflar (en az 5):
   - https://ae01.alicdn.com/kf/Sxxxxx.jpg
   - https://ae01.alicdn.com/kf/Sxxxxx.jpg
   - [vs.]

5. Varyantlar:
   - Renk: [liste]
   - Model: [liste]

6. Özellikler:
   - [Gerçek özellik 1]
   - [Gerçek özellik 2]
```

---

## 🔧 SİSTEM KURALLARI

### Kural 1: Asla Tahmin Etme
❌ "Muhtemelen şu fiyattır"
❌ "Genelde şu varyantlar olur"
❌ "Benzer ürünlerde şu özellikler var"

✅ "Bu bilgiyi alamıyorum, manuel gir"
✅ "Ürün sayfasını aç ve fotoğrafları kaydet"
✅ "Lütfen gerçek fiyatı ver"

### Kural 2: 404 = Dur
Link 404 veriyorsa:
1. **DUR** - Devam etme
2. Kullanıcıya söyle
3. Yeni link iste

### Kural 3: Doğrulanmamış = Kullanma
API veya browser ile doğrulanmamış hiçbir bilgi kullanma.

---

## 🎯 ÇÖZÜM: MANUEL SİSTEM

En güvenilir yöntem:

1. **Kullanıcı ürünü seçer**
   - AliExpress.com'da arama yapar
   - Uygun ürünü bulur (10K+ satış)
   - Link'i kopyalar

2. **Sistem browser açar**
   - Gerçek sayfayı yükler
   - Screenshot alır
   - Fotoğrafları indirir
   - Fiyatı okur

3. **Kullanıcı onaylar**
   - "Bu ürün doğru mu?"
   - "Fiyat doğru mu?"
   - "Fotoğraflar uygun mu?"

4. **Sistem eBay'e listeler**
   - Sadece doğrulanmış bilgiler
   - Gerçek fotoğraflar
   - Gerçek fiyat
   - Gerçek açıklama

---

## 💡 ÖZET

### YAPILACAKLAR:
✅ Gerçek AliExpress linklerini doğrula
✅ Browser ile ürün sayfasını aç
✅ Fotoğrafları manuel indir
✅ Kullanıcıdan bilgi iste
✅ Her şeyi doğrula

### YAPILMAYACAKLAR:
❌ Uydurma link
❌ Placeholder fotoğraf
❌ Tahmini fiyat
❌ Varsayılan varyant
❌ Genel açıklama

---

**NOT:** Bu kurallar mutlak ve değişmez. Hiçbir durumda uydurma bilgi kullanılmayacak.

---

**Oluşturulma:** 8 Kasım 2026  
**Durum:** AKTİF VE ZORUNLU  
**Geçerlilik:** Her AliExpress-eBay entegrasyonunda
