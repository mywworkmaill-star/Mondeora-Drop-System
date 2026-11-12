"""
eBay Production - Automatic Token Refresh Manager
Her 30 dakikada access token'ı refresh token ile yenile
Token hiçbir zaman süresi dolmaz
"""

import os
import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

class EbayAutoRefreshManager:
    def __init__(self):
        load_dotenv()
        
        self.refresh_token = os.getenv("EBAY_REFRESH_TOKEN")
        self.oauth_endpoint = "https://api.ebay.com/identity/v1/oauth2/token"
        self.token_file = Path("data/ebay_auto_refresh_token.json")
        self.env_file = find_dotenv() or '.env'
        
        self.load_token_info()
    
    def load_token_info(self):
        """Token bilgisini yükle"""
        if self.token_file.exists():
            with open(self.token_file, 'r') as f:
                self.token_info = json.load(f)
        else:
            self.token_info = {
                "status": "not_initialized",
                "renewal_count": 0,
            }
    
    def refresh_access_token(self):
        """Refresh token ile yeni access token al"""
        print(f"\n🔄 Access Token Yenileniyor...")
        print(f"   Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            response = requests.post(
                self.oauth_endpoint,
                data=payload,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                
                print(f"   ✅ Yeni Access Token alındı!")
                print(f"      Token: {new_access_token[:50]}...")
                print(f"      Expires: {expires_in} seconds")
                
                # .env güncelle
                self.update_env_token(new_access_token)
                
                # Metadata güncelle
                self.token_info.update({
                    "access_token": new_access_token[:50] + "...",
                    "last_renewal": datetime.now().isoformat(),
                    "next_renewal": (datetime.now() + timedelta(minutes=30)).isoformat(),
                    "renewal_count": self.token_info.get("renewal_count", 0) + 1,
                    "status": "active",
                })
                
                self.save_token_info()
                
                return True
            else:
                print(f"   ❌ Failed: {response.status_code}")
                print(f"      Error: {response.text[:100]}")
                
                self.token_info["error_count"] = self.token_info.get("error_count", 0) + 1
                self.save_token_info()
                
                return False
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            self.token_info["error_count"] = self.token_info.get("error_count", 0) + 1
            self.save_token_info()
            return False
    
    def update_env_token(self, new_token):
        """Yeni token'ı .env'ye yaz"""
        with open(self.env_file, 'r') as f:
            env_content = f.read()
        
        lines = env_content.split('\n')
        updated = []
        found = False
        
        for line in lines:
            if line.startswith('EBAY_ACCESS_TOKEN='):
                updated.append(f'EBAY_ACCESS_TOKEN={new_token}')
                found = True
            else:
                updated.append(line)
        
        if not found:
            updated.append(f'EBAY_ACCESS_TOKEN={new_token}')
        
        with open(self.env_file, 'w') as f:
            f.write('\n'.join(updated))
        
        # OS'de de güncelle
        os.environ['EBAY_ACCESS_TOKEN'] = new_token
    
    def save_token_info(self):
        """Token bilgisini kaydet"""
        self.token_file.parent.mkdir(exist_ok=True)
        with open(self.token_file, 'w') as f:
            json.dump(self.token_info, f, indent=2)
    
    def should_refresh(self):
        """Token yenilenmesi gerekli mi kontrol et"""
        if "next_renewal" not in self.token_info:
            return True
        
        next_renewal = datetime.fromisoformat(self.token_info["next_renewal"])
        return datetime.now() >= next_renewal
    
    def run_check(self):
        """Otomatik kontrol ve yenileme çalıştır"""
        print(f"\n╔════════════════════════════════════════════════════════════╗")
        print(f"║ 🔄 eBay Auto-Token-Refresh Check                           ║")
        print(f"║ {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^56}║")
        print(f"╚════════════════════════════════════════════════════════════╝")
        
        if self.should_refresh():
            print(f"\n✅ Token yenilenmesi zamanı geldi!")
            success = self.refresh_access_token()
            return success
        else:
            next_renewal = datetime.fromisoformat(self.token_info.get("next_renewal", datetime.now().isoformat()))
            time_left = next_renewal - datetime.now()
            
            print(f"\n⏰ Token henüz geçerli")
            print(f"   Sonraki yenileme: {next_renewal.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Kalan süre: {time_left.total_seconds()/60:.1f} dakika")
            
            return True

if __name__ == "__main__":
    manager = EbayAutoRefreshManager()
    manager.run_check()
