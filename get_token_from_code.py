"""
Desktop Credentials + Authorization Code ile Token Al
Dosyada zaten kod var! /auth/token/create endpoint'ini kullan
"""

import hmac
import hashlib
import time
import json
import requests

print("\n" + "╔" + "="*68 + "╗")
print("║ 🔐 AUTHORIZATION CODE İLE TOKEN AL                            ║")
print("║ (Desktop'taki aliexpress_token.py'den)                        ║")
print("╚" + "="*68 + "╝")

# Credentials — loaded from .env, never hard-coded
import os
from dotenv import load_dotenv
load_dotenv()
APP_KEY = os.environ["ALIEXPRESS_APP_KEY"]
APP_SECRET = os.environ["ALIEXPRESS_APP_SECRET"]
CODE = os.environ.get("ALIEXPRESS_AUTH_CODE") or input("Authorization code (from redirect URL): ").strip()

print(f"\n1️⃣  Credentials:")
print(f"   ✅ App Key:    {APP_KEY}")
print(f"   ✅ App Secret: {APP_SECRET}")
print(f"   ✅ Code:       {CODE}")

print(f"\n2️⃣  Token alınıyor...")
print(f"   📤 Endpoint: https://api-sg.aliexpress.com/rest/auth/token/create")
print(f"   📤 Method: SHA256 signature ile POST")

try:
    path = "/auth/token/create"
    
    # Parametreler
    params = {
        "app_key": APP_KEY,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "sha256",
        "code": CODE
    }
    
    # SHA256 signature oluştur
    base = path + "".join(k + params[k] for k in sorted(params))
    params["sign"] = hmac.new(
        APP_SECRET.encode(),
        base.encode(),
        hashlib.sha256
    ).hexdigest().upper()
    
    print(f"\n   📝 Parameters:")
    for k, v in params.items():
        if len(str(v)) > 50:
            print(f"      {k}: {str(v)[:50]}...")
        else:
            print(f"      {k}: {v}")
    
    # Request gönder
    print(f"\n3️⃣  HTTP POST gönderiliyor...")
    
    response = requests.post(
        "https://api-sg.aliexpress.com/rest" + path,
        data=params,
        timeout=30
    )
    
    print(f"   📥 HTTP Status: {response.status_code}")
    print(f"   📥 Response: {response.text[:300]}")
    
    if response.status_code == 200:
        data = response.json()
        
        if "access_token" in data:
            ACCESS_TOKEN = data.get("access_token")
            REFRESH_TOKEN = data.get("refresh_token")
            EXPIRES_IN = data.get("expires_in")
            ACCOUNT = data.get("account")
            
            print(f"\n   ✅✅✅ BAŞARILI! TOKEN ALINDI! ✅✅✅")
            print(f"      Access Token:  {ACCESS_TOKEN[:60]}...")
            print(f"      Refresh Token: {REFRESH_TOKEN[:60]}...")
            print(f"      Expires In:    {EXPIRES_IN} seconds")
            if ACCOUNT:
                print(f"      Account:       {ACCOUNT}")
            
            # .env dosyasını güncelle
            print(f"\n4️⃣  .env dosyası güncelleniyor...")
            
            try:
                with open(".env", "r") as f:
                    env_content = f.read()
                
                lines = env_content.split("\n")
                updated = []
                
                replacements = {
                    "ALIEXPRESS_APP_KEY": f"ALIEXPRESS_APP_KEY={APP_KEY}",
                    "ALIEXPRESS_APP_SECRET": f"ALIEXPRESS_APP_SECRET={APP_SECRET}",
                    "ALIEXPRESS_ACCESS_TOKEN": f"ALIEXPRESS_ACCESS_TOKEN={ACCESS_TOKEN}",
                    "ALIEXPRESS_REFRESH_TOKEN": f"ALIEXPRESS_REFRESH_TOKEN={REFRESH_TOKEN}",
                }
                
                found_keys = set()
                
                for line in lines:
                    updated_line = False
                    for key, new_val in replacements.items():
                        if line.startswith(key + "="):
                            updated.append(new_val)
                            found_keys.add(key)
                            updated_line = True
                            break
                    if not updated_line and line.strip():
                        updated.append(line)
                
                for key, new_val in replacements.items():
                    if key not in found_keys:
                        updated.append(new_val)
                
                with open(".env", "w") as f:
                    f.write("\n".join(updated))
                
                print(f"   ✅ .env dosyası güncellendi!")
                
                # Dosyayı kontrol et
                with open(".env", "r") as f:
                    updated_content = f.read()
                
                print(f"\n5️⃣  Güncellenmiş .env:")
                print(f"   " + "="*60)
                for line in updated_content.split("\n"):
                    if "ALIEXPRESS" in line:
                        if "TOKEN" in line:
                            key, val = line.split("=", 1)
                            print(f"   {key}={val[:40]}...")
                        else:
                            print(f"   {line}")
                print(f"   " + "="*60)
                
            except Exception as e:
                print(f"   ❌ .env güncelleme hatası: {str(e)}")
                exit(1)
            
            # Test
            print(f"\n6️⃣  Sistem test ediliyor...")
            
            try:
                from src.api.aliexpress_client import AliExpressAPIClient
                
                client = AliExpressAPIClient()
                
                if client.check_token_validity():
                    print(f"   ✅ TOKEN GEÇERLİ!")
                else:
                    print(f"   ⚠️  Token geçerliliği kontrol edilemedi")
                    
            except:
                print(f"   ⚠️  Test atlandi (module yok)")
            
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
    → Seçenek 1: Tam Sistem

4️⃣  Dashboard aç:
    http://localhost:5000

═════════════════════════════════════════════════════════════════════
""")
        else:
            print(f"\n   ❌ Token alınamadı!")
            print(f"   Response: {json.dumps(data, indent=2)}")
    else:
        print(f"\n   ❌ HTTP Error {response.status_code}")
        
except Exception as e:
    print(f"\n   ❌ Exception: {str(e)}")
    import traceback
    traceback.print_exc()
