"""Zotero Local API behaviour, simulated with httpx.MockTransport (no real Zotero)."""

import json

import httpx
import pytest
from sqlalchemy import select

from paper_navigator.ads.mapping import ads_doc_to_record
from paper_navigator.errors import ErrorCode, PNError
from paper_navigator.models import Reconciliation, ZoteroLink
from paper_navigator.repository import upsert_paper
from paper_navigator.zotero.client import ZoteroLocalClient, parse_item, record_to_zotero_item
from paper_navigator.zotero.sync import sync_collection

from .conftest import FIXTURES, doc

ITEMS = json.loads((FIXTURES / "zotero" / "collection_items.json").read_text())


class FakeZotero:
    def __init__(self, version="10.0", enabled=True, server_id="SRV1", write_status=200):
        self.version, self.enabled, self.server_id = version, enabled, server_id
        self.write_status = write_status
        self.posts: list[httpx.Request] = []

    def handler(self, req: httpx.Request) -> httpx.Response:
        h = {"X-Zotero-Version": self.version, "Zotero-API-Version": "3"}
        if self.server_id:
            h["Zotero-Server-ID"] = self.server_id
        if not self.enabled:
            return httpx.Response(403, text="Request not allowed", headers=h)
        path = req.url.path
        if req.method == "GET" and path == "/api/":
            return httpx.Response(200, text="Nothing here", headers=h)
        if path == "/api/users/0/collections":
            return httpx.Response(
                200,
                json=[
                    {
                        "key": "COLL0001",
                        "data": {"key": "COLL0001", "name": "Thesis", "parentCollection": False},
                        "meta": {"numItems": 3},
                    }
                ],
                headers=h,
            )
        if path == "/api/users/0/collections/COLL0001/items/top":
            return httpx.Response(200, json=ITEMS, headers=h)
        if req.method == "GET" and path == "/api/users/0/items":
            q = req.url.params.get("q", "")
            hits = [i for i in ITEMS if i["data"].get("DOI", "").lower() == q]
            return httpx.Response(200, json=hits, headers=h)
        if req.method == "POST" and path == "/api/users/0/items":
            self.posts.append(req)
            if not req.headers.get("Zotero-API-Key"):
                return httpx.Response(401, headers=h)
            if self.write_status != 200:
                return httpx.Response(self.write_status, headers=h)
            return httpx.Response(
                200, json={"successful": {"0": {"key": "NEWK0001"}}, "failed": {}}, headers=h
            )
        if req.method == "POST" and path == "/api/local/authorize":
            if req.headers.get("Zotero-Server-ID") != self.server_id:
                return httpx.Response(428, headers=h)
            return httpx.Response(200, json={"key": "local-key-xyz", "remember": True}, headers=h)
        return httpx.Response(404, headers=h)

    def client(self, key="") -> ZoteroLocalClient:
        return ZoteroLocalClient(api_key=key, transport=httpx.MockTransport(self.handler))


def _down(req):
    raise httpx.ConnectError("refused", request=req)


def test_status_unavailable_when_zotero_not_running():
    st = ZoteroLocalClient(transport=httpx.MockTransport(_down)).status()
    assert st.state == "unavailable" and not st.reachable
    with pytest.raises(PNError) as e:
        ZoteroLocalClient(transport=httpx.MockTransport(_down)).collections()
    assert e.value.code == ErrorCode.ZOTERO_UNAVAILABLE


def test_status_local_api_disabled():
    st = FakeZotero(enabled=False).client().status()
    assert st.state == "local_api_disabled" and "Allow other applications" in st.message


@pytest.mark.parametrize(
    "version,sid,key,state",
    [
        ("7.0.15", None, "", "read_only"),
        ("8.0.1", None, "", "read_only"),
        ("10.0", "SRV1", "", "write_needs_authorization"),
        ("10.0", "SRV1", "k", "read_write"),
    ],
)
def test_status_versions(version, sid, key, state):
    st = FakeZotero(version=version, server_id=sid).client(key).status()
    assert st.state == state


