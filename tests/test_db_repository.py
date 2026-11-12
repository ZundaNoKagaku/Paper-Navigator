import json

import pytest
from sqlalchemy import inspect, select, text

from paper_navigator.ads.mapping import ads_doc_to_record
from paper_navigator.db import LATEST_VERSION, Database, current_version, migrate
from paper_navigator.errors import ErrorCode, PNError
from paper_navigator.models import Base, CitationEdge, DuplicateCandidate, Paper
from paper_navigator.records import PaperRecord
from paper_navigator.repository import add_edge, find_paper, upsert_paper

from .conftest import bib, doc


def test_migrations_create_schema_matching_orm(db: Database):
    assert current_version(db.engine) == LATEST_VERSION
    insp = inspect(db.engine)
    for table in Base.metadata.sorted_tables:
        db_cols = {c["name"] for c in insp.get_columns(table.name)}
        assert db_cols == {c.name for c in table.columns}, table.name


def test_migrate_is_idempotent(db: Database):
    assert migrate(db.engine) == []


def test_newer_schema_refused(db: Database):
    with db.engine.begin() as c:
        c.execute(text("INSERT INTO schema_migrations VALUES (999, 'future', 'x')"))
    with pytest.raises(PNError) as e:
        migrate(db.engine)
    assert e.value.code == ErrorCode.DATABASE_ERROR


def test_upsert_creates_and_preserves_author_order(db: Database):
    rec = ads_doc_to_record(doc(1, author=["Zeta, Z.", "Alpha, A.", "Mid, M."]))
    with db.session() as s:
        r = upsert_paper(s, rec)
        assert r.created
    with db.session() as s:
        p = find_paper(s, bib(1))
        assert p.author_names == ["Zeta, Z.", "Alpha, A.", "Mid, M."]
        assert p.authors[0].family == "Zeta" and p.authors[0].given == "Z."
        assert json.loads(p.missing_fields) == []


def test_dedup_by_doi_bibcode_and_arxiv(db: Database):
    with db.session() as s:
        a = upsert_paper(s, ads_doc_to_record(doc(1))).paper.id
        # same DOI, different (alternate) bibcode -> same paper
        b = upsert_paper(
            s,
            PaperRecord(
                source="zotero", doi="https://doi.org/10.5555/TEST.1", bibcode="2000arXiv0001.0001X"
            ),
        ).paper.id
        assert a == b
        # alternate bibcode now resolves to the same paper
        c = upsert_paper(s, PaperRecord(source="x", bibcode="2000arXiv0001.0001X")).paper.id
        assert c == a
        d = upsert_paper(s, PaperRecord(source="x", arxiv_id="0001.00010", title="t")).paper.id
        e = upsert_paper(s, PaperRecord(source="x", arxiv_id="0001.00010")).paper.id
        assert d == e
        assert s.scalar(select(Paper).where(Paper.id == a)).title.startswith("Synthetic")
    with db.session() as s:
        assert len(s.scalars(select(Paper)).all()) == 2


def test_none_does_not_erase_known_values(db: Database):
    with db.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1)))
        upsert_paper(s, PaperRecord(source="ads", bibcode=bib(1)))
    with db.session() as s:
        p = find_paper(s, bib(1))
        assert p.title and p.year == 2001 and p.doi == "10.5555/test.1"


def test_similar_titles_become_candidates_not_merged(db: Database):
    with db.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1, title=["Coronal loop heating I"])))
        r = upsert_paper(
            s, ads_doc_to_record(doc(2, title=["Coronal loop heating I."], author=["Author1, A."]))
        )
        assert r.created and r.candidates == 1
        # different first author -> no candidate even with identical title
        r2 = upsert_paper(
            s, ads_doc_to_record(doc(3, title=["Coronal loop heating I"], author=["Other, O."]))
        )
        assert r2.candidates == 0
    with db.session() as s:
        assert len(s.scalars(select(Paper)).all()) == 3
        cands = s.scalars(select(DuplicateCandidate)).all()
        assert len(cands) == 1 and cands[0].status == "pending"


