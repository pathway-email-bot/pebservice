"""
Logging utilities for the PEB Service.

Provides:
- setup_cloud_logging(): configures structured JSON logging for Cloud Functions
- @log_function decorator: automatically logs entry/exit/errors with timing
"""

import functools
import inspect
import logging
import os
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def setup_cloud_logging():
    """Configure logging for the current environment.

    On GCP (Cloud Functions sets K_SERVICE automatically):
      Uses google-cloud-logging's StructuredLogHandler which outputs JSON
      to stdout with proper severity, sourceLocation, and trace fields
      that Cloud Logging parses natively.

    Locally:
      Falls back to standard basicConfig for readable console output.
    """
    if os.environ.get("K_SERVICE"):
        # Running in Cloud Functions — use structured JSON logging
        import google.cloud.logging
        client = google.cloud.logging.Client()
        client.setup_logging(log_level=logging.INFO)
    else:
        # Local development — plain text to console
        logging.basicConfig(level=logging.INFO)

# Parameter names whose values should be masked in logs
SENSITIVE_PARAMS = frozenset({
    'api_key', 'password', 'secret', 'token', 'refresh_token',
    'client_secret', 'credentials', 'creds',
})


def _summarize(value: Any, max_len: int = 120) -> str:
    """Create a concise summary of a return value for logging."""
    if value is None:
        return "None"
    
    type_name = type(value).__name__
    
    if isinstance(value, str):
        if len(value) > max_len:
            return f"str({len(value)} chars): {value[:max_len]}..."
        return f"str: {value}"
    
    if isinstance(value, (list, tuple)):
        return f"{type_name}({len(value)} items)"
    
    if isinstance(value, dict):
        return f"dict({len(value)} keys: {list(value.keys())[:5]})"
    
    if isinstance(value, bool):
        return str(value)
    
    if isinstance(value, (int, float)):
        return str(value)
    
    # For dataclasses or objects, show type and key attributes
    text = repr(value)
    if len(text) > max_len:
        return f"{type_name}: {text[:max_len]}..."
    return f"{type_name}: {text}"


def _format_params(func: Callable, args: tuple, kwargs: dict) -> str:
    """Format function parameters for logging, masking sensitive values."""
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    
    parts = []
    for name, value in bound.arguments.items():
        if name in ('self', 'cls'):
            continue
        if name in SENSITIVE_PARAMS:
            parts.append(f"{name}=***")
        elif isinstance(value, str) and len(value) > 80:
            parts.append(f"{name}='{value[:80]}...'")
        else:
            parts.append(f"{name}={value!r}")
    
    return ", ".join(parts)


def log_function(func: Callable) -> Callable:
    """
    Decorator that logs function entry, exit, duration, and errors.
    
    Usage:
        @log_function
        def my_function(x, y):
            return x + y
    """
    # Determine the qualified name for logging
    qual_name = func.__qualname__
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Format parameters
        try:
            params_str = _format_params(func, args, kwargs)
        except Exception:
            params_str = "(unable to format params)"
        
        logger.info(f"▶ {qual_name}({params_str})")
        start = time.time()
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            result_summary = _summarize(result)
            logger.info(f"◀ {qual_name} → {result_summary} [{elapsed:.2f}s]")
            return result
        except Exception:
            elapsed = time.time() - start
            logger.info(f"◀ {qual_name} FAILED [{elapsed:.2f}s]")
            raise
    
    return wrapper
