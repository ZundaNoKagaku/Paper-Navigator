"""LIVE tests against the real NASA ADS API. Skipped by default (pytest -m live to run).
Require ADS_API_TOKEN and outbound access to api.adsabs.harvard.edu. Results depend on
the live ADS index, so assertions only check structure and edge direction, not counts."""

import os

import pytest

from paper_navigator.ads.client import ADSClient
from paper_navigator.ads.query import citations_query, references_query

pytestmark = pytest.mark.live
TOKEN = os.environ.get("ADS_API_TOKEN", "")
SEED = os.environ.get("PN_LIVE_SEED_BIBCODE", "1998ApJ...509..678G")  # ADS docs' example


@pytest.fixture
def client():
    if not TOKEN:
        pytest.skip("ADS_API_TOKEN not set")
    with ADSClient(TOKEN) as c:
        yield c


def test_live_lookup(client):
    r = client.search(f'identifier:"{SEED}"', max_results=1)
    assert r.num_found >= 1 and r.records[0].bibcode


def test_live_references_and_citations_direction(client):
    refs = client.search(references_query(SEED), max_results=20)
    cits = client.search(citations_query(SEED), max_results=20)
    assert refs.num_found and cits.num_found
    # a paper's references are (almost always) older than or equal to it
    seed_year = int(SEED[:4])
    assert all(r.year is None or r.year <= seed_year + 1 for r in refs.records)
    assert all(c.year is None or c.year >= seed_year - 1 for c in cits.records)
    assert client.rate_limit.limit is not None
