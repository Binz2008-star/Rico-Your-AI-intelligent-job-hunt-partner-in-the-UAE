"""Regression tests for the Phase-3 DB connection pool / RicoDB.connect.

Guards the production incident where the OLD pooling path did
``conn._rico_pool = pool`` on a psycopg2 connection (no ``__dict__``) and took
down every DB-backed endpoint with AttributeError.

The new architecture routes ALL connections through a single acquire/release
path (``src.db._ConnectionPool`` + ``_PooledConnection``): raw psycopg2
connections are never mutated, close() returns them to the pool, and a
slots-only fake connection proves nothing is ever stashed on it.
"""
from unittest.mock import patch

import pytest

from src import db as src_db
from src.rico_db import RicoDB


class _SlotsConn:
    """Mimics a psycopg2 connection: __slots__ → arbitrary setattr raises."""

    __slots__ = ("closed", "close_count", "autocommit")

    def __init__(self) -> None:
        self.closed = 0
        self.close_count = 0
        self.autocommit = False

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.close_count += 1
        self.closed = 1


@pytest.fixture
def pool_env():
    """An isolated _ConnectionPool over slots-only fake connections.

    The psycopg2.connect patch stays active for the whole test so the pool's
    lazy connection creation always hits the fake.
    """
    created: list[_SlotsConn] = []

    def fake_connect(dsn, **kwargs):
        c = _SlotsConn()
        created.append(c)
        return c

    with patch.object(src_db.psycopg2, "connect", fake_connect):
        pool = src_db._ConnectionPool(
            "postgresql://fake/db",
            minconn=0,
            maxconn=2,
            acquire_timeout=0.5,
        )
        yield pool, created


def test_pool_never_stashes_attributes_on_raw_connection(pool_env):
    pool, created = pool_env
    conn = pool.acquire()
    assert conn is created[0]
    assert not hasattr(conn, "_rico_pool")  # original-incident guard


def test_acquire_release_reuses_the_same_connection(pool_env):
    pool, created = pool_env
    first = pool.acquire()
    pool.release(first)
    second = pool.acquire()
    assert second is first
    assert len(created) == 1


def test_release_does_not_close_a_live_connection(pool_env):
    pool, created = pool_env
    conn = pool.acquire()
    pool.release(conn)
    assert created[0].close_count == 0  # returned to the pool, not closed


def test_wrapper_close_returns_to_pool_and_is_idempotent(pool_env):
    pool, created = pool_env
    wrapped = src_db._PooledConnection(pool.acquire(), pool)
    wrapped.close()
    wrapped.close()  # second close is a no-op
    assert created[0].close_count == 0
    assert pool.acquire() is created[0]


def test_pool_discards_dead_connections(pool_env):
    pool, created = pool_env
    conn = pool.acquire()
    conn.closed = 1  # simulate a broken/dead connection
    pool.release(conn)
    fresh = pool.acquire()
    assert fresh is not conn  # dead conn was discarded, a new one was created
    assert len(created) == 2


def test_pool_exhaustion_times_out(pool_env):
    pool, created = pool_env
    # maxconn=2 in the fixture: hold BOTH, then the third acquire must time out.
    a = pool.acquire()
    b = pool.acquire()
    try:
        with pytest.raises(src_db.PoolTimeoutError):
            src_db._PooledConnection(pool.acquire(), pool)
    finally:
        pool.release(a)
        pool.release(b)


def test_pool_close_cleans_up():
    created: list[_SlotsConn] = []

    def fake_connect(dsn, **kwargs):
        c = _SlotsConn()
        created.append(c)
        return c

    with patch.object(src_db.psycopg2, "connect", fake_connect):
        pool = src_db._ConnectionPool("postgresql://fake/db", minconn=2, maxconn=2)
        a = pool.acquire()
        b = pool.acquire()
        pool.close()
        # Connections checked out at close time are closed on release.
        pool.release(a)
        pool.release(b)
    assert all(c.close_count >= 1 for c in created)


def test_transaction_releases_without_attr_error(pool_env):
    pool, created = pool_env

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch.object(_SlotsConn, "commit", lambda self: None, create=True), \
         patch.object(_SlotsConn, "cursor", lambda self: _Ctx(), create=True), \
         patch.object(src_db, "_pool_for", return_value=pool):
        db = RicoDB("postgresql://fake/db")
        with db._transaction(ensure_schema=False) as conn:
            assert conn._raw is created[0]
        assert created[0].close_count == 0  # returned to the pool, not closed


def test_connect_raises_when_unavailable():
    db = RicoDB("postgresql://fake/db")
    db.database_url = ""  # force unavailable deterministically
    with pytest.raises(RuntimeError):
        db.connect()


def test_pooled_rows_support_both_access_styles():
    """The pool must serve both row['col']/row.get() (dict) and row[0] (tuple)
    callers — RealDictRow is name-only and DictRow lacks .get(), so a one-or-the-
    other choice silently breaks the other half of the codebase."""
    from src.db import _CompatibleRow

    cursor = type("C", (), {"description": (("id",), ("email",), ("n",))})()
    row = _CompatibleRow(cursor)
    row[0] = 7
    row[1] = "u@example.com"
    row[2] = 3

    assert row["id"] == 7 and row[0] == 7
    assert row["email"] == "u@example.com" and row[1] == "u@example.com"
    assert row.get("n") == 3 and row[2] == 3
    assert isinstance(row, dict)
    assert dict(row) == {"id": 7, "email": "u@example.com", "n": 3}
