import iop
import json
import os
import time

URL = "https://api-sg.aliexpress.com/rest"
APP_KEY = "552270"
APP_SECRET = "pKo6BY...3FsJ"
CODE = "0_2DL4DV3jcU1UOT7WGI1A4rY91"
UUID = "uuid"

OUTPUT_FILE = os.path.expanduser("~") + "\\Desktop\\tokens.json"

client = iop.IopClient(URL, APP_KEY, APP_SECRET)
request = iop.IopRequest('/auth/token/create')
request.add_api_param('code', CODE)
request.add_api_param('uuid', UUID)

print("🔄 İstek atılıyor...")
response = client.execute(request)

print("📦 Cevap:")
print("Type:", response.type)
print("Body:", response.body)

try:
    data = response.body if hasattr(response, 'body') else str(response)
    result = json.loads(data) if isinstance(data, str) else data
    
    if "access_token" in result:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("\n✅ Token kaydedildi: C:\\Users\\Administrator\\Desktop\\tokens.json")
    else:
        print("\n❌ access_token bulunamadı")
        print(result)

except Exception as e:
    print("\n⚠️ Hata:", str(e))
