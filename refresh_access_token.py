"""
Refresh Token ile Yeni Access Token Al
Desktop tokens.json'daki refresh token kullan
"""

import hmac
import hashlib
import time
import requests
import json

print("\n" + "╔" + "="*68 + "╗")
print("║ 🔐 REFRESH TOKEN → YENİ ACCESS TOKEN                          ║")
print("╚" + "="*68 + "╝")

# Credentials — loaded from .env, never hard-coded
import os
from dotenv import load_dotenv
load_dotenv()
APP_KEY = os.environ["ALIEXPRESS_APP_KEY"]
APP_SECRET = os.environ["ALIEXPRESS_APP_SECRET"]
REFRESH_TOKEN = os.environ["ALIEXPRESS_REFRESH_TOKEN"]

print(f"\n1️⃣  Credentials:")
print(f"   ✅ App Key:      {APP_KEY}")
print(f"   ✅ App Secret:   {APP_SECRET}")
print(f"   ✅ Refresh Token: {REFRESH_TOKEN[:50]}...")

print(f"\n2️⃣  Yeni Access Token alınıyor...")

# Yöntem 1: SHA256 signature ile /auth/token/refresh
endpoint = "/auth/token/refresh"

params = {
    "app_key": APP_KEY,
    "timestamp": str(int(time.time() * 1000)),
    "sign_method": "sha256",
    "refresh_token": REFRESH_TOKEN,
}

# SHA256 signature
path = endpoint
base = path + "".join(k + params[k] for k in sorted(params))
params["sign"] = hmac.new(
    APP_SECRET.encode(),
    base.encode(),
    hashlib.sha256
).hexdigest().upper()

print(f"\n   📤 POST: https://api-sg.aliexpress.com/rest{endpoint}")
print(f"   📝 Parameters:")
print(f"      app_key: {APP_KEY}")
print(f"      refresh_token: {REFRESH_TOKEN[:50]}...")
print(f"      timestamp: {params['timestamp']}")
print(f"      sign: {params['sign']}")

try:
    response = requests.post(
        f"https://api-sg.aliexpress.com/rest{endpoint}",
        data=params,
        timeout=15
    )
    
    print(f"\n   📥 HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        if "access_token" in data:
            NEW_ACCESS_TOKEN = data.get("access_token")
            NEW_REFRESH_TOKEN = data.get("refresh_token", REFRESH_TOKEN)
            
            print(f"\n   ✅✅✅ BAŞARILI! YENİ TOKEN ALINDI! ✅✅✅")
            print(f"      New Access Token:  {NEW_ACCESS_TOKEN[:60]}...")
            print(f"      New Refresh Token: {NEW_REFRESH_TOKEN[:60]}...")
            
            # .env güncelle
            print(f"\n3️⃣  .env dosyası güncelleniyor...")
            
            try:
                with open(".env", "r") as f:
                    env_content = f.read()
                
                lines = env_content.split("\n")
                updated = []
                
                replacements = {
                    "ALIEXPRESS_APP_KEY": f"ALIEXPRESS_APP_KEY={APP_KEY}",
                    "ALIEXPRESS_APP_SECRET": f"ALIEXPRESS_APP_SECRET={APP_SECRET}",
                    "ALIEXPRESS_ACCESS_TOKEN": f"ALIEXPRESS_ACCESS_TOKEN={NEW_ACCESS_TOKEN}",
                    "ALIEXPRESS_REFRESH_TOKEN": f"ALIEXPRESS_REFRESH_TOKEN={NEW_REFRESH_TOKEN}",
                }
                
                found = set()
                
                for line in lines:
                    matched = False
                    for key, new_val in replacements.items():
                        if line.startswith(key + "="):
                            updated.append(new_val)
                            found.add(key)
                            matched = True
                            break
                    if not matched and line.strip():
                        updated.append(line)
                
                for key, new_val in replacements.items():
                    if key not in found:
                        updated.append(new_val)
                
                with open(".env", "w") as f:
                    f.write("\n".join(updated))
                
                print(f"   ✅ .env dosyası güncellendi!")
                
                # .env kontrol et
                print(f"\n4️⃣  Güncellenmiş .env (AliExpress):")
                print(f"   " + "="*60)
                with open(".env", "r") as f:
                    for line in f:
                        if "ALIEXPRESS" in line:
                            if "TOKEN" in line:
                                k, v = line.split("=", 1)
                                print(f"   {k}={v.strip()[:40]}...")
                            else:
                                print(f"   {line.strip()}")
                print(f"   " + "="*60)
                
            except Exception as e:
                print(f"   ❌ .env güncelleme hatası: {str(e)}")
                exit(1)
            
            print(f"""

╔════════════════════════════════════════════════════════════════════╗
║ ✅✅✅ BAŞARILI! SİSTEM HAZIR! ✅✅✅                              ║
╚════════════════════════════════════════════════════════════════════╝

🎉 YENİ CREDENTIALS .env'YE KAYDEDILDI!

📖 SONRAKI ADIMLAR:

1️⃣  Sistemi test et:
    python test_real_product.py

2️⃣  DEMO çalıştır:
    python DEMO.py

3️⃣  Sistemi başlat:
    python main.py

4️⃣  Dashboard aç:
    http://localhost:5000

═════════════════════════════════════════════════════════════════════
""")
        else:
            print(f"\n   ❌ access_token alınamadı!")
            print(f"   Response: {json.dumps(data, indent=2)}")
    else:
        print(f"   ❌ HTTP {response.status_code}")
        print(f"   Response: {response.text[:300]}")
        
except Exception as e:
    print(f"\n   ❌ Exception: {str(e)}")
    import traceback
    traceback.print_exc()
