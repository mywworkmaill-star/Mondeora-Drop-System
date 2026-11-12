# ============================================================================
# Mondeora Drop System - Otomatik Token Refresh (PowerShell)
# ============================================================================
# Bu script şunları yapar:
#   1. Proje ana dizinine geçer
#   2. Python 3.11 ile token_auto_refresh_continuous.py'yi çalıştırır
#   3. Her 5. dakikada 1 kez otomatik token kontrolü yapar
#   4. Gerekli halde otomatik yenilenir
#   5. Logları logs\token_refresh.log'ta tutar
#
# Kullanım:
#   1. Dosyayı c:/Users/Administrator/Desktop/Mondeora-Drop-System/ klasöre kopyala
#   2. PowerShell'de: .\start_token_refresh.ps1
#
# Alternatif:
#   cd C:\Users\Administrator\Desktop\Mondeora-Drop-System
#   C:\Program Files\Python311\python.exe token_auto_refresh_continuous.py
# ============================================================================

$ErrorActionPreference = "Stop"

# =========================
# 1. YOL AYARLARI
# =========================
$ProjectRoot = "C:\Users\Administrator\Desktop\Mondeora-Drop-System"
$PythonExe = "C:\Program Files\Python311\python.exe"
$PythonScript = "$ProjectRoot\token_auto_refresh_continuous.py"
$LogFile = "$ProjectRoot\logs\token_refresh.log"

# =========================
# 2. ÖN KONTROL
# =========================
if (-not (Test-Path $PythonScript)) {
    Write-Host "❌ HATA: $PythonScript bulunamadı!" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "❌ HATA: $PythonExe bulunamadı! Python 3.11 kurulu değil mi?" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "❌ HATA: $ProjectRoot\.env bulunamadı! Token bilgilerini girin." -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "🚀 MONDEORA AUTOMATIC TOKEN REFRESH" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "📁 Proje: $ProjectRoot"
Write-Host "🐍 Python: $PythonExe"
Write-Host "📝 Script: $PythonScript"
Write-Host "📋 Log: $LogFile"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  Sistemin 5. dakikada 1 kez otomatik token kontrolü yapacaktır."
Write-Host "⏹️  Durdurmak için Ctrl+C'ye basın."
Write-Host ""

# =========================
# 3. ÇALIŞTIRMA
# =========================
try {
    $Process = Start-Process -FilePath $PythonExe `
        -ArgumentList "$PythonScript" `
        -WorkingDirectory $ProjectRoot `
        -PassThru `
        -NoNewWindow

    # Process'ı bekle
    Wait-Process -Id $Process.Id -Timeout 3600

    Write-Host ""
    Write-Host "✅ Sistem durduruldu." -ForegroundColor Green

} catch {
    Write-Host "❌ HATA: $_" -ForegroundColor Red
    exit 1
}
