"""5. Test Suite Entegrasyonu - current_revision_software_tests çözümü"""
from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import sys
import hashlib

ROOT = Path('C:/Users/Administrator/Desktop/Mondeora-Drop-System')

# Kaynak parmak izi oluştur
def source_fingerprint():
    """Calculate fingerprint of all Python source files"""
    hasher = hashlib.sha256()
    py_files = sorted(ROOT.rglob('*.py'))
    for path in py_files:
        if '.venv' in str(path) or '__pycache__' in str(path):
            continue
        try:
            hasher.update(path.read_bytes())
        except:
            pass
    return hasher.hexdigest()[:16]

# Testleri çalıştır
print("Test suite çalıştırılıyor...")
result = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests', '-q', '--tb=no'],
    cwd=ROOT,
    capture_output=True,
    text=True,
    timeout=180
)

# Sonuçları parse et
output = result.stdout + result.stderr
passed = failed = errors = 0

for line in output.split('\n'):
    if 'passed' in line:
        import re
        match = re.search(r'(\d+)\s+passed', line)
        if match:
            passed = int(match.group(1))
        match = re.search(r'(\d+)\s+failed', line)
        if match:
            failed = int(match.group(1))

verification = {
    'verified_at': datetime.now(timezone.utc).isoformat(),
    'source_fingerprint': source_fingerprint(),
    'passed': result.returncode == 0 and failed == 0,
    'test_count': passed,
    'errors': errors,
    'failures': failed,
    'exit_code': result.returncode
}

# Kaydet
verification_path = ROOT / 'data/software_verification.json'
verification_path.write_text(json.dumps(verification, indent=2), encoding='utf-8')

result_summary = {
    'updated_at': datetime.now(timezone.utc).isoformat(),
    'tests_passed': passed,
    'tests_failed': failed,
    'verification_passed': verification['passed'],
    'resolved': 'current_revision_software_tests' if verification['passed'] else 'tests_failed'
}

print(json.dumps(result_summary, indent=2, ensure_ascii=False))
