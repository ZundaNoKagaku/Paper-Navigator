"""Validate a Better BibTeX ``.bib`` export (UC-05, spec §6.2).

The file is never modified. Checks:
* syntax: brace balance per entry, entries the parser could not read
* DUPLICATE_KEY (error), DUPLICATE_DOI (warning), INVALID_DOI (error)
* MISSING_REQUIRED (error) / MISSING_RECOMMENDED (warning) per entry type
* BAD_KEY_CHARS (error), SAME_AUTHOR_YEAR (info, e.g. peter2014a / peter2014b)
* UNESCAPED_SPECIAL (warning): bare ``&``, ``%``, ``#`` that break LaTeX
* NON_ASCII (info): Unicode is preserved; BBT can be set to export LaTeX commands
* snapshot comparison: KEY_CHANGED (warning) when a DOI's key differs from the last
  accepted snapshot, KEY_REMOVED (warning).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

from ..normalize import family_key, normalize_doi

REQUIRED: dict[str, list[tuple[str, ...]]] = {
    "article": [("author",), ("title",), ("journal",), ("year",)],
    "book": [("author", "editor"), ("title",), ("publisher",), ("year",)],
    "inproceedings": [("author",), ("title",), ("booktitle",), ("year",)],
    "incollection": [("author",), ("title",), ("booktitle",), ("year",)],
    "phdthesis": [("author",), ("title",), ("school",), ("year",)],
    "mastersthesis": [("author",), ("title",), ("school",), ("year",)],
    "techreport": [("author",), ("title",), ("institution",), ("year",)],
    "misc": [("author", "title"), ("year",)],
    "software": [("author", "title"), ("year",)],
    "dataset": [("author", "title"), ("year",)],
}
RECOMMENDED: dict[str, list[str]] = {
    "article": ["volume", "pages", "doi"],
    "inproceedings": ["pages"],
}
_ENTRY_START = re.compile(r"@\s*([A-Za-z]+)\s*([{(])\s*([^,{}()\n]*?)\s*,", re.M)
_BAD_KEY = re.compile(r"[\s,{}#%~\\\"'()=]")
_SKIP_TYPES = {"comment", "string", "preamble"}


@dataclass
class Issue:
    severity: str  # error | warning | info
    code: str
    key: str | None
    message: str
    line: int | None = None


@dataclass
class BibReport:
    path: str
    entries: int = 0
    keys: list[str] = field(default_factory=list)
    doi_to_key: dict[str, str] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def count(self, severity: str) -> int:
        return sum(1 for i in self.issues if i.severity == severity)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _scan_entries(text: str) -> list[tuple[str, str, int, str, int, int]]:
    """Return (type, key, line, body, start, end) per entry, using brace matching."""
    out = []
    for m in _ENTRY_START.finditer(text):
        etype, opener, key = m.group(1).lower(), m.group(2), m.group(3)
        if etype in _SKIP_TYPES:
            continue
        # Track brace depth; the entry ends at the closer when no inner brace is open.
        braces, i, closed = 0, m.end(), False
        nxt = _ENTRY_START.search(text, m.end())
        limit = nxt.start() if nxt else len(text)
        while i < limit:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "{":
                braces += 1
            elif ch == "}":
                if braces == 0 and opener == "{":
                    closed = True
                    break
                braces -= 1
            elif ch == ")" and opener == "(" and braces == 0:
                closed = True
                break
            i += 1
        line = text.count("\n", 0, m.start()) + 1
        body = text[m.end() : i] if closed and braces == 0 else "\0UNBALANCED"
        out.append((etype, key, line, body, m.start(), i))
    return out


def _strip_braces(v: str) -> str:
    return re.sub(r"[{}]", "", v).strip()


def _unescaped(value: str, ch: str) -> bool:
    return re.search(r"(?<!\\)" + re.escape(ch), value) is not None


def check_bib(path: Path) -> BibReport:
    report = BibReport(path=str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.issues.append(Issue("error", "ENCODING", None, "file is not valid UTF-8"))
        return report
    except OSError as exc:
        report.issues.append(Issue("error", "IO_ERROR", None, str(exc)))
        return report

    scanned = _scan_entries(text)
    # BibTeX treats every '@' outside an entry as the start of an entry (even in comments).
    for m in re.finditer(r"@", text):
        if any(st <= m.start() <= en for *_, st, en in scanned):
            continue
        if re.match(r"@\s*(comment|string|preamble)\b", text[m.start() :], re.I):
            continue
        line = text.count("\n", 0, m.start()) + 1
        report.issues.append(
            Issue(
                "error",
                "STRAY_AT",
                None,
                "'@' outside an entry; BibTeX will read it as an entry "
                "start (remove it, also from % comments)",
                line,
            )
        )
    lines: dict[str, int] = {}
    seen: dict[str, int] = {}
    for etype, key, line, body, _s, _e in scanned:
        lines.setdefault(key, line)
        if not key:
            report.issues.append(Issue("error", "MISSING_KEY", None, f"@{etype} without key", line))
        elif _BAD_KEY.search(key):
            report.issues.append(
                Issue(
                    "error",
                    "BAD_KEY_CHARS",
                    key,
                    "citation key contains characters BibTeX cannot use",
                    line,
                )
            )
        if key in seen:
            report.issues.append(
                Issue("error", "DUPLICATE_KEY", key, f"key also defined at line {seen[key]}", line)
            )
        else:
            seen[key] = line
        if body == "\0UNBALANCED":
            report.issues.append(
                Issue("error", "UNBALANCED_BRACES", key, "entry braces are not balanced", line)
            )

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    try:
        db = bibtexparser.loads(text, parser=parser)
    except Exception as exc:  # bibtexparser raises assorted pyparsing errors
        report.issues.append(Issue("error", "PARSE_ERROR", None, f"parser failed: {exc}"))
        return report
    entries = db.entries
    report.entries = len(scanned)
    if len(entries) < len(scanned):
        parsed_keys = {e.get("ID") for e in entries}
        for _etype, key, line, *_ in scanned:
            if key not in parsed_keys:
                report.issues.append(
                    Issue("error", "UNPARSEABLE_ENTRY", key, "entry could not be parsed", line)
                )

    doi_keys: dict[str, list[str]] = defaultdict(list)
    author_year: dict[tuple[str, str], list[str]] = defaultdict(list)
    for e in entries:
        key, etype = e.get("ID", ""), e.get("ENTRYTYPE", "").lower()
        report.keys.append(key)
        eline: int | None = lines.get(key)
        for alts in REQUIRED.get(etype, [("title",), ("year",)]):
            if not any(_strip_braces(e.get(f, "")) for f in alts):
                report.issues.append(
                    Issue(
                        "error",
                        "MISSING_REQUIRED",
                        key,
                        f"@{etype} requires {' or '.join(alts)}",
                        eline,
                    )
                )
        for f in RECOMMENDED.get(etype, []):
            if not _strip_braces(e.get(f, "")):
                report.issues.append(
                    Issue("warning", "MISSING_RECOMMENDED", key, f"@{etype} should have {f}", eline)
                )
        if e.get("doi"):
            nd = normalize_doi(_strip_braces(e["doi"]))
            if nd is None:
                report.issues.append(
                    Issue(
                        "error", "INVALID_DOI", key, f"DOI {e['doi']!r} is not a valid DOI", eline
                    )
                )
            else:
                doi_keys[nd].append(key)
        year = _strip_braces(e.get("year", ""))
        if year and not re.fullmatch(r"\d{4}", year):
            report.issues.append(
                Issue("warning", "YEAR_FORMAT", key, f"year {year!r} is not a 4-digit year", eline)
            )
        authors = e.get("author", "")
        if authors and year:
            first = re.split(r"\s+and\s+", authors)[0]
            author_year[(family_key(_strip_braces(first)), year)].append(key)
        for fname in ("title", "journal", "booktitle", "publisher"):
            v = e.get(fname, "")
            for ch in ("&", "%", "#"):
                if v and _unescaped(v, ch):
                    report.issues.append(
                        Issue(
                            "warning",
                            "UNESCAPED_SPECIAL",
                            key,
                            f"{fname} contains unescaped {ch!r}",
                            eline,
                        )
                    )
        if any(ord(c) > 127 for v in e.values() for c in str(v)):
            report.issues.append(
                Issue(
                    "info",
                    "NON_ASCII",
                    key,
                    "contains non-ASCII characters (preserved as-is)",
                    eline,
                )
            )
    for doi, keys in doi_keys.items():
        report.doi_to_key[doi] = keys[0]
        if len(keys) > 1:
            report.issues.append(
                Issue(
                    "warning",
                    "DUPLICATE_DOI",
                    keys[1],
                    f"DOI {doi} shared by keys {', '.join(keys)}",
                )
            )
    for (fam, _year), keys in author_year.items():
        if len(set(keys)) > 1 and fam:
            report.issues.append(
                Issue(
                    "info",
                    "SAME_AUTHOR_YEAR",
                    keys[0],
                    f"same first author and year: {', '.join(keys)} "
                    "(check the a/b suffixes are intended)",
                )
            )
    return report


def compare_with_snapshot(report: BibReport, snapshot: Path) -> list[Issue]:
    """Detect citation keys that changed or disappeared since the accepted snapshot."""
    if not snapshot.is_file():
        return []
    old = json.loads(snapshot.read_text(encoding="utf-8"))
    issues = []
    for doi, old_key in old.get("doi_to_key", {}).items():
        new_key = report.doi_to_key.get(doi)
        if new_key and new_key != old_key:
            issues.append(
                Issue(
                    "warning",
                    "KEY_CHANGED",
                    new_key,
                    f"DOI {doi}: key changed {old_key} -> {new_key}; documents "
                    f"citing {old_key} will break",
                )
            )
    for k in sorted(set(old.get("keys", [])) - set(report.keys)):
        issues.append(Issue("warning", "KEY_REMOVED", k, "key present in snapshot is gone"))
    return issues


def save_snapshot(report: BibReport, snapshot: Path) -> None:
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(
        json.dumps(
            {"keys": report.keys, "doi_to_key": report.doi_to_key}, indent=1, sort_keys=True
        ),
        encoding="utf-8",
    )
