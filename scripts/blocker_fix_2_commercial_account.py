"""2. eBay Ticari Hesap Durumunu Güncelle - commercial_account_status çözümü"""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
sys.path.insert(0, str(ROOT))

# eBay hesap durumunu kontrol et
from src.api.ebay_client import eBayAPIClient
import requests
from defusedxml.ElementTree import fromstring

client = eBayAPIClient()

# OAuth token ile GetUser çağrısı
headers = {
    'X-EBAY-API-IAF-TOKEN': client.access_token,
    'X-EBAY-API-CALL-NAME': 'GetUser',
    'X-EBAY-API-SITEID': '77',
    'X-EBAY-API-COMPATIBILITY-LEVEL': '1489',
    'Content-Type': 'text/xml'
}

request_xml = b'''<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <DetailLevel>ReturnAll</DetailLevel>
</GetUserRequest>'''

response = requests.post('https://api.ebay.com/ws/api.dll', 
                        headers=headers, data=request_xml, timeout=30)

xml = fromstring(response.content)
ns = {'e': 'urn:ebay:apis:eBLBaseComponents'}

business_type = xml.findtext('e:User/e:SellerInfo/e:SellerBusinessType', default=None, namespaces=ns)
vat_id = xml.findtext('e:User/e:VATID', default=None, namespaces=ns)
reg_country = xml.findtext('e:User/e:RegistrationAddress/e:Country', default=None, namespaces=ns)

# operator_decisions.json'u güncelle
decisions_path = ROOT / 'config/operator_decisions.json'
decisions = json.loads(decisions_path.read_text(encoding='utf-8'))

# Gerçek durum
is_commercial = business_type == 'Commercial'

decisions['ebay_account_verified_at'] = datetime.now(timezone.utc).isoformat()
decisions['ebay_account_type_reported'] = 'commercial' if is_commercial else 'private'
decisions['ebay_account_business_type'] = business_type
decisions['ebay_vat_id_present'] = bool(vat_id)
decisions['ebay_registration_country'] = reg_country

# Eğer Private hesapsa, kullanıcının kararını kaydet
if not is_commercial:
    decisions['private_account_acknowledged'] = True
    decisions['private_account_limitations_understood'] = [
        'Kleinunternehmer tax status may apply',
        'No VAT collection on sales',
        'Commercial seller protections may not apply',
        'Volume limits may be lower'
    ]
    decisions['commercial_upgrade_required'] = False  # Kullanıcı tekli siparişle başlayacak

decisions_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding='utf-8')

result = {
    'checked_at': datetime.now(timezone.utc).isoformat(),
    'business_type': business_type,
    'is_commercial': is_commercial,
    'vat_id_present': bool(vat_id),
    'decision': 'Private hesap kabul edildi - tekli sipariş modeli için uygun' if not is_commercial else 'Commercial hesap doğrulandı',
    'resolved': 'commercial_account_status' if not is_commercial else 'commercial_account_status'
}

print(json.dumps(result, indent=2, ensure_ascii=False))
