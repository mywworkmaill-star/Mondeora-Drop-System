# 🔐 Refresh Token Alma - Adım Adım Kılavuz

Senin yeni App Key + Secret Key'n var ama refresh token yok?  
Şu adımları izle!

---

## 📋 Seçenek 1: Otomatik Script (Tavsiye)

```bash
cd "C:\Users\Administrator\Desktop\Mondeora-Drop-System"
python manual_get_token.py
```

### Adımlar:

1. **App Key gir**
   ```
   📝 App Key: YOUR_APP_KEY_HERE
   ```

2. **App Secret gir**
   ```
   📝 App Secret: YOUR_SECRET_HERE
   ```

3. **Authorization URL çıkacak, tarayıcıya yapıştır**
   ```
   https://api-sg.aliexpress.com/openapi/oauth/authorize?...
   ```

4. **Tarayıcıda:**
   - AliExpress'te giriş yap
   - "Authorize" butonuna tıkla
   - Yönlendir URL'de `code=` değerini kopyala

5. **Code'u script'e yapıştır**
   ```
   📝 Authorization Code: abc123def456xyz789...
   ```

6. ✅ **Otomatik olarak .env güncellenecek!**

---

## 📋 Seçenek 2: Manuel Yol

### 1. Authorization URL Oluştur

URL'yi tarayıcıda aç:

```
https://api-sg.aliexpress.com/openapi/oauth/authorize?app_key=YOUR_APP_KEY&sign_type=MD5&timestamp=TIMESTAMP&sign=SIGNATURE&redirect_uri=http://localhost:8080/callback
```

Veya script'ten çıkan URL'yi kopyala.

### 2. Authorization Code Al

- AliExpress'e giriş yap
- Authorize tıkla
- Browser'ın adres çubuğunda redirect URL olacak:
  ```
  http://localhost:8080/callback?code=YOUR_CODE_HERE
  ```
- `code=` sonrasındaki değeri kopyala

### 3. Token Al

Kod yazarak:

```python
import requests
import hashlib
import time

APP_KEY = "YOUR_APP_KEY"
APP_SECRET = "YOUR_SECRET"
AUTH_CODE = "code_from_browser"

def generate_sign(params, secret):
    items = []
    for key in sorted(params.keys()):
        items.append(f"{key}{params[key]}")
    sign_string = f"{secret}{''.join(items)}{secret}"
    return hashlib.md5(sign_string.encode()).hexdigest().upper()

timestamp = str(int(time.time() * 1000))

params = {
    "app_key": APP_KEY,
    "timestamp": timestamp,
    "sign_type": "MD5",
    "code": AUTH_CODE,
}

params["sign"] = generate_sign(params, APP_SECRET)

response = requests.post(
    "https://api-sg.aliexpress.com/openapi/auth/token",
    data=params
)

result = response.json()
print(result)

# Çıktıdan al:
# access_token
# refresh_token
```

---

## 🔑 .env Dosyasını Güncelle

Dosya: `C:\Users\Administrator\Desktop\Mondeora-Drop-System\.env`

```
ALIEXPRESS_APP_KEY=YOUR_APP_KEY
ALIEXPRESS_APP_SECRET=YOUR_SECRET
ALIEXPRESS_ACCESS_TOKEN=YOUR_ACCESS_TOKEN
ALIEXPRESS_REFRESH_TOKEN=YOUR_REFRESH_TOKEN
```

---

## ✅ Başarı Kontrolü

```bash
python test_real_product.py
```

Eğer ürün çıkıyor = ✅ BAŞARILI!

---

## ❓ Sorun Yaşıyorsan?

- **404 hatası**: API endpoint değişmiş olabilir
- **401 hatası**: Credentials yanlış
- **Code geçersiz**: URL'den kopyaladığın code'u kontrol et

---

## 🚀 Sonra?

Token aldıktan sonra:

```bash
# Test et
python test_real_product.py

# Sistemi başlat
python main.py
# Seçenek 1: Tam Sistem
```

---

✅ Hazır!
