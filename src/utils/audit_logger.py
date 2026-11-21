#!/usr/bin/env python3
"""
Comprehensive Audit Logger
===========================

HER KÜÇÜK ADIMI database'e anlık kaydeder.

USAGE:
    from src.utils.audit_logger import AuditLogger
    
    logger = AuditLogger()
    logger.log('price_update', 'Product 123 price changed', data={'old': 10, 'new': 15})
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

ROOT = Path(__file__).parent.parent.parent


class AuditLogger:
    """
    Comprehensive audit logger - HER ADIMI kaydet.
    
    Categories:
        - api_call: eBay/AliExpress API calls
        - price_change: Price updates
        - listing_update: Listing changes
        - competitor_analysis: Competitor data collection
        - database_sync: Database synchronization
        - error: Errors and failures
        - success: Successful operations
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize logger."""
        if db_path is None:
            db_path = ROOT / 'data' / 'dropshipping.db'
        
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Ensure audit_log table exists with correct schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='audit_log'
        ''')
        
        if not cursor.fetchone():
            # Create table
            cursor.execute('''
                CREATE TABLE audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    category VARCHAR(50),
                    action VARCHAR(100),
                    level VARCHAR(20),
                    message TEXT,
                    data TEXT,
                    product_id VARCHAR(50),
                    ebay_item_id VARCHAR(50),
                    success BOOLEAN,
                    duration_ms INTEGER
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX idx_audit_timestamp ON audit_log(timestamp)')
            cursor.execute('CREATE INDEX idx_audit_category ON audit_log(category)')
            cursor.execute('CREATE INDEX idx_audit_product ON audit_log(product_id)')
            cursor.execute('CREATE INDEX idx_audit_ebay_item ON audit_log(ebay_item_id)')
            
            conn.commit()
        
        conn.close()
    
    def log(self, 
            action: str,
            message: str,
            category: str = 'general',
            level: str = 'info',
            data: Optional[Dict[str, Any]] = None,
            product_id: Optional[str] = None,
            ebay_item_id: Optional[str] = None,
            success: Optional[bool] = None,
            duration_ms: Optional[int] = None):
        """
        Log an audit entry with automatic retry on database lock.
        
        Args:
            action: What happened (e.g., 'price_updated', 'listing_created')
            message: Human-readable description
            category: Category (api_call, price_change, listing_update, etc.)
            level: info, warning, error, success
            data: Additional JSON data
            product_id: AliExpress product ID
            ebay_item_id: eBay item ID
            success: True/False for operation result
            duration_ms: Operation duration in milliseconds
        
        Returns:
            int: Inserted row ID
        """
        import time
        
        max_retries = 5
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                cursor = conn.cursor()
                
                # Enable WAL mode
                cursor.execute('PRAGMA journal_mode=WAL')
                
                # Convert data to JSON if provided
                data_json = json.dumps(data, ensure_ascii=False) if data else None
                
                cursor.execute('''
                    INSERT INTO audit_log (
                        timestamp,
                        category,
                        action,
                        level,
                        message,
                        data,
                        product_id,
                        ebay_item_id,
                        success,
                        duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    category,
                    action,
                    level,
                    message,
                    data_json,
                    product_id,
                    ebay_item_id,
                    success,
                    duration_ms
                ))
                
                row_id = cursor.lastrowid
                conn.commit()
                conn.close()
                
                return row_id
                
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and attempt < max_retries - 1:
                    # Database locked, retry with exponential backoff
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    # Max retries reached or different error
                    raise
            except Exception as e:
                raise
    
    def log_api_call(self, 
                     endpoint: str,
                     method: str,
                     success: bool,
                     duration_ms: int,
                     response_code: Optional[int] = None,
                     error: Optional[str] = None):
        """Log API call."""
        return self.log(
            action=f'{method} {endpoint}',
            message=f'API call: {method} {endpoint} - {response_code or "N/A"}',
            category='api_call',
            level='success' if success else 'error',
            data={
                'endpoint': endpoint,
                'method': method,
                'response_code': response_code,
                'error': error
            },
            success=success,
            duration_ms=duration_ms
        )
    
    def log_price_change(self,
                        product_id: str,
                        ebay_item_id: Optional[str],
                        old_price: float,
                        new_price: float,
                        reason: str):
        """Log price change."""
        change_pct = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0
        
        return self.log(
            action='price_updated',
            message=f'Price updated: €{old_price:.2f} → €{new_price:.2f} ({change_pct:+.1f}%)',
            category='price_change',
            level='info',
            data={
                'old_price': old_price,
                'new_price': new_price,
                'change_amount': new_price - old_price,
                'change_percent': change_pct,
                'reason': reason
            },
            product_id=product_id,
            ebay_item_id=ebay_item_id,
            success=True
        )
    
    def log_listing_update(self,
                          ebay_item_id: str,
                          product_id: Optional[str],
                          field: str,
                          old_value: Any,
                          new_value: Any,
                          success: bool):
        """Log listing field update."""
        return self.log(
            action=f'listing_update_{field}',
            message=f'Updated {field}: {old_value} → {new_value}',
            category='listing_update',
            level='success' if success else 'error',
            data={
                'field': field,
                'old_value': str(old_value),
                'new_value': str(new_value)
            },
            product_id=product_id,
            ebay_item_id=ebay_item_id,
            success=success
        )
    
    def log_competitor_analysis(self,
                               product_id: str,
                               ebay_item_id: Optional[str],
                               competitors_found: int,
                               aspects_found: int,
                               price_recommendation: Optional[float]):
        """Log competitor analysis."""
        return self.log(
            action='competitor_analysis_complete',
            message=f'Analyzed {competitors_found} competitors, found {aspects_found} aspects',
            category='competitor_analysis',
            level='success',
            data={
                'competitors_found': competitors_found,
                'aspects_found': aspects_found,
                'price_recommendation': price_recommendation
            },
            product_id=product_id,
            ebay_item_id=ebay_item_id,
            success=True
        )
    
    def log_database_sync(self,
                         sync_type: str,
                         items_added: int,
                         items_updated: int,
                         items_removed: int,
                         success: bool):
        """Log database sync operation."""
        return self.log(
            action=f'database_sync_{sync_type}',
            message=f'Sync: +{items_added} added, ~{items_updated} updated, -{items_removed} removed',
            category='database_sync',
            level='success' if success else 'error',
            data={
                'sync_type': sync_type,
                'items_added': items_added,
                'items_updated': items_updated,
                'items_removed': items_removed
            },
            success=success
        )
    
    def log_error(self,
                 action: str,
                 error_message: str,
                 product_id: Optional[str] = None,
                 ebay_item_id: Optional[str] = None,
                 stack_trace: Optional[str] = None):
        """Log error."""
        return self.log(
            action=action,
            message=error_message,
            category='error',
            level='error',
            data={
                'error': error_message,
                'stack_trace': stack_trace
            },
            product_id=product_id,
            ebay_item_id=ebay_item_id,
            success=False
        )
    
    def get_recent(self, limit: int = 100, category: Optional[str] = None):
        """Get recent audit entries."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT * FROM audit_log 
                WHERE category = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT * FROM audit_log 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        entries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return entries
    
    def get_for_product(self, product_id: str, limit: int = 100):
        """Get audit entries for specific product."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM audit_log 
            WHERE product_id = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (product_id, limit))
        
        entries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return entries
    
    def get_stats(self, hours: int = 24):
        """Get audit statistics for last N hours."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                category,
                level,
                COUNT(*) as count,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                AVG(duration_ms) as avg_duration_ms
            FROM audit_log
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
            GROUP BY category, level
            ORDER BY count DESC
        ''', (hours,))
        
        stats = cursor.fetchall()
        conn.close()
        
        return stats


# Global logger instance
_logger = None

def get_logger():
    """Get global audit logger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger
