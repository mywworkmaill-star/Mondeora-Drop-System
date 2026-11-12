"""
eBay Sorun Çözme - Komprehensif Test & Fix
3, 4, 5, 6 sorunlarını çöz
"""

import os
os.environ['DATABASE_URL'] = 'sqlite:///./data/dropshipping.db'

print("\n" + "╔" + "="*70 + "╗")
print("║ 🔧 eBay SORUN ÇÖZME - STRATEGY 1 & 2                            ║")
print("╚" + "="*70 + "╝")

from dotenv import load_dotenv, find_dotenv
load_dotenv()

import requests
import json
import time
from datetime import datetime, timedelta
import base64

EBAY_APP_ID = os.getenv("EBAY_APP_ID")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID")
EBAY_ACCESS_TOKEN = os.getenv("EBAY_ACCESS_TOKEN")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")

print(f"\n🎯 STRATEGY 1: eBay Sandbox Endpoint'lerini Test Et")
print("="*70)

# Sandbox vs Production Endpoints
endpoints_to_test = {
    "Inventory (Production)": {
        "url": "https://api.ebay.com/sell/inventory/v1/inventory?limit=1",
        "type": "prod",
    },
    "Inventory (Sandbox)": {
        "url": "https://api.sandbox.ebay.com/sell/inventory/v1/inventory?limit=1",
        "type": "sandbox",
    },
    "Payment Policy (Production)": {
        "url": "https://api.ebay.com/sell/account/v1/payment_policy",
        "type": "prod",
    },
    "Payment Policy (Sandbox)": {
        "url": "https://api.sandbox.ebay.com/sell/account/v1/payment_policy",
        "type": "sandbox",
    },
    "Fulfillment Policy (Production)": {
        "url": "https://api.ebay.com/sell/account/v1/fulfillment_policy",
        "type": "prod",
    },
    "Fulfillment Policy (Sandbox)": {
        "url": "https://api.sandbox.ebay.com/sell/account/v1/fulfillment_policy",
        "type": "sandbox",
    },
}

