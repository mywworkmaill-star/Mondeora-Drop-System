"""Real-time monitoring for critical Mondeora metrics.

Tracks:
- Token expiry (< 1 hour warning)
- Failed jobs (3+ consecutive)
- Zero sales (7+ days)
- Invisible listings (> 50%)
- API rate limit approached
"""
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
MONITORING_DIR = ROOT / 'data' / 'monitoring'
DASHBOARD_FILE = ROOT / 'data' / 'monitoring_dashboard.json'


class MonitoringMetrics:
    """Collect and analyze critical system metrics."""
    
    def __init__(self):
        MONITORING_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self.metrics = {}
        self.alerts = []
        
    def collect_all_metrics(self) -> Dict:
        """Collect all monitoring metrics."""
        self.metrics = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'token_status': self._check_token_expiry(),
            'job_failures': self._check_failed_jobs(),
            'sales_status': self._check_sales(),
            'listing_visibility': self._check_listing_visibility(),
            'api_limits': self._check_api_limits(),
        }
        
        # Generate alerts based on metrics
        self._generate_alerts()
        
        # Save dashboard
        self._save_dashboard()
        
        return {
            'metrics': self.metrics,
            'alerts': self.alerts,
            'status': 'critical' if any(a['severity'] == 'critical' for a in self.alerts) 
                     else 'warning' if self.alerts 
                     else 'healthy'
        }
    
    def _check_token_expiry(self) -> Dict:
        """Check token expiry times."""
        status = {}
        
        for name, path in [
            ('ebay', ROOT / 'data' / 'ebay_oauth_metadata.json'),
            ('aliexpress', ROOT / 'data' / 'aliexpress_oauth_metadata.json')
        ]:
            try:
                if not path.exists():
                    status[name] = {'status': 'missing', 'minutes_left': None}
                    continue
                    
                metadata = json.loads(path.read_text(encoding='utf-8'))
                expires_at = metadata.get('expires_at', 0)
                
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at).timestamp()
                
                seconds_left = int(float(expires_at) - time.time())
                minutes_left = seconds_left // 60
                hours_left = seconds_left // 3600
                
                if seconds_left < 3600:  # < 1 hour
                    status[name] = {
                        'status': 'critical',
                        'minutes_left': minutes_left,
                        'hours_left': hours_left
                    }
                elif seconds_left < 7200:  # < 2 hours
                    status[name] = {
                        'status': 'warning',
                        'minutes_left': minutes_left,
                        'hours_left': hours_left
                    }
                else:
                    status[name] = {
                        'status': 'ok',
                        'minutes_left': minutes_left,
                        'hours_left': hours_left
                    }
                    
            except Exception as e:
                status[name] = {'status': 'error', 'error': str(e)[:200]}
        
        return status
    
    def _check_failed_jobs(self) -> Dict:
        """Check for consecutive job failures."""
        if not self.db_path.exists():
            return {'status': 'db_missing'}
        
        try:
            conn = sqlite3.connect(f'file:{self.db_path.as_posix()}?mode=ro', uri=True)
            c = conn.cursor()
            
            # Get last 5 runs per job
            c.execute('''
                SELECT automation_name, status, started_at
                FROM automation_runs
                WHERE id IN (
                    SELECT id FROM automation_runs
                    ORDER BY started_at DESC
                    LIMIT 100
                )
                ORDER BY automation_name, started_at DESC
            ''')
            
            rows = c.fetchall()
            conn.close()
            
            # Group by job name
            job_history = {}
            for name, status, started_at in rows:
                if name not in job_history:
                    job_history[name] = []
                job_history[name].append({
                    'status': status,
                    'started_at': started_at
                })
            
            # Check for consecutive failures
            failed_jobs = {}
            for name, runs in job_history.items():
                recent = runs[:5]  # Last 5 runs
                consecutive_fails = 0
                
                for run in recent:
                    if run['status'] != 'completed':
                        consecutive_fails += 1
                    else:
                        break
                
                if consecutive_fails >= 3:
                    failed_jobs[name] = {
                        'consecutive_failures': consecutive_fails,
                        'last_success': next(
                            (r['started_at'] for r in recent if r['status'] == 'completed'),
                            'never'
                        ),
                        'last_attempt': recent[0]['started_at'] if recent else None
                    }
            
            return {
                'status': 'critical' if failed_jobs else 'ok',
                'failed_jobs': failed_jobs,
                'total_jobs_tracked': len(job_history)
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)[:200]}
    
    def _check_sales(self) -> Dict:
        """Check for zero sales in last 7 days."""
        if not self.db_path.exists():
            return {'status': 'db_missing'}
        
        try:
            conn = sqlite3.connect(f'file:{self.db_path.as_posix()}?mode=ro', uri=True)
            c = conn.cursor()
            
            # Check sales in last 7 days
            c.execute('''
                SELECT COUNT(*), COALESCE(SUM(sale_price), 0), COALESCE(SUM(profit), 0)
                FROM sales
                WHERE sale_date >= date('now', '-7 days')
            ''')
            
            count, revenue, profit = c.fetchone()
            
            # Check last sale date
            c.execute('SELECT MAX(sale_date) FROM sales')
            last_sale = c.fetchone()[0]
            
            conn.close()
            
            days_since_sale = None
            if last_sale:
                last_sale_dt = datetime.fromisoformat(last_sale)
                days_since_sale = (datetime.now() - last_sale_dt).days
            
            status = 'ok'
            if count == 0:
                if days_since_sale and days_since_sale >= 7:
                    status = 'critical'
                elif days_since_sale and days_since_sale >= 3:
                    status = 'warning'
            
            return {
                'status': status,
                'sales_7d': count or 0,
                'revenue_7d': float(revenue or 0),
                'profit_7d': float(profit or 0),
                'last_sale_date': last_sale,
                'days_since_sale': days_since_sale
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)[:200]}
    
    def _check_listing_visibility(self) -> Dict:
        """Check percentage of invisible/inactive listings."""
        if not self.db_path.exists():
            return {'status': 'db_missing'}
        
        try:
            conn = sqlite3.connect(f'file:{self.db_path.as_posix()}?mode=ro', uri=True)
            c = conn.cursor()
            
            # Count total and listed
            c.execute('SELECT COUNT(*), SUM(is_listed) FROM products')
            total, listed = c.fetchone()
            
            # Count zero stock listings
            c.execute('''
                SELECT COUNT(*) FROM products 
                WHERE is_listed = 1 AND stock_quantity = 0
            ''')
            zero_stock = c.fetchone()[0] or 0
            
            conn.close()
            
            if not total or total == 0:
                return {'status': 'no_products'}
            
            listed = listed or 0
            visibility_pct = (listed / total) * 100
            invisible_pct = 100 - visibility_pct
            
            status = 'ok'
            if invisible_pct > 50:
                status = 'critical'
            elif invisible_pct > 30:
                status = 'warning'
            
            return {
                'status': status,
                'total_products': total,
                'listed': listed,
                'unlisted': total - listed,
                'visibility_pct': round(visibility_pct, 1),
                'invisible_pct': round(invisible_pct, 1),
                'zero_stock_listings': zero_stock
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)[:200]}
    
    def _check_api_limits(self) -> Dict:
        """Check API call frequency and potential rate limits."""
        # Check healing state for circuit breaker status
        healing_state_path = ROOT / 'data' / 'healing_state.json'
        
        status = {
            'status': 'ok',
            'circuit_breakers': {}
        }
        
        try:
            if healing_state_path.exists():
                healing = json.loads(healing_state_path.read_text(encoding='utf-8'))
                
                for name, state in healing.get('circuit_breakers', {}).items():
                    if state.get('state') != 'closed':
                        status['circuit_breakers'][name] = state
                        status['status'] = 'warning'
                        
        except Exception as e:
            status['error'] = str(e)[:200]
        
        return status
    
    def _generate_alerts(self):
        """Generate alerts based on collected metrics."""
        self.alerts = []
        
        # Token expiry alerts
        token_status = self.metrics.get('token_status', {})
        for platform, status in token_status.items():
            if status.get('status') == 'critical':
                self.alerts.append({
                    'severity': 'critical',
                    'category': 'token_expiry',
                    'platform': platform,
                    'message': f'{platform.upper()} token expires in {status["minutes_left"]} minutes!',
                    'action': 'Run token_refresh job immediately'
                })
            elif status.get('status') == 'warning':
                self.alerts.append({
                    'severity': 'warning',
                    'category': 'token_expiry',
                    'platform': platform,
                    'message': f'{platform.upper()} token expires in {status["hours_left"]} hours',
                    'action': 'Token will auto-renew soon'
                })
        
        # Failed jobs alerts
        job_failures = self.metrics.get('job_failures', {})
        if job_failures.get('status') == 'critical':
            for job_name, details in job_failures.get('failed_jobs', {}).items():
                self.alerts.append({
                    'severity': 'critical',
                    'category': 'job_failure',
                    'job': job_name,
                    'message': f'Job {job_name} failed {details["consecutive_failures"]} times consecutively',
                    'last_success': details['last_success'],
                    'action': 'Check logs and investigate root cause'
                })
        
        # Sales alerts
        sales_status = self.metrics.get('sales_status', {})
        if sales_status.get('status') == 'critical':
            self.alerts.append({
                'severity': 'critical',
                'category': 'zero_sales',
                'message': f'No sales for {sales_status["days_since_sale"]} days!',
                'last_sale': sales_status.get('last_sale_date'),
                'action': 'Check listings visibility, prices, and promoted ads'
            })
        elif sales_status.get('status') == 'warning':
            self.alerts.append({
                'severity': 'warning',
                'category': 'low_sales',
                'message': f'No sales for {sales_status["days_since_sale"]} days',
                'action': 'Monitor closely'
            })
        
        # Listing visibility alerts
        visibility = self.metrics.get('listing_visibility', {})
        if visibility.get('status') == 'critical':
            self.alerts.append({
                'severity': 'critical',
                'category': 'low_visibility',
                'message': f'{visibility["invisible_pct"]}% of products are not listed!',
                'unlisted': visibility['unlisted'],
                'total': visibility['total_products'],
                'action': 'Run inventory_sync and check for errors'
            })
        
        if visibility.get('zero_stock_listings', 0) > 5:
            self.alerts.append({
                'severity': 'warning',
                'category': 'zero_stock',
                'message': f'{visibility["zero_stock_listings"]} listings have zero stock',
                'action': 'Run inventory_sync to update stock'
            })
        
        # API limit alerts
        api_status = self.metrics.get('api_limits', {})
        if api_status.get('circuit_breakers'):
            self.alerts.append({
                'severity': 'warning',
                'category': 'circuit_breaker',
                'message': 'Circuit breakers open - API calls being throttled',
                'breakers': api_status['circuit_breakers'],
                'action': 'Wait for automatic recovery or check API credentials'
            })
    
    def _save_dashboard(self):
        """Save metrics to dashboard file."""
        dashboard = {
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'metrics': self.metrics,
            'alerts': self.alerts,
            'overall_status': 'critical' if any(a['severity'] == 'critical' for a in self.alerts)
                            else 'warning' if self.alerts
                            else 'healthy'
        }
        
        DASHBOARD_FILE.write_text(
            json.dumps(dashboard, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        # Also save to monitoring history
        history_file = MONITORING_DIR / f'history_{datetime.now().strftime("%Y%m%d")}.jsonl'
        with open(history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(dashboard, ensure_ascii=False) + '\n')


def collect_metrics() -> Dict:
    """Main entry point for metric collection."""
    monitor = MonitoringMetrics()
    return monitor.collect_all_metrics()


if __name__ == '__main__':
    result = collect_metrics()
    print(json.dumps(result, ensure_ascii=False, indent=2))
