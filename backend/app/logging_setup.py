import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# Sensitive dictionary keys to immediately redact
SENSITIVE_KEYS = {
    "password",
    "key",
    "secret",
    "token",
    "authorization",
    "cookie",
    "encrypted_key",
    "master_key",
    "api_key",
    "apikey",
    "csrf_token",
    "session_token",
}

# Regex patterns to detect secret tokens inside strings
SECRET_PATTERNS = [
    (re.compile(r"lgw_[A-Za-z0-9_-]{10,}", re.IGNORECASE), "lgw_[REDACTED]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}", re.IGNORECASE), "sk-ant-[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{10,}", re.IGNORECASE), "sk-[REDACTED]"),
    (re.compile(r"AIza[A-Za-z0-9_-]{10,}", re.IGNORECASE), "AIza[REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_.-]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE), "Basic [REDACTED]"),
]


def redact_string(val: str) -> str:
    """Scrub secret patterns from a string."""
    result = val
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_data(obj: Any) -> Any:
    """Recursively redact sensitive keys and values from data structures."""
    if isinstance(obj, dict):
        new_dict: dict[str, Any] = {}
        for k, v in obj.items():
            k_str = str(k).lower()
            if any(s in k_str for s in SENSITIVE_KEYS):
                new_dict[k] = "[REDACTED]"
            else:
                new_dict[k] = redact_data(v)
        return new_dict
    elif isinstance(obj, list):
        return [redact_data(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(redact_data(item) for item in obj)
    elif isinstance(obj, str):
        return redact_string(obj)
    return obj


def redaction_processor(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor to strip secrets from all log events."""
    for key in list(event_dict.keys()):
        val = event_dict[key]
        key_lower = str(key).lower()
        if any(s in key_lower for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        else:
            event_dict[key] = redact_data(val)
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON output and mandatory redaction."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redaction_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
