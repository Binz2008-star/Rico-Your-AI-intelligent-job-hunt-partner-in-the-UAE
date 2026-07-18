"""Posting-history archive (job_observations, migration 046).

Pins the write-path contract:

- versioned fingerprint is normalization-stable across providers
  (case/punctuation/whitespace/city-format variants land on one identity);
- ``record_observations`` never raises, no-ops without a DB, and stores
  NO description text (hash + length only) and NO user data;
- an absent table (migration 046 not applied, pgcode 42P01) disables the
  archive for the process instead of hammering the hot path.
"""
from __future__ import annotations

from datetime import timezone
from unittest.mock import MagicMock, patch

import pytest

from src.repositories import job_observations_repo as repo


@pytest.fixture(autouse=True)
def _reset_state():
    repo._reset_state_for_tests()
    yield
    repo._reset_state_for_tests()


# ── Fingerprint ───────────────────────────────────────────────────────────────

def test_fingerprint_is_stable_across_provider_formatting():
    a = repo.compute_fingerprint("Operations Manager", "ACME Group", "Dubai, Dubai, AE")
    b = repo.compute_fingerprint("operations   manager", "acme group!", "dubai")
    assert a == b
    assert len(a) == 64


def test_fingerprint_differs_on_company_title_or_city():
    base = repo.compute_fingerprint("Operations Manager", "ACME", "Dubai")
    assert repo.compute_fingerprint("Operations Manager", "Other Co", "Dubai") != base
    assert repo.compute_fingerprint("HSE Officer", "ACME", "Dubai") != base
    assert repo.compute_fingerprint("Operations Manager", "ACME", "Abu Dhabi") != base


def test_fingerprint_handles_arabic_text():
    a = repo.compute_fingerprint("مدير عمليات", "شركة الاتحاد", "دبي")
    b = repo.compute_fingerprint("مدير  عمليات", "شركة الاتحاد،", "دبي, الإمارات")
    assert a == b


def test_claimed_posted_at_parses_iso_and_rejects_garbage():
    parsed = repo._parse_claimed_posted("2026-07-01T10:00:00.000Z")
    assert parsed is not None and parsed.tzinfo == timezone.utc
    assert repo._parse_claimed_posted("3 days ago") is None
    assert repo._parse_claimed_posted("") is None
    assert repo._parse_claimed_posted(None) is None


# ── Write path ────────────────────────────────────────────────────────────────

_ITEM = {
    "title": "Operations Manager",
    "company": "ACME Group",
    "location": "Dubai, Dubai, AE",
    "job_id": "prov-123",
    "apply_link": "https://careers.acme.example.com/apply/9?src=x",
    "description": "Run daily operations. " * 50,
    "salary_string": "AED 20,000",
    "employment_type": "FULLTIME",
    "posted_at": "2026-07-01T10:00:00.000Z",
}


def _mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_noop_when_db_unavailable():
    with patch.object(repo, "is_db_available", return_value=False), \
         patch.object(repo, "get_db_connection") as get_conn:
        assert repo.record_observations([_ITEM], provider="jsearch") == 0
    assert not get_conn.called


def test_records_rows_without_description_text_or_user_data():
    conn, cursor = _mock_conn()
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn):
        written = repo.record_observations(
            [_ITEM, {"title": ""}, "not-a-dict"],
            provider="jsearch", query_context="operations manager dubai UAE",
        )
    assert written == 1  # empty-title and non-dict items are skipped
    assert cursor.executemany.called
    _sql, rows = cursor.executemany.call_args[0]
    (row,) = rows
    assert _ITEM["description"] not in row  # never the raw text
    values = [v for v in row if isinstance(v, str)]
    assert repo.compute_fingerprint("Operations Manager", "ACME Group", "Dubai, Dubai, AE") in values
    assert "careers.acme.example.com" in values  # domain only, not the full URL
    assert not any("src=x" in v for v in values)
    assert row[-2] == len(_ITEM["description"])  # description_len
    assert conn.commit.called


def test_missing_table_disables_archive_for_process():
    conn, cursor = _mock_conn()
    exc = Exception("relation \"job_observations\" does not exist")
    exc.pgcode = "42P01"
    cursor.executemany.side_effect = exc
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn) as get_conn:
        assert repo.record_observations([_ITEM], provider="jsearch") == 0
        assert repo.record_observations([_ITEM], provider="jsearch") == 0
    assert get_conn.call_count == 1  # second call short-circuited


def test_generic_db_error_is_swallowed_and_does_not_disable():
    conn, cursor = _mock_conn()
    cursor.executemany.side_effect = Exception("connection reset")
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection", return_value=conn) as get_conn:
        assert repo.record_observations([_ITEM], provider="jooble") == 0
        assert repo.record_observations([_ITEM], provider="jooble") == 0
    assert get_conn.call_count == 2  # transient errors do not latch the kill flag


def test_empty_items_are_a_noop():
    with patch.object(repo, "is_db_available", return_value=True), \
         patch.object(repo, "get_db_connection") as get_conn:
        assert repo.record_observations([], provider="jsearch") == 0
    assert not get_conn.called
