"""Persistence operations: de-duplicating upserts, edges, fetch state, jobs.

De-duplication policy (spec §4.4, documented in docs/SYSTEM_SPECIFICATION.md §6.2):
1. normalized DOI match           -> same paper (merge)
2. ADS bibcode / alternate match  -> same paper (merge)
3. arXiv id match                 -> same paper (merge)
4. title similarity >= 0.90 AND same first-author family name AND |year diff| <= 1
   -> *duplicate candidate* only; recorded for manual review, never merged.
If one record's identifiers point at two different stored papers, nothing is merged and a
candidate with reason ``identifier_conflict`` is recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from . import __version__
from .models import (
    CitationEdge,
    DuplicateCandidate,
    FetchState,
    Paper,
    PaperAuthor,
    PaperIdentifier,
    RetrievalJob,
    utcnow_iso,
)
from .normalize import family_key, normalize_doi, split_author, title_similarity
from .records import PaperRecord

CANDIDATE_TITLE_THRESHOLD = 0.90
_MERGE_FIELDS = (
    "title",
    "year",
    "pub",
    "bibstem",
    "volume",
    "issue",
    "page",
    "doctype",
    "abstract",
)


@dataclass
class UpsertResult:
    paper: Paper
    created: bool
    candidates: int = 0
    conflict: bool = False


def _identifier_pairs(rec: PaperRecord) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for d in [rec.doi, *rec.extra_dois]:
        nd = normalize_doi(d)
        if nd:
            pairs.append(("doi", nd))
    for b in [rec.bibcode, *rec.alternate_bibcodes]:
        if b:
            pairs.append(("bibcode", b))
    if rec.arxiv_id:
        pairs.append(("arxiv", rec.arxiv_id))
    return list(dict.fromkeys(pairs))


def _find_by_identifiers(s: Session, pairs: list[tuple[str, str]]) -> list[tuple[str, Paper]]:
    """Return (scheme, paper) matches ordered by scheme priority (doi, bibcode, arxiv)."""
    found: list[tuple[str, Paper]] = []
    seen: set[int] = set()
    col = {"doi": Paper.doi, "bibcode": Paper.bibcode, "arxiv": Paper.arxiv_id}
    for scheme in ("doi", "bibcode", "arxiv"):
        values = [v for sch, v in pairs if sch == scheme]
        if not values:
            continue
        direct = s.scalars(select(Paper).where(col[scheme].in_(values))).all()
        via_ids = s.scalars(
            select(Paper)
            .join(PaperIdentifier)
            .where(PaperIdentifier.scheme == scheme, PaperIdentifier.value.in_(values))
        ).all()
        for p in [*direct, *via_ids]:
            if p.id not in seen:
                seen.add(p.id)
                found.append((scheme, p))
    return found


def _set_authors(paper: Paper, names: list[str]) -> None:
    paper.authors.clear()
    for i, name in enumerate(names):
        family, given = split_author(name)
        paper.authors.append(PaperAuthor(position=i, name=name, family=family, given=given))


def _owned_by_other(s: Session, scheme: str, value: str, paper_id: int | None) -> bool:
    col = {"doi": Paper.doi, "bibcode": Paper.bibcode, "arxiv": Paper.arxiv_id}[scheme]
    q = select(Paper.id).where(col == value)
    ids = set(s.scalars(q).all())
    ids |= set(
        s.scalars(
            select(PaperIdentifier.paper_id).where(
                PaperIdentifier.scheme == scheme, PaperIdentifier.value == value
            )
        ).all()
    )
    ids.discard(paper_id)  # type: ignore[arg-type]
    return bool(ids)


def _register_identifiers(s: Session, paper: Paper, pairs: list[tuple[str, str]]) -> None:
    existing = {(i.scheme, i.value) for i in paper.identifiers}
    for scheme, value in pairs:
        if (scheme, value) in existing or _owned_by_other(s, scheme, value, paper.id):
            continue
        paper.identifiers.append(PaperIdentifier(scheme=scheme, value=value))
        existing.add((scheme, value))


def _apply_record(s: Session, paper: Paper, rec: PaperRecord, *, overwrite: bool) -> None:
    for name in _MERGE_FIELDS:
        new = getattr(rec, name)
        if new is None:
            continue  # never erase a known value with "unknown"
        if overwrite or getattr(paper, name) is None:
            setattr(paper, name, new)
    for scheme, attr, value in (
        ("doi", "doi", normalize_doi(rec.doi)),
        ("bibcode", "bibcode", rec.bibcode),
        ("arxiv", "arxiv_id", rec.arxiv_id),
    ):
        if (
            value
            and getattr(paper, attr) is None
            and not _owned_by_other(s, scheme, value, paper.id)
        ):
            setattr(paper, attr, value)
    if rec.authors and (overwrite or not paper.authors):
        _set_authors(paper, rec.authors)
    ids = json.loads(paper.source_ids or "{}")
    ids.update(rec.source_ids)
    paper.source_ids = json.dumps(ids, sort_keys=True)
    paper.source = rec.source if overwrite or not paper.source else paper.source
    paper.retrieved_at = utcnow_iso()
    paper.updated_at = utcnow_iso()
    # recompute completeness from the merged state
    merged = PaperRecord(
        source=paper.source,
        title=paper.title,
        authors=[a.name for a in paper.authors],
        year=paper.year,
        pub=paper.pub,
        volume=paper.volume,
        page=paper.page,
        doi=paper.doi,
        bibcode=paper.bibcode,
        abstract=paper.abstract,
    )
    paper.missing_fields = json.dumps(merged.missing_fields())
    paper.validation_status = merged.validation_status()


def _add_candidate(s: Session, a: int, b: int, score: float, reason: str) -> bool:
    lo, hi = sorted((a, b))
    exists = s.scalar(
        select(DuplicateCandidate.id).where(
            DuplicateCandidate.paper_a == lo, DuplicateCandidate.paper_b == hi
        )
    )
    if exists:
        return False
    s.add(DuplicateCandidate(paper_a=lo, paper_b=hi, score=round(score, 4), reason=reason))
    return True


def _detect_candidates(s: Session, paper: Paper) -> int:
    if not paper.title or paper.year is None:
        return 0
    fam = family_key(paper.authors[0].name) if paper.authors else ""
    q = (
        select(Paper)
        .options(selectinload(Paper.authors))
        .where(Paper.id != paper.id, Paper.year.between(paper.year - 1, paper.year + 1))
    )
    if paper.authors and paper.authors[0].family:
        # Candidates require the same first-author family name: pre-filter in SQL
        # (indexed) instead of comparing titles against every paper of the period.
        q = q.join(PaperAuthor, (PaperAuthor.paper_id == Paper.id) & (PaperAuthor.position == 0))
        q = q.where(func.lower(PaperAuthor.family) == paper.authors[0].family.lower())
    rows = s.scalars(q.limit(5000)).all()
    n = 0
    for other in rows:
        other_fam = family_key(other.authors[0].name) if other.authors else ""
        if fam and other_fam and fam != other_fam:
            continue
        score = title_similarity(paper.title, other.title)
        if score >= CANDIDATE_TITLE_THRESHOLD:
            reason = "similar_title_same_first_author" if fam else "similar_title"
            n += _add_candidate(s, paper.id, other.id, score, reason)
    return n


def upsert_paper(s: Session, rec: PaperRecord, *, overwrite: bool = True) -> UpsertResult:
    pairs = _identifier_pairs(rec)
    matches = _find_by_identifiers(s, pairs)
    conflict = len(matches) > 1
    if matches:
        paper = matches[0][1]
        if conflict:
            for _, other in matches[1:]:
                _add_candidate(s, paper.id, other.id, 1.0, "identifier_conflict")
        _apply_record(s, paper, rec, overwrite=overwrite)
        _register_identifiers(s, paper, pairs)
        s.flush()
        return UpsertResult(paper=paper, created=False, conflict=conflict)
    paper = Paper(
        source=rec.source,
        retrieved_at=utcnow_iso(),
        validation_status="incomplete",
        created_at=utcnow_iso(),
        updated_at=utcnow_iso(),
    )
    s.add(paper)
    _apply_record(s, paper, rec, overwrite=True)
    s.flush()
    _register_identifiers(s, paper, pairs)
    s.flush()
    n = _detect_candidates(s, paper)
    return UpsertResult(paper=paper, created=True, candidates=n)


def add_edge(
    s: Session,
    citing_id: int,
    cited_id: int,
    *,
    source: str,
    job_id: int | None,
    source_query: str | None,
) -> bool:
    """Insert ``citing -> cited``; returns True if newly created."""
    edge = s.scalar(
        select(CitationEdge).where(
            CitationEdge.citing_id == citing_id, CitationEdge.cited_id == cited_id
        )
    )
    now = utcnow_iso()
    if edge:
        edge.retrieved_at = now
        edge.job_id = job_id
        return False
    s.add(
        CitationEdge(
            citing_id=citing_id,
            cited_id=cited_id,
            source=source,
            job_id=job_id,
            source_query=source_query,
            retrieved_at=now,
            verification_status="source_reported",
        )
    )
    s.flush()
    return True


def get_fetch_state(s: Session, paper_id: int, direction: str) -> FetchState | None:
    return s.get(FetchState, (paper_id, direction))


def set_fetch_state(
    s: Session,
    paper_id: int,
    direction: str,
    *,
    num_found: int | None,
    num_fetched: int,
    complete: bool,
    job_id: int | None,
) -> None:
    st = s.get(FetchState, (paper_id, direction))
    if st is None:
        st = FetchState(paper_id=paper_id, direction=direction)
        s.add(st)
    st.fetched_at = utcnow_iso()
    st.num_found = num_found
    st.num_fetched = num_fetched
    st.complete = int(complete)
    st.job_id = job_id


def start_job(
    s: Session, kind: str, query: str | None, params: dict, seed_paper_id: int | None = None
) -> RetrievalJob:
    job = RetrievalJob(
        kind=kind,
        query=query,
        params=json.dumps(params, sort_keys=True),
        seed_paper_id=seed_paper_id,
        started_at=utcnow_iso(),
        status="running",
        software_version=__version__,
    )
    s.add(job)
    s.flush()
    return job


def find_paper(s: Session, ident: str) -> Paper | None:
    """Look up by internal id (``#12``), DOI, bibcode, or arXiv id."""
    ident = ident.strip()
    if ident.startswith("#") and ident[1:].isdigit():
        return s.get(Paper, int(ident[1:]))
    doi = normalize_doi(ident)
    conds = [Paper.bibcode == ident, Paper.arxiv_id == ident]
    if doi:
        conds.append(Paper.doi == doi)
    p = s.scalar(select(Paper).where(or_(*conds)))
    if p:
        return p
    pid = s.scalar(
        select(PaperIdentifier.paper_id).where(
            PaperIdentifier.value.in_([ident] + ([doi] if doi else []))
        )
    )
    return s.get(Paper, pid) if pid else None


def mark_stale_jobs(s: Session, older_than_hours: int = 6) -> int:
    """Jobs still 'running' long after start were interrupted (crash, closed UI).

    They are marked failed/INTERRUPTED; data already committed per list is kept.
    """
    from datetime import UTC, datetime, timedelta

    cutoff = (datetime.now(UTC) - timedelta(hours=older_than_hours)).isoformat(timespec="seconds")
    res = s.execute(
        update(RetrievalJob)
        .where(RetrievalJob.status == "running", RetrievalJob.started_at < cutoff)
        .values(
            status="failed",
            error_code="INTERRUPTED",
            finished_at=utcnow_iso(),
            error_detail="job did not finish (process stopped); partial data kept",
        )
    )
    return int(res.rowcount or 0)  # type: ignore[attr-defined]
