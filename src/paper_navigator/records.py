"""Source-independent paper record produced by adapters and consumed by the repository."""

from __future__ import annotations

from dataclasses import dataclass, field

# Fields whose absence makes a record "incomplete" for bibliographic use.
CORE_FIELDS = ("title", "authors", "year", "pub", "volume", "page", "doi", "bibcode")


@dataclass
class PaperRecord:
    source: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    pub: str | None = None
    bibstem: str | None = None
    volume: str | None = None
    issue: str | None = None
    page: str | None = None
    doctype: str | None = None
    doi: str | None = None
    bibcode: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    alternate_bibcodes: list[str] = field(default_factory=list)
    extra_dois: list[str] = field(default_factory=list)
    source_ids: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def missing_fields(self) -> list[str]:
        missing = []
        for name in CORE_FIELDS:
            value = getattr(self, name)
            if value is None or value == "" or value == []:
                missing.append(name)
        if self.abstract is None:
            missing.append("abstract")
        return missing

    def validation_status(self) -> str:
        essential = {"title", "authors", "year"}
        return "incomplete" if essential & set(self.missing_fields()) else "complete"
