"""
Mondeora Drop System - Otomatik Token Refresh (Başlatıcı)
========================================================
Bu script şunları yapar:
  1. Proje kök dizinini otomatik belirler
  2. Engine + Token Auto-Refresh sistemlerini başlatır
  3. Her 5. dakikada 1 kez token kontrolü yapar
  4. Gerekli halde otomatik yenilenir
  5. System log'larını izler

# Kullanım:
#   cd C:\\Users\\Administrator\\Desktop\\Mondeora-Drop-System
#   C:\\Program Files\\Python311\\python.exe token_auto_refresh_continuous.py
"""

import sys
import os
import time
import logging
import schedule
from pathlib import Path

# =========================
# 1. PROJE YOLU TESPİTİ
# =========================
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
# src/ dizinini ekle
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# =========================
# 2. LOG AYARLARI
# =========================
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "token_refresh.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TokenAutoRefresh")

# =========================
# 3. SİSTEM KODLAMA
# =========================
def setup_environment():
    """Ortamı yükle (dotenv, sys.path, vb.)"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    logger.info("✅ Ortam yüklendi (dotenv)")
    logger.info(f"📁 Proje kökü: {PROJECT_ROOT}")

def start_automation_engine():
    """AutamationEngine'i başlat"""
    # Engine importu
    from src.automation.engine import AutamationEngine
    engine = AutamationEngine()
    logger.info("✅ AutamationEngine başlatıldı")
    logger.info(f"   -> ebay_token_refresher: {engine.ebay_token_refresher is not None}")
    logger.info(f"   -> ebay_recovery: {engine.ebay_recovery is not None}")
    return engine

def check_and_refresh_tokens(engine):
    """Token kontrolü ve gerekliğinde yenilenmesi"""
    try:
        logger.info("🔄 Token kontrol ediliyor...")
        
        # eBay Token kontrolü
        if engine.ebay_token_refresher:
            result = engine.ebay_token_refresher.refresh_token()
            if result.get("success"):
                logger.info(f"   ✅ eBay Token yenilendi: {result.get('method')}")
            else:
                logger.warning(f"   ⚠️  eBay Token: {result.get('message', 'Bilinmeyen hata')}")
        
        # AliExpress Token kontrolü
        if engine.ali_token_refresher:
            result = engine.ali_token_refresher.check_and_refresh_if_needed()
            if result.get("success"):
                logger.info(f"   ✅ AliExpress Token yenilendi")
            elif result.get("status") == "not_needed":
                logger.info(f"   ℹ️  AliExpress Token hala geçerli")
            else:
                logger.warning(f"   ⚠️  AliExpress Token: {result.get('message', 'Bilinmeyen hata')}")
        
        logger.info("✅ Token kontrolüTamamlandı")
    except Exception as e:
        logger.error(f"❌ Token kontrol hatası: {str(e)[:80]}")

def run_forever():
    """Main schedule loop"""
    logger.info("=" * 60)
    logger.info("🚀 MONDEORA AUTOMATIC TOKEN REFRESH STARTED")
    logger.info("=" * 60)
    
    # Environment setup
    setup_environment()
    
    # Engine start
    engine = start_automation_engine()
    
    # Schedule jobs
    # Job 1: Her 5. dakikada token kontrolü
    schedule.every(5).minutes.do(
        check_and_refresh_tokens, engine=engine
    )
    
    # Job 2: Her 5. dakikada 1 kez otomatik refresh system çalışır
    schedule.every(5).minutes.do(
        lambda: logger.debug("🔄 Auto refresh system check")
    )
    
    logger.info("📋 Planlanan görevler:")
    logger.info("   • Her 5. dakikada 1 kez token kontrolü (check_and_refresh_tokens)")
    logger.info("   • Her 5. dakikada 1 kez auto refresh check (debug)")
    
    # Main loop
    logger.info("⏳ Sistem çalışmaya başlıyor... (CTRL+C ile durdurabilirsiniz)")
    logger.info("=" * 60)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("⏹️  Sistem durduruldu (KeyboardInterrupt)")
        sys.exit(0)

# =========================
# 4. BAŞLATMA
# =========================
if __name__ == "__main__":
    run_forever()
