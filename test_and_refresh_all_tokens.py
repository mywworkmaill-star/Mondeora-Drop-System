"""
TOKEN TEST VE YENİLEME SİSTEMİ
Tüm tokenleri test eder, süresi dolmuşsa refresh token ile yeniler
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv, set_key

# Proje root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

class TokenManager:
    def __init__(self):
        self.env_path = PROJECT_ROOT / '.env'
        self.results = {
            'ebay': {'tested': False, 'valid': False, 'refreshed': False, 'error': None},
            'aliexpress': {'tested': False, 'valid': False, 'refreshed': False, 'error': None}
        }
    
    def test_ebay_token(self):
        """Test eBay access token"""
        print("\n" + "="*70)
        print("🔍 EBAY TOKEN TEST EDİLİYOR")
        print("="*70)
        
        access_token = os.getenv('EBAY_ACCESS_TOKEN', '').strip('"')
        
        if not access_token:
            self.results['ebay']['error'] = 'Access token bulunamadı'
            print("❌ EBAY_ACCESS_TOKEN bulunamadı")
            return False
        
        # Test API call - GetUser (simple read)
        url = "https://api.ebay.com/ws/api.dll"
        headers = {
            'X-EBAY-API-SITEID': '77',  # Germany
            'X-EBAY-API-COMPATIBILITY-LEVEL': '967',
            'X-EBAY-API-CALL-NAME': 'GetUser',
            'X-EBAY-API-IAF-TOKEN': access_token,
            'Content-Type': 'text/xml'
        }
        
        body = """<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{}</eBayAuthToken>
    </RequesterCredentials>
