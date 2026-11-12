import pytest

from paper_navigator.ads.query import (
    InputKind,
    build_search_query,
    citations_query,
    detect_input,
    references_query,
)
from paper_navigator.errors import ErrorCode, PNError
from paper_navigator.normalize import (
    normalize_arxiv,
    normalize_bibcode,
    normalize_doi,
    normalize_title,
    split_author,
    title_similarity,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.1086/146579", "10.1086/146579"),
        ("https://doi.org/10.1007/S11207-011-9841-3", "10.1007/s11207-011-9841-3"),
        ("doi: 10.5555/ABC.", "10.5555/abc"),
        ("http://dx.doi.org/10.5555/x", "10.5555/x"),
        ("not a doi", None),
        ("10.12/too-short-prefix", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


@pytest.mark.parametrize(
    "raw,ok",
    [
        ("1998ApJ...509..678G", True),
        ("2012SoPh..275....3P", True),
        ("2020A&A...641A...6P", True),
        (" 1998ApJ...509..678G ", True),
        ("1998ApJ...509..678", False),  # 18 chars
        ("Solar flares review", False),
    ],
)
def test_normalize_bibcode(raw, ok):
    assert (normalize_bibcode(raw) is not None) == ok


def test_bibcode_case_preserved():
    assert normalize_bibcode("1998ApJ...509..678G") == "1998ApJ...509..678G"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("arXiv:2101.01234v2", "2101.01234"),
        ("2101.0123", "2101.0123"),
        ("astro-ph/0601001v1", "astro-ph/0601001"),
        ("https://arxiv.org/abs/2101.01234", "2101.01234"),
        ("arXiv:foo", None),
    ],
)
def test_normalize_arxiv(raw, expected):
    assert normalize_arxiv(raw) == expected


def test_title_normalization_and_similarity():
    assert (
        normalize_title(r"The {\it Solar} Dynamics Observatory (SDO)")
        == "the solar dynamics observatory sdo"
    )
    assert normalize_title("Ångström-scale café") == "angstrom scale cafe"
    assert title_similarity("Coronal Loops I", "coronal loops i.") == 1.0
    assert title_similarity("A", None) == 0.0


def test_split_author():
    assert split_author("Parker, E. N.") == ("Parker", "E. N.")
    assert split_author("Collaboration XYZ") == ("Collaboration XYZ", None)


def test_detect_input_kinds():
    assert detect_input("10.5555/test.1").kind == InputKind.DOI
    assert detect_input("2001TEST....1....1A").kind == InputKind.BIBCODE
    assert detect_input("arXiv:2101.01234").kind == InputKind.ARXIV
    assert detect_input("  coronal   heating ").value == "coronal heating"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 501, "a\x00b"])
def test_detect_input_rejects(bad):
    with pytest.raises(PNError) as e:
        detect_input(bad)
    assert e.value.code == ErrorCode.INPUT_ERROR


def test_forced_kind_validation():
    with pytest.raises(PNError):
        detect_input("hello", InputKind.DOI)


def test_query_building_escapes_quotes():
    q = build_search_query(detect_input('solar "wind" \\ test'))
    assert q == 'title:"solar \\"wind\\" \\\\ test"'
    assert (
        build_search_query(detect_input("10.5555/test.1"), 2000, 2010)
        == 'doi:"10.5555/test.1" year:[2000 TO 2010]'
    )


def test_reference_and_citation_query_semantics():
    # references(X): papers X cites.  citations(X): papers citing X.
    assert references_query("2001TEST....1....1A") == 'references(bibcode:"2001TEST....1....1A")'
    assert (
        citations_query("2001TEST....1....1A", 2005)
        == 'citations(bibcode:"2001TEST....1....1A") year:[2005 TO *]'
    )
    with pytest.raises(PNError):
        build_search_query(detect_input("x"), 2010, 2000)
