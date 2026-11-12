"""Use-case services (UC-01 search, UC-03 detail). UI and CLI call only this layer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .ads.client import ADSClient
from .ads.query import InputKind, build_search_query, detect_input
from .db import Database
from .errors import ErrorCode, PNError
from .models import Paper, RetrievalJob, ZoteroLink, utcnow_iso
from .repository import find_paper, start_job, upsert_paper


@dataclass
class SearchOutcome:
    status: str  # success | partial | failed | empty
    papers: list[dict[str, Any]] = field(default_factory=list)
    num_found: int | None = None
    from_cache: bool = False
    job_id: int | None = None
    error: PNError | None = None
    query: str | None = None
    warnings: list[str] = field(default_factory=list)


def _is_fresh(ts: str | None, ttl_days: int) -> bool:
    if not ts:
        return False
    try:
        when = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return datetime.now(UTC) - when <= timedelta(days=ttl_days)


def search_papers(
    db: Database,
    client: ADSClient | None,
    text: str,
    *,
    kind: InputKind | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    max_results: int = 25,
    refresh: bool = False,
    cache_ttl_days: int = 30,
) -> SearchOutcome:
    """Search ADS (or the local cache for identifier lookups) and persist results."""
    try:
        parsed = detect_input(text, kind)
        q = build_search_query(parsed, year_from, year_to)
    except PNError as exc:
        return SearchOutcome(status="failed", error=exc)

    if parsed.kind != InputKind.TITLE and not refresh:
        with db.session() as s:
            cached = find_paper(s, parsed.value)
            if cached and _is_fresh(cached.retrieved_at, cache_ttl_days):
                return SearchOutcome(
                    status="success",
                    papers=[cached.as_dict()],
                    num_found=1,
                    from_cache=True,
                    query=q,
                )

    if client is None:
        return SearchOutcome(
            status="failed",
            query=q,
            error=PNError(
                ErrorCode.CONFIG_ERROR, "ADS_API_TOKEN is not set; only cached papers are available"
            ),
        )

    with db.session() as s:
        job = start_job(
            s,
            "search",
            q,
            {
                "text": text,
                "kind": parsed.kind.value,
                "max_results": max_results,
                "year_from": year_from,
                "year_to": year_to,
            },
        )
        job_id = job.id
    try:
        result = client.search(
            q,
            max_results=max_results,
            page_size=min(max_results, 200),
            sort="score desc" if parsed.kind == InputKind.TITLE else "bibcode asc",
        )
    except PNError as exc:
        _finish(db, job_id, "failed", exc, requests=client.requests_made)
        return SearchOutcome(status="failed", error=exc, job_id=job_id, query=q)

    papers: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        with db.session() as s:
            for rec in result.records:
                up = upsert_paper(s, rec)
                warnings.extend(rec.warnings)
                if up.conflict:
                    warnings.append(
                        f"identifier conflict for {rec.bibcode}; see duplicate candidates"
                    )
                papers.append(up.paper.as_dict())
    except PNError as exc:
        _finish(db, job_id, "failed", exc, requests=client.requests_made)
        return SearchOutcome(status="failed", error=exc, job_id=job_id, query=q)

    if result.num_found == 0:
        status = "empty"
    elif result.error is not None:
        status = "partial"
    else:
        status = "success"
    _finish(
        db,
        job_id,
        "partial" if status == "partial" else "success",
        result.error,
        requests=client.requests_made,
        pages=result.pages,
        papers=len(papers),
        skipped=result.skipped,
        paging=result.paging,
    )
    return SearchOutcome(
        status=status,
        papers=papers,
        num_found=result.num_found,
        job_id=job_id,
        error=result.error,
        query=q,
        warnings=warnings,
    )


def _finish(
    db: Database,
    job_id: int,
    status: str,
    error: PNError | None,
    *,
    requests: int = 0,
    pages: int = 0,
    papers: int = 0,
    edges: int = 0,
    skipped: int = 0,
    cache_hits: int = 0,
    truncated: bool = False,
    truncation_reason: str | None = None,
    paging: list | None = None,
) -> None:
    with db.session() as s:
        job = s.get(RetrievalJob, job_id)
        if job is None:
            return
        job.status = status
        job.finished_at = utcnow_iso()
        job.error_code = error.code.value if error else None
        job.error_detail = error.detail if error else None
        job.requests_made = requests
        job.pages_fetched = pages
        job.papers_found = papers
        job.edges_found = edges
        job.skipped = skipped
        job.cache_hits = cache_hits
        job.truncated = int(truncated)
        job.truncation_reason = truncation_reason
        job.paging_state = json.dumps(paging or [])


def paper_detail(db: Database, ident: str) -> dict[str, Any] | None:
    with db.session() as s:
        p = find_paper(s, ident)
        if p is None:
            return None
        p = s.scalar(select(Paper).options(selectinload(Paper.authors)).where(Paper.id == p.id))
        assert p is not None
        d = p.as_dict()
        links = s.scalars(select(ZoteroLink).where(ZoteroLink.paper_id == p.id)).all()
        d["zotero"] = [
            {
                "key": z.zotero_key,
                "citation_key": z.citation_key,
                "matched_by": z.matched_by,
                "checked": z.last_checked_at,
            }
            for z in links
        ]
        return d


def list_jobs(db: Database, limit: int = 50) -> list[dict[str, Any]]:
    with db.session() as s:
        jobs = s.scalars(select(RetrievalJob).order_by(RetrievalJob.id.desc()).limit(limit)).all()
        return [{c.name: getattr(j, c.name) for c in RetrievalJob.__table__.columns} for j in jobs]