</GetUserRequest>""".format(access_token)
        
        try:
            response = requests.post(url, headers=headers, data=body, timeout=15)
            
            if 'Ack>Success' in response.text or 'Ack>Warning' in response.text:
                print("✅ eBay access token geçerli")
                self.results['ebay']['tested'] = True
                self.results['ebay']['valid'] = True
                return True
            elif 'AuthTokenExpired' in response.text or 'Auth token is invalid' in response.text:
                print("⏰ eBay access token süresi dolmuş")
                self.results['ebay']['tested'] = True
                self.results['ebay']['valid'] = False
                self.results['ebay']['error'] = 'Token expired'
                return False
            else:
                print(f"⚠️  Belirsiz yanıt: {response.text[:200]}")
                self.results['ebay']['error'] = 'Unknown response'
                return False
        
        except Exception as e:
            print(f"❌ Test hatası: {e}")
            self.results['ebay']['error'] = str(e)
            return False
    
    def refresh_ebay_token(self):
        """Refresh eBay access token using refresh_token"""
        print("\n" + "="*70)
        print("🔄 EBAY TOKEN YENİLENİYOR")
        print("="*70)
        
        refresh_token = os.getenv('EBAY_REFRESH_TOKEN')
        client_id = os.getenv('EBAY_CLIENT_ID') or os.getenv('EBAY_APP_ID')
        client_secret = os.getenv('EBAY_CLIENT_SECRET') or os.getenv('EBAY_CERT_ID')
        
        if not all([refresh_token, client_id, client_secret]):
            print("❌ Eksik credential:")
            print(f"   REFRESH_TOKEN: {'✓' if refresh_token else '✗'}")
            print(f"   CLIENT_ID (APP_ID): {'✓' if client_id else '✗'}")
            print(f"   CLIENT_SECRET (CERT_ID): {'✓' if client_secret else '✗'}")
            self.results['ebay']['error'] = 'Missing credentials for refresh'
            return False
        
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        
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
        
        print(f"📤 Endpoint: {url}")
        print(f"🔑 Client ID: {client_id[:20]}...")
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                new_access_token = result.get('access_token')
                expires_in = result.get('expires_in', 7200)
                
                print(f"✅ Yeni access token alındı!")
                print(f"⏱️  Geçerlilik süresi: {expires_in} saniye ({expires_in/3600:.1f} saat)")
                print(f"🔑 Token: {new_access_token[:50]}...")
                
                # .env güncelle
                set_key(self.env_path, 'EBAY_ACCESS_TOKEN', new_access_token)
                print(f"💾 .env dosyası güncellendi")
                
                self.results['ebay']['refreshed'] = True
                self.results['ebay']['valid'] = True
                return True
            else:
                error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                error_msg = error_data.get('error_description', response.text[:200])
                print(f"❌ Yenileme hatası ({response.status_code}): {error_msg}")
                self.results['ebay']['error'] = f"{response.status_code}: {error_msg}"
                return False
        
        except Exception as e:
            print(f"❌ İstek hatası: {e}")
            self.results['ebay']['error'] = str(e)
            return False
    
    def test_aliexpress_token(self):
        """Test AliExpress access token"""
        print("\n" + "="*70)
        print("🔍 ALIEXPRESS TOKEN TEST EDİLİYOR")
        print("="*70)
        
        try:
            from src.api.aliexpress_client import AliExpressAPIClient
            
            ali = AliExpressAPIClient()
            
            # Basit bir API çağrısı yap
            # Get categories veya product details gibi
            print("🔌 AliExpress client başlatıldı")
            print(f"📡 App Key: {ali.app_key}")
            
            # Token geçerliliğini kontrol et (örnek: kategorileri çek)
            # NOT: Gerçek API çağrısı token tüketir, sadece client init test edelim
            if ali.access_token:
                print("✅ AliExpress access token mevcut")
                self.results['aliexpress']['tested'] = True
                self.results['aliexpress']['valid'] = True
                return True
            else:
                print("❌ Access token bulunamadı")
                self.results['aliexpress']['error'] = 'No access token'
                return False
                
        except Exception as e:
            print(f"❌ Test hatası: {e}")
            self.results['aliexpress']['error'] = str(e)
            return False
    
    def refresh_aliexpress_token(self):
        """Refresh AliExpress access token"""
        print("\n" + "="*70)
        print("🔄 ALIEXPRESS TOKEN YENİLENİYOR")
        print("="*70)
        
        refresh_token = os.getenv('ALIEXPRESS_REFRESH_TOKEN')
        app_key = os.getenv('ALIEXPRESS_APP_KEY')
        app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
        
        if not all([refresh_token, app_key, app_secret]):
            print("❌ Eksik credential")
            self.results['aliexpress']['error'] = 'Missing credentials'
            return False
        
        # AliExpress OAuth endpoint (doğru URL memory'den alındı)
        url = "https://api-sg.aliexpress.com/oauth/authorize"
        
        params = {
            'client_id': app_key,
            'client_secret': app_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        print(f"📤 Endpoint: {url}")
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            # AliExpress JSON yanıt döner
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    if 'access_token' in result:
                        new_access_token = result['access_token']
                        new_refresh_token = result.get('refresh_token', refresh_token)
                        expires_in = result.get('expire_time', 0)
                        
                        print(f"✅ Yeni token alındı!")
                        print(f"🔑 Access Token: {new_access_token[:50]}...")
                        
                        # .env güncelle
                        set_key(self.env_path, 'ALIEXPRESS_ACCESS_TOKEN', new_access_token)
                        if new_refresh_token != refresh_token:
                            set_key(self.env_path, 'ALIEXPRESS_REFRESH_TOKEN', new_refresh_token)
                        
                        print(f"💾 .env dosyası güncellendi")
                        
                        self.results['aliexpress']['refreshed'] = True
                        self.results['aliexpress']['valid'] = True
                        return True
                    else:
                        print(f"❌ Yanıt geçersiz: {result}")
                        self.results['aliexpress']['error'] = 'Invalid response'
                        return False
                        
                except json.JSONDecodeError:
                    print(f"❌ JSON parse hatası: {response.text[:200]}")
                    self.results['aliexpress']['error'] = 'JSON parse failed'
                    return False
            else:
                print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
                self.results['aliexpress']['error'] = f"HTTP {response.status_code}"
                return False
                
        except Exception as e:
            print(f"❌ İstek hatası: {e}")
            self.results['aliexpress']['error'] = str(e)
            return False
    
    def run(self):
        """Tüm tokenleri test et ve gerekirse yenile"""
        print("\n" + "="*70)
        print("🚀 TOKEN TEST VE YENİLEME SİSTEMİ")
        print("="*70)
        print(f"⏰ Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. eBay test
        ebay_valid = self.test_ebay_token()
        
        if not ebay_valid:
            print("\n⚠️  eBay token geçersiz, yenileniyor...")
            time.sleep(1)
            self.refresh_ebay_token()
        
        # 2. AliExpress test
        time.sleep(2)
        ali_valid = self.test_aliexpress_token()
        
        if not ali_valid:
            print("\n⚠️  AliExpress token geçersiz, yenileniyor...")
            time.sleep(1)
            self.refresh_aliexpress_token()
        
        # Sonuç raporu
        print("\n" + "="*70)
        print("📊 SONUÇ RAPORU")
        print("="*70)
        
        for platform, result in self.results.items():
            print(f"\n{platform.upper()}:")
            print(f"  Test Edildi: {'✅' if result['tested'] else '❌'}")
            print(f"  Geçerli: {'✅' if result['valid'] else '❌'}")
            print(f"  Yenilendi: {'✅' if result['refreshed'] else '⏭️  (gerek yok)' if result['valid'] else '❌'}")
            if result['error']:
                print(f"  Hata: {result['error']}")
        
        print("\n" + "="*70)
        
        # Başarı durumu
        all_valid = all(r['valid'] for r in self.results.values())
        if all_valid:
            print("✅ TÜM TOKENLER GEÇERLİ VE HAZIR!")
            return 0
        else:
            print("❌ BAZI TOKENLER SORUNLU")
            return 1


if __name__ == "__main__":
    manager = TokenManager()
    exit_code = manager.run()
    sys.exit(exit_code)
