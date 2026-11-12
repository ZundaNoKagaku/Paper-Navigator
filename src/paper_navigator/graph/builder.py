"""Build a citation network around a seed paper (UC-02, spec P0-B / §5.1).

Edge direction is fixed everywhere: ``A -> B`` means *paper A cites paper B*.
* ``references`` of X (ADS ``references(bibcode:X)``) produce edges ``X -> ref``.
* ``citations`` of X (ADS ``citations(bibcode:X)``) produce edges ``citer -> X``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select

from ..ads.client import ADSClient
from ..ads.query import citations_query, references_query
from ..db import Database
from ..errors import ErrorCode, PNError
from ..models import JobPaper, Paper
from ..repository import (
    add_edge,
    find_paper,
    get_fetch_state,
    set_fetch_state,
    start_job,
    upsert_paper,
)
from ..services import _finish, _is_fresh, search_papers

Direction = Literal["references", "citations", "both"]
FATAL = {ErrorCode.AUTH_ERROR, ErrorCode.RATE_LIMITED, ErrorCode.CONFIG_ERROR}


@dataclass
class NetworkParams:
    direction: Direction = "both"
    depth: int = 1
    max_papers: int = 300
    max_requests: int = 50
    year_from: int | None = None
    year_to: int | None = None
    refresh: bool = False
    cache_ttl_days: int = 30

    def validate(self) -> None:
        if self.direction not in ("references", "citations", "both"):
            raise PNError(ErrorCode.INPUT_ERROR, "direction must be references|citations|both")
        if not 1 <= self.depth <= 5:
            raise PNError(ErrorCode.INPUT_ERROR, "depth must be between 1 and 5")
        if not 1 <= self.max_papers <= 20000:
            raise PNError(ErrorCode.INPUT_ERROR, "max_papers must be between 1 and 20000")
        if not 1 <= self.max_requests <= 5000:
            raise PNError(ErrorCode.INPUT_ERROR, "max_requests must be between 1 and 5000")
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise PNError(ErrorCode.INPUT_ERROR, "year_from must be <= year_to")


@dataclass
class NetworkOutcome:
    job_id: int | None
    status: str
    seed_id: int | None = None
    papers: int = 0
    edges: int = 0
    requests: int = 0
    cache_hits: int = 0
    truncated: bool = False
    truncation_reason: str | None = None
    errors: list[PNError] = field(default_factory=list)
    incomplete_lists: list[str] = field(default_factory=list)


def _cached_neighbors(db: Database, paper_id: int, direction: str) -> list[int]:
    from ..models import CitationEdge

    with db.session() as s:
        if direction == "references":
            q = select(CitationEdge.cited_id).where(CitationEdge.citing_id == paper_id)
        else:
            q = select(CitationEdge.citing_id).where(CitationEdge.cited_id == paper_id)
        return list(s.scalars(q).all())


def _year_ok(db: Database, pid: int, p: NetworkParams) -> bool:
    if p.year_from is None and p.year_to is None:
        return True
    with db.session() as s:
        y = s.scalar(select(Paper.year).where(Paper.id == pid))
    if y is None:
        return False
    return (p.year_from is None or y >= p.year_from) and (p.year_to is None or y <= p.year_to)


def build_network(
    db: Database,
    client: ADSClient | None,
    seed: str,
    params: NetworkParams,
    progress: Callable[[str], None] | None = None,
) -> NetworkOutcome:
    params.validate()
    say = progress or (lambda _m: None)

    with db.session() as s:
        seed_paper = find_paper(s, seed)
        seed_id = seed_paper.id if seed_paper else None
        seed_bib = seed_paper.bibcode if seed_paper else None
    if seed_paper is None:
        found = search_papers(db, client, seed, max_results=2, cache_ttl_days=params.cache_ttl_days)
        if found.error and not found.papers:
            return NetworkOutcome(job_id=None, status="failed", errors=[found.error])
        if len(found.papers) != 1:
            return NetworkOutcome(
                job_id=None,
                status="failed",
                errors=[
                    PNError(
                        ErrorCode.NOT_FOUND if not found.papers else ErrorCode.INPUT_ERROR,
                        "seed must resolve to exactly one paper (use DOI or bibcode)",
                    )
                ],
            )
        seed_id, seed_bib = found.papers[0]["id"], found.papers[0]["bibcode"]
    if not seed_bib:
        return NetworkOutcome(
            job_id=None,
            status="failed",
            seed_id=seed_id,
            errors=[PNError(ErrorCode.INPUT_ERROR, "seed paper has no ADS bibcode")],
        )

    with db.session() as s:
        job = start_job(s, "network", seed_bib, params.__dict__, seed_paper_id=seed_id)
        job_id = job.id
        s.add(JobPaper(job_id=job_id, paper_id=seed_id, depth=0, role="seed"))

    directions = ["references", "citations"] if params.direction == "both" else [params.direction]
    roles: dict[int, str] = {seed_id: "seed"}  # type: ignore[dict-item]
    depth_of: dict[int, int] = {seed_id: 0}  # type: ignore[dict-item]
    bib_of: dict[int, str] = {seed_id: seed_bib}  # type: ignore[dict-item]
    edges_new = 0
    cache_hits = 0
    errors: list[PNError] = []
    incomplete: list[str] = []
    truncated = False
    reasons: list[str] = []
    requests_start = client.requests_made if client else 0
    queue: deque[int] = deque([seed_id])  # type: ignore[list-item]
    fatal = False

    def requests_used() -> int:
        return (client.requests_made - requests_start) if client else 0

    def admit(pid: int, d: int, role: str) -> bool:
        nonlocal truncated
        if pid in roles:
            if roles[pid] not in ("seed", role):
                roles[pid] = "both"
            return False
        if len(roles) >= params.max_papers:
            truncated = True
            if "max_papers" not in reasons:
                reasons.append("max_papers")
            return False
        roles[pid] = role
        depth_of[pid] = d
        return True

    while queue and not fatal:
        pid = queue.popleft()
        d = depth_of[pid]
        if d >= params.depth:
            continue
        for direction in directions:
            # Role = the kind of link through which a node was reached: via a reference
            # list (prior work, "reference") or a citation list (later work, "citation").
            # Nodes reached both ways become "both".
            role = "reference" if direction == "references" else "citation"
            state = None
            with db.session() as s:
                state = get_fetch_state(s, pid, direction)
            if (
                state
                and state.complete
                and not params.refresh
                and _is_fresh(state.fetched_at, params.cache_ttl_days)
            ):
                cache_hits += 1
                for nid in _cached_neighbors(db, pid, direction):
                    if _year_ok(db, nid, params) and admit(nid, d + 1, role):
                        queue.append(nid)
                continue
            if client is None:
                errors.append(
                    PNError(ErrorCode.CONFIG_ERROR, "ADS_API_TOKEN not set; cache incomplete")
                )
                incomplete.append(f"{bib_of.get(pid, pid)}:{direction}")
                fatal = True
                break
            if requests_used() >= params.max_requests:
                truncated = True
                if "max_requests" not in reasons:
                    reasons.append("max_requests")
                incomplete.append(f"{bib_of.get(pid, pid)}:{direction}")
                continue
            bib = bib_of.get(pid)
            if bib is None:
                with db.session() as s:
                    bib = s.scalar(select(Paper.bibcode).where(Paper.id == pid))
            if not bib:
                incomplete.append(f"#{pid}:{direction} (no bibcode)")
                continue
            q = (references_query if direction == "references" else citations_query)(
                bib, params.year_from, params.year_to
            )
            say(f"{direction} of {bib} (depth {d + 1})")
            remaining = max(params.max_papers - len(roles), 0)
            if remaining == 0:
                truncated = True
                if "max_papers" not in reasons:
                    reasons.append("max_papers")
                incomplete.append(f"{bib}:{direction}")
                continue
            try:
                result = client.search(
                    q,
                    max_results=remaining,
                    page_size=min(200, remaining),
                    request_budget=lambda: requests_used() < params.max_requests,
                )
            except PNError as exc:
                errors.append(exc)
                incomplete.append(f"{bib}:{direction}")
                if exc.code in FATAL:
                    fatal = True
                    break
                continue
            if result.error:
                errors.append(result.error)
                if result.error.code in FATAL:
                    fatal = True
            if not result.complete:
                incomplete.append(f"{bib}:{direction}")
                if result.stopped_by_limit:
                    truncated = True
                    if "max_papers_or_requests" not in reasons:
                        reasons.append("max_papers_or_requests")
            try:
                with db.session() as s:  # one transaction per fetched list
                    for rec in result.records:
                        up = upsert_paper(s, rec)
                        nid = up.paper.id
                        bib_of[nid] = up.paper.bibcode or ""
                        if nid == pid:
                            continue  # self-reference reported by source; ignore as edge
                        if direction == "references":
                            edges_new += add_edge(
                                s, pid, nid, source="ads", job_id=job_id, source_query=q
                            )
                        else:
                            edges_new += add_edge(
                                s, nid, pid, source="ads", job_id=job_id, source_query=q
                            )
                        if admit(nid, d + 1, role):
                            queue.append(nid)
                    unfiltered = params.year_from is None and params.year_to is None
                    set_fetch_state(
                        s,
                        pid,
                        direction,
                        num_found=result.num_found,
                        num_fetched=result.fetched,
                        complete=result.complete and unfiltered,
                        job_id=job_id,
                    )
            except PNError as exc:
                errors.append(exc)
                incomplete.append(f"{bib}:{direction}")

    with db.session() as s:
        for pid, role in roles.items():
            if pid == seed_id:
                continue
            s.merge(JobPaper(job_id=job_id, paper_id=pid, depth=depth_of[pid], role=role))
        if fatal and queue:
            truncated = True
            reasons.append("aborted_on_error")

    partial = bool(errors or incomplete or truncated)
    status = "partial" if partial else "success"
    if fatal and len(roles) == 1:
        status = "failed"
    reason = ", ".join(reasons) or None
    _finish(
        db,
        job_id,
        status,
        errors[0] if errors else None,
        requests=requests_used(),
        papers=len(roles),
        edges=edges_new,
        cache_hits=cache_hits,
        truncated=truncated,
        truncation_reason=reason,
        paging=[{"incomplete": incomplete}],
    )
    return NetworkOutcome(
        job_id=job_id,
        status=status,
        seed_id=seed_id,
        papers=len(roles),
        edges=edges_new,
        requests=requests_used(),
        cache_hits=cache_hits,
        truncated=truncated,
        truncation_reason=reason,
        errors=errors,
        incomplete_lists=incomplete,
    )
