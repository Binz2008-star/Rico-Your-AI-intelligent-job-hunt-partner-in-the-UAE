"""
tests/unit/test_ujc_batch_row_isolation.py

Regression coverage for the batch-upsert row-isolation hardening.

A single malformed match (e.g. a value the DB driver rejects) must NOT abort
the whole apply-link persistence batch: the bad row is rolled back to its
SAVEPOINT and logged, while the remaining rows still persist and the
transaction still commits.

DB is fully mocked — no live Neon connection opened.
"""
from __future__ import annotations

from unittest.mock import patch

import src.repositories.user_job_context_repo as repo


_POISON_TITLE = "POISON ROW"


class _FakeCursor:
    """Records INSERTs and SAVEPOINT control flow; raises on the poison row."""

    def __init__(self):
        self.inserted: list[str] = []          # titles successfully inserted
        self.savepoints = 0
        self.releases = 0
        self.rollbacks = 0

    def execute(self, sql, params=None):
        s = sql.strip()
        if s.startswith("SAVEPOINT"):
            self.savepoints += 1
            return
        if s.startswith("ROLLBACK TO SAVEPOINT"):
            self.rollbacks += 1
            return
        if s.startswith("RELEASE SAVEPOINT"):
            self.releases += 1
            return
        if "INSERT INTO user_job_context" in s:
            title = params[1]
            if title == _POISON_TITLE:
                raise ValueError("A string literal cannot contain NUL (0x00) characters")
            self.inserted.append(title)
            return
        # any other statement is a no-op for this fake

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _match(title, company="ACME"):
    return {
        "title": title,
        "company": company,
        "apply_url": f"https://careers.example.com/{title}",
        "source_url": f"https://jsearch.example/{title}",
    }


def _run(matches):
    conn = _FakeConn()
    with patch("src.db.get_db_connection", return_value=conn):
        repo.upsert_matches("user:synthetic@example.com", matches)
    return conn


def test_poison_row_does_not_drop_the_rest_of_the_batch():
    conn = _run([_match("Good One"), _match(_POISON_TITLE), _match("Good Two")])
    cur = conn.cursor_obj

    # The two healthy rows persisted; the poison row did not.
    assert cur.inserted == ["Good One", "Good Two"]
    # The poison row was isolated: rolled back to its savepoint, not released.
    assert cur.rollbacks == 1
    assert cur.releases == 2
    assert cur.savepoints == 3
    # The transaction still committed the good rows (no whole-batch rollback).
    assert conn.committed is True
    assert conn.rolled_back is False
    assert conn.closed is True


def test_leading_poison_row_still_persists_following_rows():
    conn = _run([_match(_POISON_TITLE), _match("Good After")])
    cur = conn.cursor_obj
    assert cur.inserted == ["Good After"]
    assert cur.rollbacks == 1
    assert conn.committed is True


def test_all_good_batch_persists_every_row_and_commits():
    conn = _run([_match("A"), _match("B"), _match("C")])
    cur = conn.cursor_obj
    assert cur.inserted == ["A", "B", "C"]
    assert cur.rollbacks == 0
    assert cur.releases == 3
    assert conn.committed is True
