"""Paper Navigator local web UI (P0-F). Start with ``pn ui`` (binds 127.0.0.1).

Every operation reports one of: success / partial / failed / empty / cache, plus the
error class (e.g. CONFIG_ERROR) so users can tell "0 results" from "could not fetch".
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from paper_navigator.ads.query import InputKind
from paper_navigator.app import AppContext, make_context
from paper_navigator.bibliography.bibcheck import check_bib
from paper_navigator.bibliography.cites import check_citations
from paper_navigator.bibliography.latex import build
from paper_navigator.errors import PNError
from paper_navigator.graph.builder import Direction, NetworkParams, build_network
from paper_navigator.graph.view import (
    ROLE_STYLE,
    GraphFilter,
    export_all,
    filter_graph,
    graph_summary,
    load_job_graph,
    render_html,
)
from paper_navigator.services import list_jobs, paper_detail, search_papers
from paper_navigator.zotero.sync import sync_collection

st.set_page_config(page_title="Paper Navigator", layout="wide")

if "ctx" not in st.session_state:
    try:
        st.session_state["ctx"] = make_context()
    except PNError as e:
        st.error(f"[{e.code}] {e.user_message}  \n{e.detail}")
        st.stop()
ctx: AppContext = st.session_state["ctx"]

BADGE = {
    "success": "✅ 成功",
    "partial": "⚠️ 部分成功",
    "failed": "❌ 失敗",
    "empty": "∅ 該当なし (0件)",
    "cache": "💾 キャッシュ使用",
}


def show_error(e: PNError | None) -> None:
    if e is not None:
        st.error(f"[{e.code}] {e.user_message}")
        with st.expander("開発者向け詳細"):
            st.code(e.detail or "(no detail)")


# ---- sidebar ----------------------------------------------------------------------------
with st.sidebar:
    st.header("Paper Navigator")
    s = ctx.settings
    st.write("ADSトークン:", "設定済み" if s.ads_token else "**未設定** (検索不可・キャッシュのみ)")
    st.write("DB:", f"`{s.db_path}`")
    st.caption("既定は 127.0.0.1 のみで待ち受けます。")
    st.info("日本語翻訳・PDF解析・共引用分析は **P1以降（未実装）** です。")
    st.caption("引用関係は研究上の影響を完全には表さず、引用数は研究の質・重要度を示しません。")

tab_search, tab_graph, tab_detail, tab_zot, tab_ref = st.tabs(
    ["🔎 検索", "🕸 引用グラフ", "📄 論文詳細", "📚 Zotero / BibTeX", "🧾 ApJ Reference"]
)

# ---- search ----------------------------------------------------------------------------
with tab_search:
    with st.form("search"):
        text = st.text_input("タイトル / DOI / Bibcode / arXiv ID", max_chars=500)
        c1, c2, c3, c4 = st.columns(4)
        kind = c1.selectbox("種別", ["自動判定"] + [k.value for k in InputKind])
        yf = c2.number_input("出版年(から)", 0, 3000, 0, help="0 = 指定なし")
        yt = c3.number_input("出版年(まで)", 0, 3000, 0, help="0 = 指定なし")
        mx = c4.number_input("最大件数", 1, 200, 25)
        refresh = st.checkbox("キャッシュを使わず再取得")
        go = st.form_submit_button("検索")
    if go:
        with st.spinner("NASA ADS に問い合わせ中…"):
            r = search_papers(
                ctx.db,
                ctx.ads(),
                text,
                kind=None if kind == "自動判定" else InputKind(kind),
                year_from=yf or None,
                year_to=yt or None,
                max_results=int(mx),
                refresh=refresh,
                cache_ttl_days=ctx.settings.cache_ttl_days,
            )
        st.session_state["last_search"] = r
    last = st.session_state.get("last_search")
    if last is not None:
        r = last
        st.subheader(BADGE["cache"] if r.from_cache else BADGE.get(r.status, r.status))
        if r.query:
            st.caption(f"ADS query: `{r.query}` / numFound={r.num_found}")
        show_error(r.error)
        if r.num_found and r.num_found > len(r.papers):
            st.warning(f"{r.num_found}件中 {len(r.papers)}件のみ表示（全件ではありません）")
        for w in r.warnings:
            st.warning(w)
        if r.papers:
            st.dataframe(
                [
                    {
                        "id": p["id"],
                        "bibcode": p["bibcode"],
                        "year": p["year"],
                        "first author": (p["authors"] or ["?"])[0],
                        "title": p["title"],
                        "journal": p["pub"],
                        "doi": p["doi"],
                        "欠落": ", ".join(p["missing_fields"]),
                    }
                    for p in r.papers
                ],
                hide_index=True,
                width="stretch",
            )
            choice = st.selectbox(
                "起点論文にする", [p["bibcode"] for p in r.papers], key="seed_choice"
            )
            if st.button("この論文を起点に設定"):
                st.session_state["seed"] = choice
                st.success(f"起点: {choice}（「引用グラフ」タブへ）")

# ---- graph -----------------------------------------------------------------------------
with tab_graph:
    s = ctx.settings
    with st.form("network"):
        seed = st.text_input("起点論文 (Bibcode/DOI/arXiv/#id)", st.session_state.get("seed", ""))
        c1, c2, c3, c4 = st.columns(4)
        dir_labels = {
            "both": "両方向",
            "references": "References (先行)",
            "citations": "Citations (後続)",
        }
        direction = c1.selectbox("方向", list(dir_labels), format_func=lambda k: dir_labels[k])
        depth = c2.number_input("階層数", 1, 5, s.network_depth)
        maxp = c3.number_input("最大論文数", 1, 20000, s.network_max_papers)
        maxr = c4.number_input("最大APIリクエスト数", 1, 5000, s.network_max_requests)
        c5, c6, c7 = st.columns(3)
        nyf = c5.number_input("期間(から)", 0, 3000, 0, key="nyf")
        nyt = c6.number_input("期間(まで)", 0, 3000, 0, key="nyt")
        nref = c7.checkbox("キャッシュを使わず再取得", key="nref")
        build_go = st.form_submit_button("引用ネットワークを作成")
    if build_go:
        try:
            with st.status("取得中…", expanded=True) as box:
                out = build_network(
                    ctx.db,
                    ctx.ads(),
                    seed,
                    NetworkParams(
                        direction=cast(Direction, direction or "both"),
                        depth=int(depth),
                        max_papers=int(maxp),
                        max_requests=int(maxr),
                        year_from=nyf or None,
                        year_to=nyt or None,
                        refresh=nref,
                        cache_ttl_days=s.cache_ttl_days,
                    ),
                    progress=lambda m: box.write(f"取得: {m}"),
                )
                box.update(
                    label=BADGE.get(out.status, out.status),
                    state="complete" if out.status == "success" else "error",
                )
            st.session_state["job_id"] = out.job_id
            st.write(
                f"論文 {out.papers} / 新規エッジ {out.edges} / APIリクエスト {out.requests}"
                f" / キャッシュ利用 {out.cache_hits}"
            )
            if out.truncated:
                st.warning(f"上限により打ち切り: {out.truncation_reason}（全件ではありません）")
            if out.incomplete_lists:
                st.warning("未取得または不完全なリスト: " + ", ".join(out.incomplete_lists))
            for err in out.errors:
                show_error(err)
        except PNError as e:
            show_error(e)
    jobs = [j for j in list_jobs(ctx.db, 100) if j["kind"] == "network"]
    if jobs:
        ids = [j["id"] for j in jobs]
        cur = st.session_state.get("job_id")
        jid = st.selectbox(
            "表示するジョブ",
            ids,
            index=ids.index(cur) if cur in ids else 0,
            format_func=lambda i: next(
                f"#{j['id']} {j['query']} [{j['status']}] {j['started_at']}"
                for j in jobs
                if j["id"] == i
            ),
        )
        g = load_job_graph(ctx.db, jid)
        years = [a["year"] for _, a in g.nodes(data=True) if a.get("year")]
        c1, c2, c3 = st.columns(3)
        if years and min(years) < max(years):
            yr = c1.slider("出版年フィルタ", min(years), max(years), (min(years), max(years)))
        else:
            yr = (None, None)
        roles = c2.multiselect(
            "表示する役割",
            list(ROLE_STYLE),
            list(ROLE_STYLE),
            format_func=lambda r: str(ROLE_STYLE[r]["label"]),
        )
        maxd = c3.number_input("最大階層", 0, 5, 5)
        fg = filter_graph(
            g, GraphFilter(year_from=yr[0], year_to=yr[1], max_depth=int(maxd), roles=tuple(roles))
        )
        summ = graph_summary(fg)
        st.caption(
            f"表示: ノード {summ['nodes']} / エッジ {summ['edges']} / 循環あり: "
            f"{summ['has_cycle']} / ジョブ状態: {summ['status']}"
            + (f" / 打ち切り: {summ['truncation_reason']}" if summ["truncated"] else "")
        )
        st.caption("矢印 A → B は「論文Aが論文Bを引用」。ノードをクリックすると右側に詳細を表示。")
        if fg.number_of_nodes() > 1500:
            st.warning("ノード数が多いため描画に時間がかかります。フィルタで絞り込んでください。")
        html = render_html(fg)
        # Our own template; untrusted metadata is JSON-escaped and rendered via textContent.
        st.iframe(html, height=720)
        if st.button("エクスポート (HTML/JSON/GraphML/CSV)"):
            paths = export_all(ctx.db, fg, ctx.settings.export_dir, f"network_job{jid}")
            for k, p in paths.items():
                st.download_button(
                    f"{k} をダウンロード",
                    Path(p).read_bytes(),
                    file_name=Path(p).name,
                    key=f"dl_{k}",
                )
        st.session_state["graph_nodes"] = {a["label"]: n for n, a in fg.nodes(data=True)}
    else:
        st.info("まだ引用ネットワークがありません。")

# ---- detail ----------------------------------------------------------------------------
with tab_detail:
    nodes = st.session_state.get("graph_nodes", {})
    pick = st.selectbox("グラフ内の論文", [""] + sorted(nodes)) if nodes else ""
    ident = st.text_input("または Bibcode / DOI / #id", "")
    target = ident or (f"#{nodes[pick]}" if pick else "")
    if target:
        d = paper_detail(ctx.db, target)
        if d is None:
            st.warning("ローカルDBに該当レコードがありません（先に検索してください）。")
        else:
            st.subheader(d["title"] or "（タイトル未取得）")
            st.write("**著者:** " + ("; ".join(d["authors"]) or "（未取得）"))
            cols = st.columns(4)
            cols[0].metric("出版年", d["year"] or "未取得")
            cols[1].write(
                f"**雑誌:** {d['pub'] or '未取得'}  \n**巻/号/頁:** "
                f"{d['volume'] or '-'} / {d['issue'] or '-'} / {d['page'] or '-'}"
            )
            cols[2].write(f"**DOI:** {d['doi'] or '未取得'}  \n**Bibcode:** {d['bibcode'] or '-'}")
            cols[3].write(
                f"**取得元:** {d['source']}  \n**取得日時:** {d['retrieved_at']}  \n"
                f"**状態:** {d['validation_status']}"
            )
            if d["missing_fields"]:
                st.warning("欠落フィールド: " + ", ".join(d["missing_fields"]))
            for name, url in d["links"].items():
                st.link_button(name, url)
            if not d["links"]:
                st.caption("外部リンクなし")
            st.text_area(
                "Abstract", d["abstract"] or "（Abstract未取得）", height=180, disabled=True
            )
            st.write(
                "**Zotero登録状態:**",
                ", ".join(
                    f"{z['key']} (key={z['citation_key']}, by {z['matched_by']})"
                    for z in d["zotero"]
                )
                or "未リンク（Zotero同期で確認）",
            )

# ---- zotero / bibtex -------------------------------------------------------------------
with tab_zot:
    st.subheader("Zotero Local API")
    if st.button("接続状態を確認"):
        st.session_state["zst"] = ctx.zotero().status()
    zst = st.session_state.get("zst")
    if zst:
        icon = {
            "unavailable": "❌",
            "local_api_disabled": "⛔",
            "read_only": "📖",
            "write_needs_authorization": "🔐",
            "read_write": "✅",
        }[zst.state]
        st.write(f"{icon} **{zst.state}** — Zotero {zst.zotero_version or '?'}")
        st.caption(zst.message)
        if zst.reachable and zst.api_enabled:
            try:
                zcols = ctx.zotero().collections()
                ck = st.selectbox(
                    "コレクション",
                    [c["key"] for c in zcols],
                    format_func=lambda k: next(
                        f"{c['name']} ({k})" for c in zcols if c["key"] == k
                    ),
                )
                if ck and st.button("このコレクションをローカルDBと照合（Zoteroは変更しない）"):
                    rep = sync_collection(ctx.db, ctx.zotero(), ck)
                    st.write(
                        f"項目 {rep.items} / リンク {rep.linked} / DB未登録 "
                        f"{len(rep.not_in_db)} / 引用キー無し {len(rep.missing_citation_keys)}"
                    )
                    if rep.mismatches:
                        st.dataframe(rep.mismatches, hide_index=True)
            except PNError as e:
                show_error(e)
    st.divider()
    st.subheader("Better BibTeX .bib 検証")
    bibp = st.text_input("自動エクスポートされた .bib のパス", "examples/apj/references.bib")
    if st.button("検証する"):
        p = Path(bibp).expanduser()
        if p.suffix != ".bib" or not p.is_file():
            st.error("[INPUT_ERROR] .bib ファイルが見つかりません")
        else:
            brep = check_bib(p)
            st.write(
                ("✅ エラーなし" if brep.ok else "❌ エラーあり")
                + f" — entries {brep.entries}, errors {brep.count('error')}, "
                f"warnings {brep.count('warning')}, info {brep.count('info')}"
            )
            st.dataframe(
                [
                    {
                        "severity": i.severity,
                        "code": i.code,
                        "key": i.key,
                        "line": i.line,
                        "message": i.message,
                    }
                    for i in brep.issues
                ],
                hide_index=True,
                width="stretch",
            )

# ---- ApJ references --------------------------------------------------------------------
with tab_ref:
    st.markdown(
        "`.bib` は書誌データ（Zotero + Better BibTeX）、`.bst` は書式（AAS公式 "
        "`aasjournalv7*.bst`）、AASTeXクラスは文書構造です。本システムはApJ書式を"
        "独自生成せず、公式スタイルでBibTeX/LaTeXコンパイルします。投稿規定全体への"
        "適合は保証しません。"
    )
    texp = st.text_input(".tex", "examples/apj/sample_apj.tex")
    bibp2 = st.text_input(".bib", "examples/apj/references.bib", key="bib2")
    sdir = st.text_input("AASTeXスタイルのディレクトリ", "vendor/aastex")
    if st.button("引用キー整合チェック + コンパイル"):
        tp, bp = Path(texp).expanduser(), Path(bibp2).expanduser()
        if not (tp.is_file() and tp.suffix == ".tex" and bp.is_file() and bp.suffix == ".bib"):
            st.error("[INPUT_ERROR] .tex / .bib ファイルを確認してください")
        else:
            cr = check_citations([tp], check_bib(bp).keys)
            if cr.missing:
                st.error("未定義の引用キー: " + ", ".join(cr.missing))
            else:
                st.success(f"引用キー {len(cr.cited)} 件すべて .bib に存在")
            try:
                with st.spinner("pdflatex → bibtex → pdflatex ×2"):
                    br = build(tp, [bp], [Path(sdir)], ctx.settings.export_dir / "apj")
                st.write(
                    ("✅ コンパイル成功" if br.success else "❌ コンパイル失敗")
                    + (" / 警告なし" if br.clean else " / 警告あり")
                )
                st.json(
                    {
                        "class": br.class_file,
                        "bst": br.bst_file,
                        "error": br.error,
                        "undefined_citations": br.undefined_citations,
                        "bibtex_warnings": br.bibtex_warnings,
                        "bibtex_errors": br.bibtex_errors,
                        "commands": br.commands,
                    }
                )
                if br.pdf:
                    st.download_button("PDF", br.pdf.read_bytes(), file_name=br.pdf.name)
                if br.bbl:
                    st.code(br.bbl.read_text()[:4000], language="latex")
            except PNError as e:
                show_error(e)
