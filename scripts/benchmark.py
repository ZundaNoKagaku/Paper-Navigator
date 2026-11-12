"""Measure local processing cost (excluding ADS network latency) with SYNTHETIC data.

Usage: uv run python scripts/benchmark.py  -> prints a Markdown table.
ADS latency is not measured here (mock transport); real runs add ~1 HTTP request per
200 records per list plus ADS response time.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from paper_navigator.db import Database  # noqa: E402
from paper_navigator.graph.builder import NetworkParams, build_network  # noqa: E402
from paper_navigator.graph.view import load_job_graph, render_html  # noqa: E402
from tests.conftest import FakeADS, bib, doc  # noqa: E402


def run(n_refs: int, n_cits: int) -> dict[str, float]:
    f = FakeADS()
    seed = bib(1, 2001)
    f.add(doc(1))
    refs = [doc(i, year=1990) for i in range(2, 2 + n_refs)]
    cits = [doc(i, year=2010) for i in range(2 + n_refs, 2 + n_refs + n_cits)]
    f.add(*refs, *cits)
    f.cite(seed, *[d["bibcode"] for d in refs])
    for d in cits:
        f.cite(d["bibcode"], seed)
    total = 1 + n_refs + n_cits
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "b.sqlite3")
        t0 = time.perf_counter()
        out = build_network(
            db, f.client(), seed, NetworkParams(max_papers=total, max_requests=1000)
        )
        t1 = time.perf_counter()
        g = load_job_graph(db, out.job_id)
        t2 = time.perf_counter()
        html = render_html(g)
        t3 = time.perf_counter()
        db.engine.dispose()
        size_db = sum(p.stat().st_size for p in Path(tmp).glob("b.sqlite3*"))
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "build_s": t1 - t0,
        "load_s": t2 - t1,
        "render_s": t3 - t2,
        "html_mb": len(html.encode()) / 1e6,
        "db_mb": size_db / 1e6,
    }


if __name__ == "__main__":
    print(
        "| nodes | edges | build+store (mock) s | load graph s | render HTML s | HTML MB | DB MB |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for nr, nc in ((150, 149), (1000, 999), (2500, 2499)):
        r = run(nr, nc)
        print(
            f"| {r['nodes']} | {r['edges']} | {r['build_s']:.2f} | {r['load_s']:.2f} | "
            f"{r['render_s']:.2f} | {r['html_mb']:.2f} | {r['db_mb']:.2f} |"
        )
