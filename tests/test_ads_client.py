import httpx
import pytest

from paper_navigator.ads.client import ADSClient
from paper_navigator.ads.mapping import ads_doc_to_record
from paper_navigator.errors import ErrorCode, PNError

from .conftest import TOKEN, FakeADS, bib, doc, load_json


def test_mapping_full_record():
    rec = ads_doc_to_record(
        doc(1, alternate_bibcode=["2000arXiv0001.0001X"], identifier=[bib(1), "arXiv:0001.00010"])
    )
    assert rec.bibcode == bib(1)
    assert rec.title.startswith("Synthetic paper number 1")
    assert rec.authors == ["Author1, A.", "Second, B."]  # order preserved
    assert rec.year == 2001 and rec.doi == "10.5555/test.1"
    assert rec.arxiv_id == "0001.00010"
    assert rec.alternate_bibcodes == ["2000arXiv0001.0001X"]
    assert rec.missing_fields() == []
    assert rec.validation_status() == "complete"


def test_mapping_missing_fields_are_null_not_guessed():
    rec = ads_doc_to_record({"bibcode": bib(2), "title": ["Only a title"]})
    assert rec.doi is None and rec.year is None and rec.authors == []
    assert set(rec.missing_fields()) >= {"authors", "year", "doi", "pub", "abstract"}
    assert rec.validation_status() == "incomplete"


def test_mapping_bad_values_flagged():
    rec = ads_doc_to_record({"bibcode": "weird", "doi": ["nonsense"], "year": "abcd"})
    assert rec.bibcode == "weird" and rec.doi is None and rec.year is None
    assert len(rec.warnings) == 3


def test_recorded_response_fixture_parses():
    data = load_json("search_response_sample.json")
    recs = [ads_doc_to_record(d) for d in data["response"]["docs"]]
    assert [r.bibcode for r in recs] == [bib(1), bib(2)]


def test_auth_header_sent_and_token_not_in_repr(fake_ads: FakeADS):
    fake_ads.add(doc(1))
    c = fake_ads.client()
    c.search('doi:"10.5555/test.1"')
    assert fake_ads.seen_auth[0] == f"Bearer {TOKEN}"
    assert TOKEN not in repr(c.__dict__.get("rate_limit"))


def test_empty_token_is_config_error():
    with pytest.raises(PNError) as e:
        ADSClient("")
    assert e.value.code == ErrorCode.CONFIG_ERROR


def test_paging_fetches_all_and_marks_complete(fake_ads: FakeADS):
    fake_ads.add(*[doc(i) for i in range(1, 26)])
    fake_ads.cite(bib(1), *[bib(i) for i in range(2, 26)])
    c = fake_ads.client()
    r = c.search(f'references(bibcode:"{bib(1)}")', max_results=100, page_size=10)
    assert r.num_found == 24 and r.fetched == 24 and r.pages == 3 and r.complete
    assert [p["start"] for p in r.paging] == [0, 10, 20]


def test_max_results_limit_is_not_reported_complete(fake_ads: FakeADS):
    fake_ads.add(*[doc(i) for i in range(1, 26)])
    fake_ads.cite(bib(1), *[bib(i) for i in range(2, 26)])
    r = fake_ads.client().search(f'references(bibcode:"{bib(1)}")', max_results=15, page_size=10)
    assert r.fetched == 15 and r.num_found == 24
    assert not r.complete and r.stopped_by_limit


def test_zero_results_is_not_an_error(fake_ads: FakeADS):
    r = fake_ads.client().search('doi:"10.5555/none"')
    assert r.num_found == 0 and r.error is None and r.complete


@pytest.mark.parametrize(
    "status,code",
    [
        (401, ErrorCode.AUTH_ERROR),
        (403, ErrorCode.AUTH_ERROR),
        (400, ErrorCode.INPUT_ERROR),
        (418, ErrorCode.INVALID_RESPONSE),
    ],
)
def test_http_error_classification(fake_ads: FakeADS, status, code):
    fake_ads.fail = lambda p, n: httpx.Response(status, text="err")
    with pytest.raises(PNError) as e:
        fake_ads.client().search('doi:"x"')
    assert e.value.code == code
    assert len(fake_ads.calls) == 1  # non-retryable


def test_rate_limit_retries_then_fails(fake_ads: FakeADS):
    sleeps: list[float] = []
    fake_ads.fail = lambda p, n: httpx.Response(429, headers={"Retry-After": "7"})
    c = fake_ads.client(max_retries=2, sleep=sleeps.append)
    with pytest.raises(PNError) as e:
        c.search('doi:"x"')
    assert e.value.code == ErrorCode.RATE_LIMITED
    assert len(fake_ads.calls) == 3 and sleeps == [7.0, 7.0]


def test_quota_exhausted_does_not_retry(fake_ads: FakeADS):
    fake_ads.fail = lambda p, n: httpx.Response(
        429, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Limit": "5000"}
    )
    with pytest.raises(PNError) as e:
        fake_ads.client(max_retries=3).search('doi:"x"')
    assert e.value.code == ErrorCode.RATE_LIMITED and len(fake_ads.calls) == 1


def test_transient_5xx_recovers(fake_ads: FakeADS):
    fake_ads.add(doc(1))
    fake_ads.fail = lambda p, n: httpx.Response(503) if n == 1 else None
    r = fake_ads.client(max_retries=2).search('doi:"10.5555/test.1"')
    assert r.fetched == 1 and len(fake_ads.calls) == 2


def test_timeout_and_network_errors():
    def boom_timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def boom_conn(request):
        raise httpx.ConnectError("refused", request=request)

    for fn, code in ((boom_timeout, ErrorCode.TIMEOUT), (boom_conn, ErrorCode.NETWORK_ERROR)):
        c = ADSClient(TOKEN, transport=httpx.MockTransport(fn), max_retries=1, sleep=lambda s: None)
        with pytest.raises(PNError) as e:
            c.search('doi:"x"')
        assert e.value.code == code


@pytest.mark.parametrize(
    "body", [b"not json", b"[1,2]", b'{"response": {"docs": "x"}}', b'{"foo": 1}']
)
def test_invalid_response_shapes(body):
    c = ADSClient(TOKEN, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))
    with pytest.raises(PNError) as e:
        c.search('doi:"x"')
    assert e.value.code == ErrorCode.INVALID_RESPONSE


def test_failure_after_first_page_is_partial(fake_ads: FakeADS):
    fake_ads.add(*[doc(i) for i in range(1, 26)])
    fake_ads.cite(bib(1), *[bib(i) for i in range(2, 26)])
    fake_ads.fail = lambda p, n: httpx.Response(500) if p.get("start") == "10" else None
    r = fake_ads.client(max_retries=0).search(
        f'references(bibcode:"{bib(1)}")', max_results=100, page_size=10
    )
    assert r.fetched == 10 and r.error is not None and not r.complete


def test_docs_without_bibcode_are_skipped(fake_ads: FakeADS):
    def h(request):
        return httpx.Response(
            200, json={"response": {"numFound": 2, "docs": [doc(1), {"title": ["no id"]}]}}
        )

    c = ADSClient(TOKEN, transport=httpx.MockTransport(h))
    r = c.search("x", max_results=10)
    assert r.fetched == 1 and r.skipped == 1 and r.complete


def test_rate_limit_headers_captured(fake_ads: FakeADS):
    fake_ads.add(doc(1))
    c = fake_ads.client()
    c.search('doi:"10.5555/test.1"')
    assert c.rate_limit.limit == 5000 and c.rate_limit.remaining == 4999
