import hmac, hashlib, time, json, requests

# Ayarlar
APP_KEY = "552270"
APP_SECRET="pKo6BY...3FsJ"  # Kendi secret'inizle degistirin
FILE = r"C:\Users\Administrator\Desktop\Mondeora-Drop-System\tokens.json"
BASE_URL = "https://api-sg.aliexpress.com/rest"
PATH = "/auth/token/refresh"

# Token dosyasini oku
try:
    with open(FILE, "r", encoding="utf-8") as f:
        old = json.load(f)
    refresh_token = old["refresh_token"]
    print("✅ Token dosyasi okundu")
except Exception as e:
    print("❌ Token dosyasi okunamadi:", str(e))
    exit(1)

# Params hazirla
params = {
    "app_key": APP_KEY,
    "timestamp": str(int(time.time()*1000)),
    "sign_method": "sha256",
    "refresh_token": refresh_token
}

# Sign hesapla
base = PATH + "".join(k + params[k] for k in sorted(params))
params["sign"] = hmac.new(APP_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest().upper()

# URL
url = BASE_URL + PATH
print(f"🔄 Request at: {url}")

# Istek at
r = requests.post(url, data=params, timeout=30)
new = r.json()

print("HTTP", r.status_code, "| yeni token geldi mi:", "access_token" in new)

# Sonucu kaydet
if "access_token" in new:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(new, f, indent=2)
    print("✅ Token güncellendi!")
else:
    print("❌ Token alinamadi:")
    print({k: v for k, v in new.items() if "token" not in k})
