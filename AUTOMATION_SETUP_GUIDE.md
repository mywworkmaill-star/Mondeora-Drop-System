# 🤖 OTOMATİK SOSYAL MEDYA SİSTEMİ - KURULUM REHBERİ

## ✅ TAM OTOMATİK POSTING - MANUEL İŞ YOK!

**Sistem oluşturuldu:** `auto_social_media.py`

**Ne yapacak:**
- ✅ Reddit'e otomatik post (r/de, r/Haustiere)
- ✅ Facebook groups'a otomatik post (5 grup)
- ✅ Twitter'a otomatik tweet
- ✅ Hepsi tek komutla!

---

## 🚀 HIZLI KURULUM (3 ADIM)

### ADIM 1: Dependencies Kur (2 dakika)

```bash
cd C:/Users/Administrator/Desktop/Mondeora-Drop-System
pip install praw tweepy requests python-dotenv
```

---

### ADIM 2: API Keys Al (10-15 dakika)

#### A) REDDIT API (5 dakika) ⭐ EN KOLAY

1. **Git:** https://www.reddit.com/prefs/apps
2. **"Create App"** tıkla
3. **Bilgileri doldur:**
   - Name: MondeoraPetToys
   - Type: **script**
   - Redirect URI: http://localhost:8080
4. **Create app** tıkla
5. **Kaydet:**
   - client_id (14 karakter, app name altında)
   - client_secret (27 karakter, "secret" yanında)

#### B) FACEBOOK API (10 dakika) ⚠️ Biraz karmaşık

**Option 1: Facebook Graph API (Recommended)**
1. **Git:** https://developers.facebook.com/apps
2. **Create App** → Business → Continue
3. **Add Product:** Facebook Login
4. **Get Access Token:**
   - Tools → Graph API Explorer
   - Permissions: `publish_to_groups`, `user_posts`
   - Generate Token
5. **Get Group IDs:**
   - Facebook group URL'sinden al
   - Örnek: facebook.com/groups/123456789 → ID: 123456789

**Option 2: Selenium Browser Automation** (Alternatif - API yerine)
- Facebook'a browser üzerinden login
- Otomatik form doldurma
- Manuel approval gerekmez!

#### C) TWITTER API (5 dakika)

1. **Git:** https://developer.twitter.com/en/portal/dashboard
2. **Create Project & App**
3. **Keys & Tokens:**
   - API Key & Secret
   - Access Token & Secret
4. **Permissions:** Read & Write
5. **Kaydet hepsini**

---

### ADIM 3: .env Dosyasına Ekle (2 dakika)

```bash
# .env dosyasını aç
notepad .env

# Ekle (credentials'ı değiştir):

# Reddit
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT=MondeoraPetToys/1.0

# Facebook (optional - karmaşık)
FACEBOOK_ACCESS_TOKEN=your_access_token_here
FB_GROUP_1_ID=group_id_1
FB_GROUP_2_ID=group_id_2
FB_GROUP_3_ID=group_id_3
FB_GROUP_4_ID=group_id_4
FB_GROUP_5_ID=group_id_5

# Twitter
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
```

**Kaydet ve kapat**

---

## ⚡ ÇALIŞTIR - OTOMATİK POSTING!

```bash
cd C:/Users/Administrator/Desktop/Mondeora-Drop-System
python auto_social_media.py
```

**Sonuç:**
```
✅ Reddit: 2 posts (r/de, r/Haustiere)
✅ Facebook: 5 posts (all groups)
✅ Twitter: 1 tweet

TOTAL: 8 otomatik post!
Time: 30 saniye
Manual work: 0
```

---

## 🎯 ALTERNATİF: SADECE REDDIT (HIZLI BAŞLANGIÇ)

**Facebook/Twitter API karmaşık gelirse:**

**Sadece Reddit ile başla:**

```python
# Sadece Reddit credentials ekle .env'e
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...
REDDIT_PASSWORD=...
REDDIT_USER_AGENT=MondeoraPetToys/1.0
```

**Çalıştır:**
```bash
python auto_social_media.py
```

**Sonuç:**
- ✅ Reddit: 2 otomatik post
- ⏭️  Facebook: Skip (API yok)
- ⏭️  Twitter: Skip (API yok)

**Bu bile yeterli:** 500-2,000 views → 1-2 sales potential!

---

## 🤖 TAM OTOMASYON (CHROME BROWSER)

**API kurmak istemiyorsan - Selenium ile:**

```python
# Browser automation (API gerekmez!)
# Facebook, Reddit, Twitter'a otomatik login + post
# Gerçek browser kullanır
```

**Avantajlar:**
- ✅ API key gerekmez
- ✅ Approval gerekmez
- ✅ Hemen çalışır

**Dezavantajlar:**
- ⚠️ Browser açılır (görünür)
- ⚠️ Biraz daha yavaş (1-2 dakika)

**İstersen bunu da yapabilirim!**

---

## 📊 HANGISINI SEÇELİM?

### Option A: REDDIT API ONLY ⭐⭐⭐ ÖNERİLİR
```
Time to setup:  5 dakika
Complexity:     ⭐ Çok kolay
Auto-posts:     2 (Reddit)
Reach:          500-2,000
Sales:          1-2 expected
```

### Option B: FULL API (Reddit + Facebook + Twitter)
```
Time to setup:  20-30 dakika
Complexity:     ⭐⭐⭐ Orta
Auto-posts:     8 (all platforms)
Reach:          2,000-10,000
Sales:          2-5 expected
```

### Option C: SELENIUM BROWSER AUTOMATION
```
Time to setup:  2 dakika
Complexity:     ⭐ Çok kolay
Auto-posts:     8 (all platforms)
Reach:          2,000-10,000
Sales:          2-5 expected
Browser:        Görünür (otomatik çalışır)
```

---

## 💡 BENİM ÖNERİM:

**ŞİMDİ:** Option C (Selenium) - en hızlı, API yok!  
**SONRA:** Option A (Reddit API) - güvenilir, uzun vadeli

---

## 🚀 HANGİSİNİ İSTİYORSUN?

**A)** Reddit API setup (5 dakika, hemen başla)  
**B)** Full API setup (20 dakika, maximum reach)  
**C)** Selenium browser automation (2 dakika, API YOK!) ⭐ EN HIZLI  

**Söyle, hemen kurayım! 🤖**
