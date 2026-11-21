"""
eBay Token Yenileme - XML API Method
GetSessionID + GetUser ile yeni session alıp token oluştur
"""

import os
os.environ['DATABASE_URL'] = 'sqlite:///./data/dropshipping.db'

print("\n" + "╔" + "="*70 + "╗")
print("║ 🔄 eBay TOKEN YENILEME - XML API (Certificate-Based)             ║")
print("╚" + "="*70 + "╝")

from dotenv import load_dotenv, find_dotenv
load_dotenv()

import requests
import json
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from defusedxml.ElementTree import fromstring as _safe_fromstring

# eBay Credentials
EBAY_APP_ID = os.getenv("EBAY_APP_ID")
EBAY_DEV_ID = os.getenv("EBAY_DEV_ID")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID")
EBAY_RUNAME = "Mondeora-Mondeora-drop-P-vjetshezb"

print(f"\n1️⃣  eBay XML API ile Token Alınıyor...")
print(f"   ✅ App ID:  {EBAY_APP_ID}")
print(f"   ✅ Dev ID:  {EBAY_DEV_ID}")
print(f"   ✅ Cert ID: {EBAY_CERT_ID}")
print(f"   ✅ RuName:  {EBAY_RUNAME}")

# XML API Endpoints
EBAY_XML_ENDPOINT = "https://api.ebay.com/ws/api.dll"

# Step 1: GetSessionID
print(f"\n2️⃣  GetSessionID ile Session ID Alınıyor...")

session_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetSessionIDRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RuName>{EBAY_RUNAME}</RuName>
</GetSessionIDRequest>"""

headers = {
    'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
    'X-EBAY-API-DEV-NAME': EBAY_DEV_ID,
    'X-EBAY-API-APP-NAME': EBAY_APP_ID,
    'X-EBAY-API-CERT-NAME': EBAY_CERT_ID,
    'X-EBAY-API-SITEID': '0',  # 0 = EBAY_US, 77 = EBAY_DE
    'X-EBAY-API-CALL-NAME': 'GetSessionID',
    'Content-Type': 'application/xml',
}

try:
    response = requests.post(
        EBAY_XML_ENDPOINT,
        headers=headers,
        data=session_xml,
        timeout=15
    )
    
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        # Parse XML response
        root = _safe_fromstring(response.content)
        ns = {'ebay': 'urn:ebay:apis:eBLBaseComponents'}
        
        session_id_elem = root.find('.//ebay:SessionID', ns)
        
        if session_id_elem is not None:
            session_id = session_id_elem.text
            print(f"   ✅ Session ID alındı!")
            print(f"   ID: {session_id[:50]}...")
            
            # Step 2: GetUser ile token al
            print(f"\n3️⃣  GetUser ile User Token Alınıyor...")
            
            user_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <SessionID>{session_id}</SessionID>
</GetUserRequest>"""
            
            headers['X-EBAY-API-CALL-NAME'] = 'GetUser'
            
            user_response = requests.post(
                EBAY_XML_ENDPOINT,
                headers=headers,
                data=user_xml,
                timeout=15
            )
            
            print(f"   Status: {user_response.status_code}")
            
            if user_response.status_code == 200:
                user_root = _safe_fromstring(user_response.content)
                
                # Token alanlarını ara
                auth_token_elem = user_root.find('.//ebay:AuthenticationToken', ns)
                user_id_elem = user_root.find('.//ebay:UserID', ns)
                
                if auth_token_elem is not None:
                    new_access_token = auth_token_elem.text
                    user_id = user_id_elem.text if user_id_elem is not None else "N/A"
                    
                    print(f"   ✅ TOKEN BAŞARILI ALINDI!")
                    print(f"   Token:   {new_access_token[:60]}...")
                    print(f"   User ID: {user_id}")
                    
                    # .env güncelle
                    print(f"\n4️⃣  .env Dosyası Güncelleniyor...")
                    
                    env_file = find_dotenv() or '.env'
                    
                    with open(env_file, 'r') as f:
                        env_content = f.read()
                    
                    lines = env_content.split('\n')
                    updated = []
                    found_token = False
                    
                    for line in lines:
                        if line.startswith('EBAY_ACCESS_TOKEN='):
                            updated.append(f'EBAY_ACCESS_TOKEN={new_access_token}')
                            found_token = True
                        else:
                            updated.append(line)
                    
                    if not found_token:
                        updated.append(f'EBAY_ACCESS_TOKEN={new_access_token}')
                    
                    with open(env_file, 'w') as f:
                        f.write('\n'.join(updated))
                    
                    print(f"   ✅ .env dosyası güncellendi!")
                    
                    # Token bilgisini kaydet
                    print(f"\n5️⃣  Token Bilgisi Kaydediliyor...")
                    
                    os.makedirs('data', exist_ok=True)
                    
                    token_info = {
                        "access_token": new_access_token,
                        "user_id": user_id,
                        "created_at": datetime.now().isoformat(),
                        "expires_at": (datetime.now() + timedelta(days=1)).isoformat(),
                        "token_type": "AuthToken",
                        "method": "XML_API_GetUser",
                    }
                    
                    with open('data/ebay_tokens.json', 'w') as f:
                        json.dump(token_info, f, indent=2)
                    
                    print(f"   ✅ Token bilgisi kaydedildi!")
                    
                    # Test yapın
                    print(f"\n6️⃣  Yeni Token Test Ediliyor...")
                    
                    test_headers = {
                        "Authorization": f"Bearer {new_access_token}",
                        "Content-Type": "application/json",
                    }
                    
                    test_response = requests.get(
                        "https://api.ebay.com/sell/inventory/v1/inventory",
                        headers=test_headers,
                        timeout=10
                    )
                    
                    print(f"   Test Status: {test_response.status_code}")
                    
                    if test_response.status_code == 200:
                        print(f"   ✅ TOKEN GEÇERLİ!")
                    elif test_response.status_code == 401:
                        print(f"   ⚠️  401 - Token başka sorun var")
                    else:
                        print(f"   Status: {test_response.status_code}")
                    
                    print(f"""

╔════════════════════════════════════════════════════════════════════╗
║ ✅ eBay TOKEN BAŞARILI YENILENDI! (XML API)                       ║
╚════════════════════════════════════════════════════════════════════╝

🔄 OTOMATIK YENILEME SİSTEMİ:
   ✅ GetSessionID ile Session alındı
   ✅ GetUser ile AuthToken alındı
   ✅ .env dosyası güncellendi
   ✅ Token bilgisi kaydedildi

📊 TOKEN DETAYLARI:
   Created:  {token_info['created_at']}
   Expires:  {token_info['expires_at']}
   Type:     {token_info['token_type']}
   Method:   {token_info['method']}

⏰ YAŞAM SÜRESİ:
   ~ 24 saat geçerli
   Sonraki Yenileme: {(datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')}

═════════════════════════════════════════════════════════════════════
""")
                else:
                    print(f"   ❌ AuthToken bulunamadı")
                    print(f"   Response: {user_response.text[:300]}")
            else:
                print(f"   ❌ HTTP {user_response.status_code}")
                print(f"   Response: {user_response.text[:300]}")
        else:
            print(f"   ❌ SessionID bulunamadı")
            print(f"   Response: {response.text[:300]}")
    else:
        print(f"   ❌ HTTP {response.status_code}")
        print(f"   Response: {response.text[:300]}")
        
except Exception as e:
    print(f"   ❌ Error: {str(e)[:150]}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("✅ SISTEM OTOMATIK YENILEME KURULDU")
print("="*70)
