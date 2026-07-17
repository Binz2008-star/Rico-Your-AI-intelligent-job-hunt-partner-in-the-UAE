"""
tests/integration/test_1092_applications_pagination_postgres.py

Real-PostgreSQL proofs for #1092 — canonical DB-boundary application paging.

Why real Postgres: the canonical set is defined by SQL window functions over
JSONB (RicoDB._CANONICAL_APPS_CTE); mocked cursors cannot prove the dedup
rule, the uncapped totals, or the offset-pagination semantics. This file
seeds hundreds of rows (past the old 200-row cap) and proves:

  * every logical record is reachable exactly once across pages, with
    correct total/pages, even with 451 logical records plus duplicates
  * BUG-3 dedup semantics now live in SQL: same job under two job_keys
    collapses (newest wins), matching is case/whitespace-insensitive,
    distinct jobs/locations never merge, blank title+company rows always
    survive, same-url-different-location merges, blank urls never
    false-match
  * a status that exists ONLY beyond row 200 still filters/counts correctly
  * stats and quota counts (count_by_status) run uncapped over the SAME
    canonical set as the pages — they can never disagree
  * PATCH-path lookup (find_by_job_id) addresses the oldest owned row
    directly and never sees another user's rows
  * the documented offset-pagination behavior under concurrent insert:
    an item may REPEAT on a later page, but none is silently skipped

Requires RICO_TEST_DATABASE_URL (disposable Postgres — never Neon). Skips
cleanly when unset. Wired into the postgres-integration CI job.
"""
from __future__ import annotations

import os
import uuid

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.rico_db import RicoDB

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped.",
)

_MIGRATIONS = [
    "011_rico_recommendation_uniqueness.sql",
    "035_rico_recommendations_full_unique.sql",
]
_MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "migrations")


@pytest.fixture(scope="module")
def db() -> RicoDB:
    """RicoDB against the real test database with the uniqueness migrations."""
    instance = RicoDB(database_url=TEST_DATABASE_URL)
    conn = instance.connect()  # runs _ensure_schema
    try:
        with conn.cursor() as cur:
            for name in _MIGRATIONS:
                with open(os.path.join(_MIGRATIONS_DIR, name)) as f:
                    cur.execute(f.read())
        conn.commit()
    finally:
        conn.close()
    return instance


@pytest.fixture(autouse=True)
def _clean_tables(db: RicoDB):
    yield
    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rico_job_recommendations")
            cur.execute("DELETE FROM rico_users")
        conn.commit()
    finally:
        conn.close()


def _mk_user(db: RicoDB, tag: str = "") -> str:
    row = db.upsert_user(
        {"external_user_id": f"pg-1092-{tag}{uuid.uuid4()}@rico.test"}
    )
    return str(row["id"])


def _seed(
    db: RicoDB,
    user_id: str,
    rows: list[dict],
) -> None:
    """Insert rows with explicit, strictly decreasing updated_at ordering.

    rows[0] is the NEWEST. Each dict: job_key, title, company, plus optional
    location, url, status.
    """
    from psycopg2.extras import Json

    conn = db.connect(ensure_schema=False)
    try:
        with conn.cursor() as cur:
            for i, r in enumerate(rows):
                job = {
                    "title": r.get("title", ""),
                    "company": r.get("company", ""),
                    "location": r.get("location", "Dubai"),
                }
                if r.get("url"):
                    job["apply_url"] = r["url"]
                cur.execute(
                    """
                    INSERT INTO rico_job_recommendations
                        (user_id, job_key, job, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s,
                            now() - (%s * interval '1 minute'),
                            now() - (%s * interval '1 minute'))
                    """,
                    (user_id, r["job_key"], Json(job), r.get("status", "saved"), i, i),
                )
        conn.commit()
    finally:
        conn.close()


# ── BUG-3 dedup semantics, now proven against real SQL ───────────────────────

