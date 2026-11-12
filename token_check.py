# token_check.py
import requests
import base64
import json
import os

# .env dosyasından token oku
def read_env(env_file="tokens.json"):
    if not os.path.exists(env_file):
        return {"refresh_token": "***"}
    
    with open(env_file, "r", encoding="utf-8") as f:
        return eval(f.read())

token_data = read_env()

# Token'in formatını kontrol et
refresh_token = token_data.get("refresh_token", "")
print("🔍 Token Formatı Analizi:")
print(f"   - Token Uzunluğu: {len(refresh_token)} karakter")
print(f"   - Token Tipi: {'Refresh Token' if 'r^1' in refresh_token else 'Auth Token'}")

# Token'i eBay API'den test et
def check_refresh_token(token):
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token,
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET"
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=10)
        print(f"📡 OAuth2 API Cevabı (HTTP {response.status_code}):")
        print(f"   {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            new_access_token = result.get("access_token", "")
            new_refresh_token = result.get("refresh_token", "")
            
            if new_access_token and len(new_access_token) > 20:
                print("✅ TOKEN AKTİV! Yeni access token alınmıştır.")
                print(f"   Cevap: {result}")
                return True
            else:
                print("⚠️ Token geçerli ama access token alınamadı.")
                return False
        else:
            print("❌ Token geçersiz veya yetersiz izin!")
            return False
    except Exception as e:
        print(f"❌ İstek hatası: {e}")
        return False

# Kontrol
if refresh_token and refresh_token != "NONE":
    check_refresh_token(refresh_token)
else:
    print("⚠️ Token bulunamadı! .env veya tokens.json kontrol edin.")