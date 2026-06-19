"""Regression tests for RicoDB.connect() / connection release.

Guards the production incident where the DB-pooling path did
``conn._rico_pool = pool``. psycopg2 connection objects have no ``__dict__``, so
that assignment raised
    AttributeError: 'psycopg2.extensions.connection' object has no attribute '_rico_pool'
on EVERY db.connect() call — taking down all DB-backed endpoints (the follow-up
reminders sweep surfaced it as run_due_scan's safe `status="error"`).

These tests use a slots-only fake connection that mimics psycopg2 (no __dict__),
so any attempt to stash an attribute on the connection raises — exactly as it
does in production.
"""
from unittest.mock import patch

from src import rico_db
from src.rico_db import RicoDB


class _SlotsConn:
    """Mimics a psycopg2 connection: __slots__ → arbitrary setattr raises."""

    __slots__ = ("closed", "close_count")

    def __init__(self) -> None:
        self.closed = 0
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        self.closed = 1


def test_connect_does_not_stash_attributes_on_connection(monkeypatch):
    created: list[_SlotsConn] = []

    def fake_connect(dsn, **kwargs):
        c = _SlotsConn()
        created.append(c)
        return c

    monkeypatch.setattr(rico_db.psycopg2, "connect", fake_connect)

    db = RicoDB("postgresql://fake/db")
    # ensure_schema=False avoids real DDL; the key assertion is that connect()
    # returns WITHOUT raising AttributeError on a no-__dict__ connection.
    conn = db.connect(ensure_schema=False)

    assert conn is created[0]
    assert not hasattr(conn, "_rico_pool")  # no pool reference stashed on the conn


def test_return_or_close_closes_connection():
    conn = _SlotsConn()
    RicoDB._return_or_close(conn)
    assert conn.close_count == 1
    assert conn.closed == 1


def test_transaction_acquires_and_releases_without_attr_error(monkeypatch):
    created: list[_SlotsConn] = []

    def fake_connect(dsn, **kwargs):
        c = _SlotsConn()
        created.append(c)
        return c

    monkeypatch.setattr(rico_db.psycopg2, "connect", fake_connect)

    db = RicoDB("postgresql://fake/db")
    # Give the fake connection the cursor/commit surface _transaction touches.
    class _Ctx:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(_SlotsConn, "commit", lambda self: None, raising=False)

    with db._transaction(ensure_schema=False) as conn:
        assert conn is created[0]
    # Released (closed) on exit, no AttributeError raised anywhere.
    assert created[0].close_count == 1


def test_connect_raises_when_unavailable():
    db = RicoDB("postgresql://fake/db")
    db.database_url = ""  # force unavailable deterministically
    try:
        db.connect()
        assert False, "expected RuntimeError when DATABASE_URL missing"
    except RuntimeError:
        pass
