#!/usr/bin/env python3
"""
Mondeora Orchestrator - Master Automation Controller
====================================================

Tüm Mondeora otomasyonlarını orkestre eder:
- Dependency management
- Execution order
- Error handling & retry
- Rollback mechanism
- State management
- Real-time monitoring

USAGE:
    python src/orchestrator/master.py
    python src/orchestrator/master.py --workflow daily
    python src/orchestrator/master.py --status
"""

import sys
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.audit_logger import get_logger
from src.jobs import SEMANTIC_EXIT, PROGRESS_FIELDS

SEMANTIC_SCRIPTS = {f'scripts/{name}.py': name for name in
                    ('listing_standards', 'listing_prepare', 'listing_pipeline')}


def _semantic_result(name, result):
    lines = [line.removeprefix('MONDEORA_JOB_OUTCOME ') for line in result.stdout.splitlines()
             if line.startswith('MONDEORA_JOB_OUTCOME ')]
    if len(lines) != 1:
        raise ValueError('missing_or_duplicate_semantic_outcome')
    value = json.loads(lines[0])
    if (not isinstance(value, dict) or value.get('version') != 1 or value.get('job') != name
            or value.get('status') not in SEMANTIC_EXIT
            or SEMANTIC_EXIT[value['status']] != result.returncode
            or not isinstance(value.get('progress'), dict)):
        raise ValueError('invalid_semantic_outcome')
    progress = value['progress']
    if any(key not in PROGRESS_FIELDS or type(count) is not int or count < 0 for key, count in progress.items()):
        raise ValueError('invalid_semantic_progress')
    return {'version': 1, 'job': name, 'status': value['status'], 'progress': progress}


class JobStatus(Enum):
    """Job execution status."""
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    BLOCKED = 'blocked'
    DEFERRED = 'deferred'
    SKIPPED = 'skipped'
    ROLLED_BACK = 'rolled_back'


class Job:
    """Orchestrated job definition."""
    
    def __init__(self, 
                 name: str,
                 script: str,
                 dependencies: List[str] = None,
                 retry_count: int = 3,
                 timeout: int = 300,
                 critical: bool = False,
                 rollback_script: Optional[str] = None):
        """
        Initialize job.
        
        Args:
            name: Job name
            script: Script path to execute
            dependencies: List of job names that must complete first
            retry_count: Number of retries on failure
            timeout: Timeout in seconds
            critical: If True, workflow stops on failure
            rollback_script: Script to run if rollback needed
        """
        self.name = name
        self.script = script
        self.dependencies = dependencies or []
        self.retry_count = retry_count
        self.timeout = timeout
        self.critical = critical
        self.rollback_script = rollback_script
        
        self.status = JobStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.duration = None
        self.error = None
        self.output = None
        self.attempts = 0
        self.progress = {}


class Workflow:
    """Workflow definition with jobs."""
    
    def __init__(self, name: str, jobs: List[Job]):
        """
        Initialize workflow.
        
        Args:
            name: Workflow name
            jobs: List of jobs in this workflow
        """
        self.name = name
        self.jobs = {job.name: job for job in jobs}
        self.execution_order = self._calculate_execution_order()
    
    def _calculate_execution_order(self) -> List[str]:
        """Calculate job execution order based on dependencies."""
        order = []
        visited = set()
        
        def visit(job_name: str):
            if job_name in visited:
                return
            
            job = self.jobs[job_name]
            
            # Visit dependencies first
            for dep in job.dependencies:
                if dep in self.jobs:
                    visit(dep)
            
            visited.add(job_name)
            order.append(job_name)
        
        # Visit all jobs
        for job_name in self.jobs:
            visit(job_name)
        
        return order
    
    def get_job(self, name: str) -> Optional[Job]:
        """Get job by name."""
        return self.jobs.get(name)
    
    def get_next_jobs(self) -> List[Job]:
        """Get jobs that are ready to run (dependencies met)."""
        ready = []
        
        for job_name in self.execution_order:
            job = self.jobs[job_name]
            
            # Skip if not pending
            if job.status != JobStatus.PENDING:
                continue
            
            # Check dependencies
            deps_met = all(
                self.jobs[dep].status == JobStatus.SUCCESS
                for dep in job.dependencies
                if dep in self.jobs
            )
            
            if deps_met:
                ready.append(job)
        
        return ready


