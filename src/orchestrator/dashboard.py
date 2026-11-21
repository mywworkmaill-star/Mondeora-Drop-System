#!/usr/bin/env python3
"""
Real-Time Orchestrator Dashboard
=================================

Live monitoring of all Mondeora automation:
- Active workflows
- Job status
- Performance metrics
- Error tracking
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


class OrchestratorDashboard:
    """Real-time orchestrator dashboard."""
    
    def __init__(self):
        """Initialize dashboard."""
        self.db_path = ROOT / 'data' / 'dropshipping.db'
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get currently running workflows."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id,
                workflow_name,
                started_at,
                total_jobs,
                successful_jobs,
                failed_jobs,
                skipped_jobs
            FROM workflow_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
        ''')
        
        workflows = []
        for row in cursor.fetchall():
            workflows.append({
                'id': row[0],
                'name': row[1],
                'started_at': row[2],
                'total_jobs': row[3],
                'successful': row[4] or 0,
                'failed': row[5] or 0,
                'skipped': row[6] or 0
            })
        
        conn.close()
        return workflows
    
    def get_recent_workflows(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent workflow runs."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT 
                id,
                workflow_name,
                started_at,
                completed_at,
                status,
                total_jobs,
                successful_jobs,
                failed_jobs,
                skipped_jobs,
                duration_seconds
            FROM workflow_runs
            WHERE started_at >= ?
            ORDER BY started_at DESC
            LIMIT ?
        ''', (since, limit))
        
        workflows = []
        for row in cursor.fetchall():
            workflows.append({
                'id': row[0],
                'name': row[1],
                'started_at': row[2],
                'completed_at': row[3],
                'status': row[4],
                'total_jobs': row[5],
                'successful': row[6] or 0,
                'failed': row[7] or 0,
                'skipped': row[8] or 0,
                'duration': row[9]
            })
        
        conn.close()
        return workflows
    
    def get_job_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get job execution statistics."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Overall stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped,
                AVG(duration_seconds) as avg_duration,
                SUM(CASE WHEN attempts > 1 THEN 1 ELSE 0 END) as retried
            FROM job_executions
            WHERE started_at >= ?
        ''', (since,))
        
        row = cursor.fetchone()
        stats = {
            'total': row[0],
            'success': row[1],
            'failed': row[2],
            'skipped': row[3],
            'avg_duration': round(row[4], 1) if row[4] else 0,
            'retried': row[5]
        }
        
        # Top slowest jobs
        cursor.execute('''
            SELECT job_name, AVG(duration_seconds) as avg_duration
            FROM job_executions
            WHERE started_at >= ? AND duration_seconds IS NOT NULL
            GROUP BY job_name
            ORDER BY avg_duration DESC
            LIMIT 5
        ''', (since,))
        
        stats['slowest_jobs'] = [
            {'name': row[0], 'avg_duration': round(row[1], 1)}
            for row in cursor.fetchall()
        ]
        
        # Top failing jobs
        cursor.execute('''
            SELECT 
                job_name, 
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failures,
                COUNT(*) as total
            FROM job_executions
            WHERE started_at >= ?
            GROUP BY job_name
            HAVING failures > 0
            ORDER BY failures DESC
            LIMIT 5
        ''', (since,))
        
        stats['failing_jobs'] = [
            {'name': row[0], 'failures': row[1], 'total': row[2]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return stats
    
    def display_dashboard(self):
        """Display dashboard."""
        print(f"\n{'='*70}")
        print(f"🎭 MONDEORA ORCHESTRATOR DASHBOARD")
        print(f"{'='*70}\n")
        
        # Active workflows
        active = self.get_active_workflows()
        
        print(f"🔄 ACTIVE WORKFLOWS: {len(active)}")
        print(f"{'-'*70}")
        
        if active:
            for wf in active:
                elapsed = (datetime.now() - datetime.fromisoformat(wf['started_at'])).total_seconds()
                progress = wf['successful'] + wf['failed'] + wf['skipped']
                pct = (progress / wf['total_jobs'] * 100) if wf['total_jobs'] > 0 else 0
                
                print(f"  {wf['name']}")
                print(f"    Progress: {progress}/{wf['total_jobs']} ({pct:.0f}%)")
                print(f"    ✅ {wf['successful']}  ❌ {wf['failed']}  ⏭️ {wf['skipped']}")
                print(f"    Running: {elapsed:.0f}s")
                print()
        else:
            print("  No active workflows\n")
        
        # Recent workflows
        recent = self.get_recent_workflows(hours=24, limit=5)
        
        print(f"📊 RECENT WORKFLOWS (Last 24h):")
        print(f"{'-'*70}")
        
        for wf in recent:
            status_icon = '✅' if wf['status'] == 'success' else '❌'
            completed_at = wf['completed_at'] or 'Running...'
            
            print(f"  {status_icon} {wf['name']}")
            print(f"    Started: {wf['started_at']}")
            if wf['completed_at']:
                print(f"    Duration: {wf['duration']}s")
                print(f"    ✅ {wf['successful']}  ❌ {wf['failed']}  ⏭️ {wf['skipped']}")
            print()
        
        # Job stats
        stats = self.get_job_stats(hours=24)
        
        print(f"📈 JOB STATISTICS (Last 24h):")
        print(f"{'-'*70}")
        print(f"  Total executions: {stats['total']}")
        print(f"  ✅ Success: {stats['success']}")
        print(f"  ❌ Failed: {stats['failed']}")
        print(f"  ⏭️  Skipped: {stats['skipped']}")
        print(f"  🔄 Retried: {stats['retried']}")
        print(f"  ⏱️  Avg duration: {stats['avg_duration']}s")
        print()
        
        if stats['slowest_jobs']:
            print(f"🐌 SLOWEST JOBS:")
            for job in stats['slowest_jobs']:
                print(f"  • {job['name']}: {job['avg_duration']}s")
            print()
        
        if stats['failing_jobs']:
            print(f"⚠️  FAILING JOBS:")
            for job in stats['failing_jobs']:
                fail_rate = (job['failures'] / job['total'] * 100)
                print(f"  • {job['name']}: {job['failures']}/{job['total']} ({fail_rate:.0f}%)")
            print()
        
        print(f"{'='*70}\n")


def main():
    """Main entry point."""
    dashboard = OrchestratorDashboard()
    dashboard.display_dashboard()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
