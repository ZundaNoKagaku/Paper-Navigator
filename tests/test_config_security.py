"""PN-SEC-001: secrets are masked, never logged, never stored; local-only defaults."""

import logging
import subprocess
from pathlib import Path

import pytest

from paper_navigator.config import Secret, load_settings, parse_dotenv
from paper_navigator.errors import ErrorCode, PNError
from paper_navigator.logging_utils import RedactingFilter, setup_logging

from .conftest import TOKEN, FakeADS, doc

ROOT = Path(__file__).parent.parent


def test_secret_masked_in_repr():
    s = Secret("abc123secret")
    assert "abc123secret" not in repr(s) and "abc123secret" not in str(s)
    st = load_settings(env={"ADS_API_TOKEN": "abc123secret"}, dotenv=None)
    assert "abc123secret" not in repr(st)


def test_dotenv_parsing_and_env_precedence(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# c\nADS_API_TOKEN='fromfile'\nexport PN_NETWORK_DEPTH=2\n\nBAD LINE\n")
    assert parse_dotenv(p) == {"ADS_API_TOKEN": "fromfile", "PN_NETWORK_DEPTH": "2"}
    s = load_settings(env={"ADS_API_TOKEN": "fromenv"}, dotenv=p)
    assert s.ads_token.get() == "fromenv" and s.network_depth == 2


def test_defaults_are_small_and_configurable():
    s = load_settings(env={}, dotenv=None)
    assert (s.network_depth, s.network_max_papers) == (1, 300)
    s2 = load_settings(env={"PN_NETWORK_MAX_PAPERS": "1000"}, dotenv=None)
    assert s2.network_max_papers == 1000


@pytest.mark.parametrize(
    "env",
    [
        {"PN_NETWORK_DEPTH": "x"},
        {"PN_NETWORK_DEPTH": "0"},
        {"ZOTERO_BASE_URL": "http://192.168.1.5:23119"},
        {"ZOTERO_BASE_URL": "http://127.0.0.1.evil.example:23119"},
        {"ZOTERO_BASE_URL": "https://localhost@evil.example/"},
    ],
)
def test_invalid_config_is_config_error(env):
    with pytest.raises(PNError) as e:
        load_settings(env=env, dotenv=None)
    assert e.value.code == ErrorCode.CONFIG_ERROR


def test_loopback_variants_accepted():
    for url in ("http://127.0.0.1:23119", "http://localhost:23119/", "http://[::1]:23119"):
        assert load_settings(env={"ZOTERO_BASE_URL": url}, dotenv=None).zotero_base_url


def test_missing_token_is_config_error():
    with pytest.raises(PNError) as e:
        load_settings(env={}, dotenv=None).require_ads_token()
    assert e.value.code == ErrorCode.CONFIG_ERROR


def test_redaction_patterns():
    f = RedactingFilter(["mysecretvalue"])
    for text in [
        "Authorization: Bearer abc.def-123",
        "headers={'Authorization': 'Bearer x1'}",
        "url?api_key=zzz&x=1",
        "token=qqq",
        "value mysecretvalue here",
        "Zotero-API-Key: kkk",
    ]:
        out = f.redact(text)
        for leaked in ("abc.def-123", "x1'", "zzz", "qqq", "mysecretvalue", "kkk"):
            assert leaked not in out


def test_no_secret_in_logs_during_retries(caplog):
    import httpx

    setup_logging("DEBUG", [TOKEN])
    fake = FakeADS()
    fake.add(doc(1))
    fake.fail = lambda p, n: httpx.Response(503) if n == 1 else None
    logger = logging.getLogger("paper_navigator")
    logger.addHandler(caplog.handler)
    from paper_navigator.logging_utils import get_redactor

    caplog.handler.addFilter(get_redactor())
    with caplog.at_level(logging.DEBUG, logger="paper_navigator"):
        fake.client(max_retries=2).search('doi:"10.5555/test.1"')
        logging.getLogger("paper_navigator.test").warning("Authorization: Bearer %s", TOKEN)
    assert caplog.records
    assert TOKEN not in caplog.text


def test_gitignore_covers_secrets_and_data():
    gi = (ROOT / ".gitignore").read_text()
    for pat in (".env", "data/", "*.sqlite3", "vendor/", "zotero_local_api_key"):
        assert pat in gi
    ex = (ROOT / ".env.example").read_text()
    assert "ADS_API_TOKEN=" in ex
    for line in ex.splitlines():
        if line.startswith("ADS_API_TOKEN="):
            assert line.strip() == "ADS_API_TOKEN="  # placeholder only, no value


def test_no_token_like_strings_in_tracked_sources():
    """Scan source/docs for bearer tokens or 40-char ADS-like secrets."""
    import re

    pat = re.compile(r"Bearer\s+[A-Za-z0-9]{20,}|['\"][A-Za-z0-9]{40}['\"]")
    hits = []
    for p in (
        list((ROOT / "src").rglob("*.py"))
        + list((ROOT / "docs").rglob("*.md"))
        + [ROOT / "README.md"]
    ):
        if p.exists() and pat.search(p.read_text(encoding="utf-8")):
            hits.append(str(p))
    assert hits == []


def test_streamlit_config_binds_loopback():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text()
    assert 'address = "127.0.0.1"' in cfg


def test_key_file_written_owner_only(tmp_path):
    from paper_navigator.app import read_key_file, write_key_file

    p = tmp_path / "k"
    write_key_file(p, "secret-key")
    assert oct(p.stat().st_mode & 0o777) == "0o600" and read_key_file(p) == "secret-key"


def test_git_check_ignore(tmp_path):
    if subprocess.run(["git", "-C", str(ROOT), "rev-parse"], capture_output=True).returncode:
        pytest.skip("not a git checkout")
    for f in (
        ".env",
        "data/paper_navigator.sqlite3",
        "data/zotero_local_api_key",
        "vendor/aastex/aastex701.cls",
    ):
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", f])
        assert r.returncode == 0, f
