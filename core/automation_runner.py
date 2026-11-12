"""
AUTOMATION RUNNER - Core System
================================
Tüm otomasyonları state tracking ile çalıştırır
Mevcut Mondeora sistemine entegre olur
"""

import sqlite3
import json
import time
import uuid
import traceback
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AutomationRunner:
    """
    Her automation çalışmasını state machine ile track eder
    """
    
    def __init__(self, automation_name, db_path='data/dropshipping.db'):
        self.automation_name = automation_name
        self.run_id = str(uuid.uuid4())
        self.db_path = db_path
        
        # Run başlat
        self._create_run()
        
        logger.info(f"🚀 Automation started: {automation_name} (run_id: {self.run_id})")
    
    def _create_run(self):
        """Run kaydı oluştur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO automation_runs (
                run_id, automation_name, status, started_at, current_step
            ) VALUES (?, ?, 'running', ?, 'initializing')
        """, (self.run_id, self.automation_name, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def run_step(self, step_name, step_func, input_data=None, step_number=None):
        """
        Tek bir adımı çalıştır ve kaydet
        
        Args:
            step_name: Adım ismi
            step_func: Çalıştırılacak fonksiyon
            input_data: Fonksiyona girecek veri
            step_number: Adım numarası
        
        Returns:
            Fonksiyonun dönüş değeri
        """
        
        logger.info(f"   [{step_name}] Starting...")
        
        # Step başlat
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO automation_steps (
                run_id, step_name, step_number, status, started_at, input_data
            ) VALUES (?, ?, ?, 'running', ?, ?)
        """, (
            self.run_id, 
            step_name, 
            step_number,
            datetime.now().isoformat(),
            json.dumps(input_data) if input_data else None
        ))
        
        step_id = cursor.lastrowid
        conn.commit()
        
        # Current step güncelle
        cursor.execute("""
            UPDATE automation_runs
            SET current_step = ?
            WHERE run_id = ?
        """, (step_name, self.run_id))
        
        conn.commit()
        conn.close()
        
        try:
            # Adımı çalıştır
            start_time = time.time()
            
            if input_data is not None:
                output_data = step_func(input_data)
            else:
                output_data = step_func()
            
            duration = time.time() - start_time
            
            # Başarılı
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE automation_steps
                SET status = 'completed',
                    completed_at = ?,
                    duration_seconds = ?,
                    output_data = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                duration,
                json.dumps(output_data) if output_data else None,
                step_id
            ))
            
            # Completed steps arttır
            cursor.execute("""
                UPDATE automation_runs
                SET completed_steps = completed_steps + 1
                WHERE run_id = ?
            """, (self.run_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"   [{step_name}] ✅ Completed ({duration:.2f}s)")
            
            return output_data
            
        except Exception as e:
            # Hata
            duration = time.time() - start_time
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE automation_steps
                SET status = 'failed',
                    completed_at = ?,
                    duration_seconds = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                duration,
                str(e),
                step_id
            ))
            
            # Failed steps arttır
            cursor.execute("""
                UPDATE automation_runs
                SET failed_steps = failed_steps + 1
                WHERE run_id = ?
            """, (self.run_id,))
            
            conn.commit()
            conn.close()
            
            logger.error(f"   [{step_name}] ❌ Failed: {e}")
            
            raise
    
    def check_item(self, step_name, item_name, passed, is_critical=False, reason=None, data=None):
        """
        Checklist item'ı işaretle
        
        Args:
            step_name: Adım ismi
            item_name: Checklist item ismi
            passed: Başarılı mı?
            is_critical: Kritik item mi?
            reason: Başarısız olma sebebi
            data: Ekstra veri
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO automation_checklist (
                run_id, step_name, checklist_item, 
                is_critical, checked, passed, checked_at, reason
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        """, (
            self.run_id, 
            step_name, 
            item_name,
            1 if is_critical else 0,
            1 if passed else 0,
            datetime.now().isoformat(),
            reason
        ))
        
        conn.commit()
        conn.close()
        
        # Critical item başarısız?
        if is_critical and not passed:
            logger.warning(f"   ⚠️ CRITICAL FAILURE: {step_name}.{item_name} - {reason}")
            
            # Decision kaydet
            self.log_decision(step_name, item_name, 'reject', reason)
    
    def log_decision(self, step_name, decision_point, decision, reason, confidence=1.0, data=None):
        """
        Otomatik kararı logla
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO automation_decisions (
                run_id, step_name, decision_point, decision,
                reason, confidence_score, made_at, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.run_id,
            step_name,
            decision_point,
            decision,
            reason,
            confidence,
            datetime.now().isoformat(),
            json.dumps(data) if data else None
        ))
        
        conn.commit()
        conn.close()
    
    def complete(self, success=True, error_message=None):
        """
        Run'ı tamamla
        """
        
        status = 'completed' if success else 'failed'
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE automation_runs
            SET status = ?,
                completed_at = ?,
                error_message = ?
            WHERE run_id = ?
        """, (status, datetime.now().isoformat(), error_message, self.run_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"🏁 Automation {status}: {self.automation_name}")
    
    def get_summary(self):
        """
        Run özeti
        """
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, completed_steps, failed_steps, started_at, completed_at
            FROM automation_runs
            WHERE run_id = ?
        """, (self.run_id,))
        
        row = cursor.fetchone()
        
        if not row:
            return None
        
        status, completed, failed, started, completed_at = row
        
        # Steps detayı
        cursor.execute("""
            SELECT step_name, status, duration_seconds
            FROM automation_steps
            WHERE run_id = ?
            ORDER BY id
        """, (self.run_id,))
        
        steps = []
        for step_name, step_status, duration in cursor.fetchall():
            steps.append({
                'name': step_name,
                'status': step_status,
                'duration': duration
            })
        
        conn.close()
        
        return {
            'run_id': self.run_id,
            'automation': self.automation_name,
            'status': status,
            'completed_steps': completed,
            'failed_steps': failed,
            'started_at': started,
            'completed_at': completed_at,
            'steps': steps
        }