def test_read_collections_and_items_skip_notes():
    c = FakeZotero().client()
    assert c.collections()[0]["name"] == "Thesis"
    items = c.collection_items("COLL0001")
    assert [i.key for i in items] == ["AAAA1111", "BBBB2222", "CCCC3333"]
    assert items[0].doi == "10.5555/test.1" and items[0].citation_key == "author12001"
    assert items[1].citation_key == "collab2003"  # from Extra
    assert items[1].ads_bibcode == "2003TEST....3....3A" and items[1].year == 2003
    with pytest.raises(PNError):
        c.collection_items("../../etc")


def test_write_refused_on_old_zotero_without_posting():
    z = FakeZotero(version="7.0.15", server_id=None)
    out = z.client("k").create_item(ads_doc_to_record(doc(50)))
    assert out.status == "unsupported" and not z.posts


def test_write_needs_authorization_without_key():
    z = FakeZotero()
    out = z.client().create_item(ads_doc_to_record(doc(50)))
    assert out.status == "needs_authorization" and not z.posts


def test_write_duplicate_doi_not_added():
    z = FakeZotero()
    out = z.client("k").create_item(ads_doc_to_record(doc(1)))  # DOI 10.5555/test.1 exists
    assert out.status == "exists" and out.zotero_key == "AAAA1111" and not z.posts


def test_write_success_and_headers():
    z = FakeZotero()
    out = z.client("k").create_item(ads_doc_to_record(doc(50)), collection_key="COLL0001")
    assert out.status == "created" and out.zotero_key == "NEWK0001"
    req = z.posts[0]
    assert req.headers["Zotero-API-Key"] == "k" and req.headers["Zotero-Server-ID"] == "SRV1"
    assert req.headers["Zotero-Write-Token"]
    body = json.loads(req.content)[0]
    assert body["collections"] == ["COLL0001"] and body["DOI"] == "10.5555/test.50"


@pytest.mark.parametrize(
    "code,status", [(401, "needs_authorization"), (412, "failed"), (500, "failed")]
)
def test_write_failures_never_report_success(code, status):
    z = FakeZotero(write_status=code)
    out = z.client("k").create_item(ads_doc_to_record(doc(50)))
    assert out.status == status and out.zotero_key is None


def test_authorize_flow():
    assert FakeZotero().client().request_authorization() == "local-key-xyz"
    with pytest.raises(PNError) as e:
        FakeZotero(version="7.0").client().request_authorization()
    assert e.value.code == ErrorCode.ZOTERO_AUTH_REQUIRED


def test_record_to_item_mapping():
    item = record_to_zotero_item(ads_doc_to_record(doc(5, author=["Solo, H.", "Big Team"])))
    assert item["creators"][0] == {"creatorType": "author", "lastName": "Solo", "firstName": "H."}
    assert item["creators"][1] == {"creatorType": "author", "name": "Big Team"}
    assert "ADS Bibcode:" in item["extra"]


def test_sync_links_and_reconciles(db):
    with db.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1)))
        upsert_paper(s, ads_doc_to_record(doc(3, year=2003)))
    rep = sync_collection(db, FakeZotero().client(), "COLL0001")
    assert rep.items == 3 and rep.linked == 2 and rep.not_in_db == ["CCCC3333"]
    fields = {(m["zotero_key"], m["field"]): m["decision"] for m in rep.mismatches}
    assert fields[("AAAA1111", "journal")] == "prefer_zotero"  # abbreviation only
    assert ("AAAA1111", "pages") not in fields  # first page equal
    assert fields[("BBBB2222", "title")] == "manual_review"
    assert fields[("BBBB2222", "volume")] == "manual_review"
    with db.session() as s:
        links = s.scalars(select(ZoteroLink)).all()
        assert {lk.matched_by for lk in links} == {"doi", "ads_bibcode"}
        assert s.scalars(select(Reconciliation)).all()
    sync_collection(db, FakeZotero().client(), "COLL0001")  # idempotent
    with db.session() as s:
        assert len(s.scalars(select(ZoteroLink)).all()) == 2


def test_parse_item_handles_missing_fields():
    it = parse_item({"key": "X", "data": {"itemType": "book"}})
    assert it.title is None and it.year is None and it.doi is None and it.creators == []
