import logging
import sys
import json
import datetime
from typing import Any, Dict
from config import settings
from utils import context

# Keys that should never have their values logged in plain text
SENSITIVE_KEYS = {
    "api_token", 
    "authorization", 
    "secret", 
    "password", 
    "token", 
    "key",
    "env",
    "credential"
}

class JsonFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Includes correlation ID from context and redacts sensitive information.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Basic log structure
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available in context
        correlation_id = context.get_correlation_id()
        if correlation_id:
            log_obj["correlation_id"] = correlation_id

        # Add extra fields if they exist
        if hasattr(record, "extra_info"):
            log_obj.update(record.extra_info)
        
        # Also check standard 'extra' passed to logger.info(msg, extra={...})
        # Note: logging puts these in record.__dict__ items that aren't standard
        # A more robust way is to filter record.__dict__
        standard_fields = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'msg', 'name', 'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'thread', 'threadName', 'extra_info'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                log_obj[key] = value

        # Redaction logic for all keys in the log object
        return json.dumps(self._redact(log_obj))

    def _redact(self, data: Any) -> Any:
        """Recursively redacts sensitive keys in dictionaries."""
        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if any(sk in k.lower() for sk in SENSITIVE_KEYS) else self._redact(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._redact(item) for item in data]
        return data

def setup_logger(name="backend"):
    """Sets up a standardized JSON logger for the application."""
    logger = logging.getLogger(name)
    
    # Use log level from centralized settings
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Prevent duplicate handlers if called multiple times
    if not logger.handlers:
        # Console Handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# Create a shared logger instance
logger = setup_logger()
