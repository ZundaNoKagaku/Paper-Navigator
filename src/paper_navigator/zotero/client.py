"""Zotero desktop Local API client (UC-04).

Verified against https://www.zotero.org/support/dev/web_api/v3/local_api (2026-11-12):
* Base ``http://localhost:23119/api/``; user id ``0`` = local user; only API v3.
* Reads need no auth but require Settings → Advanced → "Allow other applications on this
  computer to communicate with Zotero"; otherwise ``403``.
* Writes exist only in **Zotero 10+**: they need a local API key obtained via
  ``POST /api/local/authorize`` (user approves a dialog) and the ``Zotero-Server-ID``
  header (missing -> 428, mismatch -> 412; missing/invalid key -> 401; denied -> 403).
* No pagination by default on the local API (``limit``/``start`` still work).

The client never reports a write as successful unless Zotero answered with a created key.
Item contents are not logged.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import ErrorCode, PNError
from ..normalize import normalize_doi, split_author
from ..records import PaperRecord

log = logging.getLogger(__name__)

ZOTERO_WRITE_MIN_MAJOR = 10


@dataclass
class ZoteroStatus:
    reachable: bool
    api_enabled: bool
    zotero_version: str | None = None
    api_version: str | None = None
    server_id: str | None = None
    write_supported: bool = False
    write_key_configured: bool = False
    message: str = ""

    @property
    def state(self) -> str:
        if not self.reachable:
            return "unavailable"
        if not self.api_enabled:
            return "local_api_disabled"
        if not self.write_supported:
            return "read_only"
        return "read_write" if self.write_key_configured else "write_needs_authorization"


@dataclass
class ZoteroItem:
    key: str
    item_type: str
    title: str | None
    creators: list[str]
    year: int | None
    doi: str | None
    journal: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    citation_key: str | None
    ads_bibcode: str | None
    collections: list[str] = field(default_factory=list)


@dataclass
class WriteOutcome:
    status: str  # created | exists | needs_authorization | unsupported | failed
    zotero_key: str | None = None
    message: str = ""


def _major(version: str | None) -> int | None:
    if not version:
        return None
    m = re.match(r"(\d+)", version)
    return int(m.group(1)) if m else None


_ADS_IN_EXTRA = re.compile(r"(?im)^\s*(?:ADS Bibcode|bibcode)\s*:\s*(\S{19})\s*$")
_ADS_IN_URL = re.compile(r"adsabs\.harvard\.edu/abs/([^/\s?#]{19})")
_CITEKEY_IN_EXTRA = re.compile(r"(?im)^\s*Citation Key\s*:\s*(\S+)\s*$")


def parse_item(raw: dict[str, Any]) -> ZoteroItem:
    data = raw.get("data", raw)
    creators = []
    for c in data.get("creators", []) or []:
        if c.get("name"):
            creators.append(c["name"])
        else:
            creators.append(", ".join(x for x in (c.get("lastName"), c.get("firstName")) if x))
    year = None
    m = re.search(r"\b(\d{4})\b", data.get("date") or "")
    if m:
        year = int(m.group(1))
    extra = data.get("extra") or ""
    ck = data.get("citationKey") or None
    if not ck:
        mm = _CITEKEY_IN_EXTRA.search(extra)
        ck = mm.group(1) if mm else None
    bib = None
    mb = _ADS_IN_EXTRA.search(extra) or _ADS_IN_URL.search(data.get("url") or "")
    if mb:
        bib = mb.group(1)
    return ZoteroItem(
        key=data.get("key") or raw.get("key", ""),
        item_type=data.get("itemType", ""),
        title=data.get("title") or None,
        creators=creators,
        year=year,
        doi=normalize_doi(data.get("DOI")),
        journal=data.get("publicationTitle") or None,
        volume=data.get("volume") or None,
        issue=data.get("issue") or None,
        pages=data.get("pages") or None,
        citation_key=ck,
        ads_bibcode=bib,
        collections=list(data.get("collections") or []),
    )


def record_to_zotero_item(rec: PaperRecord, collection_key: str | None = None) -> dict[str, Any]:
    creators = []
    for name in rec.authors:
        last, first = split_author(name)
        if first:
            creators.append({"creatorType": "author", "lastName": last, "firstName": first})
        else:
            creators.append({"creatorType": "author", "name": last})
    item: dict[str, Any] = {
        "itemType": "journalArticle",
        "title": rec.title or "",
        "creators": creators,
        "date": str(rec.year) if rec.year else "",
        "publicationTitle": rec.pub or "",
        "volume": rec.volume or "",
        "issue": rec.issue or "",
        "pages": rec.page or "",
        "DOI": rec.doi or "",
        "abstractNote": rec.abstract or "",
        "libraryCatalog": "NASA ADS",
        "url": f"https://ui.adsabs.harvard.edu/abs/{rec.bibcode}/abstract" if rec.bibcode else "",
        "extra": f"ADS Bibcode: {rec.bibcode}" if rec.bibcode else "",
    }
    if collection_key:
        item["collections"] = [collection_key]
    return item


class ZoteroLocalClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:23119",
        timeout: float = 5.0,
        api_key: str = "",
        transport: httpx.BaseTransport | None = None,
    ):
        self.base = base_url.rstrip("/")
        self._key = api_key
        self._server_id: str | None = None
        self._client = httpx.Client(
            base_url=self.base,
            timeout=timeout,
            transport=transport,
            headers={"Zotero-API-Version": "3"},
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        try:
            resp = self._client.request(method, path, **kw)
        except httpx.TimeoutException as exc:
            raise PNError(ErrorCode.ZOTERO_UNAVAILABLE, "Zotero did not respond (timeout)") from exc
        except httpx.TransportError as exc:
            raise PNError(
                ErrorCode.ZOTERO_UNAVAILABLE, f"cannot connect to {self.base} (is Zotero running?)"
            ) from exc
        sid = resp.headers.get("Zotero-Server-ID")
        if sid:
            self._server_id = sid
        return resp

    def status(self) -> ZoteroStatus:
        try:
            resp = self._request("GET", "/api/")
        except PNError as exc:
            return ZoteroStatus(reachable=False, api_enabled=False, message=exc.detail)
        version = resp.headers.get("X-Zotero-Version")
        st = ZoteroStatus(
            reachable=True,
            api_enabled=resp.status_code == 200,
            zotero_version=version,
            api_version=resp.headers.get("Zotero-API-Version"),
            server_id=resp.headers.get("Zotero-Server-ID"),
            write_key_configured=bool(self._key),
        )
        major = _major(version)
        st.write_supported = bool(
            st.api_enabled
            and st.server_id
            and major is not None
            and major >= ZOTERO_WRITE_MIN_MAJOR
        )
        if resp.status_code == 403:
            st.message = (
                "Local API is disabled: enable Settings → Advanced → 'Allow other "
                "applications on this computer to communicate with Zotero'."
            )
        elif resp.status_code != 200:
            st.message = f"unexpected HTTP {resp.status_code} from Zotero"
        elif not st.write_supported:
            st.message = (
                f"Zotero {version or '(version unknown)'}: reads available; local API "
                f"writes require Zotero {ZOTERO_WRITE_MIN_MAJOR}+."
            )
        elif not st.write_key_configured:
            st.message = "Writes supported but not authorized yet (run `pn zotero-authorize`)."
        else:
            st.message = "Read/write available."
        return st

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._request("GET", path, params=params)
        if resp.status_code == 403:
            raise PNError(ErrorCode.ZOTERO_UNAVAILABLE, "Zotero local API is disabled (403)")
        if resp.status_code == 404:
            raise PNError(ErrorCode.NOT_FOUND, f"Zotero: {path} not found")
        if resp.status_code != 200:
            raise PNError(ErrorCode.INVALID_RESPONSE, f"Zotero HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise PNError(ErrorCode.INVALID_RESPONSE, "Zotero returned non-JSON") from exc

    def collections(self) -> list[dict[str, Any]]:
        data = self._get_json("/api/users/0/collections")
        return [
            {
                "key": c.get("key") or c.get("data", {}).get("key"),
                "name": c.get("data", {}).get("name"),
                "parent": c.get("data", {}).get("parentCollection") or None,
                "items": c.get("meta", {}).get("numItems"),
            }
            for c in data
        ]

    def collection_items(self, collection_key: str) -> list[ZoteroItem]:
        if not re.fullmatch(r"[A-Z0-9]{8}", collection_key or ""):
            raise PNError(ErrorCode.INPUT_ERROR, "invalid Zotero collection key")
        data = self._get_json(
            f"/api/users/0/collections/{collection_key}/items/top", {"format": "json"}
        )
        return [
            parse_item(d)
            for d in data
            if d.get("data", {}).get("itemType") not in ("attachment", "note", "annotation")
        ]

    def find_by_doi(self, doi: str) -> list[ZoteroItem]:
        nd = normalize_doi(doi)
        if not nd:
            return []
        data = self._get_json(
            "/api/users/0/items", {"q": nd, "qmode": "everything", "format": "json"}
        )
        return [it for it in (parse_item(d) for d in data) if it.doi == nd]

    def request_authorization(
        self, app_name: str = "Paper Navigator", timeout: float = 120.0
    ) -> str:
        """Ask the user (Zotero dialog) for a write key. Returns the key; never logs it."""
        st = self.status()
        if not st.write_supported:
            raise PNError(ErrorCode.ZOTERO_AUTH_REQUIRED, st.message)
        resp = self._request(
            "POST",
            "/api/local/authorize",
            json={"appName": app_name},
            headers={"Zotero-Server-ID": st.server_id or ""},
            timeout=timeout,
        )
        if resp.status_code == 200:
            key = resp.json().get("key")
            if key:
                self._key = key
                return str(key)
        if resp.status_code == 403:
            raise PNError(ErrorCode.ZOTERO_AUTH_REQUIRED, "authorization denied in Zotero")
        if resp.status_code == 429:
            raise PNError(
                ErrorCode.RATE_LIMITED,
                "too many authorization requests",
                retry_after=float(resp.headers.get("Retry-After", "60")),
            )
        raise PNError(ErrorCode.INVALID_RESPONSE, f"authorize: HTTP {resp.status_code}")

    def create_item(self, rec: PaperRecord, collection_key: str | None = None) -> WriteOutcome:
        st = self.status()
        if not st.reachable or not st.api_enabled:
            return WriteOutcome("failed", message=st.message or "Zotero unavailable")
        if rec.doi:
            existing = self.find_by_doi(rec.doi)
            if existing:
                return WriteOutcome(
                    "exists", existing[0].key, "an item with this DOI already exists; not added"
                )
        if not st.write_supported:
            return WriteOutcome("unsupported", message=st.message)
        if not self._key:
            return WriteOutcome("needs_authorization", message=st.message)
        headers = {
            "Zotero-API-Key": self._key,
            "Zotero-Server-ID": st.server_id or "",
            "Zotero-Write-Token": uuid.uuid4().hex,
            "Content-Type": "application/json",
        }
        resp = self._request(
            "POST",
            "/api/users/0/items",
            json=[record_to_zotero_item(rec, collection_key)],
            headers=headers,
        )
        if resp.status_code == 401:
            self._key = ""
            return WriteOutcome(
                "needs_authorization",
                message="key rejected or single-use key consumed; re-authorize",
            )
        if resp.status_code in (412, 428):
            return WriteOutcome(
                "failed",
                message=f"Zotero-Server-ID problem (HTTP "
                f"{resp.status_code}); retry after refreshing status",
            )
        if resp.status_code != 200:
            return WriteOutcome("failed", message=f"Zotero HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            return WriteOutcome("failed", message="non-JSON write response")
        ok = (body.get("successful") or {}).get("0") or {}
        key = ok.get("key") or (body.get("success") or {}).get("0")
        if key:
            return WriteOutcome("created", key, "item created")
        failed = (body.get("failed") or {}).get("0") or {}
        return WriteOutcome(
            "failed",
            message=f"Zotero rejected item: "
            f"{failed.get('code', '?')} {failed.get('message', '')}".strip(),
        )
