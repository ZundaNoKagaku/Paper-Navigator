"""Load a stored network job as a NetworkX DiGraph, filter it, and export it.

Edges: ``u -> v`` == *u cites v* (same as the database and every export).

HTML rendering uses vis-network (the library bundled with PyVis, inlined from the
installed ``pyvis`` package so the file works offline). PyVis's own template writes node
tooltips with ``innerHTML``; since titles/abstracts are untrusted external data, we use
our own template that injects data as escaped JSON and renders it with ``textContent``.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import __version__
from ..db import Database
from ..errors import ErrorCode, PNError
from ..models import CitationEdge, ExportRecord, FetchState, JobPaper, Paper, RetrievalJob

ROLE_STYLE = {
    # Shape AND colour encode the role so it is distinguishable without colour vision.
    "seed": {
        "color": "#d62728",
        "shape": "star",
        "size": 30,
        "symbol": "★",
        "label": "起点論文 (seed)",
    },
    "reference": {
        "color": "#1f77b4",
        "shape": "dot",
        "size": 14,
        "symbol": "●",
        "label": "先行研究 (reference list経由)",
    },
    "citation": {
        "color": "#2ca02c",
        "shape": "triangle",
        "size": 14,
        "symbol": "▲",
        "label": "後続研究 (citation list経由)",
    },
    "both": {
        "color": "#9467bd",
        "shape": "diamond",
        "size": 16,
        "symbol": "◆",
        "label": "両方向から到達",
    },
}


def load_job_graph(db: Database, job_id: int) -> nx.DiGraph:
    with db.session() as s:
        job = s.get(RetrievalJob, job_id)
        if job is None or job.kind != "network":
            raise PNError(ErrorCode.NOT_FOUND, f"network job {job_id} not found")
        members = s.scalars(select(JobPaper).where(JobPaper.job_id == job_id)).all()
        ids = [m.paper_id for m in members]
        papers = {
            p.id: p
            for p in s.scalars(
                select(Paper).options(selectinload(Paper.authors)).where(Paper.id.in_(ids))
            )
        }
        edges = s.scalars(
            select(CitationEdge).where(
                CitationEdge.citing_id.in_(ids), CitationEdge.cited_id.in_(ids)
            )
        ).all()
        states = s.scalars(select(FetchState).where(FetchState.paper_id.in_(ids))).all()
        g = nx.DiGraph(
            job_id=job_id,
            seed_id=job.seed_paper_id,
            status=job.status,
            truncated=bool(job.truncated),
            truncation_reason=job.truncation_reason or "",
            edge_semantics="u -> v means u cites v",
            software_version=__version__,
        )
        fetch = {(st.paper_id, st.direction): st for st in states}
        for m in members:
            p = papers.get(m.paper_id)
            if p is None:
                continue
            refs = fetch.get((p.id, "references"))
            cits = fetch.get((p.id, "citations"))
            g.add_node(
                p.id,
                role=m.role,
                depth=m.depth,
                title=p.title or "",
                year=p.year,
                authors=p.author_names,
                pub=p.pub or "",
                bibcode=p.bibcode or "",
                doi=p.doi or "",
                abstract=p.abstract or "",
                label=p.label(),
                links=p.links(),
                source=p.source,
                retrieved_at=p.retrieved_at,
                missing=p.missing,
                references_status=_fs(refs),
                citations_status=_fs(cits),
            )
        for e in edges:
            g.add_edge(
                e.citing_id,
                e.cited_id,
                source=e.source,
                retrieved_at=e.retrieved_at,
                verification=e.verification_status,
            )
    return g


def _fs(st: FetchState | None) -> str:
    if st is None:
        return "not fetched"
    tag = "complete" if st.complete else "incomplete"
    return f"{tag} ({st.num_fetched}/{st.num_found if st.num_found is not None else '?'})"


@dataclass
class GraphFilter:
    year_from: int | None = None
    year_to: int | None = None
    max_depth: int | None = None
    roles: tuple[str, ...] = ("seed", "reference", "citation", "both")
    include_unknown_year: bool = True


def filter_graph(g: nx.DiGraph, f: GraphFilter) -> nx.DiGraph:
    keep = []
    for n, a in g.nodes(data=True):
        if a.get("role") == "seed":
            keep.append(n)  # the seed is always retained
            continue
        if a.get("role") not in f.roles:
            continue
        if f.max_depth is not None and a.get("depth", 0) > f.max_depth:
            continue
        y = a.get("year")
        if y is None:
            if not f.include_unknown_year:
                continue
        else:
            if f.year_from is not None and y < f.year_from:
                continue
            if f.year_to is not None and y > f.year_to:
                continue
        keep.append(n)
    return g.subgraph(keep).copy()


def graph_summary(g: nx.DiGraph) -> dict[str, Any]:
    roles: dict[str, int] = {}
    for _, a in g.nodes(data=True):
        roles[a.get("role", "?")] = roles.get(a.get("role", "?"), 0) + 1
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "roles": roles,
        "has_cycle": not nx.is_directed_acyclic_graph(g),
        **dict(g.graph),
    }


# -- exports -------------------------------------------------------------------------------
def to_node_link(g: nx.DiGraph) -> dict[str, Any]:
    data = nx.node_link_data(g, edges="edges")
    return data


def write_json(g: nx.DiGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_node_link(g), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def write_graphml(g: nx.DiGraph, path: Path) -> Path:
    h = nx.DiGraph()
    h.graph.update({k: str(v) for k, v in g.graph.items()})
    for n, a in g.nodes(data=True):
        h.add_node(
            n,
            **{
                k: (
                    json.dumps(v, ensure_ascii=False)
                    if isinstance(v, list | dict)
                    else ("" if v is None else v)
                )
                for k, v in a.items()
            },
        )
    for u, v, a in g.edges(data=True):
        h.add_edge(u, v, **a)
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(h, path)
    return path


def write_edges_csv(g: nx.DiGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["citing_id", "citing_bibcode", "cited_id", "cited_bibcode", "source"])
        for u, v, a in g.edges(data=True):
            w.writerow(
                [u, g.nodes[u].get("bibcode"), v, g.nodes[v].get("bibcode"), a.get("source")]
            )
    return path


def _vis_js() -> str:
    import pyvis

    lib = Path(pyvis.__file__).parent / "templates" / "lib" / "vis-9.1.2" / "vis-network.min.js"
    return lib.read_text(encoding="utf-8")


def _safe_json(obj: Any) -> str:
    """JSON safe for embedding inside <script>: escape <, >, & and line separators."""
    s = json.dumps(obj, ensure_ascii=False)
    return (
        s.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:;">
<title>Paper Navigator citation graph</title>
<style>
body{margin:0;font-family:system-ui,sans-serif;display:flex;height:100vh}
#net{flex:1;border-right:1px solid #ddd}
#side{width:360px;overflow:auto;padding:10px;font-size:13px}
#side h3{margin:.2em 0}.k{color:#555}.legend span{display:inline-block;margin-right:8px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:3px}
#abs{white-space:pre-wrap}
</style></head><body>
<div id="net"></div>
<div id="side">
 <div class="legend" id="legend"></div>
 <p class="k">矢印 A → B は「論文Aが論文Bを引用している」。引用関係は研究上の影響を完全には表さず、
 引用数は研究の質や重要度を示しません。</p>
 <p class="k" id="meta"></p>
 <hr><div id="detail"><p class="k">ノードをクリックすると詳細を表示します。</p></div>
</div>
<script>__VIS__</script>
<script>
const DATA = __DATA__;
const STYLE = __STYLE__;
const legend = document.getElementById('legend');
for (const [role, st] of Object.entries(STYLE)) {
  const s = document.createElement('span');
  const d = document.createElement('span'); d.style.color = st.color; d.textContent = st.symbol + ' ';
  s.appendChild(d); s.appendChild(document.createTextNode(st.label)); legend.appendChild(s);
}
document.getElementById('meta').textContent =
  `nodes=${DATA.nodes.length} edges=${DATA.edges.length} status=${DATA.graph.status}` +
  (DATA.graph.truncated ? ` (打ち切りあり: ${DATA.graph.truncation_reason})` : '');
const nodes = new vis.DataSet(DATA.nodes.map(n => {
  const st = STYLE[n.role] || STYLE.reference;
  const tip = document.createElement('div');
  tip.textContent = `${n.title}\\n${(n.authors||[]).slice(0,3).join('; ')}` +
                    `${(n.authors||[]).length>3?' et al.':''}\\n${n.year ?? '年不明'} ${n.pub}`;
  tip.style.whiteSpace='pre-wrap'; tip.style.maxWidth='320px';
  return {id: n.id, label: n.label, title: tip, color: st.color, shape: st.shape,
          size: st.size, font: {size: 10}};
}));
const edges = new vis.DataSet(DATA.edges.map((e,i) => ({id:i, from:e.source, to:e.target,
  arrows:'to', color:{opacity:0.4}})));
const big = DATA.nodes.length > 400;
const net = new vis.Network(document.getElementById('net'), {nodes, edges}, {
  layout: {randomSeed: 20261112},  // fixed seed: same graph -> same initial layout
  physics: {enabled: true, stabilization: {iterations: big ? 150 : 400},
            barnesHut: {gravitationalConstant: -4000}},
  interaction: {hover: true, tooltipDelay: 150, hideEdgesOnDrag: big},
  edges: {smooth: !big}
});
net.once('stabilizationIterationsDone', () => net.setOptions({physics: false}));
const byId = Object.fromEntries(DATA.nodes.map(n => [n.id, n]));
function row(parent, k, v) {
  const p = document.createElement('p');
  const b = document.createElement('span'); b.className='k'; b.textContent = k + ': ';
  p.appendChild(b); p.appendChild(document.createTextNode(v == null || v === '' ? '（未取得）' : v));
  parent.appendChild(p);
}
net.on('click', params => {
  if (!params.nodes.length) return;
  const n = byId[params.nodes[0]]; const box = document.getElementById('detail');
  box.replaceChildren();
  const h = document.createElement('h3'); h.textContent = n.title || '（タイトル未取得）';
  box.appendChild(h);
  row(box, '著者', (n.authors||[]).join('; '));
  row(box, '出版年', n.year); row(box, '雑誌', n.pub); row(box, 'DOI', n.doi);
  row(box, 'Bibcode', n.bibcode); row(box, '役割', (STYLE[n.role]||{}).label);
  row(box, '階層', n.depth); row(box, '取得元', n.source + ' / ' + n.retrieved_at);
  row(box, 'References取得', n.references_status); row(box, 'Citations取得', n.citations_status);
  row(box, '欠落フィールド', (n.missing||[]).join(', ') || 'なし');
  for (const [name, url] of Object.entries(n.links || {})) {
    if (!/^https:\\/\\/(ui\\.adsabs\\.harvard\\.edu|doi\\.org|arxiv\\.org)\\//.test(url)) continue;
    const a = document.createElement('a'); a.href = url; a.textContent = name;
    a.target = '_blank'; a.rel = 'noopener noreferrer'; box.appendChild(a);
    box.appendChild(document.createTextNode(' '));
  }
  const ab = document.createElement('p'); ab.id='abs'; ab.textContent = n.abstract || '（Abstract未取得）';
  box.appendChild(ab);
});
</script></body></html>
"""