class Orchestrator:
    """Master orchestrator."""
    
    def __init__(self):
        """Initialize orchestrator."""
        self.logger = get_logger()
        self.db_path = ROOT / 'data' / 'dropshipping.db'
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure orchestrator tables exist."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Workflow runs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_name VARCHAR(100),
                started_at DATETIME,
                completed_at DATETIME,
                status VARCHAR(20),
                total_jobs INTEGER,
                successful_jobs INTEGER,
                failed_jobs INTEGER,
                skipped_jobs INTEGER,
                duration_seconds INTEGER,
                error TEXT
            )
        ''')
        
        # Job executions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_run_id INTEGER,
                job_name VARCHAR(100),
                started_at DATETIME,
                completed_at DATETIME,
                status VARCHAR(20),
                attempts INTEGER,
                duration_seconds INTEGER,
                error TEXT,
                output TEXT,
                FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
            )
        ''')
        
        columns = {row[1] for row in cursor.execute('PRAGMA table_info(workflow_runs)')}
        for column in ('blocked_jobs', 'deferred_jobs'):
            if column not in columns:
                cursor.execute('ALTER TABLE workflow_runs ADD COLUMN ' + column + ' INTEGER DEFAULT 0')
        conn.commit()
        conn.close()
    
    def execute_job(self, job: Job) -> bool:
        """
        Execute a single job with retry logic.
        
        Args:
            job: Job to execute
        
        Returns:
            bool: Success
        """
        import subprocess
        
        job.status = JobStatus.RUNNING
        job.start_time = datetime.now()
        semantic_name = SEMANTIC_SCRIPTS.get(Path(job.script).as_posix())
        # Resume/readback on a later invocation, never retry a possibly executed release.
        attempt_limit = 1 if semantic_name else job.retry_count
        
        print(f"\n{'='*70}")
        print(f"🎯 EXECUTING: {job.name}")
        print(f"{'='*70}")
        print(f"  Script: {job.script}")
        print(f"  Dependencies: {', '.join(job.dependencies) if job.dependencies else 'None'}")
        print(f"  Timeout: {job.timeout}s")
        print(f"  Critical: {job.critical}")
        
        while job.attempts < attempt_limit:
            job.attempts += 1
            
            if job.attempts > 1:
                print(f"\n  🔄 Retry {job.attempts}/{job.retry_count}")
            
            try:
                # Execute script
                script_path = ROOT / job.script
                
                # Determine how to run the script
                if script_path.suffix == '.py':
                    # Python script
                    cmd = ['C:/Program Files/Python311/python.exe', str(script_path)]
                else:
                    # Other scripts (bash, etc.) - try python first
                    cmd = ['C:/Program Files/Python311/python.exe', str(script_path)]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=job.timeout,
                    cwd=ROOT
                )
                
                if semantic_name:
                    try:
                        outcome = _semantic_result(semantic_name, result)
                        job.status = JobStatus(outcome['status'])
                        job.progress = outcome['progress']
                        job.output = json.dumps(outcome, sort_keys=True)
                        job.error = None if job.status == JobStatus.SUCCESS else 'semantic_' + job.status.value
                    except (ValueError, TypeError, KeyError):
                        job.status = JobStatus.FAILED
                        job.error = 'invalid_semantic_outcome'
                        job.output = None
                    job.end_time = datetime.now()
                    job.duration = (job.end_time - job.start_time).total_seconds()
                    self.logger.log(action=f'job_executed_{job.name}', message='Listing job outcome',
                                    category='orchestrator', level='success' if job.status == JobStatus.SUCCESS else 'warning',
                                    data={'job': job.name, 'status': job.status.value, 'progress': job.progress},
                                    success=job.status == JobStatus.SUCCESS, duration_ms=int(job.duration * 1000))
                    return job.status == JobStatus.SUCCESS

                job.output = result.stdout
                
                if result.returncode == 0:
                    # Success
                    job.status = JobStatus.SUCCESS
                    job.end_time = datetime.now()
                    job.duration = (job.end_time - job.start_time).total_seconds()
                    
                    print(f"  ✅ SUCCESS in {job.duration:.1f}s")
                    
                    self.logger.log(
                        action=f'job_executed_{job.name}',
                        message=f'Job {job.name} completed successfully',
                        category='orchestrator',
                        level='success',
                        data={
                            'job': job.name,
                            'duration': job.duration,
                            'attempts': job.attempts
                        },
                        success=True,
                        duration_ms=int(job.duration * 1000)
                    )
                    
                    return True
                else:
                    # Failed
                    job.error = result.stderr
                    
                    if job.attempts < attempt_limit:
                        print(f"  ⚠️  Failed (exit {result.returncode}), retrying...")
                        time.sleep(2 ** job.attempts)  # Exponential backoff
                    else:
                        job.status = JobStatus.FAILED
                        job.end_time = datetime.now()
                        job.duration = (job.end_time - job.start_time).total_seconds()
                        
                        print(f"  ❌ FAILED after {job.attempts} attempts")
                        print(f"  Error: {job.error[:200] if job.error else 'Unknown'}")
                        
                        self.logger.log_error(
                            action=f'job_failed_{job.name}',
                            error_message=f'Job {job.name} failed after {job.attempts} attempts',
                            product_id=None,
                            stack_trace=job.error
                        )
                        
                        return False
            
            except subprocess.TimeoutExpired:
                job.error = f'Timeout after {job.timeout}s'
                
                if job.attempts < attempt_limit:
                    print(f"  ⚠️  Timeout, retrying...")
                    time.sleep(2 ** job.attempts)
                else:
                    job.status = JobStatus.FAILED
                    job.end_time = datetime.now()
                    job.duration = (job.end_time - job.start_time).total_seconds()
                    
                    print(f"  ❌ TIMEOUT after {job.attempts} attempts")
                    
                    return False
            
            except Exception as e:
                job.error = type(e).__name__ if semantic_name else str(e)
                job.status = JobStatus.FAILED
                job.end_time = datetime.now()
                job.duration = (job.end_time - job.start_time).total_seconds()
                
                print(f"  ❌ EXCEPTION: {job.error}")
                
                return False
        
        return False
    
    def execute_workflow(self, workflow: Workflow) -> Dict[str, Any]:
        """
        Execute workflow with orchestration.
        
        Args:
            workflow: Workflow to execute
        
        Returns:
            dict: Execution results
        """
        print(f"\n{'='*70}")
        print(f"🎭 WORKFLOW: {workflow.name}")
        print(f"{'='*70}")
        print(f"  Total jobs: {len(workflow.jobs)}")
        print(f"  Execution order: {' → '.join(workflow.execution_order)}")
        
        # Create workflow run record
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO workflow_runs (
                workflow_name,
                started_at,
                status,
                total_jobs
            ) VALUES (?, ?, ?, ?)
        ''', (workflow.name, datetime.now().isoformat(), 'running', len(workflow.jobs)))
        
        workflow_run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Execute jobs
        start_time = datetime.now()
        stats = {'success': 0, 'failed': 0, 'skipped': 0, 'blocked': 0, 'deferred': 0}
        progress = {}
        
        for job_name in workflow.execution_order:
            job = workflow.get_job(job_name)
            
            # Check dependencies
            deps_failed = any(
                workflow.jobs[dep].status != JobStatus.SUCCESS
                for dep in job.dependencies
                if dep in workflow.jobs
            )
            
            if deps_failed:
                job.status = JobStatus.SKIPPED
                stats['skipped'] += 1
                print(f"\n⏭️  SKIPPED: {job.name} (dependency failed)")
                continue
            
            # Execute job
            success = self.execute_job(job)
            if SEMANTIC_SCRIPTS.get(Path(job.script).as_posix()) == 'listing_standards':
                progress.update(job.progress)
            
            # Save job execution
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO job_executions (
                    workflow_run_id,
                    job_name,
                    started_at,
                    completed_at,
                    status,
                    attempts,
                    duration_seconds,
                    error,
                    output
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workflow_run_id,
                job.name,
                job.start_time.isoformat() if job.start_time else None,
                job.end_time.isoformat() if job.end_time else None,
                job.status.value,
                job.attempts,
                job.duration,
                job.error,
                job.output[:1000] if job.output else None  # Truncate output
            ))
            
            conn.commit()
            conn.close()
            
            if success:
                stats['success'] += 1
            else:
                stats[job.status.value if job.status in (JobStatus.BLOCKED, JobStatus.DEFERRED) else 'failed'] += 1
                
                # Stop if critical job failed
                if job.critical and job.status == JobStatus.FAILED:
                    print(f"\n🛑 CRITICAL JOB FAILED - Stopping workflow")
                    break
        
        # Update workflow run
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        status = ('failed' if stats['failed'] else 'blocked' if stats['blocked'] else
                  'deferred' if stats['deferred'] or stats['skipped'] else 'success')
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE workflow_runs
            SET completed_at = ?,
                status = ?,
                successful_jobs = ?,
                failed_jobs = ?,
                skipped_jobs = ?,
                blocked_jobs = ?,
                deferred_jobs = ?,
                duration_seconds = ?
            WHERE id = ?
        ''', (
            end_time.isoformat(),
            status,
            stats['success'],
            stats['failed'],
            stats['skipped'],
            stats['blocked'],
            stats['deferred'],
            duration,
            workflow_run_id
        ))
        
        conn.commit()
        conn.close()
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"📊 WORKFLOW COMPLETE: {workflow.name}")
        print(f"{'='*70}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  ✅ Success: {stats['success']}")
        print(f"  ❌ Failed: {stats['failed']}")
        print(f"  ⏭️  Skipped: {stats['skipped']}")
        print(f"  Blocked: {stats['blocked']}; Deferred: {stats['deferred']}")
        print(f"{'='*70}\n")
        
        self.logger.log(
            action='workflow_completed',
            message=f'Workflow {workflow.name} completed',
            category='orchestrator',
            level='success' if status == 'success' else 'error' if status == 'failed' else 'warning',
            data=stats,
            success=status == 'success',
            duration_ms=int(duration * 1000)
        )
        
        return {
            'workflow': workflow.name,
            'duration': duration,
            'stats': stats,
            'status': status,
            'progress': progress,
            'run_id': workflow_run_id
        }


