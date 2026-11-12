"""Non-interactive launcher. Live operations are explicitly opt-in."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]

class SingleInstance:
    def __enter__(self):
        path = PROJECT_ROOT / 'data/automation.lock'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('a+b')
        self.file.seek(0); self.file.write(b'0'); self.file.flush(); self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Mondeora zaten calisiyor; ikinci islem baslatilmadi.') from None
        return self
    def __exit__(self, *args):
        self.file.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()

def configure_logging(config):
    directory = PROJECT_ROOT / 'logs'
    directory.mkdir(exist_ok=True)
    sensitive = [str(v) for k, v in config.items() if v and any(word in k for word in ('TOKEN', 'SECRET', 'CERT', 'APP_KEY', 'APP_ID'))]
    class Redact(logging.Filter):
        def filter(self, record):
            value = record.getMessage()
            for secret in sensitive:
                value = value.replace(secret, '[REDACTED]')
            record.msg, record.args = value, ()
            return True
    handler = RotatingFileHandler(directory / 'automation.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.addFilter(Redact())
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s', handlers=[handler], force=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description='Mondeora otomasyon: varsayilan mod guvenli izleme.')
    parser.add_argument('--mode', choices=['full', 'automation', 'dashboard'], default='full')
    parser.add_argument('--read-only', action='store_true', help='Bu islem boyunca tum canli ticaret yazmalarini zorunlu kapat')
    parser.add_argument('--check', action='store_true', help='Hazirlik raporu olustur ve cik')
    parser.add_argument('--live-check', action='store_true', help='Salt-okunur canli API kontrollerini de yap')
    parser.add_argument('--research', action='store_true', help='Urunleri kendisi arastirir; ilan veya siparis olusturmaz')
    parser.add_argument('--research-limit', type=int, default=5)
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--smoke-seconds', type=float, default=0, help='Belirtilen sure sonra guvenli kapat')
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 11):
        print('Python 3.11 gerekli.', file=sys.stderr); return 2
    os.chdir(PROJECT_ROOT)
    from src.runtime import read_config, writes_allowed, enable_read_only
    if args.read_only:
        enable_read_only()
    config = read_config()
    configure_logging(config)
    if args.research:
        from src.automation.research import ProductResearcher
        from src.api.aliexpress_client import AliExpressAPIClient
        from src.api.ebay_client import eBayAPIClient
        report = ProductResearcher(AliExpressAPIClient(), eBayAPIClient(), config).run(args.research_limit)
        print(json.dumps({'status': report['status'], 'candidate_count': report['candidate_count'],
            'manual_product_ids_required': False, 'report': str(PROJECT_ROOT / 'data/product_research.json'),
            'candidates': report['candidates'], 'errors': report['errors']}, ensure_ascii=True, indent=2))
        return 0 if report['candidate_count'] else 2
    if args.check or args.live_check:
        from src.readiness import build_report, save_report
        report = build_report(live=args.live_check)
        save_report(report)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if report['ready_for_live'] else 2
    if writes_allowed(config):
        from src.readiness import build_report, save_report
        report = build_report(live=True)
        save_report(report)
        if not report['ready_for_live']:
            print('Canli baslatma engellendi. data/readiness_report.json raporunu inceleyin.', file=sys.stderr)
            return 2
    from src.automation.engine import AutamationEngine
    from src import dashboard
    automation = None
    try:
        with SingleInstance():
            try:
                automation = AutamationEngine()
                dashboard.engine = automation
                from src.operations import OperationalLifecycle
                automation.operations = OperationalLifecycle(automation)
                if args.mode in {'full', 'automation'}:
                    automation.schedule_automations()
                    automation.operations.install()
                    automation.scheduler.start()
                automation.operations.tick()
                print('Mondeora: ' + ('CANLI' if writes_allowed(config) else 'GUVENLI IZLEME - canli islemler kapali'), flush=True)
                deadline = time.monotonic() + args.smoke_seconds if args.smoke_seconds > 0 else float('inf')
                if args.mode in {'full', 'dashboard'}:
                    from werkzeug.serving import make_server
                    server = make_server('127.0.0.1', args.port, dashboard.app, threaded=True)
                    server.timeout = 0.5
                    print(f'Panel: http://127.0.0.1:{args.port}', flush=True)
                    try:
                        while time.monotonic() < deadline:
                            server.handle_request()
                    finally:
                        server.server_close()
                else:
                    while time.monotonic() < deadline:
                        time.sleep(0.5)
            finally:
                # Retain the process lock until all scheduled jobs have stopped.
                if automation is not None:
                    automation.shutdown()
                    automation.engine.dispose()
                    automation = None
                    dashboard.engine = None
    except KeyboardInterrupt:
        print('Sistem durduruldu.')
    except Exception as error:
        print(f'Baslatma hatasi ({type(error).__name__}). Hazirlik raporunu kontrol edin.', file=sys.stderr)
        logging.error('Startup failed: %s', type(error).__name__)
        return 1
    finally:
        if automation is not None:
            automation.shutdown()
    return 0
