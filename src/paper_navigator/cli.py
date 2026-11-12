"""Command-line interface (``pn``). Exit codes: 0 success, 2 partial/warnings, 1 failure."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .ads.query import InputKind
from .app import AppContext, make_context, write_key_file, zotero_key_path
from .bibliography.bibcheck import check_bib, compare_with_snapshot, save_snapshot
from .bibliography.cites import check_citations
from .bibliography.latex import build
from .errors import PNError
from .graph.builder import NetworkParams, build_network
from .graph.view import GraphFilter, export_all, filter_graph, graph_summary, load_job_graph
from .records import PaperRecord
from .services import list_jobs, paper_detail, search_papers
from .zotero.sync import sync_collection


def _out(obj: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{k}: {v}")
    else:
        print(obj)


def _err(e: PNError) -> int:
    print(f"[{e.code}] {e.user_message}", file=sys.stderr)
    if e.detail:
        print(f"  detail: {e.detail}", file=sys.stderr)
    return 1


def cmd_init_db(ctx: AppContext, a: argparse.Namespace) -> int:
    print(f"database ready: {ctx.settings.db_path}")
    return 0


def cmd_backup(ctx: AppContext, a: argparse.Namespace) -> int:
    try:
        dest = ctx.db.backup(Path(a.dest or ctx.settings.db_path.parent / "backups"))
    except PNError as e:
        return _err(e)
    print(f"backup written: {dest}")
    return 0


def cmd_search(ctx: AppContext, a: argparse.Namespace) -> int:
    r = search_papers(
        ctx.db,
        ctx.ads(),
        a.text,
        kind=InputKind(a.kind) if a.kind else None,
        year_from=a.year_from,
        year_to=a.year_to,
        max_results=a.max,
        refresh=a.refresh,
        cache_ttl_days=ctx.settings.cache_ttl_days,
    )
    if a.json:
        _out(
            {
                "status": r.status,
                "num_found": r.num_found,
                "from_cache": r.from_cache,
                "query": r.query,
                "error": r.error and r.error.code,
                "papers": r.papers,
            },
            True,
        )
    else:
        print(f"status={r.status} found={r.num_found} cache={r.from_cache} query={r.query}")
        for p in r.papers:
            au = "; ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
            print(f"  #{p['id']} {p['bibcode']} {p['year']} {au}\n      {p['title']}")
        if r.num_found and r.num_found > len(r.papers):
            print(f"  ({len(r.papers)} of {r.num_found} shown; raise --max to see more)")
    if r.error:
        _err(r.error)
    return {"success": 0, "empty": 0, "partial": 2}.get(r.status, 1)


def cmd_network(ctx: AppContext, a: argparse.Namespace) -> int:
    s = ctx.settings
    params = NetworkParams(
        direction=a.direction,
        depth=a.depth or s.network_depth,
        max_papers=a.max_papers or s.network_max_papers,
        max_requests=a.max_requests or s.network_max_requests,
        year_from=a.year_from,
        year_to=a.year_to,
        refresh=a.refresh,
        cache_ttl_days=s.cache_ttl_days,
    )
    try:
        out = build_network(
            ctx.db,
            ctx.ads(),
            a.seed,
            params,
            progress=lambda m: print(f"  fetching {m}", file=sys.stderr),
        )
    except PNError as e:
        return _err(e)
    print(
        f"job={out.job_id} status={out.status} papers={out.papers} new_edges={out.edges} "
        f"requests={out.requests} cache_hits={out.cache_hits}"
    )
    if out.truncated:
        print(f"  TRUNCATED: {out.truncation_reason}")
    for lst in out.incomplete_lists:
        print(f"  incomplete list: {lst}")
    for err in out.errors:
        print(f"  [{err.code}] {err.detail}", file=sys.stderr)
    if out.job_id and a.export_dir:
        g = load_job_graph(ctx.db, out.job_id)
        for k, p in export_all(ctx.db, g, Path(a.export_dir), f"network_job{out.job_id}").items():
            print(f"  exported {k}: {p}")
    return {"success": 0, "partial": 2}.get(out.status, 1)


def cmd_export_graph(ctx: AppContext, a: argparse.Namespace) -> int:
    try:
        g = load_job_graph(ctx.db, a.job_id)
    except PNError as e:
        return _err(e)
    g = filter_graph(
        g, GraphFilter(year_from=a.year_from, year_to=a.year_to, max_depth=a.max_depth)
    )
    out_dir = Path(a.out or ctx.settings.export_dir)
    for k, p in export_all(ctx.db, g, out_dir, f"network_job{a.job_id}").items():
        print(f"{k}: {p}")
    print(json.dumps(graph_summary(g), ensure_ascii=False, default=str))
    return 0


def cmd_show(ctx: AppContext, a: argparse.Namespace) -> int:
    d = paper_detail(ctx.db, a.ident)
    if d is None:
        print("not in local database (search for it first)", file=sys.stderr)
        return 1
    _out(d, a.json)
    return 0


def cmd_jobs(ctx: AppContext, a: argparse.Namespace) -> int:
    for j in list_jobs(ctx.db, a.limit):
        print(
            f"#{j['id']} {j['kind']:7} {j['status']:8} {j['started_at']} q={j['query']} "
            f"papers={j['papers_found']} req={j['requests_made']} "
            f"{'TRUNCATED ' + (j['truncation_reason'] or '') if j['truncated'] else ''}"
            f"{' err=' + j['error_code'] if j['error_code'] else ''}"
        )
    return 0


def cmd_duplicates(ctx: AppContext, a: argparse.Namespace) -> int:
    from sqlalchemy import select

    from .models import DuplicateCandidate

    with ctx.db.session() as s:
        for c in s.scalars(select(DuplicateCandidate)).all():
            print(
                f"#{c.paper_a} ~ #{c.paper_b} score={c.score} reason={c.reason} status={c.status}"
            )
    return 0


def cmd_zotero_status(ctx: AppContext, a: argparse.Namespace) -> int:
    st = ctx.zotero().status()
    _out(
        {
            "state": st.state,
            "zotero_version": st.zotero_version,
            "api_version": st.api_version,
            "write_supported": st.write_supported,
            "write_key_configured": st.write_key_configured,
            "message": st.message,
        },
        a.json,
    )
    return 0 if st.reachable and st.api_enabled else 1


def cmd_zotero_collections(ctx: AppContext, a: argparse.Namespace) -> int:
    try:
        for c in ctx.zotero().collections():
            print(f"{c['key']}  {c['name']}  items={c['items']}")
    except PNError as e:
        return _err(e)
    return 0


def cmd_zotero_sync(ctx: AppContext, a: argparse.Namespace) -> int:
    try:
        rep = sync_collection(ctx.db, ctx.zotero(), a.collection)
    except PNError as e:
        return _err(e)
    print(
        f"items={rep.items} linked={rep.linked} not_in_db={len(rep.not_in_db)} "
        f"mismatches={len(rep.mismatches)} missing_citation_keys="
        f"{len(rep.missing_citation_keys)}"
    )
    for m in rep.mismatches:
        print(
            f"  #{m['paper_id']} {m['zotero_key']} {m['field']}: ADS={m['ads']!r} "
            f"Zotero={m['zotero']!r} -> {m['decision']}"
        )
    for zk, pid, sc in rep.possible_matches:
        print(f"  possible match (not linked): Zotero {zk} ~ #{pid} (title sim {sc})")
    return 2 if any(m["decision"] == "manual_review" for m in rep.mismatches) else 0


def cmd_zotero_add(ctx: AppContext, a: argparse.Namespace) -> int:
    d = paper_detail(ctx.db, a.ident)
    if d is None:
        print("paper not in local database", file=sys.stderr)
        return 1
    rec = PaperRecord(
        source="local",
        title=d["title"],
        authors=d["authors"],
        year=d["year"],
        pub=d["pub"],
        volume=d["volume"],
        issue=d["issue"],
        page=d["page"],
        doi=d["doi"],
        bibcode=d["bibcode"],
        abstract=d["abstract"],
    )
    try:
        out = ctx.zotero().create_item(rec, a.collection)
    except PNError as e:
        return _err(e)
    print(f"status={out.status} key={out.zotero_key} {out.message}")
    if out.status == "unsupported":
        print(
            "  Manual alternative: in Zotero use 'Add Item by Identifier' (magic wand) "
            f"with DOI {d['doi'] or '(none)'}."
        )
    return 0 if out.status in ("created", "exists") else 1


def cmd_zotero_authorize(ctx: AppContext, a: argparse.Namespace) -> int:
    print("A dialog will appear in Zotero; choose 'Always Allow' to keep the key.")
    try:
        key = ctx.zotero().request_authorization()
    except PNError as e:
        return _err(e)
    path = zotero_key_path(ctx.settings)
    write_key_file(path, key)
    print(f"write key stored in {path} (mode 600; git-ignored). Key value not shown.")
    return 0


def cmd_bib_check(ctx: AppContext, a: argparse.Namespace) -> int:
    rep = check_bib(Path(a.bib))
    if a.snapshot:
        rep.issues += compare_with_snapshot(rep, Path(a.snapshot))
    if a.json:
        _out(rep.as_dict(), True)
    else:
        print(
            f"{a.bib}: entries={rep.entries} errors={rep.count('error')} "
            f"warnings={rep.count('warning')} info={rep.count('info')}"
        )
        for i in rep.issues:
            loc = f"line {i.line}" if i.line else ""
            print(f"  {i.severity.upper():7} {i.code:20} {i.key or '-':28} {loc:9} {i.message}")
    if a.snapshot and a.accept and rep.ok:
        save_snapshot(rep, Path(a.snapshot))
        print(f"snapshot saved: {a.snapshot}")
    return 1 if not rep.ok else (2 if rep.count("warning") else 0)


def cmd_cite_check(ctx: AppContext, a: argparse.Namespace) -> int:
    bib = check_bib(Path(a.bib))
    rep = check_citations([Path(t) for t in a.tex], bib.keys)
    print(f"cited keys={len(rep.cited)} missing={len(rep.missing)} unused={len(rep.unused)}")
    for k in rep.missing:
        print(f"  MISSING {k}  at {', '.join(rep.cited[k])}")
    for k in rep.unused:
        print(f"  unused  {k}")
    return 0 if rep.ok else 1


def cmd_apj_build(ctx: AppContext, a: argparse.Namespace) -> int:
    style_dirs = [Path(d) for d in (a.style_dir or ["vendor/aastex"])]
    try:
        rep = build(
            Path(a.tex),
            [Path(b) for b in a.bib],
            style_dirs,
            Path(a.out or ctx.settings.export_dir / "apj"),
        )
    except PNError as e:
        return _err(e)
    _out(
        {
            "success": rep.success,
            "clean": rep.clean,
            "pdf": rep.pdf,
            "bbl": rep.bbl,
            "class": rep.class_file,
            "bst": rep.bst_file,
            "error": rep.error,
            "undefined_citations": rep.undefined_citations,
            "bibtex_warnings": rep.bibtex_warnings,
            "bibtex_errors": rep.bibtex_errors,
            "commands": rep.commands,
            "tools": rep.tool_versions,
        },
        a.json,
    )
    return 0 if rep.clean else (2 if rep.success else 1)


def cmd_ui(ctx: AppContext, a: argparse.Namespace) -> int:
    app = Path(__file__).parent / "ui" / "streamlit_app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.address",
        a.address,
        "--server.port",
        str(a.port),
        "--browser.gatherUsageStats",
        "false",
    ]
    if a.address not in ("127.0.0.1", "localhost", "::1"):
        print(
            "WARNING: binding to a non-loopback address exposes your local data and "
            "Zotero access to the network.",
            file=sys.stderr,
        )
    return subprocess.call(cmd)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pn", description="Paper Navigator (P0)")
    p.add_argument("--version", action="version", version=f"paper-navigator {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, fn: Any, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        return sp

    add("init-db", cmd_init_db, "create/migrate the SQLite database")
    sp = add("backup", cmd_backup, "write a consistent copy of the database")
    sp.add_argument("--dest", help="directory (default: data/backups)")
    sp = add("search", cmd_search, "search NASA ADS by title, DOI, bibcode or arXiv id")
    sp.add_argument("text")
    sp.add_argument("--kind", choices=[k.value for k in InputKind])
    sp.add_argument("--year-from", type=int)
    sp.add_argument("--year-to", type=int)
    sp.add_argument("--max", type=int, default=25)
    sp.add_argument("--refresh", action="store_true", help="ignore cache")
    sp = add("network", cmd_network, "build citation network from a seed paper")
    sp.add_argument("seed", help="DOI, bibcode, arXiv id or #id")
    sp.add_argument("--direction", choices=["references", "citations", "both"], default="both")
    sp.add_argument("--depth", type=int)
    sp.add_argument("--max-papers", type=int)
    sp.add_argument("--max-requests", type=int)
    sp.add_argument("--year-from", type=int)
    sp.add_argument("--year-to", type=int)
    sp.add_argument("--refresh", action="store_true")
    sp.add_argument("--export-dir")
    sp = add("export-graph", cmd_export_graph, "export a network job (HTML/JSON/GraphML/CSV)")
    sp.add_argument("job_id", type=int)
    sp.add_argument("--out")
    sp.add_argument("--year-from", type=int)
    sp.add_argument("--year-to", type=int)
    sp.add_argument("--max-depth", type=int)
    sp = add("show", cmd_show, "show stored paper detail")
    sp.add_argument("ident")
    sp = add("jobs", cmd_jobs, "list retrieval jobs")
    sp.add_argument("--limit", type=int, default=20)
    add("duplicates", cmd_duplicates, "list duplicate candidates (never auto-merged)")
    add("zotero-status", cmd_zotero_status, "check Zotero Local API state")
    add("zotero-collections", cmd_zotero_collections, "list Zotero collections")
    sp = add("zotero-sync", cmd_zotero_sync, "link a Zotero collection to local papers")
    sp.add_argument("collection", help="8-character collection key")
    sp = add("zotero-add", cmd_zotero_add, "add a stored paper to Zotero (Zotero 10+)")
    sp.add_argument("ident")
    sp.add_argument("--collection")
    add("zotero-authorize", cmd_zotero_authorize, "request a Zotero local write key")
    sp = add("bib-check", cmd_bib_check, "validate a Better BibTeX .bib export")
    sp.add_argument("bib")
    sp.add_argument("--snapshot", help="JSON snapshot to compare keys against")
    sp.add_argument("--accept", action="store_true", help="save snapshot if no errors")
    sp = add("cite-check", cmd_cite_check, r"check \cite keys in .tex files against .bib")
    sp.add_argument("bib")
    sp.add_argument("tex", nargs="+")
    sp = add("apj-build", cmd_apj_build, "compile with AASTeX + official AAS .bst")
    sp.add_argument("tex")
    sp.add_argument("--bib", nargs="+", required=True)
    sp.add_argument("--style-dir", action="append")
    sp.add_argument("--out")
    sp = add("ui", cmd_ui, "start the local Streamlit UI (127.0.0.1 by default)")
    sp.add_argument("--address", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8501)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = make_context()
        return int(args.fn(ctx, args))
    except PNError as e:
        return _err(e)


if __name__ == "__main__":
    sys.exit(main())
