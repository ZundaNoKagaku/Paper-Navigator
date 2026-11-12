"""System/acceptance tests: Streamlit UI (headless AppTest) and the `pn` CLI.
ADS is the in-memory fake (mock); no live network is used."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paper_navigator.app import AppContext
from paper_navigator.cli import main
from paper_navigator.config import load_settings
from paper_navigator.db import Database

from .conftest import TOKEN, FakeADS, bib, doc

ROOT = Path(__file__).parent.parent
APP = str(ROOT / "src" / "paper_navigator" / "ui" / "streamlit_app.py")


class FakeCtx(AppContext):
    fake: FakeADS | None = None

    def ads(self):  # type: ignore[override]
        return self.fake.client() if self.fake else None


def _ctx(tmp_path: Path, fake: FakeADS | None) -> FakeCtx:
    s = load_settings(
        env={"PN_DB_PATH": str(tmp_path / "ui.sqlite3"), "PN_EXPORT_DIR": str(tmp_path / "exp")},
        dotenv=None,
    )
    c = FakeCtx(settings=s, db=Database(s.db_path))
    c.fake = fake
    return c


def _world() -> FakeADS:
    f = FakeADS()
    f.add(*[doc(i, year=2000 + i) for i in range(1, 6)])
    f.cite(bib(1, 2001), bib(2, 2002), bib(3, 2003))
    f.cite(bib(4, 2004), bib(1, 2001))
    return f


def _run(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_ui_without_token_shows_config_error_and_does_not_crash(tmp_path):
    at = AppTest.from_file(APP)
    at.session_state["ctx"] = _ctx(tmp_path, None)
    _run(at)
    assert any("未設定" in m.value for m in at.sidebar.markdown)
    at.text_input[0].input("coronal loops")
    at.button[0].click()  # form submit
    _run(at)
    assert any("CONFIG_ERROR" in e.value for e in at.error)


def test_ui_end_to_end_search_graph_detail_bib(tmp_path):
    ctx = _ctx(tmp_path, _world())
    at = AppTest.from_file(APP)
    at.session_state["ctx"] = ctx
    _run(at)
    # UC-01 search by bibcode
    at.text_input[0].input(bib(1, 2001))
    at.button[0].click()
    _run(at)
    assert any("成功" in h.value for h in at.subheader)
    assert len(at.dataframe) >= 1
    # choose seed
    next(b for b in at.button if "起点に設定" in b.label).click()
    _run(at)
    assert at.session_state["seed"] == bib(1, 2001)
    # UC-02 network (graph tab form submit)
    next(b for b in at.button if "引用ネットワークを作成" in b.label).click()
    _run(at)
    assert at.session_state["job_id"] is not None
    assert any("論文 4 " in m.value for m in at.markdown)  # seed + 2 refs + 1 citer
    assert "graph_nodes" in at.session_state
    # UC-03 detail via selectbox of graph nodes
    det = next(s for s in at.selectbox if s.label == "グラフ内の論文")
    det.select(det.options[1])
    _run(at)
    assert any("Synthetic paper" in h.value for h in at.subheader)
    # UC-05 bib check on the example bib
    next(b for b in at.button if b.label == "検証する").click()
    _run(at)
    assert any("エラーなし" in m.value for m in at.markdown)


def test_ui_shows_partial_status(tmp_path):
    import httpx

    f = _world()
    f.fail = lambda p, n: httpx.Response(500) if p["q"].startswith("citations") else None
    ctx = _ctx(tmp_path, f)
    ctx.fake.client = lambda **kw: FakeADS.client(f, max_retries=0)  # type: ignore[method-assign]
    at = AppTest.from_file(APP)
    at.session_state["ctx"] = ctx
    at.session_state["seed"] = bib(1, 2001)
    _run(at)
    next(b for b in at.button if "引用ネットワークを作成" in b.label).click()
    _run(at)
    assert any("NETWORK_ERROR" in e.value for e in at.error)
    assert any("不完全" in w.value for w in at.warning)


def _cli_env(tmp_path: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "ADS_API_TOKEN"}
    env.update(
        PN_DB_PATH=str(tmp_path / "cli.sqlite3"),
        PN_EXPORT_DIR=str(tmp_path / "x"),
        ZOTERO_BASE_URL="http://127.0.0.1:9",
    )  # nothing listens on port 9
    return env


def _pn(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "paper_navigator.cli", *args],
        cwd=ROOT,
        env=_cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_setup_from_empty_db_and_restart(tmp_path):
    r = _pn(tmp_path, "init-db")
    assert r.returncode == 0 and (tmp_path / "cli.sqlite3").exists()
    r = _pn(tmp_path, "search", "coronal loops")
    assert r.returncode == 1 and "CONFIG_ERROR" in r.stderr  # clear error, no traceback
    assert "Traceback" not in r.stderr
    r = _pn(tmp_path, "zotero-status")
    assert r.returncode == 1 and "unavailable" in r.stdout


def test_cli_bib_cite_apj(tmp_path):
    r = _pn(tmp_path, "bib-check", "tests/fixtures/bib/bad.bib")
    assert r.returncode == 1 and "DUPLICATE_KEY" in r.stdout
    r = _pn(
        tmp_path,
        "bib-check",
        "examples/apj/references.bib",
        "--snapshot",
        str(tmp_path / "snap.json"),
        "--accept",
    )
    assert r.returncode in (0, 2) and (tmp_path / "snap.json").exists()
    r = _pn(tmp_path, "cite-check", "examples/apj/references.bib", "tests/fixtures/tex/paper.tex")
    assert r.returncode == 1 and "MISSING peter2099" in r.stdout


@pytest.mark.latex
def test_cli_apj_build(tmp_path):
    from paper_navigator.bibliography.latex import tool_available

    if not (tool_available("pdflatex") and (ROOT / "vendor/aastex").is_dir()):
        pytest.skip("LaTeX or vendor/aastex not available")
    r = _pn(
        tmp_path,
        "apj-build",
        "examples/apj/sample_apj.tex",
        "--bib",
        "examples/apj/references.bib",
        "--out",
        str(tmp_path / "apj"),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "apj" / "sample_apj.pdf").exists()


def test_cli_network_with_fake_ads(tmp_path, monkeypatch, capsys):
    f = _world()
    monkeypatch.setenv("PN_DB_PATH", str(tmp_path / "n.sqlite3"))
    monkeypatch.setenv("ADS_API_TOKEN", TOKEN)
    monkeypatch.setattr(AppContext, "ads", lambda self: f.client())
    assert main(["network", bib(1, 2001), "--export-dir", str(tmp_path / "e")]) == 0
    out = capsys.readouterr().out
    assert "status=success" in out and "exported html" in out
    assert main(["show", bib(2, 2002), "--json"]) == 0
    assert TOKEN not in capsys.readouterr().out


def test_cli_backup(tmp_path):
    assert _pn(tmp_path, "init-db").returncode == 0
    r = _pn(tmp_path, "backup", "--dest", str(tmp_path / "bk"))
    assert r.returncode == 0 and list((tmp_path / "bk").glob("*.sqlite3"))
