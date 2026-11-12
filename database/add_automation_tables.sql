-- ============================================
-- AUTOMATION TRACKING TABLES
-- Mevcut dropshipping.db'ye eklenir
-- Version: 1.0.0
-- Created: 2026-11-10
-- ============================================

-- 1. AUTOMATION RUNS
CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    automation_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    total_steps INTEGER DEFAULT 0,
    completed_steps INTEGER DEFAULT 0,
    failed_steps INTEGER DEFAULT 0,
    current_step TEXT,
    error_message TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_runs_name ON automation_runs(automation_name);
CREATE INDEX IF NOT EXISTS idx_automation_runs_status ON automation_runs(status);

-- 2. AUTOMATION STEPS
CREATE TABLE IF NOT EXISTS automation_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_number INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    input_data TEXT,
    output_data TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_automation_steps_run ON automation_steps(run_id);

-- 3. AUTOMATION CHECKLIST
CREATE TABLE IF NOT EXISTS automation_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    checklist_item TEXT NOT NULL,
    is_critical INTEGER DEFAULT 0,
    checked INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    checked_at TIMESTAMP,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_checklist_run ON automation_checklist(run_id);

-- 4. AUDIT LOG
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT,
    data TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_category ON audit_log(category);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);

-- 5. AUTOMATION DECISIONS
CREATE TABLE IF NOT EXISTS automation_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    step_name TEXT,
    decision_point TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT,
    confidence_score REAL,
    made_at TIMESTAMP NOT NULL,
    data TEXT
);

CREATE INDEX IF NOT EXISTS idx_automation_decisions_point ON automation_decisions(decision_point);

-- 6. HEALTH CHECKS
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    healthy INTEGER NOT NULL,
    response_time_ms REAL,
    error_message TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_health_checks_name ON health_checks(check_name);
