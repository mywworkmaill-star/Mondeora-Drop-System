"""Telegram alerting for critical Mondeora monitoring events.

Sends notifications to Telegram when critical thresholds are exceeded.
"""
import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
ALERT_HISTORY_FILE = ROOT / 'data' / 'monitoring' / 'alert_history.jsonl'


class TelegramAlerter:
    """Send alerts to Telegram."""
    
    def __init__(self, chat_id: str = "8472230106"):
        self.chat_id = chat_id
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        
        if not self.bot_token:
            # Try to read from .env file
            env_file = ROOT / '.env'
            if env_file.exists():
                for line in env_file.read_text(encoding='utf-8').splitlines():
                    if line.startswith('TELEGRAM_BOT_TOKEN='):
                        self.bot_token = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Ensure alert history directory exists
        ALERT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def send_alert(self, message: str, parse_mode: str = "HTML") -> Dict:
        """Send a single alert message to Telegram."""
        if not self.bot_token:
            return {
                'success': False,
                'error': 'TELEGRAM_BOT_TOKEN not configured'
            }
        
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=10
            )
            
            result = response.json()
            
            # Log alert
            self._log_alert(message, result.get('ok', False))
            
            if result.get('ok'):
                return {'success': True, 'message_id': result.get('result', {}).get('message_id')}
            else:
                return {
                    'success': False,
                    'error': result.get('description', 'Unknown error')
                }
                
        except Exception as e:
            error_msg = f'{type(e).__name__}: {str(e)}'[:200]
            self._log_alert(message, False, error_msg)
            return {'success': False, 'error': error_msg}
    
    def send_monitoring_alerts(self, alerts: List[Dict]) -> Dict:
        """Send monitoring alerts to Telegram."""
        if not alerts:
            return {
                'success': True,
                'alerts_sent': 0,
                'message': 'No alerts to send'
            }
        
        # Group alerts by severity
        critical_alerts = [a for a in alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts if a.get('severity') == 'warning']
        
        results = []
        
        # Send critical alerts immediately
        if critical_alerts:
            message = self._format_critical_alerts(critical_alerts)
            result = self.send_alert(message)
            results.append({'type': 'critical', 'count': len(critical_alerts), 'result': result})
        
        # Send warnings if any
        if warning_alerts:
            message = self._format_warning_alerts(warning_alerts)
            result = self.send_alert(message)
            results.append({'type': 'warning', 'count': len(warning_alerts), 'result': result})
        
        success_count = sum(1 for r in results if r['result'].get('success'))
        
        return {
            'success': success_count > 0,
            'alerts_sent': success_count,
            'total_alerts': len(alerts),
            'results': results
        }
    
    def send_daily_summary(self, metrics: Dict) -> Dict:
        """Send daily monitoring summary."""
        message = self._format_daily_summary(metrics)
        return self.send_alert(message)
    
    def _format_critical_alerts(self, alerts: List[Dict]) -> str:
        """Format critical alerts for Telegram."""
        lines = [
            "🚨 <b>CRITICAL ALERTS - MONDEORA</b> 🚨",
            f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
            ""
        ]
        
        for i, alert in enumerate(alerts, 1):
            category = alert.get('category', 'unknown')
            message = alert.get('message', 'No message')
            action = alert.get('action', 'No action specified')
            
            lines.append(f"<b>{i}. {category.upper().replace('_', ' ')}</b>")
            lines.append(f"⚠️ {message}")
            lines.append(f"👉 Action: {action}")
            
            # Add specific details
            if 'platform' in alert:
                lines.append(f"Platform: {alert['platform']}")
            if 'job' in alert:
                lines.append(f"Job: {alert['job']}")
            if 'last_success' in alert:
                lines.append(f"Last success: {alert['last_success']}")
            
            lines.append("")
        
        lines.append("⚡ <b>Immediate action required!</b>")
        
        return '\n'.join(lines)
    
    def _format_warning_alerts(self, alerts: List[Dict]) -> str:
        """Format warning alerts for Telegram."""
        lines = [
            "⚠️ <b>WARNING - MONDEORA</b>",
            f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
            ""
        ]
        
        for i, alert in enumerate(alerts, 1):
            category = alert.get('category', 'unknown')
            message = alert.get('message', 'No message')
            
            lines.append(f"<b>{i}. {category.upper().replace('_', ' ')}</b>")
            lines.append(f"⚠️ {message}")
            
            if 'action' in alert:
                lines.append(f"👉 {alert['action']}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def _format_daily_summary(self, metrics: Dict) -> str:
        """Format daily monitoring summary."""
        lines = [
            "📊 <b>MONDEORA DAILY SUMMARY</b>",
            f"<i>{datetime.now().strftime('%Y-%m-%d')}</i>",
            ""
        ]
        
        # Token status
        token_status = metrics.get('token_status', {})
        lines.append("<b>🔐 Tokens:</b>")
        for platform, status in token_status.items():
            if status.get('status') == 'ok':
                hours = status.get('hours_left', 0)
                lines.append(f"  ✅ {platform.upper()}: {hours}h remaining")
            else:
                lines.append(f"  ❌ {platform.upper()}: {status.get('status', 'unknown')}")
        lines.append("")
        
        # Sales
        sales = metrics.get('sales_status', {})
        if sales:
            lines.append("<b>💰 Sales (Last 7 days):</b>")
            lines.append(f"  Sales: {sales.get('sales_7d', 0)}")
            lines.append(f"  Revenue: EUR {sales.get('revenue_7d', 0):.2f}")
            lines.append(f"  Profit: EUR {sales.get('profit_7d', 0):.2f}")
            if sales.get('days_since_sale'):
                lines.append(f"  Last sale: {sales.get('days_since_sale')} days ago")
            lines.append("")
        
        # Listing visibility
        visibility = metrics.get('listing_visibility', {})
        if visibility:
            lines.append("<b>📦 Listings:</b>")
            lines.append(f"  Total: {visibility.get('total_products', 0)}")
            lines.append(f"  Listed: {visibility.get('listed', 0)} ({visibility.get('visibility_pct', 0)}%)")
            if visibility.get('zero_stock_listings', 0) > 0:
                lines.append(f"  ⚠️ Zero stock: {visibility['zero_stock_listings']}")
            lines.append("")
        
        # Job status
        jobs = metrics.get('job_failures', {})
        if jobs.get('failed_jobs'):
            lines.append("<b>⚠️ Failed Jobs:</b>")
            for job, details in jobs['failed_jobs'].items():
                lines.append(f"  ❌ {job}: {details['consecutive_failures']} consecutive failures")
        else:
            lines.append("<b>✅ All jobs running normally</b>")
            lines.append("")
        
        return '\n'.join(lines)
    
    def _log_alert(self, message: str, success: bool, error: Optional[str] = None):
        """Log alert to history file."""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'success': success,
            'message': message[:200],  # Truncate long messages
            'error': error
        }
        
        with open(ALERT_HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')


def send_alerts_from_monitoring(dashboard_file: Optional[Path] = None) -> Dict:
    """Load monitoring dashboard and send alerts."""
    if dashboard_file is None:
        dashboard_file = ROOT / 'data' / 'monitoring_dashboard.json'
    
    if not dashboard_file.exists():
        return {
            'success': False,
            'error': 'Dashboard file not found. Run monitoring first.'
        }
    
    try:
        dashboard = json.loads(dashboard_file.read_text(encoding='utf-8'))
        alerts = dashboard.get('alerts', [])
        
        alerter = TelegramAlerter()
        return alerter.send_monitoring_alerts(alerts)
        
    except Exception as e:
        return {
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'[:200]
        }


def send_test_alert() -> Dict:
    """Send a test alert to verify Telegram integration."""
    alerter = TelegramAlerter()
    message = (
        "✅ <b>MONDEORA MONITORING TEST</b>\n\n"
        f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n\n"
        "Monitoring system is active and configured correctly.\n"
        "You will receive alerts when:\n"
        "  🔐 Tokens expire in < 1 hour\n"
        "  ❌ Jobs fail 3+ times\n"
        "  💰 Zero sales for 7+ days\n"
        "  📦 50%+ listings invisible\n"
    )
    return alerter.send_alert(message)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        result = send_test_alert()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = send_alerts_from_monitoring()
        print(json.dumps(result, ensure_ascii=False, indent=2))
