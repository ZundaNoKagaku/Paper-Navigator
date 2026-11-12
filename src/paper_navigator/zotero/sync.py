"""Link Zotero items to local papers and record ADS/Zotero metadata disagreements.

Policy (docs/SYSTEM_SPECIFICATION.md §6.4):
* Linking: DOI match, else ADS bibcode found in Zotero ``Extra``/``URL``. Title similarity
  alone never links; it is only reported as ``possible_match``.
* Field decisions: ``match`` (equal after normalization); ``prefer_zotero`` for cosmetic
  differences (title case/punctuation, journal abbreviation) since the .bib is produced
  from Zotero; ``manual_review`` for substantive differences (DOI, year, volume, pages,
  different title text).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ..db import Database
from ..models import Paper, Reconciliation, ZoteroLink, utcnow_iso
from ..normalize import normalize_title, title_similarity
from .client import ZoteroItem, ZoteroLocalClient


@dataclass
class SyncReport:
    collection: str
    items: int = 0
    linked: int = 0
    not_in_db: list[str] = field(default_factory=list)
    possible_matches: list[tuple[str, int, float]] = field(default_factory=list)
    mismatches: list[dict] = field(default_factory=list)
    missing_citation_keys: list[str] = field(default_factory=list)


def _first_page(p: str | None) -> str | None:
    return p.split("-")[0].strip().lstrip("0") or None if p else None


def compare_fields(paper: Paper, item: ZoteroItem) -> list[tuple[str, str | None, str | None, str]]:
    out = []

    def add(field_: str, a: object, z: object, decision: str) -> None:
        out.append((field_, None if a is None else str(a), None if z is None else str(z), decision))

    if paper.doi or item.doi:
        add("doi", paper.doi, item.doi, "match" if paper.doi == item.doi else "manual_review")
    if paper.title and item.title:
        if paper.title == item.title:
            d = "match"
        elif normalize_title(paper.title) == normalize_title(item.title):
            d = "prefer_zotero"
        else:
            d = "manual_review"
        add("title", paper.title, item.title, d)
    if paper.year is not None and item.year is not None:
        add("year", paper.year, item.year, "match" if paper.year == item.year else "manual_review")
    if paper.volume and item.volume:
        add(
            "volume",
            paper.volume,
            item.volume,
            "match" if paper.volume.strip() == item.volume.strip() else "manual_review",
        )
    if paper.page and item.pages:
        add(
            "pages",
            paper.page,
            item.pages,
            "match" if _first_page(paper.page) == _first_page(item.pages) else "manual_review",
        )
    if paper.pub and item.journal:
        add(
            "journal",
            paper.pub,
            item.journal,
            "match"
            if normalize_title(paper.pub) == normalize_title(item.journal)
            else "prefer_zotero",
        )
    return out


def _match_paper(
    papers_by_doi: dict, papers_by_bib: dict, item: ZoteroItem
) -> tuple[Paper | None, str]:
    if item.doi and item.doi in papers_by_doi:
        return papers_by_doi[item.doi], "doi"
    if item.ads_bibcode and item.ads_bibcode in papers_by_bib:
        return papers_by_bib[item.ads_bibcode], "ads_bibcode"
    return None, ""


def sync_collection(db: Database, client: ZoteroLocalClient, collection_key: str) -> SyncReport:
    """Read-only with respect to Zotero; writes links/reconciliations to the local DB."""
    items = client.collection_items(collection_key)
    report = SyncReport(collection=collection_key, items=len(items))
    with db.session() as s:
        papers = s.scalars(select(Paper).options(selectinload(Paper.authors))).all()
        by_doi = {p.doi: p for p in papers if p.doi}
        by_bib = {p.bibcode: p for p in papers if p.bibcode}
        for item in items:
            if not item.citation_key:
                report.missing_citation_keys.append(item.key)
            paper, how = _match_paper(by_doi, by_bib, item)
            if paper is None:
                report.not_in_db.append(item.key)
                if item.title:
                    best = max(
                        ((title_similarity(item.title, p.title), p.id) for p in papers),
                        default=(0.0, -1),
                    )
                    if best[0] >= 0.9:
                        report.possible_matches.append((item.key, best[1], round(best[0], 3)))
                continue
            report.linked += 1
            s.merge(
                ZoteroLink(
                    paper_id=paper.id,
                    zotero_key=item.key,
                    library="user:0",
                    citation_key=item.citation_key,
                    matched_by=how,
                    last_checked_at=utcnow_iso(),
                )
            )
            s.execute(
                delete(Reconciliation).where(
                    Reconciliation.paper_id == paper.id, Reconciliation.zotero_key == item.key
                )
            )
            for f, a, z, decision in compare_fields(paper, item):
                s.add(
                    Reconciliation(
                        paper_id=paper.id,
                        zotero_key=item.key,
                        field=f,
                        ads_value=a,
                        zotero_value=z,
                        decision=decision,
                    )
                )
                if decision != "match":
                    report.mismatches.append(
                        {
                            "paper_id": paper.id,
                            "zotero_key": item.key,
                            "field": f,
                            "ads": a,
                            "zotero": z,
                            "decision": decision,
                        }
                    )
    return report
