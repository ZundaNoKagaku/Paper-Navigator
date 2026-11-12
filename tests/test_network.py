"""UC-02: network building against the in-memory fake ADS (mock, not live)."""

import json

import httpx
import networkx as nx
import pytest
from sqlalchemy import select

from paper_navigator.errors import ErrorCode
from paper_navigator.graph.builder import NetworkParams, build_network
from paper_navigator.graph.view import (
    GraphFilter,
    export_all,
    filter_graph,
    graph_summary,
    load_job_graph,
    render_html,
)
from paper_navigator.models import RetrievalJob
from paper_navigator.services import search_papers

from .conftest import FakeADS, bib, doc

S = bib(1)  # seed


@pytest.fixture
def world(fake_ads: FakeADS) -> FakeADS:
    """seed(1) cites 2,3,4 ; 5,6 cite seed ; 5 also cites 2 (shared prior work) ;
    2 cites 7 ; 3 cites seed (cycle 1->3->1)."""
    fake_ads.add(*[doc(i, year=2000 + i) for i in range(1, 8)])
    fake_ads.cite(bib(1, 2001), bib(2, 2002), bib(3, 2003), bib(4, 2004))
    fake_ads.cite(bib(5, 2005), bib(1, 2001), bib(2, 2002))
    fake_ads.cite(bib(6, 2006), bib(1, 2001))
    fake_ads.cite(bib(2, 2002), bib(7, 2007))
    fake_ads.cite(bib(3, 2003), bib(1, 2001))
    return fake_ads


SEED = bib(1, 2001)


def _bibs(g, nodes):
    return {g.nodes[n]["bibcode"] for n in nodes}


def test_edge_direction_references_and_citations(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(direction="both", depth=1))
    assert out.status == "success", out.errors
    g = load_job_graph(db, out.job_id)
    seed = out.seed_id
    # references: seed -> cited
    assert _bibs(g, g.successors(seed)) == {bib(2, 2002), bib(3, 2003), bib(4, 2004)}
    # citations: citer -> seed
    assert _bibs(g, g.predecessors(seed)) == {bib(3, 2003), bib(5, 2005), bib(6, 2006)}
    roles = {g.nodes[n]["bibcode"]: g.nodes[n]["role"] for n in g}
    assert roles[SEED] == "seed"
    assert roles[bib(2, 2002)] == "reference" and roles[bib(5, 2005)] == "citation"
    assert roles[bib(3, 2003)] == "both"
    assert g.graph["edge_semantics"] == "u -> v means u cites v"


def test_shared_reference_and_cycle_kept_as_digraph(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(direction="both", depth=2))
    g = load_job_graph(db, out.job_id)
    ids = {g.nodes[n]["bibcode"]: n for n in g}
    # paper 2 is cited by both seed and 5 -> one node, two incoming edges
    assert g.in_degree(ids[bib(2, 2002)]) == 2
    assert len([n for n in g if g.nodes[n]["bibcode"] == bib(2, 2002)]) == 1
    assert graph_summary(g)["has_cycle"]  # 1 -> 3 -> 1
    assert ids[bib(7, 2007)] in g and g.nodes[ids[bib(7, 2007)]]["depth"] == 2


def test_references_only_direction(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(direction="references"))
    g = load_job_graph(db, out.job_id)
    assert g.number_of_nodes() == 4
    assert all(g.nodes[n]["role"] in ("seed", "reference") for n in g)


def test_max_papers_truncation_recorded(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(max_papers=3))
    assert out.truncated and out.status == "partial"
    assert "max_papers" in (out.truncation_reason or "")
    assert out.papers == 3
    with db.session() as s:
        job = s.get(RetrievalJob, out.job_id)
        assert job.truncated == 1 and job.status == "partial"


def test_max_requests_truncation(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(depth=3, max_requests=2))
    assert out.truncated and "max_requests" in out.truncation_reason
    assert out.requests <= 2 + 1  # +1: seed lookup is not part of the budget


def test_cache_reuse_avoids_api_calls(db, world):
    build_network(db, world.client(), SEED, NetworkParams())
    calls_before = len(world.calls)
    out2 = build_network(db, world.client(), SEED, NetworkParams())
    assert len(world.calls) == calls_before  # all lists complete & fresh in cache
    assert out2.cache_hits == 2 and out2.status == "success"
    # without any client the cached graph can still be rebuilt
    out3 = build_network(db, None, SEED, NetworkParams())
    assert out3.status == "success" and out3.papers == 7 - 1  # 1..6 minus 7 (depth 1)


def test_year_filtered_fetch_is_not_cached_as_complete(db, world):
    build_network(db, world.client(), SEED, NetworkParams(year_from=2004))
    n = len(world.calls)
    build_network(db, world.client(), SEED, NetworkParams())
    assert len(world.calls) > n