def create_daily_workflow() -> Workflow:
    """Create daily workflow with proper orchestration."""
    
    jobs = [
        # Phase 1: Health & Tokens (Critical)
        Job('health-check', 'scripts/health_check.py', 
            dependencies=[], critical=True, retry_count=3),
        
        Job('token-refresh', 'scripts/token_refresh.py',
            dependencies=['health-check'], critical=True, retry_count=3),
        
        # Phase 2: Database Sync (Critical)
        Job('db-backup', 'scripts/db_backup.py',
            dependencies=['health-check'], critical=True),
        
        Job('ebay-realtime-monitor', 'scripts/realtime_ebay_monitor.py',
            dependencies=['token-refresh'], critical=True, timeout=600),
        
        # Phase 3: Inventory & Products
        Job('product-sync', 'scripts/product_sync.py',
            dependencies=['ebay-realtime-monitor']),
        
        Job('inventory-sync', 'scripts/inventory_sync.py',
            dependencies=['product-sync']),
        
        # Phase 4: Competitor Analysis
        Job('competitor-analysis', 'scripts/batch_competitor_analysis.py',
            dependencies=['inventory-sync'], timeout=600),
        
        # Phase 5: Price Optimization
        Job('price-optimize', 'scripts/price_optimize.py',
            dependencies=['competitor-analysis']),
        
        Job('price-refresh', 'scripts/update_ebay_prices_with_audit.py',
            dependencies=['price-optimize'], timeout=600),
        
        # Phase 6: Orders & Fulfillment
        Job('orders-poll', 'scripts/orders_poll.py',
            dependencies=['token-refresh']),
        
        Job('orders-sync', 'scripts/orders_sync.py',
            dependencies=['orders-poll']),
        
        Job('order-fulfillment', 'scripts/order_fulfillment.py',
            dependencies=['orders-sync']),
        
        Job('tracking-update', 'scripts/tracking_update.py',
            dependencies=['order-fulfillment']),
        
        # Phase 7: A general read-only standards pass precedes saved preparation/release.
        # The actual release still enforces its own fresh plan and buyer verification.
        Job('listing-standards', 'scripts/listing_standards.py',
            dependencies=['ebay-realtime-monitor'], retry_count=1, timeout=150),

        Job('listing-prepare', 'scripts/listing_prepare.py',
            dependencies=['listing-standards', 'price-optimize'], retry_count=1, timeout=600),

        Job('listing-pipeline', 'scripts/listing_pipeline.py',
            dependencies=['listing-prepare'], retry_count=1, timeout=600),
        
        # Phase 8: Reporting
        Job('daily-report', 'scripts/daily_report.py',
            dependencies=['orders-sync', 'inventory-sync', 'price-refresh'])
    ]
    
    return Workflow('daily', jobs)


def create_listing_review_workflow() -> Workflow:
    """Exercise the shared audit through orchestration without any publication jobs."""
    return Workflow('listing-review', [
        Job('listing-standards', 'scripts/listing_standards.py',
            dependencies=[], retry_count=1, timeout=150),
    ])


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Mondeora Orchestrator')
    parser.add_argument('--workflow', choices=['daily', 'hourly', 'realtime', 'listing-review'],
                       help='Workflow to execute')
    parser.add_argument('--status', action='store_true',
                       help='Show orchestrator status')
    
    args = parser.parse_args()
    
    orchestrator = Orchestrator()
    
    if args.status:
        # Show status
        print("Orchestrator status not yet implemented")
        return 0
    
    if args.workflow in ('daily', 'listing-review'):
        workflow = create_daily_workflow() if args.workflow == 'daily' else create_listing_review_workflow()
        result = orchestrator.execute_workflow(workflow)
        
        return SEMANTIC_EXIT[result['status']]
    else:
        print("Usage: python src/orchestrator/master.py --workflow daily")
        return 1


if __name__ == '__main__':
    sys.exit(main())
