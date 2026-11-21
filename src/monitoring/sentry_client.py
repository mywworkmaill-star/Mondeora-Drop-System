"""
Sentry Integration
Error tracking and performance monitoring
"""

import sys
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import logging

from monitoring.config import (
    SENTRY_DSN,
    SENTRY_ENVIRONMENT,
    SENTRY_TRACES_SAMPLE_RATE,
    is_sentry_enabled
)


def init_sentry():
    """
    Initialize Sentry error tracking
    
    Call this at the start of your application
    """
    
    if not is_sentry_enabled():
        print("⚠️  Sentry not configured (SENTRY_DSN missing)")
        return False
    
    try:
        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )
        
        # Initialize Sentry
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            integrations=[logging_integration],
            
            # Additional options
            send_default_pii=False,  # Don't send PII (email, username, etc.)
            attach_stacktrace=True,  # Attach stack trace to messages
            
            # Set release version (optional)
            # release="mondeora@1.0.0",
            
            # Before send callback (optional filtering)
            before_send=before_send_filter,
        )
        
        print(f"✅ Sentry initialized (env: {SENTRY_ENVIRONMENT})")
        return True
        
    except Exception as e:
        print(f"❌ Sentry initialization failed: {e}")
        return False


def before_send_filter(event, hint):
    """
    Filter events before sending to Sentry
    
    Use this to:
    - Remove sensitive data
    - Filter out noise
    - Add custom context
    """
    
    # Skip certain exceptions
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        
        # Skip keyboard interrupts
        if isinstance(exc_value, KeyboardInterrupt):
            return None
        
        # Skip common network errors that are expected
        # (you can customize this)
        # if isinstance(exc_value, requests.exceptions.Timeout):
        #     return None
    
    return event


def capture_exception(error: Exception, context: dict = None):
    """
    Manually capture an exception
    
    Args:
        error: Exception to capture
        context: Additional context dict
    """
    
    if not is_sentry_enabled():
        # Fallback: print to console
        print(f"❌ ERROR: {error}")
        if context:
            print(f"   Context: {context}")
        return
    
    # Add context if provided
    if context:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_context(key, value)
            sentry_sdk.capture_exception(error)
    else:
        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = 'info', context: dict = None):
    """
    Capture a message (not an exception)
    
    Args:
        message: Message to capture
        level: 'debug', 'info', 'warning', 'error', 'fatal'
        context: Additional context dict
    """
    
    if not is_sentry_enabled():
        # Fallback: print to console
        level_emoji = {
            'debug': '🐛',
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'fatal': '💀'
        }
        print(f"{level_emoji.get(level, 'ℹ️')} {message}")
        if context:
            print(f"   Context: {context}")
        return
    
    # Add context if provided
    if context:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_context(key, value)
            sentry_sdk.capture_message(message, level=level)
    else:
        sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: str = None, email: str = None, **kwargs):
    """
    Set user context for error tracking
    
    Args:
        user_id: User ID
        email: User email
        **kwargs: Additional user properties
    """
    
    if not is_sentry_enabled():
        return
    
    user_data = {}
    if user_id:
        user_data['id'] = user_id
    if email:
        user_data['email'] = email
    
    user_data.update(kwargs)
    
    sentry_sdk.set_user(user_data)


def add_breadcrumb(message: str, category: str = None, level: str = 'info', data: dict = None):
    """
    Add a breadcrumb (trail of events leading to error)
    
    Args:
        message: Breadcrumb message
        category: Category (e.g., 'api', 'db', 'ui')
        level: 'debug', 'info', 'warning', 'error'
        data: Additional data dict
    """
    
    if not is_sentry_enabled():
        return
    
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {}
    )


# Decorator for automatic error tracking
def track_errors(context: dict = None):
    """
    Decorator to automatically track errors in functions
    
    Usage:
        @track_errors(context={'operation': 'listing'})
        def create_listing(product_id):
            # your code
    """
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                capture_exception(e, context=context)
                raise  # Re-raise after capturing
        
        return wrapper
    
    return decorator
