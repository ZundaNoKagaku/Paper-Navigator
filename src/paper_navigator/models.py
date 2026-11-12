"""ORM mappings. The physical schema is created by explicit, versioned DDL in
:mod:`paper_navigator.db` (migrations); ``tests/test_db.py`` checks these mappings match it.

Responsibilities are separated so P1 features (files, translations, model info) can be
added as new tables that reference ``papers.id`` without altering existing ones.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    pub: Mapped[str | None] = mapped_column(Text)
    bibstem: Mapped[str | None] = mapped_column(String)
    volume: Mapped[str | None] = mapped_column(String)
    issue: Mapped[str | None] = mapped_column(String)
    page: Mapped[str | None] = mapped_column(String)
    doctype: Mapped[str | None] = mapped_column(String)
    doi: Mapped[str | None] = mapped_column(String, unique=True)
    bibcode: Mapped[str | None] = mapped_column(String, unique=True)
    arxiv_id: Mapped[str | None] = mapped_column(String, unique=True)
    abstract: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_ids: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    retrieved_at: Mapped[str] = mapped_column(String, nullable=False)
    missing_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    validation_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)

    authors: Mapped[list[PaperAuthor]] = relationship(
        back_populates="paper",
        order_by="PaperAuthor.position",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list[PaperIdentifier]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )

    @property
    def author_names(self) -> list[str]:
        return [a.name for a in self.authors]

    @property
    def missing(self) -> list[str]:
        return list(json.loads(self.missing_fields or "[]"))

    def links(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.bibcode:
            out["ADS"] = f"https://ui.adsabs.harvard.edu/abs/{self.bibcode}/abstract"
        if self.doi:
            out["DOI"] = f"https://doi.org/{self.doi}"
        if self.arxiv_id:
            out["arXiv"] = f"https://arxiv.org/abs/{self.arxiv_id}"
        return out

    def label(self) -> str:
        first = self.authors[0].family if self.authors and self.authors[0].family else "?"
        return f"{first} {self.year or '????'} ({self.bibcode or self.doi or f'#{self.id}'})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.author_names,
            "year": self.year,
            "pub": self.pub,
            "bibstem": self.bibstem,
            "volume": self.volume,
            "issue": self.issue,
            "page": self.page,
            "doctype": self.doctype,
            "doi": self.doi,
            "bibcode": self.bibcode,
            "arxiv_id": self.arxiv_id,
            "abstract": self.abstract,
            "source": self.source,
            "retrieved_at": self.retrieved_at,
            "missing_fields": self.missing,
            "validation_status": self.validation_status,
            "links": self.links(),
        }


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str | None] = mapped_column(Text)
    given: Mapped[str | None] = mapped_column(Text)

    paper: Mapped[Paper] = relationship(back_populates="authors")


class PaperIdentifier(Base):
    __tablename__ = "paper_identifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    scheme: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)

    paper: Mapped[Paper] = relationship(back_populates="identifiers")


class CitationEdge(Base):
    """Directed edge: ``citing_id -> cited_id`` means *citing cites cited*."""

    __tablename__ = "citation_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    citing_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    cited_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_query: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("retrieval_jobs.id", ondelete="SET NULL"))
    retrieved_at: Mapped[str] = mapped_column(String, nullable=False)
    verification_status: Mapped[str] = mapped_column(String, nullable=False)


class FetchState(Base):
    """Records whether a paper's references/citations list was fetched completely."""

    __tablename__ = "fetch_state"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    direction: Mapped[str] = mapped_column(String, primary_key=True)
    fetched_at: Mapped[str] = mapped_column(String, nullable=False)
    num_found: Mapped[int | None] = mapped_column(Integer)
    num_fetched: Mapped[int] = mapped_column(Integer, nullable=False)
    complete: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("retrieval_jobs.id", ondelete="SET NULL"))


class RetrievalJob(Base):
    __tablename__ = "retrieval_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str | None] = mapped_column(Text)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    seed_paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"))
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String)
    error_detail: Mapped[str | None] = mapped_column(Text)
    requests_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    papers_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edges_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncation_reason: Mapped[str | None] = mapped_column(Text)
    paging_state: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    software_version: Mapped[str] = mapped_column(String, nullable=False)


class JobPaper(Base):
    """Membership of a paper in a network job (hop depth and role relative to the seed)."""

    __tablename__ = "job_papers"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("retrieval_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_a: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    paper_b: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)


class ZoteroLink(Base):
    __tablename__ = "zotero_links"

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    zotero_key: Mapped[str] = mapped_column(String, primary_key=True)
    library: Mapped[str] = mapped_column(String, nullable=False)
    citation_key: Mapped[str | None] = mapped_column(String)
    matched_by: Mapped[str] = mapped_column(String, nullable=False)
    last_checked_at: Mapped[str] = mapped_column(String, nullable=False)


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    zotero_key: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    ads_value: Mapped[str | None] = mapped_column(Text)
    zotero_value: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)


class ExportRecord(Base):
    __tablename__ = "export_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("retrieval_jobs.id", ondelete="SET NULL"))
    details: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False, default=utcnow_iso)
