"""1. Readiness Raporu Otomatik Güncelleme - readiness_report_stale çözümü"""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')
sys.path.insert(0, str(ROOT))

from src.readiness import build_report

# Readiness raporunu güncelle
print("Readiness raporu güncelleniyor...")
report = build_report(live=True)

# Kaydet
report_path = ROOT / 'data/readiness_report.json'
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

result = {
    'updated_at': datetime.now(timezone.utc).isoformat(),
    'ready_for_live': report.get('ready_for_live', False),
    'ready_for_supervised_trial': report.get('ready_for_supervised_trial', False),
    'total_checks': len(report.get('checks', [])),
    'passed_checks': sum(1 for c in report.get('checks', []) if c.get('passed')),
    'failed_checks': [c['name'] for c in report.get('checks', []) if not c.get('passed')],
    'resolved': 'readiness_report_stale'
}

print(json.dumps(result, indent=2, ensure_ascii=False))
