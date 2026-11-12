"""Compile an AASTeX document with the official AAS BibTeX style and inspect the logs.

Responsibilities are kept separate (spec §6.3): the ``.bib`` holds bibliographic data
(from Zotero + Better BibTeX), the ``.bst`` (AAS ``aasjournalv7*.bst``) defines the
reference format, and the AASTeX class defines document structure. This module only runs
``pdflatex``/``bibtex`` — it never re-implements ApJ reference formatting and never edits
the official style files.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import ErrorCode, PNError

_CITE_UNDEF = re.compile(r"Citation [`'](.+?)' on page \S+ undefined")
_BLG_WARN = re.compile(r"^Warning--(.*)$", re.M)
_BLG_ERR = re.compile(r"^(.*)---line \d+ of file (.*)$", re.M)
_NO_ENTRY = re.compile(r'I didn\'t find a database entry for "(.+?)"')


@dataclass
class BuildReport:
    success: bool
    pdf: Path | None = None
    bbl: Path | None = None
    commands: list[str] = field(default_factory=list)
    undefined_citations: list[str] = field(default_factory=list)
    bibtex_warnings: list[str] = field(default_factory=list)
    bibtex_errors: list[str] = field(default_factory=list)
    latex_warnings: list[str] = field(default_factory=list)
    error: str | None = None
    tool_versions: dict[str, str] = field(default_factory=dict)
    class_file: str | None = None
    bst_file: str | None = None

    @property
    def clean(self) -> bool:
        return (
            self.success
            and not self.undefined_citations
            and not self.bibtex_errors
            and not self.bibtex_warnings
        )


def _first_error(log: Path) -> str:
    """First TeX error ('! ...') with a few following non-empty lines."""
    if not log.exists():
        return "no log produced"
    lines = log.read_text(errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("!"):
            ctx = [x.strip() for x in lines[i : i + 8] if x.strip()]
            return " ".join(ctx)[:400]
    return "see log"


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def _version(cmd: str) -> str:
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.splitlines()[0] if out.stdout else "?"
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _find_style(name: str, search: list[Path]) -> Path | None:
    for d in search:
        p = d / name
        if p.is_file():
            return p
    if tool_available("kpsewhich"):
        out = subprocess.run(["kpsewhich", name], capture_output=True, text=True, timeout=20)
        if out.stdout.strip():
            return Path(out.stdout.strip())
    return None


def _declared(tex: str) -> tuple[str | None, str | None]:
    cls = re.search(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}", tex)
    bst = re.search(r"\\bibliographystyle\{([^}]+)\}", tex)
    return (cls.group(1) + ".cls" if cls else None, bst.group(1) + ".bst" if bst else None)


def build(
    tex_path: Path,
    extra_files: list[Path],
    style_dirs: list[Path],
    out_dir: Path,
    timeout: int = 180,
) -> BuildReport:
    """pdflatex → bibtex → pdflatex → pdflatex in a scratch dir; copy PDF/BBL/logs out."""
    for tool in ("pdflatex", "bibtex"):
        if not tool_available(tool):
            raise PNError(ErrorCode.LATEX_BUILD_ERROR, f"{tool} not found on PATH")
    tex = tex_path.read_text(encoding="utf-8")
    cls_name, bst_name = _declared(tex)
    rep = BuildReport(
        success=False,
        tool_versions={"pdflatex": _version("pdflatex"), "bibtex": _version("bibtex")},
    )
    for name, attr in ((cls_name, "class_file"), (bst_name, "bst_file")):
        if name is None:
            continue
        found = _find_style(name, style_dirs)
        if found is None:
            rep.error = (
                f"style file {name} not found (run scripts/fetch_aastex.sh or install "
                "AASTeX from the AAS site)"
            )
            return rep
        setattr(rep, attr, str(found))
    stem = tex_path.stem
    with tempfile.TemporaryDirectory(prefix="pn-latex-") as tmp:
        work = Path(tmp)
        shutil.copy2(tex_path, work / tex_path.name)
        for f in extra_files:
            shutil.copy2(f, work / f.name)
        for attr in ("class_file", "bst_file"):
            src = getattr(rep, attr)
            if src and not (work / Path(src).name).exists():
                shutil.copy2(src, work / Path(src).name)  # byte-for-byte copy, unmodified
        steps = [
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            ["bibtex", stem],
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        ]
        for cmd in steps:
            rep.commands.append(" ".join(cmd))
            try:
                proc = subprocess.run(
                    cmd, cwd=work, capture_output=True, text=True, timeout=timeout, errors="replace"
                )
            except subprocess.TimeoutExpired:
                rep.error = f"timeout: {' '.join(cmd)}"
                break
            if proc.returncode != 0 and cmd[0] == "pdflatex":
                rep.error = f"pdflatex failed (exit {proc.returncode}): " + _first_error(
                    work / f"{stem}.log"
                )
                break
            if proc.returncode not in (0, 1, 2) and cmd[0] == "bibtex":
                # bibtex exits 1 on warnings, 2 on errors; both are parsed from the .blg
                rep.error = f"bibtex failed (exit {proc.returncode})"
                break
        blg = work / f"{stem}.blg"
        log = work / f"{stem}.log"
        if blg.exists():
            t = blg.read_text(errors="replace")
            rep.bibtex_warnings = [w.strip() for w in _BLG_WARN.findall(t)]
            rep.bibtex_errors = [f"{a.strip()} ({b.strip()})" for a, b in _BLG_ERR.findall(t)]
            rep.bibtex_warnings += [f"no database entry for {k}" for k in _NO_ENTRY.findall(t)]
        if log.exists():
            t = log.read_text(errors="replace")
            rep.undefined_citations = sorted(set(_CITE_UNDEF.findall(t)))
            rep.latex_warnings = sorted(
                {ln.strip() for ln in t.splitlines() if ln.startswith("LaTeX Warning")}
            )[:50]
        out_dir.mkdir(parents=True, exist_ok=True)
        for suffix in (".pdf", ".bbl", ".blg", ".log"):
            src = work / f"{stem}{suffix}"
            if src.exists():
                shutil.copy2(src, out_dir / src.name)
        pdf = out_dir / f"{stem}.pdf"
        rep.pdf = pdf if pdf.exists() and rep.error is None else None
        bbl = out_dir / f"{stem}.bbl"
        rep.bbl = bbl if bbl.exists() else None
        rep.success = rep.error is None and rep.pdf is not None
    return rep
