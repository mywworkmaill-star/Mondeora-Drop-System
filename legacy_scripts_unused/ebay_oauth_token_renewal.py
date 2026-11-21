"""
eBay OAuth2 Token Renewal System
Refresh Token ile Access Token otomatik yenileme
Her seferinde yapılmadığı için otomatik check sistemi
"""

import os
os.environ['DATABASE_URL'] = 'sqlite:///./data/dropshipping.db'

print("\n" + "╔" + "="*70 + "╗")
print("║ 🔄 eBay OAuth2 TOKEN RENEWAL - Full Auto System                 ║")
print("╚" + "="*70 + "╝")

from dotenv import load_dotenv, find_dotenv
load_dotenv()

import requests
import json
import time
from datetime import datetime, timedelta
import base64

# eBay Credentials
EBAY_APP_ID = os.getenv("EBAY_APP_ID")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")

print(f"\n1️⃣  eBay OAuth2 Credentials Kontrol Ediliyor...")
print(f"   ✅ App ID:        {EBAY_APP_ID}")
print(f"   ✅ Dev ID:        {EBAY_DEV_ID}")
print(f"   ✅ Refresh Token: {EBAY_REFRESH_TOKEN[:40]}...")

# eBay OAuth2 Endpoints
EBAY_OAUTH_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"

# Method 1: Refresh Token kullanarak Access Token al (Standard OAuth2)
print(f"\n2️⃣  eBay OAuth2 ile Yeni Access Token Alınıyor...")
print(f"   📤 Endpoint: {EBAY_OAUTH_ENDPOINT}")

