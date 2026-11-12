"""Configuration loaded from environment variables and an optional local ``.env`` file.

Secrets are wrapped in :class:`Secret` so they never appear in ``repr``/logs.
Environment variables always win over values from ``.env``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .errors import ErrorCode, PNError


class Secret:
    """Opaque holder for a secret string; ``str``/``repr`` are masked."""

    __slots__ = ("_value",)

    def __init__(self, value: str):
        self._value = value

    def get(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:
        return "Secret('****')" if self._value else "Secret('')"

    __str__ = __repr__


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (comments, blank lines, optional quotes)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        values[key] = val
    return values


def _int(env: dict[str, str], key: str, default: int, minimum: int = 0) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise PNError(ErrorCode.CONFIG_ERROR, f"{key} must be an integer") from exc
    if value < minimum:
        raise PNError(ErrorCode.CONFIG_ERROR, f"{key} must be >= {minimum}")
    return value


def _float(env: dict[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise PNError(ErrorCode.CONFIG_ERROR, f"{key} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    ads_token: Secret = field(default_factory=lambda: Secret(""))
    ads_base_url: str = "https://api.adsabs.harvard.edu/v1"
    ads_timeout: float = 30.0
    ads_max_retries: int = 3
    ads_page_size: int = 200
    db_path: Path = Path("data/paper_navigator.sqlite3")
    cache_ttl_days: int = 30
    # Network defaults: deliberately small; all configurable (spec P0-B).
    network_depth: int = 1
    network_max_papers: int = 300
    network_max_requests: int = 50
    zotero_base_url: str = "http://127.0.0.1:23119"
    zotero_timeout: float = 5.0
    zotero_api_key: Secret = field(default_factory=lambda: Secret(""))
    export_dir: Path = Path("data/exports")
    log_level: str = "INFO"

    def require_ads_token(self) -> str:
        if not self.ads_token:
            raise PNError(
                ErrorCode.CONFIG_ERROR,
                "ADS_API_TOKEN is not set (see .env.example)",
            )
        return self.ads_token.get()


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_loopback_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme == "http" and (parts.hostname or "") in LOOPBACK_HOSTS


def load_settings(
    env: dict[str, str] | None = None, dotenv: Path | None = Path(".env")
) -> Settings:
    merged: dict[str, str] = {}
    if dotenv is not None:
        merged.update(parse_dotenv(dotenv))
    merged.update(os.environ if env is None else env)
    zotero_url = merged.get("ZOTERO_BASE_URL", "http://127.0.0.1:23119").rstrip("/")
    # Local API reads are unauthenticated; refuse non-loopback targets by default.
    if not is_loopback_url(zotero_url) and merged.get("ZOTERO_ALLOW_REMOTE") != "1":
        raise PNError(
            ErrorCode.CONFIG_ERROR,
            "ZOTERO_BASE_URL must be a loopback http URL (ZOTERO_ALLOW_REMOTE=1 overrides)",
        )
    return Settings(
        ads_token=Secret(merged.get("ADS_API_TOKEN", "").strip()),
        ads_base_url=merged.get("ADS_BASE_URL", Settings.ads_base_url).rstrip("/"),
        ads_timeout=_float(merged, "ADS_TIMEOUT", 30.0),
        ads_max_retries=_int(merged, "ADS_MAX_RETRIES", 3),
        ads_page_size=min(_int(merged, "ADS_PAGE_SIZE", 200, minimum=1), 2000),
        db_path=Path(merged.get("PN_DB_PATH", str(Settings.db_path))),
        cache_ttl_days=_int(merged, "PN_CACHE_TTL_DAYS", 30),
        network_depth=_int(merged, "PN_NETWORK_DEPTH", 1, minimum=1),
        network_max_papers=_int(merged, "PN_NETWORK_MAX_PAPERS", 300, minimum=1),
        network_max_requests=_int(merged, "PN_NETWORK_MAX_REQUESTS", 50, minimum=1),
        zotero_base_url=zotero_url,
        zotero_timeout=_float(merged, "ZOTERO_TIMEOUT", 5.0),
        zotero_api_key=Secret(merged.get("ZOTERO_LOCAL_API_KEY", "").strip()),
        export_dir=Path(merged.get("PN_EXPORT_DIR", str(Settings.export_dir))),
        log_level=merged.get("PN_LOG_LEVEL", "INFO").upper(),
    )
