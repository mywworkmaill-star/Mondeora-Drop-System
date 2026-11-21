"""
Monitoring & Alerting Configuration
Centralized error tracking and alerting system
"""

import os
from typing import Optional, Dict, Any

# Sentry Configuration
SENTRY_DSN: Optional[str] = os.getenv('SENTRY_DSN', None)
SENTRY_ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'production')
SENTRY_TRACES_SAMPLE_RATE: float = 1.0  # 100% of transactions for tracing

# Telegram Alerting Configuration
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN', None)
TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID', None)

# Alert Thresholds
ALERT_ON_ERRORS: bool = True
ALERT_ON_STOCK_OUT: bool = True
ALERT_ON_LISTING_FAIL: bool = True
ALERT_ON_API_FAIL: bool = True

# Health Check Settings
HEALTH_CHECK_INTERVAL: int = 300  # 5 minutes
MAX_API_FAILURES: int = 3  # Alert after 3 consecutive failures
MAX_LISTING_FAILURES: int = 2  # Alert after 2 consecutive failures

# Monitoring Metrics
METRICS_ENABLED: bool = True
METRICS_FILE: str = 'data/metrics.json'

# Alert Cooldown (prevent spam)
ALERT_COOLDOWN_SECONDS: int = 3600  # 1 hour per alert type


def is_sentry_enabled() -> bool:
    """Check if Sentry is configured"""
    return SENTRY_DSN is not None


def is_telegram_enabled() -> bool:
    """Check if Telegram alerting is configured"""
    return TELEGRAM_BOT_TOKEN is not None and TELEGRAM_CHAT_ID is not None
