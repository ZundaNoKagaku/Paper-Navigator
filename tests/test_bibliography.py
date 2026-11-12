import shutil
from pathlib import Path

import pytest

from paper_navigator.bibliography.bibcheck import check_bib, compare_with_snapshot, save_snapshot
from paper_navigator.bibliography.cites import check_citations, extract_citations
from paper_navigator.bibliography.latex import build, tool_available

from .conftest import FIXTURES

ROOT = Path(__file__).parent.parent
BIB = FIXTURES / "bib"
VENDOR = ROOT / "vendor" / "aastex"


def codes(rep):
    return [(i.code, i.key) for i in rep.issues]


def test_good_bib_has_no_errors():
    rep = check_bib(BIB / "good.bib")
    assert rep.ok, [i for i in rep.issues if i.severity == "error"]
    assert rep.entries == 5 and "corrales2015" in rep.keys
    assert rep.doi_to_key["10.1088/0004-637x/805/1/23"] == "corrales2015"


def test_bad_bib_detects_every_defect():
    rep = check_bib(BIB / "bad.bib")
    c = codes(rep)
    assert ("DUPLICATE_KEY", "peter2014a") in c
    assert ("DUPLICATE_DOI", "peter2014b") in c
    assert ("INVALID_DOI", "nojournal2016") in c
    assert ("MISSING_REQUIRED", "nojournal2016") in c
    assert ("BAD_KEY_CHARS", "bad key") in c
    assert ("UNBALANCED_BRACES", "unbalanced2019") in c
    assert ("UNESCAPED_SPECIAL", "peter2014b") in c
    assert ("NON_ASCII", "unicode2018") in c
    assert any(code == "STRAY_AT" for code, _ in c)
    assert any(code == "SAME_AUTHOR_YEAR" for code, _ in c)
    assert not rep.ok


def test_unicode_preserved_file_not_modified(tmp_path):
    p = tmp_path / "u.bib"
    shutil.copy(BIB / "bad.bib", p)
    before = p.read_bytes()
    check_bib(p)
    assert p.read_bytes() == before


def test_non_utf8_reported(tmp_path):
    p = tmp_path / "latin1.bib"
    p.write_bytes("@article{k, title={caf\xe9}}".encode("latin-1"))
    assert codes(check_bib(p)) == [("ENCODING", None)]


def test_snapshot_detects_key_change(tmp_path):
    snap = tmp_path / "snap.json"
    rep = check_bib(BIB / "good.bib")
    save_snapshot(rep, snap)
    assert compare_with_snapshot(rep, snap) == []
    changed = tmp_path / "changed.bib"
    changed.write_text((BIB / "good.bib").read_text().replace("corrales2015", "corrales2015x"))
    issues = compare_with_snapshot(check_bib(changed), snap)
    assert {i.code for i in issues} == {"KEY_CHANGED", "KEY_REMOVED"}


def test_extract_citations_variants():
    keys = extract_citations((FIXTURES / "tex" / "paper.tex").read_text())
    assert set(keys) == {
        "astropycollaboration2013",
        "corrales2015",
        "bertin1996",
        "cloutier2018",
        "lamport1994",
        "peter2099",
        "alsomissing",
    }
    assert "commentedout" not in keys


def test_check_citations_missing_and_unused():
    bib = check_bib(BIB / "good.bib")
    rep = check_citations([FIXTURES / "tex" / "paper.tex"], bib.keys)
    assert rep.missing == ["alsomissing", "peter2099"] and not rep.ok
    assert rep.unused == []
    rep2 = check_citations([ROOT / "examples" / "apj" / "sample_apj.tex"], bib.keys)
    assert rep2.ok and rep2.unused == []


needs_latex = pytest.mark.skipif(
    not (tool_available("pdflatex") and tool_available("bibtex") and VENDOR.is_dir()),
    reason="pdflatex/bibtex or vendor/aastex missing (run scripts/fetch_aastex.sh)",
)


@pytest.mark.latex
@needs_latex
def test_apj_sample_compiles_with_official_style(tmp_path):
    rep = build(
        ROOT / "examples/apj/sample_apj.tex",
        [ROOT / "examples/apj/references.bib"],
        [VENDOR],
        tmp_path,
    )
    assert rep.success, rep.error
    assert rep.clean, (rep.bibtex_errors, rep.bibtex_warnings, rep.undefined_citations)
    assert rep.bst_file.endswith("aasjournalv7.bst")
    bbl = rep.bbl.read_text()
    assert r"\bibitem" in bbl and "corrales2015" in bbl and r"\dodoi{10.1088" in bbl


@pytest.mark.latex
@needs_latex
def test_apj_build_reports_undefined_citation(tmp_path):
    tex = tmp_path / "broken.tex"
    tex.write_text(
        (ROOT / "examples/apj/sample_apj.tex")
        .read_text()
        .replace(r"\citet{corrales2015}", r"\citet{doesnotexist2020}")
    )
    rep = build(tex, [ROOT / "examples/apj/references.bib"], [VENDOR], tmp_path / "out")
    assert rep.success  # LaTeX still produces a PDF ...
    assert not rep.clean  # ... but the problem is surfaced
    assert "doesnotexist2020" in rep.undefined_citations
    assert any("doesnotexist2020" in w for w in rep.bibtex_warnings)


@pytest.mark.latex
@needs_latex
def test_apj_build_missing_style_reported(tmp_path):
    tex = tmp_path / "x.tex"
    tex.write_text(
        (ROOT / "examples/apj/sample_apj.tex")
        .read_text()
        .replace("aasjournalv7}", "nonexistentstyle}")
    )
    rep = build(tex, [ROOT / "examples/apj/references.bib"], [VENDOR], tmp_path / "o")
    assert not rep.success and "nonexistentstyle.bst not found" in rep.error


@pytest.mark.latex
@needs_latex
def test_apj_build_with_missing_doi_still_builds(tmp_path):
    bib = tmp_path / "references.bib"
    bib.write_text(
        (ROOT / "examples/apj/references.bib")
        .read_text()
        .replace("doi = {10.1088/0004-637X/805/1/23},", "")
    )
    v = check_bib(bib)
    assert ("MISSING_RECOMMENDED", "corrales2015") in codes(v)
    rep = build(ROOT / "examples/apj/sample_apj.tex", [bib], [VENDOR], tmp_path / "o")
    assert rep.success
