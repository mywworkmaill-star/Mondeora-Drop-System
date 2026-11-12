"""
AUDIT LOGGER - Comprehensive Logging
=====================================
Tüm sistem aktivitelerini detaylı loglar
"""

import sqlite3
import json
import logging
from datetime import datetime


class AuditLogger:
    """
    Her şeyi loglar - hiçbir şey kaçmaz
    """
    
    def __init__(self, db_path='data/dropshipping.db'):
        self.db_path = db_path
        self.logger = logging.getLogger('audit')
    
    def log(self, category, action, data=None, level='info', message=None):
        """
        Aktivite logla
        
        Args:
            category: 'product_research', 'listing', 'order', vb.
            action: 'started', 'vero_check', 'price_calculated', vb.
            data: Dict ile detaylar
            level: 'debug', 'info', 'warning', 'error', 'critical'
            message: Opsiyonel mesaj
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_log (
                category, action, level, message, data, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            category,
            action,
            level,
            message,
            json.dumps(data) if data else None,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # Console'a da yaz
        log_msg = f"[{category}] {action}"
        if message:
            log_msg += f": {message}"
        
        if level == 'debug':
            self.logger.debug(log_msg)
        elif level == 'info':
            self.logger.info(log_msg)
        elif level == 'warning':
            self.logger.warning(log_msg)
        elif level == 'error':
            self.logger.error(log_msg)
        elif level == 'critical':
            self.logger.critical(log_msg)
    
    def log_decision(self, category, decision_point, decision, reason, confidence=1.0):
        """
        Otomatik karar logla
        """
        self.log(category, 'decision', {
            'decision_point': decision_point,
            'decision': decision,
            'reason': reason,
            'confidence': confidence
        }, level='info')
    
    def log_error(self, category, error, context=None):
        """
        Hata logla
        """
        import traceback
        
        self.log(category, 'error', {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'context': context
        }, level='error')
    
    def query_logs(self, category=None, level=None, start_date=None, limit=100):
        """
        Logları sorgula
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if level:
            query += " AND level = ?"
            params.append(level)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row[0],
                'category': row[1],
                'action': row[2],
                'level': row[3],
                'message': row[4],
                'data': json.loads(row[5]) if row[5] else None,
                'timestamp': row[7]
            })
        
        conn.close()
        
        return logs


# Global instance
audit = AuditLogger()
