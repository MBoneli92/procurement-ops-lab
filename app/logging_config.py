"""Structured (JSON) logging: one JSON object per line, so the logs can be searched by field.

{"time": "...", "level": "INFO", "logger": "procurement.access", "message": "request",
 "request_id": "...", "method": "GET", "path": "/suppliers", "status": 200, "duration_ms": 12}
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

# Fields a log call may pass with extra={...}; anything else is ignored on purpose,
# so nobody logs a token or a whole request body by accident.
EXTRA_FIELDS = ("request_id", "method", "path", "status", "duration_ms", "user")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
