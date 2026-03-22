"""
Structured JSON logging sistemi — tüm backend modülleri bu modülü kullanır.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

try:
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

# ─── Request ID context variable ─────────────────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


# ─── JSON Formatter ───────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Her log satırını tek satır JSON olarak formatlar."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Request ID varsa ekle
        rid = request_id_var.get("")
        if rid:
            log_obj["request_id"] = rid

        # Exception bilgisi
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)

        # Extra alanlar (log.info("msg", extra={"uid": "..."}) ile)
        for key, val in record.__dict__.items():
            if key not in (
                "msg", "args", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
                "taskName",
            ):
                log_obj[key] = val

        return json.dumps(log_obj, ensure_ascii=False, default=str)


# ─── Logger Factory ───────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Named logger döner — her modül bu fonksiyonu kullanır."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def setup_root_logger(level: str = "INFO") -> None:
    """Root logger'ı kur — main.py startup'ta çağrılır."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)


# ─── Request Timing Middleware ────────────────────────────────────────────────

if _HAS_FASTAPI:
    class RequestLoggingMiddleware(BaseHTTPMiddleware):
        """Her HTTP isteğine correlation ID atar, süreyi loglar."""

        def __init__(self, app, logger_name: str = "omr.http"):
            super().__init__(app)
            self._log = get_logger(logger_name)

        async def dispatch(self, request: Request, call_next) -> Response:
            rid = str(uuid.uuid4())[:8]
            token = request_id_var.set(rid)

            start = time.perf_counter()
            response = None
            try:
                response = await call_next(request)
            except Exception:
                raise
            finally:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                status = response.status_code if response is not None else 500
                self._log.info(
                    f"{request.method} {request.url.path} {status}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "ms": elapsed_ms,
                        "request_id": rid,
                    },
                )
                request_id_var.reset(token)

            response.headers["X-Request-ID"] = rid
            return response
