"""Logging configuration."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

_STANDARD_RECORD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRIBUTES and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())

    for handler in root_logger.handlers:
        handler.setFormatter(JsonFormatter())
