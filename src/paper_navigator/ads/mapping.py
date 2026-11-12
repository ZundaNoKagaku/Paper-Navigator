"""Map ADS Search API documents to :class:`PaperRecord`.

Nothing is inferred: absent fields stay ``None`` and are reported in ``missing_fields``.
"""

from __future__ import annotations

from typing import Any

from ..normalize import normalize_arxiv, normalize_bibcode, normalize_doi
from ..records import PaperRecord

# Fields requested from ADS (``fl``); all exist in the ADS OpenAPI ``fl`` enum.
ADS_FIELDS = [
    "bibcode",
    "alternate_bibcode",
    "title",
    "author",
    "year",
    "pub",
    "bibstem",
    "volume",
    "issue",
    "page",
    "page_range",
    "doi",
    "identifier",
    "abstract",
    "doctype",
]


def _first_str(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    if not isinstance(value, str | int):
        return None
    s = str(value).strip()
    return s or None


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v).strip() for v in value if isinstance(v, str | int) and str(v).strip()]
    return []


def ads_doc_to_record(doc: dict[str, Any]) -> PaperRecord:
    if not isinstance(doc, dict):
        raise TypeError("ADS document must be an object")
    warnings: list[str] = []
    raw_bib = _first_str(doc.get("bibcode"))
    bibcode = normalize_bibcode(raw_bib)
    if raw_bib and not bibcode:
        warnings.append(f"unrecognised bibcode format: {raw_bib!r}")
        bibcode = raw_bib  # keep ADS's identifier verbatim; it is still its primary key

    dois_raw = _str_list(doc.get("doi"))
    dois = [d for d in (normalize_doi(x) for x in dois_raw) if d]
    if len(dois) < len(dois_raw):
        warnings.append("some DOI values were not valid DOIs and were ignored")

    arxiv = None
    for ident in _str_list(doc.get("identifier")):
        if ident.lower().startswith("arxiv:"):
            arxiv = normalize_arxiv(ident)
            if arxiv:
                break

    year_raw = _first_str(doc.get("year"))
    year: int | None = None
    if year_raw:
        try:
            year = int(year_raw[:4])
        except ValueError:
            warnings.append(f"unparseable year {year_raw!r}")

    page = _first_str(doc.get("page"))
    page_range = _first_str(doc.get("page_range"))
    bibstem = _first_str(doc.get("bibstem"))

    rec = PaperRecord(
        source="ads",
        title=_first_str(doc.get("title")),
        authors=_str_list(doc.get("author")),
        year=year,
        pub=_first_str(doc.get("pub")),
        bibstem=bibstem,
        volume=_first_str(doc.get("volume")),
        issue=_first_str(doc.get("issue")),
        page=page_range or page,
        doctype=_first_str(doc.get("doctype")),
        doi=dois[0] if dois else None,
        bibcode=bibcode,
        arxiv_id=arxiv,
        abstract=_first_str(doc.get("abstract")),
        alternate_bibcodes=[b for b in _str_list(doc.get("alternate_bibcode")) if b != bibcode],
        extra_dois=dois[1:],
        source_ids={"ads_bibcode": bibcode} if bibcode else {},
        warnings=warnings,
    )
    return rec