def test_identifier_conflict_recorded_not_merged(db: Database):
    with db.session() as s:
        p1 = upsert_paper(s, ads_doc_to_record(doc(1))).paper.id
        p2 = upsert_paper(s, ads_doc_to_record(doc(2))).paper.id
        r = upsert_paper(s, PaperRecord(source="x", doi="10.5555/test.1", bibcode=bib(2)))
        assert r.conflict and r.paper.id == p1  # DOI has priority
        cand = s.scalars(select(DuplicateCandidate)).one()
        assert {cand.paper_a, cand.paper_b} == {p1, p2}
        assert cand.reason == "identifier_conflict"


def test_edges_unique_and_directed(db: Database):
    with db.session() as s:
        a = upsert_paper(s, ads_doc_to_record(doc(1))).paper.id
        b = upsert_paper(s, ads_doc_to_record(doc(2))).paper.id
        assert add_edge(s, a, b, source="ads", job_id=None, source_query="q")
        assert not add_edge(s, a, b, source="ads", job_id=None, source_query="q")
        assert add_edge(s, b, a, source="ads", job_id=None, source_query="q")  # cycle allowed
    with db.session() as s:
        assert len(s.scalars(select(CitationEdge)).all()) == 2


def test_rollback_on_error_leaves_db_unchanged(db: Database):
    with pytest.raises(PNError) as e, db.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1)))
        s.add(
            Paper(
                source="x",
                retrieved_at="t",
                validation_status="INVALID",
                created_at="t",
                updated_at="t",
            )
        )
        s.flush()  # violates CHECK -> IntegrityError -> DATABASE_ERROR
    assert e.value.code == ErrorCode.DATABASE_ERROR
    with db.session() as s:
        assert s.scalars(select(Paper)).all() == []


def test_foreign_keys_enforced(db: Database):
    with pytest.raises(PNError), db.session() as s:
        add_edge(s, 999, 998, source="ads", job_id=None, source_query=None)


def test_persistence_across_restart(tmp_path):
    path = tmp_path / "persist.sqlite3"
    d1 = Database(path)
    with d1.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1)))
    d1.engine.dispose()
    d2 = Database(path)
    with d2.session() as s:
        assert find_paper(s, "10.5555/test.1").bibcode == bib(1)
        assert find_paper(s, "#1") is not None


def test_stale_running_jobs_marked_interrupted(db: Database):
    from paper_navigator.models import RetrievalJob
    from paper_navigator.repository import mark_stale_jobs, start_job

    with db.session() as s:
        old = start_job(s, "network", "q", {})
        old.started_at = "2000-01-01T00:00:00+00:00"
        fresh = start_job(s, "network", "q", {})
        ids = (old.id, fresh.id)
    with db.session() as s:
        assert mark_stale_jobs(s) == 1
    with db.session() as s:
        o, f = (s.get(RetrievalJob, i) for i in ids)
        assert (o.status, o.error_code) == ("failed", "INTERRUPTED") and o.finished_at
        assert f.status == "running"  # a job started just now is not touched


def test_backup_is_consistent_copy(db: Database, tmp_path):
    with db.session() as s:
        upsert_paper(s, ads_doc_to_record(doc(1)))
    dest = db.backup(tmp_path / "bk")
    restored = Database(dest)
    with restored.session() as s:
        assert find_paper(s, bib(1)) is not None


def test_upgrade_from_v1_database(tmp_path):
    """A DB created by v0.1.0 (schema v1 only) is upgraded in place to v2, data kept."""
    from paper_navigator.db import MIGRATIONS, make_engine

    path = tmp_path / "old.sqlite3"
    eng = make_engine(path)
    with eng.begin() as c:
        c.execute(
            text(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
                "description TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
        )
        for stmt in MIGRATIONS[0][2]:
            c.execute(text(stmt))
        c.execute(text("INSERT INTO schema_migrations VALUES (1, 'initial schema', 't')"))
        c.execute(
            text(
                "INSERT INTO papers (title, source, retrieved_at, validation_status, "
                "created_at, updated_at, bibcode) VALUES ('Old', 'ads', 't', "
                "'complete', 't', 't', '2001TEST....1....1A')"
            )
        )
    eng.dispose()
    d = Database(path)
    assert current_version(d.engine) == 2
    idx = {
        r[0]
        for r in d.engine.connect().execute(
            text("SELECT name FROM sqlite_master WHERE type='index'")
        )
    }
    assert {"ix_papers_year", "ix_authors_family"} <= idx
    with d.session() as s:
        assert find_paper(s, "2001TEST....1....1A").title == "Old"
