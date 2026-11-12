r"""Check that every ``\cite*`` key in LaTeX sources exists in the ``.bib`` (spec P0-E).

Handles natbib/AASTeX forms: ``\citep``, ``\citet``, ``\citealt``, ``\citealp``,
``\citeauthor``, ``\citeyear``, ``\citeyearpar``, starred variants, up to two optional
arguments, comma-separated key lists, and ``\nocite``. Commented text (unescaped ``%``)
is ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_CITE = re.compile(
    r"\\(?:no)?cite(?:p|t|alt|alp|author|year|yearpar|num|text)?\*?"
    r"\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}"
)
_COMMENT = re.compile(r"(?<!\\)%.*$", re.M)


@dataclass
class CiteReport:
    cited: dict[str, list[str]] = field(default_factory=dict)  # key -> ["file:line", ...]
    missing: list[str] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)
    nocite_all: bool = False

    @property
    def ok(self) -> bool:
        return not self.missing


def extract_citations(tex: str, name: str = "<tex>") -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for lineno, line in enumerate(_COMMENT.sub("", tex).splitlines(), start=1):
        for m in _CITE.finditer(line):
            for key in m.group(1).split(","):
                key = key.strip()
                if key:
                    out.setdefault(key, []).append(f"{name}:{lineno}")
    return out


def check_citations(tex_files: list[Path], bib_keys: list[str]) -> CiteReport:
    rep = CiteReport()
    for p in tex_files:
        for k, locs in extract_citations(p.read_text(encoding="utf-8"), p.name).items():
            rep.cited.setdefault(k, []).extend(locs)
    rep.nocite_all = "*" in rep.cited
    rep.cited.pop("*", None)
    keys = set(bib_keys)
    rep.missing = sorted(k for k in rep.cited if k not in keys)
    rep.unused = [] if rep.nocite_all else sorted(keys - set(rep.cited))
    return rep
