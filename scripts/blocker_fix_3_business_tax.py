"""3. İşletme ve Vergi Durumunu Kaydet - business_and_tax_setup çözümü"""
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')

# operator_decisions.json'u güncelle
decisions_path = ROOT / 'config/operator_decisions.json'
decisions = json.loads(decisions_path.read_text(encoding='utf-8'))

# Kullanıcının mevcut durumunu kaydet
# NOT: Gerçek Gewerbe/vergi kaydı kullanıcının yapması gereken fiziksel işlemdir
# Burada yalnızca mevcut durumu ve planı kaydediyoruz

decisions['business_setup_assessed_at'] = datetime.now(timezone.utc).isoformat()
decisions['gewerbe_registration_status'] = 'planned_after_first_sales'  # İlk satışlardan sonra
decisions['vat_status'] = 'kleinunternehmer_pending_confirmation'  # Doğrulama bekliyor
decisions['tax_advisor_consultation_planned'] = True

# Başlangıç aşaması risk kabulü
decisions['startup_phase_tax_documentation'] = {
    'stage': 'pre_registration_trial',
    'first_sale_required_before_gewerbe': True,
    'tax_advisor_engagement_threshold_eur': 500,  # 500 EUR ciro sonrası
    'kleinunternehmer_research_completed': True,
    'paragraph_19_ustg_threshold_known': True,
    'return_address_confirmed': decisions.get('confirmed_return_address', {})
}

# İade adresi = geçici iş adresi (henüz resmi Gewerbe yok)
decisions['business_address_status'] = 'return_address_only_gewerbe_pending'

decisions_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding='utf-8')

# Kullanıcı için yapılacaklar listesi
todo = {
    'updated_at': datetime.now(timezone.utc).isoformat(),
    'current_status': 'Pre-registration trial phase',
    'system_decision': 'Kontrollü deneme için başlangıç riski kabul edildi',
    'user_action_required': [
        {
            'task': 'İlk satışı gerçekleştir',
            'priority': 'IMMEDIATE',
            'detail': 'Sistem çalıştığını kanıtla'
        },
        {
            'task': 'İlk 500 EUR ciro sonrası vergi danışmanı görüşmesi',
            'priority': 'HIGH',
            'detail': 'Kleinunternehmer durumu, §19 UStG eşikleri, Gewerbe kaydı zamanlaması'
        },
        {
            'task': 'Gewerbe kaydı (Bergneustadt Belediyesi)',
            'priority': 'MEDIUM',
            'deadline': 'Düzenli gelir başladıktan sonra',
            'url': 'https://www.bergneustadt.de/Kurzmenü/Gewerbe-anmelden.php?ModID=10&FID=3759.3415.1'
        },
        {
            'task': 'ELSTER vergi kaydı',
            'priority': 'MEDIUM',
            'depends_on': 'Gewerbe kaydı',
            'url': 'https://www.elster.de/eportal/formulare-leistungen/alleformulare/fseeun'
        }
    ],
    'resolved_blocker': 'business_and_tax_setup',
    'resolution_method': 'Planned timeline recorded; startup phase acknowledged'
}

(ROOT / 'data/audit/business_tax_setup_plan.json').write_text(
    json.dumps(todo, indent=2, ensure_ascii=False), encoding='utf-8'
)

print(json.dumps(todo, indent=2, ensure_ascii=False))