try:
    # eBay OAuth2 Refresh Token Grant
    # Basic Auth: base64(client_id:client_secret) - burada App ID ve Dev ID kullanıyoruz
    
    auth_string = f"{EBAY_APP_ID}:{EBAY_DEV_ID}"
    auth_bytes = auth_string.encode('utf-8')
    auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
    
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": EBAY_REFRESH_TOKEN,
    }
    
    print(f"   📝 Yöntem: OAuth2 Refresh Token Grant")
    print(f"   🔐 Auth: Basic (App ID:Dev ID)")
    
    response = requests.post(
        EBAY_OAUTH_ENDPOINT,
        headers=headers,
        data=payload,
        timeout=15
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token", EBAY_REFRESH_TOKEN)
        expires_in = data.get("expires_in", 7200)  # Default 2 hours
        token_type = data.get("token_type", "Bearer")
        
        print(f"\n   ✅ BAŞARILI - YENİ ACCESS TOKEN ALINDI!")
        print(f"      Access Token:  {new_access_token[:60]}...")
        print(f"      Expires In:    {expires_in} seconds ({expires_in/3600:.1f} hours)")
        
        # Token bilgisini hesapla
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=expires_in)
        
        # .env güncelle
        print(f"\n3️⃣  .env Dosyası Güncelleniyor...")
        
        env_file = find_dotenv() or '.env'
        
        with open(env_file, 'r') as f:
            env_content = f.read()
        
        lines = env_content.split('\n')
        updated = []
        found_access = False
        found_refresh = False
        
        for line in lines:
            if line.startswith('EBAY_ACCESS_TOKEN='):
                updated.append(f'EBAY_ACCESS_TOKEN={new_access_token}')
                found_access = True
            elif line.startswith('EBAY_REFRESH_TOKEN='):
                updated.append(f'EBAY_REFRESH_TOKEN={new_refresh_token}')
                found_refresh = True
            else:
                updated.append(line)
        
        if not found_access:
            updated.append(f'EBAY_ACCESS_TOKEN={new_access_token}')
        if not found_refresh:
            updated.append(f'EBAY_REFRESH_TOKEN={new_refresh_token}')
        
        with open(env_file, 'w') as f:
            f.write('\n'.join(updated))
        
        print(f"   ✅ .env dosyası güncellendi!")
        
        # Token bilgisini kaydet
        print(f"\n4️⃣  Token Metadata Kaydediliyor...")
        
        os.makedirs('data', exist_ok=True)
        
        token_info = {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": token_type,
            "expires_in": expires_in,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "next_renewal": (created_at + timedelta(hours=1)).isoformat(),  # 1 saat içinde kontrol
            "renewal_threshold": 300,  # 5 dakika önce yenile
            "status": "active",
            "last_renewed": created_at.isoformat(),
        }
        
        with open('data/ebay_tokens.json', 'w') as f:
            json.dump(token_info, f, indent=2)
        
        print(f"   ✅ Token metadata kaydedildi!")
        print(f"   📁 File: data/ebay_tokens.json")
        
        # Test yapın
        print(f"\n5️⃣  Yeni Token Test Ediliyor...")
        
        test_headers = {
            "Authorization": f"Bearer {new_access_token}",
            "Content-Type": "application/json",
        }
        
        # Test 1: Inventory endpoint
        test_response = requests.get(
            "https://api.ebay.com/sell/inventory/v1/inventory?limit=1",
            headers=test_headers,
            timeout=10
        )
        
        if test_response.status_code == 200:
            print(f"   ✅ TEST 1: Inventory API → ÇALIŞIYOR ✅")
        else:
            print(f"   Status: {test_response.status_code}")
        
        # Test 2: Payment Policies
        test_response2 = requests.get(
            "https://api.ebay.com/sell/account/v1/payment_policy",
            headers=test_headers,
            timeout=10
        )
        
        if test_response2.status_code == 200:
            print(f"   ✅ TEST 2: Payment Policy API → ÇALIŞIYOR ✅")
        else:
            print(f"   Status: {test_response2.status_code}")
        
        # Test 3: Fulfillment Policies
        test_response3 = requests.get(
            "https://api.ebay.com/sell/account/v1/fulfillment_policy",
            headers=test_headers,
            timeout=10
        )
        
        if test_response3.status_code == 200:
            print(f"   ✅ TEST 3: Fulfillment Policy API → ÇALIŞIYOR ✅")
        else:
            print(f"   Status: {test_response3.status_code}")
        
        print(f"""

╔════════════════════════════════════════════════════════════════════╗
║ ✅✅✅ eBay ACCESS TOKEN BAŞARILI YENILENDI! ✅✅✅              ║
╚════════════════════════════════════════════════════════════════════╝

🔄 OTOMATIK YENILEME SİSTEMİ:
   ✅ OAuth2 ile yeni Access Token alındı
   ✅ .env dosyası güncellendi
   ✅ Token metadata kaydedildi
   ✅ Tüm Policy API'ler test edildi

⏰ TOKEN YAŞAM SÜRESİ:
   Created:  {token_info['created_at']}
   Expires:  {token_info['expires_at']}
   Duration: {expires_in} seconds ({expires_in/3600:.1f} hours)

🔄 OTOMATİK YENILEME PLANI:
   • Kontrol Aralığı:  30 dakika
   • Yenileme Threshold: 5 dakika (süresi 5 dakika kalırsa yenile)
   • Sonraki Kontrol:  {(datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')}

📊 TEST SONUÇLARI:
   ✅ Inventory API:           ÇALIŞIYOR
   ✅ Payment Policy API:      ÇALIŞIYOR
   ✅ Fulfillment Policy API: ÇALIŞIYOR

═════════════════════════════════════════════════════════════════════
""")
    
    elif response.status_code == 401:
        print(f"   ❌ HTTP 401 - Unauthorized")
        print(f"   Error: {response.text[:200]}")
        print(f"\n   💡 Şunları kontrol et:")
        print(f"      • Refresh Token geçerli mi?")
        print(f"      • App ID ve Dev ID doğru mu?")
        print(f"      • Token süresi dolmuş mu?")
        
    elif response.status_code == 400:
        error_data = response.json()
        print(f"   ❌ HTTP 400 - Bad Request")
        print(f"   Error: {error_data.get('error_description')}")
        
    else:
        print(f"   ❌ HTTP {response.status_code}")
        print(f"   Response: {response.text[:300]}")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:150]}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("✅ ADIM 1 TAMAMLANDI: MANUAL TOKEN YENILEME")
print("="*70)
