"""Shared fixtures. All paper data here is SYNTHETIC (fake bibcodes ``....TEST....``,
DOI prefix 10.5555 = Crossref test prefix) and must never be presented as real."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest

from paper_navigator.ads.client import ADSClient
from paper_navigator.db import Database

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "test-token-abcdef123456"


def bib(n: int, year: int = 2001) -> str:
    code = f"{year}TEST{n:.>5}{n:.>5}A"
    assert len(code) == 19, code
    return code


def doc(n: int, year: int = 2001, **over: Any) -> dict[str, Any]:
    d = {
        "bibcode": bib(n, year),
        "title": [f"Synthetic paper number {n} on coronal loops"],
        "author": [f"Author{n}, A.", "Second, B."],
        "year": str(year),
        "pub": "Journal of Synthetic Tests",
        "bibstem": ["JST"],
        "volume": str(n),
        "page": [str(n)],
        "doi": [f"10.5555/test.{n}"],
        "identifier": [bib(n, year), f"10.5555/test.{n}"],
        "abstract": f"Synthetic abstract {n}.",
        "doctype": "article",
    }
    d.update(over)
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class FakeADS:
    """In-memory ADS: ``refs[b]`` = list of docs that paper ``b`` cites."""

    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    refs: dict[str, list[str]] = field(default_factory=dict)
    calls: list[dict[str, str]] = field(default_factory=list)
    fail: Callable[[dict[str, str], int], httpx.Response | None] | None = None
    seen_auth: list[str] = field(default_factory=list)

    def add(self, *docs: dict[str, Any]) -> None:
        for d in docs:
            self.records[d["bibcode"]] = d

    def cite(self, citing: str, *cited: str) -> None:
        self.refs.setdefault(citing, []).extend(cited)

    def _match(self, q: str) -> list[dict[str, Any]]:
        q = re.sub(r" year:\[.*\]$", "", q)
        m = re.fullmatch(r'(references|citations)\(bibcode:"(.+)"\)', q)
        if m:
            op, b = m.groups()
            if op == "references":
                keys = self.refs.get(b, [])
            else:
                keys = [c for c, lst in self.refs.items() if b in lst]
            return [self.records[k] for k in sorted(keys) if k in self.records]
        m = re.fullmatch(r'(doi|identifier|title):"(.+)"', q)
        if m:
            fld, val = m.groups()
            out = []
            for d in self.records.values():
                hit = {
                    "doi": val in d.get("doi", []),
                    "identifier": val in d.get("identifier", []) or val == d["bibcode"],
                    "title": val.lower() in d["title"][0].lower(),
                }[fld]
                if hit:
                    out.append(d)
            return out
        return []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen_auth.append(request.headers.get("Authorization", ""))
        params = dict(request.url.params)
        self.calls.append(params)
        if self.fail:
            r = self.fail(params, len(self.calls))
            if r is not None:
                return r
        docs = self._match(params["q"])
        start, rows = int(params.get("start", 0)), int(params.get("rows", 10))
        body = {
            "responseHeader": {"status": 0, "params": params},
            "response": {"numFound": len(docs), "start": start, "docs": docs[start : start + rows]},
        }
        return httpx.Response(
            200,
            json=body,
            headers={
                "X-RateLimit-Limit": "5000",
                "X-RateLimit-Remaining": "4999",
                "X-RateLimit-Reset": "1700000000",
            },
        )

    def client(self, **kw: Any) -> ADSClient:
        kw.setdefault("sleep", lambda _s: None)
        return ADSClient(TOKEN, transport=httpx.MockTransport(self.handler), **kw)


@pytest.fixture
def fake_ads() -> FakeADS:
    return FakeADS()


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.sqlite3")


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / "ads" / name).read_text(encoding="utf-8"))
