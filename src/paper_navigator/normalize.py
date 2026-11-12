"""Identifier and text normalization used for de-duplication (spec §4.4)."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_DOI_PREFIXES = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|urn:doi:)", flags=re.IGNORECASE
)
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
# ADS bibcodes are exactly 19 characters: YYYYJJJJJVVVVMPPPPA
BIBCODE_RE = re.compile(r"^\d{4}[A-Za-z&.][\w&.]{13}[A-Za-z.]$")
ARXIV_NEW_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
ARXIV_OLD_RE = re.compile(r"^([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?$", flags=re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    """Return a canonical lower-case DOI, or ``None`` if the value is not a DOI."""
    if not value:
        return None
    doi = _DOI_PREFIXES.sub("", value.strip()).strip().rstrip(".")
    doi = doi.lower()
    return doi if DOI_RE.match(doi) else None


def is_valid_doi(value: str | None) -> bool:
    return normalize_doi(value) is not None


def normalize_bibcode(value: str | None) -> str | None:
    """ADS bibcodes are case sensitive; only trim whitespace and validate length/shape."""
    if not value:
        return None
    bib = value.strip()
    return bib if BIBCODE_RE.match(bib) else None


def normalize_arxiv(value: str | None) -> str | None:
    """Canonical arXiv id without version, e.g. ``2101.01234`` or ``astro-ph/0601001``."""
    if not value:
        return None
    v = value.strip()
    v = re.sub(r"^(?:arxiv:|https?://arxiv\.org/abs/)", "", v, flags=re.IGNORECASE)
    m = ARXIV_NEW_RE.match(v)
    if m:
        return m.group(1)
    m = ARXIV_OLD_RE.match(v)
    if m:
        return m.group(1).lower()
    return None


_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?\s*")
_NON_WORD = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize_title(value: str | None) -> str:
    """Lower-case, accent-stripped, punctuation-free title used only for *candidate* matching."""
    if not value:
        return ""
    text = _LATEX_CMD.sub(" ", value)
    text = text.replace("{", "").replace("}", "").replace("$", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _NON_WORD.sub(" ", text.casefold())
    return _WS.sub(" ", text).strip()


def title_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def split_author(name: str) -> tuple[str, str | None]:
    """Split ``"Last, First M."`` into ``(last, first)``; keep unknown formats intact."""
    name = name.strip()
    if "," in name:
        last, _, first = name.partition(",")
        return last.strip(), (first.strip() or None)
    return name, None


def family_key(name: str | None) -> str:
    if not name:
        return ""
    last, _ = split_author(name)
    return normalize_title(last)