def test_partial_failure_keeps_fetched_part(db, world):
    world.fail = lambda p, n: httpx.Response(500) if p["q"].startswith("citations") else None
    out = build_network(db, world.client(max_retries=0), SEED, NetworkParams())
    assert out.status == "partial"
    assert any(e.code == ErrorCode.NETWORK_ERROR for e in out.errors)
    assert f"{SEED}:citations" in out.incomplete_lists
    g = load_job_graph(db, out.job_id)
    assert g.out_degree(out.seed_id) == 3  # references survived


def test_auth_error_aborts(db, world):
    c = world.client()
    search_papers(db, c, SEED)  # seed stored first
    world.fail = lambda p, n: httpx.Response(401)
    out = build_network(db, c, SEED, NetworkParams())
    assert out.status == "failed"
    assert out.errors[0].code == ErrorCode.AUTH_ERROR


def test_seed_not_found(db, fake_ads):
    out = build_network(db, fake_ads.client(), "10.5555/none", NetworkParams())
    assert out.status == "failed" and out.errors[0].code == ErrorCode.NOT_FOUND


def test_zero_references(db, fake_ads):
    fake_ads.add(doc(1))
    out = build_network(db, fake_ads.client(), bib(1), NetworkParams())
    assert out.status == "success" and out.papers == 1 and out.edges == 0


@pytest.mark.parametrize(
    "bad",
    [
        dict(depth=0),
        dict(depth=9),
        dict(max_papers=0),
        dict(direction="sideways"),
        dict(year_from=2010, year_to=2000),
    ],
)
def test_param_validation(db, world, bad):
    from paper_navigator.errors import PNError

    with pytest.raises(PNError):
        build_network(db, world.client(), SEED, NetworkParams(**bad))


def test_filter_and_exports(db, world, tmp_path):
    out = build_network(db, world.client(), SEED, NetworkParams(depth=2))
    g = load_job_graph(db, out.job_id)
    f = filter_graph(g, GraphFilter(year_from=2004, roles=("seed", "citation")))
    assert all(g.nodes[n]["role"] in ("seed", "citation") for n in f)
    assert out.seed_id in f
    assert all(f.nodes[n]["year"] >= 2004 for n in f if n != out.seed_id)
    paths = export_all(db, g, tmp_path, "net")
    data = json.loads(paths["json"].read_text())
    assert data["directed"] and len(data["edges"]) == g.number_of_edges()
    h = nx.read_graphml(paths["graphml"])
    assert h.number_of_edges() == g.number_of_edges() and h.is_directed()
    assert paths["edges_csv"].read_text().splitlines()[0].startswith("citing_id")
    html = paths["html"].read_text()
    assert "vis.Network" in html and "A → B" in html


def test_html_escapes_untrusted_metadata(db, fake_ads):
    evil = "</script><script>alert(1)</script><img src=x onerror=alert(2)>"
    fake_ads.add(doc(1, title=[evil], abstract=evil), doc(2))
    fake_ads.cite(bib(1), bib(2))
    out = build_network(db, fake_ads.client(), bib(1), NetworkParams())
    html = render_html(load_job_graph(db, out.job_id))
    data_part = html.split("const DATA = ", 1)[1]
    assert "<script>alert" not in data_part and "<img" not in data_part
    assert "\\u003c/script\\u003e" in data_part
    assert "innerHTML" not in html.split("</script>", 1)[1]


def test_reproducible_regeneration(db, world):
    out = build_network(db, world.client(), SEED, NetworkParams(depth=2))
    a = nx.node_link_data(load_job_graph(db, out.job_id), edges="edges")
    b = nx.node_link_data(load_job_graph(db, out.job_id), edges="edges")
    assert a == b


def test_search_service_statuses(db, fake_ads):
    fake_ads.add(doc(1))
    c = fake_ads.client()
    r = search_papers(db, c, "10.5555/test.1")
    assert r.status == "success" and not r.from_cache and r.papers[0]["bibcode"] == bib(1)
    r2 = search_papers(db, c, "10.5555/test.1")
    assert r2.from_cache
    assert search_papers(db, c, "10.5555/none").status == "empty"
    assert search_papers(db, c, "").error.code == ErrorCode.INPUT_ERROR
    r3 = search_papers(db, None, "coronal")
    assert r3.status == "failed" and r3.error.code == ErrorCode.CONFIG_ERROR
    with db.session() as s:
        jobs = s.scalars(select(RetrievalJob).where(RetrievalJob.kind == "search")).all()
        assert all(j.finished_at for j in jobs)
        assert all("Bearer" not in (j.params + (j.query or "")) for j in jobs)


def test_roles_distinguishable_without_colour_and_layout_seeded(db, world):
    from paper_navigator.graph.view import ROLE_STYLE

    shapes = [v["shape"] for v in ROLE_STYLE.values()]
    symbols = [v["symbol"] for v in ROLE_STYLE.values()]
    assert len(set(shapes)) == len(shapes) and len(set(symbols)) == len(symbols)
    out = build_network(db, world.client(), SEED, NetworkParams())
    html = render_html(load_job_graph(db, out.job_id))
    assert "randomSeed: 20261112" in html
