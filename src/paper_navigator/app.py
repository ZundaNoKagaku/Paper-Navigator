"""Wiring shared by CLI and UI: settings, DB, and optional clients."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .ads.client import ADSClient
from .config import Secret, Settings, load_settings
from .db import Database
from .logging_utils import get_redactor, setup_logging
from .repository import mark_stale_jobs
from .zotero.client import ZoteroLocalClient


@dataclass
class AppContext:
    settings: Settings
    db: Database

    def ads(self) -> ADSClient | None:
        """``None`` when no token is configured (callers show CONFIG_ERROR, never crash)."""
        if not self.settings.ads_token:
            return None
        s = self.settings
        return ADSClient(s.ads_token.get(), s.ads_base_url, s.ads_timeout, s.ads_max_retries)

    def zotero(self) -> ZoteroLocalClient:
        s = self.settings
        key = s.zotero_api_key.get() or read_key_file(zotero_key_path(s))
        get_redactor().add_secret(key)
        return ZoteroLocalClient(s.zotero_base_url, s.zotero_timeout, key)


def zotero_key_path(s: Settings) -> Path:
    return s.db_path.parent / "zotero_local_api_key"


def read_key_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_key_file(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)


def make_context(settings: Settings | None = None) -> AppContext:
    s = settings or load_settings()
    secrets = [x.get() for x in (s.ads_token, s.zotero_api_key) if isinstance(x, Secret)]
    setup_logging(s.log_level, secrets)
    db = Database(s.db_path)
    with db.session() as sess:
        mark_stale_jobs(sess)
    return AppContext(settings=s, db=db)
