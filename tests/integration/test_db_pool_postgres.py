"""
tests/integration/test_db_pool_postgres.py

Real-PostgreSQL integration tests for the Phase-3 connection pool
(``src.db._ConnectionPool``). Verifies real pool behavior that mocks cannot:
actual connection reuse, exhaustion timeout against a real server, concurrent
acquire/release from multiple threads, dead-connection discard, and clean
shutdown. Uses the dedicated database server behind RICO_TEST_DATABASE_URL;
skips cleanly when that variable is unset.
"""
from __future__ import annotations

import os
import threading
import time

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

from src.db import PoolTimeoutError, _ConnectionPool

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres pool tests skipped.",
)


@pytest.fixture
def pool():
    p = _ConnectionPool(TEST_DATABASE_URL, minconn=1, maxconn=4, acquire_timeout=2)
    yield p
    p.close()


class TestPoolRealPostgres:
    def test_successful_acquire_and_query(self, pool):
        conn = pool.acquire()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS one")
                assert cur.fetchone()["one"] == 1
        finally:
            pool.release(conn)

    def test_repeated_acquire_release_reuses_connection(self, pool):
        first = pool.acquire()
        pool.release(first)
        second = pool.acquire()
        assert second is first
        pool.release(second)

    def test_connection_is_reused_for_many_round_trips(self, pool):
        conn = pool.acquire()
        try:
            for i in range(50):
                with conn.cursor() as cur:
                    cur.execute("SELECT %s AS n", (i,))
                    assert cur.fetchone()["n"] == i
        finally:
            pool.release(conn)

    def test_pool_exhaustion_times_out(self, pool):
        held = [pool.acquire() for _ in range(pool._maxconn)]
        try:
            with pytest.raises(PoolTimeoutError):
                pool.acquire()
        finally:
            for c in held:
                pool.release(c)

    def test_concurrent_acquire_release(self, pool):
        errors: list[Exception] = []
        results: list[int] = []

        def _worker(n: int) -> None:
            try:
                for _ in range(10):
                    conn = pool.acquire()
                    with conn.cursor() as cur:
                        cur.execute("SELECT %s AS n", (n,))
                        cur.fetchone()
                    pool.release(conn)
                results.append(n)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == []
        assert len(results) == 8

    def test_dead_connection_is_discarded(self, pool):
        conn = pool.acquire()
        conn.close()  # simulate a broken/lost connection
        pool.release(conn)  # release sees closed=True and discards it
        fresh = pool.acquire()
        try:
            with fresh.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        finally:
            pool.release(fresh)
        assert fresh is not conn

    def test_connect_failure_raises(self):
        with pytest.raises(Exception):
            _ConnectionPool(
                "postgresql://nobody:wrong@127.0.0.1:59999/nowhere",
                minconn=0,
                maxconn=1,
                connect_timeout=2,
            ).acquire()

    def test_no_transaction_leak_across_reuse(self, pool):
        """A connection released with an OPEN transaction must be rolled back
        before reuse — the previous request's uncommitted rows/locks/snapshot
        must never leak into the next request (cross-user isolation)."""
        from src.db import _PooledConnection

        # Setup: create the probe table and COMMIT it (so only the INSERT is
        # subject to the rollback probe).
        setup = _PooledConnection(pool.acquire(), pool)
        with setup.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS txn_leak_probe")
            cur.execute("CREATE TABLE txn_leak_probe (id int)")
        setup.commit()
        setup.close()

        # Request 1: BEGIN, INSERT, release WITHOUT commit.
        c1 = _PooledConnection(pool.acquire(), pool)
        with c1.cursor() as cur:
            cur.execute("INSERT INTO txn_leak_probe VALUES (1)")
        assert c1._raw.info.transaction_status != 0  # transaction is open
        c1.close()

        # Request 2: reacquire the same raw connection — it must be idle and
        # must NOT see request 1's uncommitted row.
        c2 = _PooledConnection(pool.acquire(), pool)
        try:
            assert c2._raw is c1._raw
            assert c2._raw.info.transaction_status == 0, (
                "pooled connection reused with an open transaction"
            )
            with c2.cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM txn_leak_probe")
                assert cur.fetchone()["n"] == 0  # rolled back, nothing leaked
        finally:
            c2.rollback()
            c2.close()

    def test_clean_shutdown_closes_all(self, pool):
        a = pool.acquire()
        b = pool.acquire()
        pool.release(a)  # idle at close time → closed by close()
        pool.close()
        assert getattr(a, "closed", True)  # psycopg2 closed is 0/1, not bool
        # A connection still checked out at close time is closed on release.
        pool.release(b)
        assert getattr(b, "closed", True)