def render_html(g: nx.DiGraph) -> str:
    data = to_node_link(g)
    # Untrusted DATA is substituted last so its contents can never be re-substituted.
    head, sep, tail = _TEMPLATE.partition("__VIS__")
    html = head + sep + tail.replace("__STYLE__", _safe_json(ROLE_STYLE))
    html = html.replace("__DATA__", _safe_json(data))
    return html.replace("__VIS__", _vis_js().replace("</script", "<\\/script"), 1)


def write_html(g: nx.DiGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(g), encoding="utf-8")
    return path


def export_all(db: Database, g: nx.DiGraph, out_dir: Path, stem: str) -> dict[str, Path]:
    out = {
        "html": write_html(g, out_dir / f"{stem}.html"),
        "json": write_json(g, out_dir / f"{stem}.json"),
        "graphml": write_graphml(g, out_dir / f"{stem}.graphml"),
        "edges_csv": write_edges_csv(g, out_dir / f"{stem}_edges.csv"),
    }
    with db.session() as s:
        for kind, p in out.items():
            s.add(
                ExportRecord(
                    kind=f"graph_{kind}",
                    path=str(p),
                    job_id=g.graph.get("job_id"),
                    details=json.dumps(
                        {"nodes": g.number_of_nodes(), "edges": g.number_of_edges()}
                    ),
                )
            )
    return out