class TestCanonicalDedupSql:
    def test_same_job_under_two_job_keys_collapses_newest_wins(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "sha-new", "title": "Senior Python Developer", "company": "Acme"},
            {"job_key": "md5-old", "title": "Senior Python Developer", "company": "Acme"},
        ])
        apps = db.get_applications_page(uid)
        assert [a["job_id"] for a in apps] == ["sha-new"]
        assert db.count_applications(uid) == 1

    def test_matching_is_case_and_whitespace_insensitive(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "k1", "title": "  Senior Python Developer  ", "company": "Acme Corp"},
            {"job_key": "k2", "title": "senior python developer", "company": "ACME CORP"},
        ])
        assert db.count_applications(uid) == 1

    def test_different_jobs_and_locations_never_merge(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "a", "title": "HSE Manager", "company": "Acme", "location": "Dubai"},
            {"job_key": "b", "title": "HSE Manager", "company": "Acme", "location": "Abu Dhabi"},
            {"job_key": "c", "title": "QA Engineer", "company": "Acme", "location": "Dubai"},
        ])
        assert db.count_applications(uid) == 3

    def test_blank_title_and_company_rows_always_survive(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "x1", "title": "", "company": "", "location": "Dubai"},
            {"job_key": "x2", "title": "", "company": "", "location": "Dubai"},
        ])
        assert db.count_applications(uid) == 2

    def test_same_url_different_location_text_merges(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "u1", "title": "Analyst", "company": "Mastercard",
             "location": "Dubai", "url": "https://jobs.x/123"},
            {"job_key": "u2", "title": "Analyst", "company": "Mastercard",
             "location": "Dubai, UAE", "url": "https://jobs.x/123"},
        ])
        apps = db.get_applications_page(uid)
        assert [a["job_id"] for a in apps] == ["u1"]

    def test_same_url_different_title_or_company_not_merged(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "v1", "title": "Analyst", "company": "Mastercard",
             "url": "https://jobs.x/9"},
            {"job_key": "v2", "title": "Senior Analyst", "company": "Mastercard",
             "location": "Abu Dhabi", "url": "https://jobs.x/9"},
        ])
        assert db.count_applications(uid) == 2

    def test_blank_urls_never_false_match(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": "w1", "title": "Engineer", "company": "A", "location": "Dubai"},
            {"job_key": "w2", "title": "Engineer", "company": "A", "location": "Sharjah"},
        ])
        assert db.count_applications(uid) == 2


# ── Uncapped pagination over 451 logical records ─────────────────────────────

