"""MASTER: Tüm Blokerleri Çöz ve Readiness Güncelle"""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import sys

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
FIXES = Path('C:/Users/Administrator/AppData/Local/hermes/cache/scratch')

fixes = [
    ('fix_1_readiness_update.py', 'Readiness raporu güncelleme'),
    ('fix_2_commercial_account.py', 'eBay hesap durumu'),
    ('fix_3_business_tax.py', 'İşletme ve vergi planı'),
    ('fix_4_aliexpress_api.py', 'AliExpress API alternatif'),
    ('fix_5_test_suite.py', 'Test suite entegrasyonu'),
    ('fix_6_supplier_evidence.py', 'Tedarikçi belge entegrasyonu'),
    ('fix_7_demand.py', 'Talep analizi'),
    ('fix_8_supplier_agreement.py', 'Tedarikçi anlaşması')
]

results = []
print("🔧 Bloker çözümleri başlatılıyor...\n")

for script, desc in fixes:
    print(f"▶ {desc}...")
    try:
        result = subprocess.run(
            [sys.executable, str(FIXES / script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            try:
                output = json.loads(result.stdout)
                results.append({
                    'fix': desc,
                    'status': 'success',
                    'result': output
                })
                print(f"  ✓ {desc} - OK")
            except:
                results.append({
                    'fix': desc,
                    'status': 'success',
                    'output': result.stdout[:200]
                })
                print(f"  ✓ {desc} - OK")
        else:
            results.append({
                'fix': desc,
                'status': 'failed',
                'error': result.stderr[:200]
            })
            print(f"  ✗ {desc} - FAILED")
    except Exception as e:
        results.append({
            'fix': desc,
            'status': 'error',
            'error': str(e)
        })
        print(f"  ✗ {desc} - ERROR: {e}")

print("\n" + "="*60)

# Final readiness update
print("\n📊 Final readiness raporu güncelleniyor...")
sys.path.insert(0, str(ROOT))
from src.readiness import build_report

report = build_report(live=True)
report_path = ROOT / 'data/readiness_report.json'
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

# Özet
summary = {
    'completed_at': datetime.now(timezone.utc).isoformat(),
    'fixes_run': len(results),
    'fixes_successful': sum(1 for r in results if r['status'] == 'success'),
    'fixes_failed': sum(1 for r in results if r['status'] != 'success'),
    'readiness_updated': True,
    'ready_for_live': report.get('ready_for_live', False),
    'ready_for_supervised_trial': report.get('ready_for_supervised_trial', False),
    'remaining_blockers': [c['name'] for c in report.get('checks', []) if not c.get('passed')],
    'results': results
}

summary_path = ROOT / 'data/audit/blocker_resolution_summary.json'
summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

print(f"\n✅ {summary['fixes_successful']}/{summary['fixes_run']} çözüm başarılı")
print(f"📋 Kalan blokerlar: {len(summary['remaining_blockers'])}")
print(f"🎯 Supervised trial: {summary['ready_for_supervised_trial']}")
print(f"\nDetaylı rapor: data/audit/blocker_resolution_summary.json")

print(json.dumps(summary, indent=2, ensure_ascii=False))
