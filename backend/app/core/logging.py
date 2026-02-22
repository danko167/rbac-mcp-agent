from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any


_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")

_JWT_RE = re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._-]+")
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def _redact_string(value: str) -> str:
    redacted = _BEARER_RE.sub(r"\1[REDACTED]", value)
    redacted = _JWT_RE.sub("[REDACTED_JWT]", redacted)
    redacted = _EMAIL_RE.sub(r"\1***@\2", redacted)
    return redacted


def _redact_value(value: Any, sensitive_keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if str(key).lower() in sensitive_keys else _redact_value(sub, sensitive_keys))
            for key, sub in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, sensitive_keys) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, sensitive_keys) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx_var.get()
        return True


class RedactionFilter(logging.Filter):
    def __init__(self, sensitive_fields: list[str]):
        super().__init__()
        self._sensitive_fields = {f.strip().lower() for f in sensitive_fields if f.strip()}

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = _redact_value(record.msg, self._sensitive_fields)
            if record.args:
                record.args = _redact_value(record.args, self._sensitive_fields)
        except Exception:
            pass
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": message,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def set_request_id(request_id: str) -> Token[str]:
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id_ctx_var.reset(token)


def get_request_id() -> str:
    return _request_id_ctx_var.get()


def configure_logging(level: str = "INFO", *, log_format: str = "text", redact_fields: list[str] | None = None) -> None:
    """Configures the logging for the application."""
    root = logging.getLogger()

    # Prevent double configuration (uvicorn, reloads, tests, etc.)
    if root.handlers:
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    request_id_filter = RequestIdFilter()
    redaction_filter = RedactionFilter(redact_fields or [])
    for handler in root.handlers:
        handler.addFilter(request_id_filter)
        handler.addFilter(redaction_filter)
        if log_format == "json":
            handler.setFormatter(JsonFormatter())
