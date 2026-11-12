"""SQLite engine, versioned migrations, and transactional sessions (spec P0-C).

Migration policy (ADR-004): each schema change is a new entry appended to
``MIGRATIONS`` with a monotonically increasing version. Migrations run inside a single
transaction each and are recorded in ``schema_migrations``. Existing entries are never
edited once released.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .errors import ErrorCode, PNError
from .models import utcnow_iso

log = logging.getLogger(__name__)

SCHEMA_V1 = [
    """
    CREATE TABLE papers (
        id INTEGER PRIMARY KEY,
        title TEXT, year INTEGER, pub TEXT, bibstem TEXT, volume TEXT, issue TEXT,
        page TEXT, doctype TEXT,
        doi TEXT UNIQUE, bibcode TEXT UNIQUE, arxiv_id TEXT UNIQUE,
        abstract TEXT,
        source TEXT NOT NULL,
        source_ids TEXT NOT NULL DEFAULT '{}',
        retrieved_at TEXT NOT NULL,
        missing_fields TEXT NOT NULL DEFAULT '[]',
        validation_status TEXT NOT NULL
            CHECK (validation_status IN ('complete','incomplete','stub')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (year IS NULL OR (year BETWEEN 1000 AND 3000))
    )""",
    """
    CREATE TABLE paper_authors (
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        position INTEGER NOT NULL CHECK (position >= 0),
        name TEXT NOT NULL, family TEXT, given TEXT,
        PRIMARY KEY (paper_id, position)
    )""",
    """
    CREATE TABLE paper_identifiers (
        id INTEGER PRIMARY KEY,
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        scheme TEXT NOT NULL, value TEXT NOT NULL,
        UNIQUE (scheme, value)
    )""",
    """
    CREATE TABLE retrieval_jobs (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL CHECK (kind IN ('search','network')),
        query TEXT,
        params TEXT NOT NULL DEFAULT '{}',
        seed_paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
        started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL CHECK (status IN ('running','success','partial','failed')),
        error_code TEXT, error_detail TEXT,
        requests_made INTEGER NOT NULL DEFAULT 0,
        pages_fetched INTEGER NOT NULL DEFAULT 0,
        cache_hits INTEGER NOT NULL DEFAULT 0,
        papers_found INTEGER NOT NULL DEFAULT 0,
        edges_found INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0,
        truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0,1)),
        truncation_reason TEXT,
        paging_state TEXT NOT NULL DEFAULT '[]',
        software_version TEXT NOT NULL
    )""",
    """
    CREATE TABLE citation_edges (
        id INTEGER PRIMARY KEY,
        citing_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        cited_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        source TEXT NOT NULL,
        source_query TEXT,
        job_id INTEGER REFERENCES retrieval_jobs(id) ON DELETE SET NULL,
        retrieved_at TEXT NOT NULL,
        verification_status TEXT NOT NULL
            CHECK (verification_status IN ('source_reported','user_confirmed','disputed')),
        UNIQUE (citing_id, cited_id)
    )""",
    "CREATE INDEX ix_edges_cited ON citation_edges(cited_id)",
    """
    CREATE TABLE job_papers (
        job_id INTEGER NOT NULL REFERENCES retrieval_jobs(id) ON DELETE CASCADE,
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        depth INTEGER NOT NULL CHECK (depth >= 0),
        role TEXT NOT NULL CHECK (role IN ('seed','reference','citation','both')),
        PRIMARY KEY (job_id, paper_id)
    )""",
    """
    CREATE TABLE fetch_state (
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        direction TEXT NOT NULL CHECK (direction IN ('references','citations')),
        fetched_at TEXT NOT NULL,
        num_found INTEGER,
        num_fetched INTEGER NOT NULL,
        complete INTEGER NOT NULL CHECK (complete IN (0,1)),
        job_id INTEGER REFERENCES retrieval_jobs(id) ON DELETE SET NULL,
        PRIMARY KEY (paper_id, direction)
    )""",
    """
    CREATE TABLE duplicate_candidates (
        id INTEGER PRIMARY KEY,
        paper_a INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        paper_b INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        score REAL NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending','confirmed_duplicate','distinct')),
        created_at TEXT NOT NULL,
        CHECK (paper_a < paper_b),
        UNIQUE (paper_a, paper_b)
    )""",
    """
    CREATE TABLE zotero_links (
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        zotero_key TEXT NOT NULL,
        library TEXT NOT NULL,
        citation_key TEXT,
        matched_by TEXT NOT NULL,
        last_checked_at TEXT NOT NULL,
        PRIMARY KEY (paper_id, zotero_key)
    )""",
    """
    CREATE TABLE reconciliations (
        id INTEGER PRIMARY KEY,
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        zotero_key TEXT NOT NULL,
        field TEXT NOT NULL,
        ads_value TEXT, zotero_value TEXT,
        decision TEXT NOT NULL
            CHECK (decision IN ('match','prefer_ads','prefer_zotero','manual_review')),
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE export_records (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,
        path TEXT,
        job_id INTEGER REFERENCES retrieval_jobs(id) ON DELETE SET NULL,
        details TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )""",
]

# (version, description, statements). Append-only.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "initial schema", SCHEMA_V1),
    (
        2,
        "indexes for duplicate-candidate lookup (v0.1.1)",
        [
            "CREATE INDEX IF NOT EXISTS ix_papers_year ON papers(year)",
            "CREATE INDEX IF NOT EXISTS ix_authors_family "
            "ON paper_authors(lower(family), position)",
        ],
    ),
]

LATEST_VERSION = MIGRATIONS[-1][0]


def _set_sqlite_pragmas(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


def make_engine(db_path: Path | str) -> Engine:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    url = "sqlite://" if str(db_path) == ":memory:" else f"sqlite:///{db_path}"
    engine = create_engine(url, future=True)
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def current_version(engine: Engine) -> int:
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
        ).first()
        if not exists:
            return 0
        row = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).first()
        return int(row[0] or 0) if row else 0


def migrate(engine: Engine) -> list[int]:
    """Apply pending migrations; returns the list of versions applied."""
    applied: list[int] = []
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, description TEXT NOT NULL, "
                    "applied_at TEXT NOT NULL)"
                )
            )
        have = current_version(engine)
        if have > LATEST_VERSION:
            raise PNError(
                ErrorCode.DATABASE_ERROR,
                f"database schema v{have} is newer than this software (v{LATEST_VERSION})",
            )
        for version, desc, stmts in MIGRATIONS:
            if version <= have:
                continue
            with engine.begin() as conn:  # one transaction per migration
                for stmt in stmts:
                    conn.execute(text(stmt))
                conn.execute(
                    text("INSERT INTO schema_migrations VALUES (:v, :d, :t)"),
                    {"v": version, "d": desc, "t": utcnow_iso()},
                )
            applied.append(version)
            log.info("applied migration v%s (%s)", version, desc)
    except SQLAlchemyError as exc:
        raise PNError(ErrorCode.DATABASE_ERROR, f"migration failed: {exc}") from exc
    return applied


class Database:
    def __init__(self, db_path: Path | str):
        self.path = db_path
        self.engine = make_engine(db_path)
        migrate(self.engine)
        self._factory = sessionmaker(self.engine, expire_on_commit=False)

    def backup(self, dest_dir: Path) -> Path:
        """Consistent online copy via SQLite's backup API (safe while the app runs)."""
        import sqlite3
        from datetime import UTC, datetime

        if str(self.path) == ":memory:":
            raise PNError(ErrorCode.DATABASE_ERROR, "in-memory database cannot be backed up")
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = dest_dir / f"{Path(self.path).stem}-{stamp}.sqlite3"
        try:
            with sqlite3.connect(self.path) as src, sqlite3.connect(dest) as dst:
                src.backup(dst)
        except sqlite3.Error as exc:
            raise PNError(ErrorCode.DATABASE_ERROR, f"backup failed: {exc}") from exc
        return dest

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commit on success, roll back on any error."""
        session = self._factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise PNError(ErrorCode.DATABASE_ERROR, str(exc)) from exc
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