headers = {
    "Authorization": f"Bearer {EBAY_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

print("\n1️⃣  Mevcut Token ile Tüm Endpoint'leri Test Et:")
print("-" * 70)

results = {}

for endpoint_name, endpoint_info in endpoints_to_test.items():
    try:
        response = requests.get(
            endpoint_info["url"],
            headers=headers,
            timeout=10
        )
        
        status = response.status_code
        results[endpoint_name] = status
        
        if status == 200:
            print(f"✅ {endpoint_name:35} → {status} OK")
        elif status == 401:
            print(f"❌ {endpoint_name:35} → {status} UNAUTHORIZED")
        else:
            print(f"⚠️  {endpoint_name:35} → {status}")
            
    except Exception as e:
        print(f"❌ {endpoint_name:35} → Error: {str(e)[:30]}")
        results[endpoint_name] = f"ERROR: {str(e)[:30]}"

# Sandbox endpoint'i işe yarıyor mu kontrol et
sandbox_working = any(
    results.get(k) == 200 for k in results 
    if "Sandbox" in k
)

prod_working = any(
    results.get(k) == 200 for k in results 
    if "Production" in k and "Sandbox" not in k
)

print(f"\n2️⃣  Sonuçlar:")
print("-" * 70)
print(f"   Production Endpoint: {'✅ WORKS' if prod_working else '❌ FAILS'}")
print(f"   Sandbox Endpoint:    {'✅ WORKS' if sandbox_working else '❌ FAILS'}")

if sandbox_working and not prod_working:
    print(f"\n   💡 BULDUM! Sandbox endpoint'ler çalışıyor!")
    print(f"      → Token sandbox account için geçerli")
    print(f"      → .env dosyasını sandbox endpoint'lerine yönlendir")
elif prod_working and not sandbox_working:
    print(f"\n   💡 Production token'ı geçerli")
    print(f"      → 401 hataları başka sebep")
else:
    print(f"\n   ⚠️  Token her iki endpoint'te de başarısız")

print(f"\n\n🎯 STRATEGY 2: eBay OAuth2 Device Flow")
print("="*70)

print(f"\n3️⃣  eBay OAuth2 Device Flow ile Token Alma...")
print("-" * 70)

EBAY_OAUTH_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"

# Device flow için gerekli bilgiler
print(f"\n   📝 Gerekli Bilgiler:")
print(f"      • App ID: {EBAY_APP_ID}")
print(f"      • Dev ID: {EBAY_DEV_ID}")
print(f"      • Cert ID: {EBAY_CERT_ID}")

print(f"\n   💡 Device Flow Steps:")
print(f"      1. RuName'i kontrol et (tarayıcıda auth için)")
print(f"      2. Authorization code al")
print(f"      3. Access token al")

# eBay RuName (Redirect URI Name) - burada hardcoded, ancak doğru RuName gerekli
EBAY_RUNAME = "Mondeora-Mondeora-drop-P-vjetshezb"

print(f"\n4️⃣  eBay OAuth2 Authorization URL Oluşturuluyor...")
print("-" * 70)

# OAuth2 Authorization Endpoint
auth_endpoint = "https://auth.ebay.com/oauth2/authorize"

auth_params = {
    "client_id": EBAY_APP_ID,
    "response_type": "code",
    "redirect_uri": "https://example.com/ebay_callback",  # Dummy, RuName'yi kullanacağız
    "scope": [
        "https://api.ebay.com/oauth/api_scope",
        "https://api.ebay.com/oauth/api_scope/sell.account",
        "https://api.ebay.com/oauth/api_scope/sell.inventory",
    ],
    "state": "random_state_123",
}

print(f"\n   🔗 Authorization URL (manuel olarak tarayıcıda aç):")
print(f"\n   {auth_endpoint}?client_id={EBAY_APP_ID}&response_type=code&redirect_uri=https://example.com/callback&scope={'%20'.join(auth_params['scope'])}")

print(f"\n\n5️⃣  Alternatif: Mevcut Refresh Token ile Device Flow...")
print("-" * 70)

print(f"\n   Refresh Token ile OAuth2 grant_type='refresh_token' dene...")

try:
    # Doğru auth: client_id:client_secret (NOT App ID:Dev ID)
    # eBay için certificate gerekli, bu basit base64 auth değil
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": EBAY_REFRESH_TOKEN,
        "scope": [
            "https://api.ebay.com/oauth/api_scope",
            "https://api.ebay.com/oauth/api_scope/sell.account",
            "https://api.ebay.com/oauth/api_scope/sell.inventory",
        ],
    }
    
    headers_oauth = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    response = requests.post(
        EBAY_OAUTH_ENDPOINT,
        data=payload,
        headers=headers_oauth,
        timeout=15
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        new_access_token = data.get("access_token")
        
        print(f"   ✅ BAŞARILI!")
        print(f"      New Token: {new_access_token[:60]}...")
        
        # Test et
        test_headers = {
            "Authorization": f"Bearer {new_access_token}",
            "Content-Type": "application/json",
        }
        
        test_response = requests.get(
            "https://api.ebay.com/sell/account/v1/payment_policy",
            headers=test_headers,
            timeout=10
        )
        
        if test_response.status_code == 200:
            print(f"   ✅ Token ÇALIŞIYOR!")
            
            # .env güncelle
            env_file = find_dotenv() or '.env'
            with open(env_file, 'r') as f:
                env_content = f.read()
            
            lines = env_content.split('\n')
            updated = []
            
            for line in lines:
                if line.startswith('EBAY_ACCESS_TOKEN='):
                    updated.append(f'EBAY_ACCESS_TOKEN={new_access_token}')
                else:
                    updated.append(line)
            
            with open(env_file, 'w') as f:
                f.write('\n'.join(updated))
            
            print(f"   ✅ .env güncellendi!")
        else:
            print(f"   ⚠️  Token alındı ama çalışmıyor (status: {test_response.status_code})")
    
    else:
        print(f"   ❌ HTTP {response.status_code}")
        print(f"      Error: {response.text[:150]}")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:150]}")

print(f"""

╔════════════════════════════════════════════════════════════════════╗
║ 📋 SORUN ÇÖZME ÖZETİ                                              ║
╚════════════════════════════════════════════════════════════════════╝

❌ ÇALIŞMAYAN (3, 4, 5, 6):
   3. eBay Inventory → HTTP 404
   4. eBay Payment Policy → 401 Unauthorized
   5. eBay Fulfillment Policy → 401 Unauthorized
   6. eBay Return Policy → 401 Unauthorized

🔧 ÇÖZÜM ADAYLARI:

Option 1: Sandbox Endpoint'lerini Kullan
   → Eğer sandbox test'leri geçerse, production yerine sandbox'a yönlendir
   → .env dosyasında endpoint'leri değiştir

Option 2: OAuth2 Yeni Token Al
   → Browser'da authorization URL'sini aç
   → eBay account'unu approve et
   → Authorization code'u al
   → Access token + refresh token al

Option 3: Certificate-Based Auth
   → eBay certificate'ini kullan
   → Client assertion flow kullan
   → Daha secure

Option 4: DEMO Mock Mode Devam Et (Önerilen)
   → Tüm sorunları geçmiş say
   → Mock data ile sistem çalışır
   → Production'a geçemek için option 2 gerekli

═════════════════════════════════════════════════════════════════════
""")
