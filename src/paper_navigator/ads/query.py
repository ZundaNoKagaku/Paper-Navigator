"""Build NASA ADS query strings from user input.

Verified against ADS help (2026-11-12):
* ``references(query)`` returns records **cited by** the matched paper(s).
* ``citations(query)`` returns records **citing** the matched paper(s).
  https://ui.adsabs.harvard.edu/help/search/citations-and-references
* ``q`` is limited to 1000 characters (adsabs-dev-api search docs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from ..errors import ErrorCode, PNError
from ..normalize import normalize_arxiv, normalize_bibcode, normalize_doi

MAX_QUERY_LEN = 1000


class InputKind(StrEnum):
    DOI = "doi"
    BIBCODE = "bibcode"
    ARXIV = "arxiv"
    TITLE = "title"


@dataclass(frozen=True)
class ParsedInput:
    kind: InputKind
    value: str


def _quote(value: str) -> str:
    """Quote a value as a Solr phrase, escaping backslashes and double quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def detect_input(raw: str, forced: InputKind | None = None) -> ParsedInput:
    text = (raw or "").strip()
    if not text:
        raise PNError(ErrorCode.INPUT_ERROR, "search text is empty")
    if len(text) > 500:
        raise PNError(ErrorCode.INPUT_ERROR, "search text is too long (max 500 characters)")
    if any(ord(c) < 32 for c in text):
        raise PNError(ErrorCode.INPUT_ERROR, "search text contains control characters")
    checks = (
        (InputKind.DOI, normalize_doi),
        (InputKind.BIBCODE, normalize_bibcode),
        (InputKind.ARXIV, normalize_arxiv),
    )
    if forced and forced != InputKind.TITLE:
        fn = dict(checks)[forced]
        value = fn(text)
        if value is None:
            raise PNError(ErrorCode.INPUT_ERROR, f"not a valid {forced.value}: {text!r}")
        return ParsedInput(forced, value)
    if forced is None:
        for kind, fn in checks:
            value = fn(text)
            if value is not None:
                return ParsedInput(kind, value)
    return ParsedInput(InputKind.TITLE, re.sub(r"\s+", " ", text))


def build_search_query(
    parsed: ParsedInput, year_from: int | None = None, year_to: int | None = None
) -> str:
    if parsed.kind == InputKind.DOI:
        q = f"doi:{_quote(parsed.value)}"
    elif parsed.kind == InputKind.BIBCODE:
        # identifier: also matches alternate bibcodes (e.g., arXiv e-print bibcodes)
        q = f"identifier:{_quote(parsed.value)}"
    elif parsed.kind == InputKind.ARXIV:
        q = f"identifier:{_quote('arXiv:' + parsed.value)}"
    else:
        q = f"title:{_quote(parsed.value)}"
    q += year_filter(year_from, year_to)
    if len(q) > MAX_QUERY_LEN:
        raise PNError(ErrorCode.INPUT_ERROR, "query exceeds ADS 1000-character limit")
    return q


def year_filter(year_from: int | None, year_to: int | None) -> str:
    if year_from is None and year_to is None:
        return ""
    lo = str(year_from) if year_from is not None else "*"
    hi = str(year_to) if year_to is not None else "*"
    if year_from is not None and year_to is not None and year_from > year_to:
        raise PNError(ErrorCode.INPUT_ERROR, "year_from must be <= year_to")
    return f" year:[{lo} TO {hi}]"


def references_query(bibcode: str, year_from: int | None = None, year_to: int | None = None) -> str:
    """Papers cited BY ``bibcode`` (its reference list)."""
    return f"references(bibcode:{_quote(bibcode)})" + year_filter(year_from, year_to)


def citations_query(bibcode: str, year_from: int | None = None, year_to: int | None = None) -> str:
    """Papers that CITE ``bibcode``."""
    return f"citations(bibcode:{_quote(bibcode)})" + year_filter(year_from, year_to)
