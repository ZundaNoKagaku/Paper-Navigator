"""Logging setup with secret redaction (spec §8.2/§8.3).

* All timestamps are UTC ISO-8601 with an explicit offset.
* A filter masks bearer tokens, ``Authorization`` headers, API-key query params, and any
  registered secret value, in both the message and the args.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime

_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s,'\"}]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|key)=)[^&\s'\"]+"),
    re.compile(r"(?i)(zotero-api-key\s*[:=]\s*)[^\s,'\"}]+"),
]


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] = ()):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 4]

    def add_secret(self, value: str) -> None:
        if value and len(value) >= 4:
            self._secrets.append(value)

    def redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "****")
        for pat in _PATTERNS:
            text = pat.sub(lambda m: m.group(1) + "****", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = None
        return True


class UTCFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")


_FILTER = RedactingFilter()


def get_redactor() -> RedactingFilter:
    return _FILTER


def setup_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> None:
    for s in secrets:
        _FILTER.add_secret(s)
    root = logging.getLogger("paper_navigator")
    root.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(UTCFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(_FILTER)
        root.addHandler(handler)
    # httpx logs full request lines at INFO; keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
