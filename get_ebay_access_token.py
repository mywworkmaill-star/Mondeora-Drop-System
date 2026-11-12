import os
import requests
from pathlib import Path

def get_ebay_access_token():
    env_path = Path(r"C:\Users\Administrator\Desktop\Mondeora-Drop-System\.env")
    
    if not env_path.exists():
        print("❌ .env dosyası bulunamadı!")
        return
    
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                env_vars[key.strip()] = value.strip()
    
    refresh_token = env_vars.get('EBAY_REFRESH_TOKEN')
    # eBay OAuth: APP_ID = CLIENT_ID, CERT_ID = CLIENT_SECRET
    client_id = env_vars.get('EBAY_CLIENT_ID') or env_vars.get('EBAY_APP_ID')
    client_secret = env_vars.get('EBAY_CLIENT_SECRET') or env_vars.get('EBAY_CERT_ID')
    
    if not refresh_token:
        print("v^1.1# ile baslayan EBAY_REFRESH_TOKEN degerini .env dosyasina ekleyin")
        return
    
    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    
    # eBay OAuth2 requires Basic Authentication
    import base64
    auth_string = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_b64}'
    }
    
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    print(f"🔄 eBay access token alınıyor...")
    print(f"📤 Endpoint: {token_url}")
    
    try:
        response = requests.post(token_url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            new_access_token = result.get('access_token')
            expires_in = result.get('expires_in', 3600)
            
            print(f"✅ Yeni Access Token alındı!")
            print(f"⏱️  TTL: {expires_in} saniye")
            print(f"🔑 Token: {new_access_token[:50]}...")
            
            # .env dosyasına güncelle
            env_path = Path(r"C:\Users\Administrator\Desktop\Mondeora-Drop-System\.env")
            env_lines = []
            updated = False
            
            if env_path.exists():
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('EBAY_ACCESS_TOKEN'):
                            env_lines.append('EBAY_ACCESS_TOKEN=' + new_access_token + chr(10))
                            updated = True
                        else:
                            env_lines.append(line)
                if updated:
                    with open(env_path, 'w', encoding='utf-8') as f:
                        f.writelines(env_lines)

            if not updated:
                with open(env_path, 'a', encoding='utf-8') as f:
                    f.write(chr(10) + 'EBAY_ACCESS_TOKEN=' + new_access_token + chr(10))

            print(f"📁 .env güncellendi: EBAY_ACCESS_TOKEN")
            return new_access_token
        else:
            print(f"❌ Hata: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ İstek hatası: {e}")
        return None

if __name__ == "__main__":
    get_ebay_access_token()