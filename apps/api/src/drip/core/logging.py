import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class SafeJSONFormatter(logging.Formatter):
    """Redact structured sensitive fields; callers must use static, non-sensitive messages."""

    SENSITIVE_KEYS = {
        "password",
        "secret",
        "token",
        "otp",
        "authorization",
        "cookie",
        "api_key",
        "private_key",
        "credit_card",
        "cvv",
        "pin",
        "input",
        "ctx",
    }

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: "[REDACTED]"
                if any(s in k.lower() for s in self.SENSITIVE_KEYS)
                else self._sanitize(v)
                for k, v in data.items()
            }
        elif isinstance(data, (list, tuple)):
            return [self._sanitize(item) for item in data]
        return data

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "props"):
            log_obj["props"] = self._sanitize(record.props)

        if record.exc_info:
            # Exception text and traceback source lines can contain submitted credentials.
            exception_type = record.exc_info[0]
            log_obj["exception_type"] = exception_type.__name__ if exception_type else "Unknown"

        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger with the structured JSON formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(SafeJSONFormatter())
    root_logger.addHandler(console_handler)

    # Uvicorn logs ASGI exceptions again after the HTTP error handler returns.
    # Route those records through the same formatter instead of its raw traceback handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
