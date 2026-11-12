import os
"""
ESKİ TOKEN İPTAL DOĞRULAMA
Portal'dan iptal ettikten sonra çalıştırın
"""
import base64
import requests

# ESKİ TOKEN (GitHub'da sızdı)
old_refresh_token = os.environ.get('OLD_EBAY_REFRESH_TOKEN', '')  # pass the old token via env; never commit it
client_id = os.environ.get('EBAY_APP_ID', '')
client_secret = os.environ.get('EBAY_CERT_ID', '')

print("\n" + "="*70)
print("🧪 ESKİ TOKEN İPTAL DOĞRULAMA TESTİ")
print("="*70)
print(f"Token: {old_refresh_token[:40]}...")
print()

auth_string = f'{client_id}:{client_secret}'
auth_b64 = base64.b64encode(auth_string.encode()).decode()

url = 'https://api.ebay.com/identity/v1/oauth2/token'
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': f'Basic {auth_b64}'
}
data = {
    'grant_type': 'refresh_token',
    'refresh_token': old_refresh_token
}

print("📤 Test isteği gönderiliyor...")

try:
    response = requests.post(url, headers=headers, data=data, timeout=30)
    
    print(f"📊 HTTP Status: {response.status_code}")
    print()
    
    if response.status_code == 200:
        print("🔴 HATA: ESKİ TOKEN HÂLÂ ÇALIŞIYOR!")
        print("⚠️  Portal'dan iptal işlemi tamamlanmamış")
        print()
        print("📋 YAPILACAK:")
        print("   1. developer.ebay.com → My Account")
        print("   2. Application Keys → User Tokens")
        print("   3. En eski token'ı REVOKE edin")
        exit(1)
        
    elif response.status_code == 400:
        result = response.json()
        error = result.get('error', '').lower()
        
        if 'invalid' in error or 'expired' in error:
            print("✅ BAŞARILI! ESKİ TOKEN İPTAL EDİLDİ!")
            print("✅ Artık kullanılamıyor")
            print()
            print("🎉 GÜVENLİK SORUNU ÇÖZÜLDÜ!")
            print("="*70)
            exit(0)
        else:
            print(f"⚠️  Beklenmeyen hata: {result}")
            exit(1)
    else:
        print(f"⚠️  Beklenmeyen durum: {response.text[:200]}")
        exit(1)
        
except Exception as e:
    print(f"❌ Test hatası: {e}")
    exit(1)