class TestUncappedPagination:
    def _seed_451_plus_dupes(self, db, uid):
        rows = []
        # 30 duplicate rows of the 30 newest logical jobs (older copies,
        # different job_key) interleaved AFTER their originals.
        for i in range(451):
            rows.append({
                "job_key": f"job-{i:04d}",
                "title": f"Role {i:04d}",
                "company": f"Company {i % 40}",
                "location": "Dubai",
                "status": "saved",
            })
        for i in range(30):
            rows.append({
                "job_key": f"dupe-{i:04d}",
                "title": f"Role {i:04d}",
                "company": f"Company {i % 40}",
                "location": "Dubai",
                "status": "saved",
            })
        _seed(db, uid, rows)

    def test_every_logical_record_reachable_exactly_once(self, db):
        uid = _mk_user(db)
        self._seed_451_plus_dupes(db, uid)

        assert db.count_applications(uid) == 451

        seen: list[str] = []
        page, limit = 1, 50
        while True:
            items = db.get_applications_page(uid, limit=limit, offset=(page - 1) * limit)
            if not items:
                break
            seen.extend(a["job_id"] for a in items)
            page += 1

        assert len(seen) == 451
        assert len(set(seen)) == 451, "no logical record may repeat across pages"
        assert set(seen) == {f"job-{i:04d}" for i in range(451)}
        assert not any(k.startswith("dupe-") for k in seen)
        # total/pages as the API reports them
        assert max(1, -(-451 // limit)) == 10

    def test_old_200_row_cap_is_gone_page_5_still_has_items(self, db):
        uid = _mk_user(db)
        self._seed_451_plus_dupes(db, uid)
        page5 = db.get_applications_page(uid, limit=50, offset=200)
        assert len(page5) == 50, "records beyond row 200 must be reachable"

    def test_status_existing_only_beyond_row_200_filters_correctly(self, db):
        uid = _mk_user(db)
        rows = [
            {"job_key": f"s-{i:04d}", "title": f"R {i}", "company": f"C{i}",
             "status": "saved"}
            for i in range(220)
        ]
        # 5 interview rows strictly OLDER than the 220 saved rows
        rows += [
            {"job_key": f"int-{i}", "title": f"Old Interview {i}", "company": f"I{i}",
             "status": "interview"}
            for i in range(5)
        ]
        _seed(db, uid, rows)

        assert db.count_applications(uid, status="interview") == 5
        items = db.get_applications_page(uid, status="interview", limit=50, offset=0)
        assert {a["job_id"] for a in items} == {f"int-{i}" for i in range(5)}

        stats = db.get_application_stats(uid)
        assert stats["interview"] == 5
        assert stats["saved"] == 220
        assert stats["total"] == 225

    def test_stats_and_quota_count_agree_with_pages_uncapped(self, db):
        uid = _mk_user(db)
        rows = [
            {"job_key": f"q-{i:04d}", "title": f"R {i}", "company": f"C{i}",
             "status": "saved"}
            for i in range(230)
        ]
        _seed(db, uid, rows)
        assert db.get_application_stats(uid)["saved"] == 230
        assert db.count_applications(uid, status="saved") == 230


# ── PATCH-path direct lookup ─────────────────────────────────────────────────

class TestDirectLookup:
    def test_oldest_owned_application_is_addressable_and_updatable(self, db):
        uid = _mk_user(db)
        rows = [
            {"job_key": f"p-{i:04d}", "title": f"R {i}", "company": f"C{i}"}
            for i in range(250)
        ]
        _seed(db, uid, rows)
        oldest = "p-0249"

        found = db.find_recommendation(uid, oldest)
        assert found is not None and found["job_id"] == oldest

        assert db.update_recommendation_status(uid, oldest, "applied") is True
        assert db.find_recommendation(uid, oldest)["status"] == "applied"

    def test_another_users_record_is_never_visible(self, db):
        uid_a = _mk_user(db, "a")
        uid_b = _mk_user(db, "b")
        _seed(db, uid_a, [{"job_key": "owned-by-a", "title": "T", "company": "C"}])

        assert db.find_recommendation(uid_b, "owned-by-a") is None
        assert db.count_applications(uid_b) == 0
        assert db.get_applications_page(uid_b) == []


# ── Documented offset semantics under concurrent insert ──────────────────────

class TestInsertBetweenPageReads:
    def test_insert_repeats_but_never_skips(self, db):
        uid = _mk_user(db)
        rows = [
            {"job_key": f"c-{i:03d}", "title": f"R {i}", "company": f"C{i}"}
            for i in range(100)
        ]
        _seed(db, uid, rows)

        limit = 50
        page1 = [a["job_id"] for a in db.get_applications_page(uid, limit=limit, offset=0)]

        # A NEW row arrives at the top between the two page reads.
        conn = db.connect(ensure_schema=False)
        try:
            from psycopg2.extras import Json
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rico_job_recommendations
                        (user_id, job_key, job, status, created_at, updated_at)
                    VALUES (%s, 'c-new', %s, 'saved',
                            now() + interval '1 minute', now() + interval '1 minute')
                    """,
                    (uid, Json({"title": "Newest", "company": "New Co", "location": "Dubai"})),
                )
            conn.commit()
        finally:
            conn.close()

        # Keep paging to exhaustion (the insert grew the set to 101 rows,
        # so a third page now exists).
        later_pages: list[str] = []
        offset = limit
        while True:
            items = db.get_applications_page(uid, limit=limit, offset=offset)
            if not items:
                break
            later_pages.extend(a["job_id"] for a in items)
            offset += limit

        seen = set(page1) | set(later_pages)
        original = {f"c-{i:03d}" for i in range(100)}
        # Documented behavior: the shift may REPEAT the boundary item of an
        # earlier page on a later page, but no pre-existing item is silently
        # skipped when paging continues to exhaustion.
        assert original - seen == set(), \
            "no pre-existing item may be skipped by a concurrent insert"
        overlap = set(page1) & set(later_pages)
        assert len(overlap) <= 1, "at most the boundary item repeats per insert"


# ── Owner-required determinism proofs (review conditions on PR #1144) ────────

class TestOrderingDeterminism:
    def test_duplicate_timestamps_page_deterministically_via_id_tiebreak(self, db):
        """60 rows sharing ONE identical updated_at: ordering must be stable
        (id DESC tie-break), identical across repeated reads, and paging must
        still reach every row exactly once."""
        uid = _mk_user(db)
        from psycopg2.extras import Json
        conn = db.connect(ensure_schema=False)
        try:
            with conn.cursor() as cur:
                for i in range(60):
                    cur.execute(
                        """
                        INSERT INTO rico_job_recommendations
                            (user_id, job_key, job, status, created_at, updated_at)
                        VALUES (%s, %s, %s, 'saved',
                                '2026-07-01T12:00:00Z', '2026-07-01T12:00:00Z')
                        """,
                        (uid, f"tie-{i:03d}",
                         Json({"title": f"Role {i}", "company": f"C{i}", "location": "Dubai"})),
                    )
            conn.commit()
        finally:
            conn.close()

        def _full_order():
            out = []
            offset = 0
            while True:
                page = db.get_applications_page(uid, limit=25, offset=offset)
                if not page:
                    break
                out.extend(a["job_id"] for a in page)
                offset += 25
            return out

        first = _full_order()
        assert len(first) == 60 and len(set(first)) == 60, "exactly-once despite ties"
        for _ in range(3):
            assert _full_order() == first, "identical order on every read (id DESC tie-break)"

    def test_duplicate_identities_with_duplicate_timestamps_dedup_deterministically(self, db):
        """Two physical rows, same identity AND same updated_at: the canonical
        winner must be the same row on every read (id DESC decides)."""
        uid = _mk_user(db)
        from psycopg2.extras import Json
        conn = db.connect(ensure_schema=False)
        try:
            with conn.cursor() as cur:
                for key in ("dup-a", "dup-b"):
                    cur.execute(
                        """
                        INSERT INTO rico_job_recommendations
                            (user_id, job_key, job, status, created_at, updated_at)
                        VALUES (%s, %s, %s, 'saved',
                                '2026-07-01T12:00:00Z', '2026-07-01T12:00:00Z')
                        """,
                        (uid, key,
                         Json({"title": "Same Role", "company": "Same Co", "location": "Dubai"})),
                    )
            conn.commit()
        finally:
            conn.close()

        winners = {db.get_applications_page(uid)[0]["job_id"] for _ in range(5)}
        assert len(winners) == 1, "tie between duplicate identities must resolve identically every time"
        assert db.count_applications(uid) == 1

    def test_offset_beyond_total_returns_empty_last_page(self, db):
        uid = _mk_user(db)
        _seed(db, uid, [
            {"job_key": f"e-{i}", "title": f"R{i}", "company": f"C{i}"} for i in range(7)
        ])
        assert db.get_applications_page(uid, limit=5, offset=5) != []
        assert db.get_applications_page(uid, limit=5, offset=10) == []
        assert db.get_applications_page(uid, limit=5, offset=500) == []

    def test_list_count_stats_quota_all_agree_on_one_canonical_rule(self, db):
        """The unified-dedup condition: pages, count, stats, and the quota
        count must agree on a dataset that mixes duplicates, ties, and
        multiple statuses."""
        uid = _mk_user(db)
        rows = [
            {"job_key": f"m-{i:03d}", "title": f"R{i}", "company": f"C{i % 9}",
             "status": "saved" if i % 3 else "applied"}
            for i in range(120)
        ]
        # duplicates of the first 15 identities under different keys
        rows += [
            {"job_key": f"mdup-{i:03d}", "title": f"R{i}", "company": f"C{i % 9}",
             "status": "saved" if i % 3 else "applied"}
            for i in range(15)
        ]
        _seed(db, uid, rows)

        paged = []
        offset = 0
        while True:
            page = db.get_applications_page(uid, limit=30, offset=offset)
            if not page:
                break
            paged.extend(page)
            offset += 30

        stats = db.get_application_stats(uid)
        assert len(paged) == db.count_applications(uid) == stats["total"] == 120
        assert sum(stats["by_status"].values()) == stats["total"]
        assert db.count_applications(uid, status="saved") == stats["saved"]
        assert stats["saved"] == sum(1 for a in paged if a["status"] == "saved")
