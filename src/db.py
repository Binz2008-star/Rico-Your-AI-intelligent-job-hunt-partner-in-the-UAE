"""
Neon Postgres Database Integration
Provides database functions with JSON fallback for reliability.

Phase-3: all connections come from a bounded, thread-safe, per-process pool
(``_ConnectionPool``). The pool replaces the previous open-a-fresh-connection-
per-call model, which burned a new TCP+TLS handshake for every query and could
exhaust the Neon connection ceiling under concurrency.
"""

import logging
import os
import threading
import time
import psycopg2
from psycopg2 import sql, OperationalError
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
DB_ENABLED = bool(DATABASE_URL and (
    DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")
))

# Fallback to JSON if DB fails
JSON_FALLBACK = True


class PoolTimeoutError(Exception):
    """No free connection became available within the acquisition timeout."""


class _CompatibleRow(dict):
    """Row that supports BOTH dict-style and positional access.

    The codebase mixes ``row["col"]`` / ``row.get("col")`` (RealDict style) and
    ``row[0]`` / ``row[1]`` (tuple style) against the same shared connections.
    After pooling, a single cursor factory must serve both — ``RealDictRow`` is
    name-only (``row[0]`` raises KeyError) and ``DictRow`` has no ``.get()``.
    This row is a dict (name access, ``.get()``, ``isinstance(row, dict)``,
    ``dict(row)`` all work) whose integer indexing resolves against the column
    order.
    """

    def __init__(self, cursor) -> None:
        super().__init__()
        self._keys = [d[0] for d in (cursor.description or ())]

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._keys[key])
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if isinstance(key, int):
            return super().__setitem__(self._keys[key], value)
        return super().__setitem__(key, value)


def _compatible_row_factory(cursor):
    """psycopg2 row_factory protocol: (cursor) -> row object."""
    return _CompatibleRow(cursor)


class _CompatibleCursor(psycopg2.extensions.cursor):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.row_factory = _compatible_row_factory


class _ConnectionPool:
    """Bounded, thread-safe pool of live psycopg2 connections (per process).

    Properties required by Phase-3:
      * bounded max (``maxconn``) — never exceed Neon/Postgres limits;
      * acquire timeout — a caller waits at most ``acquire_timeout`` seconds;
      * dead-connection discard — a connection whose ``closed`` flag is set is
        dropped instead of returned, and replaced on demand;
      * process-local — lazy module-level init means a forked worker creates its
        own pool on first use, never inheriting another process's connections;
      * clean shutdown — ``close()`` closes every idle connection.
    """

    def __init__(
        self,
        dsn: str,
        minconn: int = 1,
        maxconn: int = 5,
        acquire_timeout: float = 5.0,
        connect_timeout: int = 5,
        statement_timeout_ms: int = 0,
    ) -> None:
        self._dsn = dsn
        self._minconn = max(0, minconn)
        self._maxconn = max(1, maxconn)
        self._acquire_timeout = max(0.5, acquire_timeout)
        self._connect_timeout = max(1, connect_timeout)
        self._statement_timeout_ms = max(0, int(statement_timeout_ms))
        self._idle: List[Any] = []
        self._total = 0
        self._closed = False
        self._cond = threading.Condition()
        for _ in range(self._minconn):
            self._idle.append(self._new_conn())
            self._total += 1

    def _new_conn(self):
        kwargs: Dict[str, Any] = {
            "cursor_factory": _CompatibleCursor,
            "connect_timeout": self._connect_timeout,
        }
        if self._statement_timeout_ms:
            # A shared connection must never be held hostage by one runaway
            # query: statement_timeout bounds each statement server-side.
            kwargs["options"] = f"-c statement_timeout={self._statement_timeout_ms}"
        return psycopg2.connect(self._dsn, **kwargs)

    def acquire(self):
        deadline = time.monotonic() + self._acquire_timeout
        with self._cond:
            while True:
                if self._closed:
                    raise RuntimeError("database connection pool is closed")
                while self._idle:
                    conn = self._idle.pop()
                    if not getattr(conn, "closed", True):
                        return conn
                    # Dead idle connection — discard; a fresh one replaces it.
                    self._total = max(0, self._total - 1)
                if self._total < self._maxconn:
                    self._total += 1
                    try:
                        return self._new_conn()
                    except Exception:
                        self._total = max(0, self._total - 1)
                        raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PoolTimeoutError(
                        "database connection pool exhausted "
                        f"(maxconn={self._maxconn}) within {self._acquire_timeout}s"
                    )
                self._cond.wait(remaining)

    def release(self, conn, *, close: bool = False) -> None:
        with self._cond:
            if self._closed or close or getattr(conn, "closed", True):
                try:
                    conn.close()
                except Exception:
                    pass
                self._total = max(0, self._total - 1)
            else:
                # Never reuse a connection carrying an open transaction: the
                # previous request's uncommitted rows, row locks, and snapshot
                # must not leak into the next request or user. rollback() is a
                # no-op on a clean connection and clears INTRANS otherwise. If
                # rollback itself fails the connection is dead — discard it.
                try:
                    if not getattr(conn, "autocommit", False):
                        conn.rollback()
                    self._idle.append(conn)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self._total = max(0, self._total - 1)
            self._cond.notify()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            for conn in self._idle:
                try:
                    conn.close()
                except Exception:
                    pass
            self._idle.clear()
            self._total = 0
            self._cond.notify_all()


class _PooledConnection:
    """Proxy over a pooled psycopg2 connection.

    ``close()`` returns the connection to the pool instead of closing it, so
    every existing ``conn.close()`` / ``finally: conn.close()`` call site works
    unchanged. ``with conn:`` still commits/rolls back (delegated); if the
    caller never closes explicitly, ``__exit__`` returns the connection to the
    pool so nothing leaks. Attribute access, cursors, commits and rollbacks all
    delegate to the underlying connection.
    """

    def __init__(self, raw, pool: "_ConnectionPool") -> None:
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_closed", False)

    def close(self) -> None:
        if self._closed:
            return
        object.__setattr__(self, "_closed", True)
        self._pool.release(self._raw)

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            return self._raw.__exit__(exc_type, exc, tb)
        finally:
            self.close()

    def __del__(self) -> None:
        try:
            if not self._closed and not getattr(self._raw, "closed", True):
                # Caller never released it: never leak a live connection.
                self.close()
        except Exception:
            pass


_POOLS: Dict[str, _ConnectionPool] = {}
_POOLS_LOCK = threading.Lock()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _pool_for(dsn: str) -> _ConnectionPool:
    """Lazy per-process pool, one per distinct DSN. Never shares a pool across
    processes (each forked worker builds its own on first use)."""
    with _POOLS_LOCK:
        pool = _POOLS.get(dsn)
        if pool is None:
            pool = _ConnectionPool(
                dsn,
                minconn=_int_env("DATABASE_POOL_MINCONN", 1),
                maxconn=_int_env("DATABASE_POOL_MAXCONN", 5),
                acquire_timeout=_int_env("DATABASE_POOL_TIMEOUT", 5),
                connect_timeout=_int_env("DATABASE_CONNECT_TIMEOUT", 5),
                statement_timeout_ms=_int_env("DATABASE_STATEMENT_TIMEOUT_MS", 0),
            )
            _POOLS[dsn] = pool
            logger.info(
                "db_pool_initialized maxconn=%s minconn=%s",
                pool._maxconn, pool._minconn,
            )
        return pool


def get_pooled_connection(dsn: Optional[str] = None):
    """Acquire a pooled connection (wrapped) for *dsn* (default DATABASE_URL).

    Returns None when no DSN is available; raises on connect failure or pool
    exhaustion."""
    target = dsn or DATABASE_URL
    if not target:
        return None
    pool = _pool_for(target)
    return _PooledConnection(pool.acquire(), pool)


def get_db_connection():
    """Get database connection with error handling.

    Returns None only when the DB is not configured or unreachable at
    acquisition time (the JSON-fallback contract). Pool exhaustion raises
    (PoolTimeoutError) rather than silently falling back to JSON — an overloaded
    pool must never turn a write into a fake JSON success.
    """
    if not DB_ENABLED:
        return None

    try:
        return get_pooled_connection()
    except OperationalError as e:
        logger.warning("db_connection_failed: %s", e)
        return None


def _commit(conn) -> None:
    if conn:
        conn.commit()


def _rollback(conn) -> None:
    if conn:
        try:
            conn.rollback()
        except Exception:
            pass


def init_db():
    """Initialize database tables if they don't exist."""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cursor:
            # Create jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    link TEXT UNIQUE NOT NULL,
                    description TEXT,
                    score INTEGER DEFAULT 0,
                    match_reason TEXT,
                    source TEXT DEFAULT 'jobspy',
                    date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    seen BOOLEAN DEFAULT FALSE
                )
            """)

            # Create applications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id SERIAL PRIMARY KEY,
                    job_link TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'saved',
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    follow_up_date TIMESTAMP,
                    FOREIGN KEY (job_link) REFERENCES jobs(link) ON DELETE CASCADE
                )
            """)

            # Create auto_apply_attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_apply_attempts (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(500) UNIQUE NOT NULL,
                    title VARCHAR(500),
                    company VARCHAR(500),
                    status VARCHAR(50) NOT NULL,
                    error TEXT,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Create settings table (used by /api/v1/settings)
            # `notifications` JSONB mirrors migration 005's definition: the
            # historical numbered migration 005 COMMENTS on settings.notifications,
            # so a fresh database created by this runtime DDL must carry the
            # column or a replay of the numbered migrations would fail. The
            # application reads the keyword/threshold columns; this is a
            # compatibility column (dead-but-present), safe on all deployments.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    user_id TEXT PRIMARY KEY,
                    include_keywords TEXT[],
                    exclude_keywords TEXT[],
                    min_score INTEGER DEFAULT 50,
                    max_daily_applies INTEGER DEFAULT 10,
                    telegram_chat_id TEXT,
                    score_threshold_apply INTEGER DEFAULT 75,
                    score_threshold_watch INTEGER DEFAULT 50,
                    notifications JSONB NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ensure new columns exist in legacy tables (idempotent migration)
            cursor.execute("""
                ALTER TABLE settings
                ADD COLUMN IF NOT EXISTS notifications JSONB NOT NULL DEFAULT '{}'
            """)
            cursor.execute("""
                ALTER TABLE settings
                ADD COLUMN IF NOT EXISTS score_threshold_apply INTEGER DEFAULT 75
            """)
            cursor.execute("""
                ALTER TABLE settings
                ADD COLUMN IF NOT EXISTS score_threshold_watch INTEGER DEFAULT 50
            """)
            cursor.execute("""
                ALTER TABLE settings
                ADD COLUMN IF NOT EXISTS blocked_companies TEXT[] DEFAULT '{}'
            """)

            # Add link verification columns to jobs table
            cursor.execute("""
                ALTER TABLE jobs
                ADD COLUMN IF NOT EXISTS link_status VARCHAR(20) DEFAULT 'needs_review'
            """)
            cursor.execute("""
                ALTER TABLE jobs
                ADD COLUMN IF NOT EXISTS link_verified_at TIMESTAMP
            """)

            # Subscription intent log — records every upgrade/WhatsApp click for lead tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscription_intents (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    email TEXT,
                    plan TEXT NOT NULL,
                    billing_mode TEXT NOT NULL DEFAULT 'manual',
                    source_page TEXT DEFAULT '/subscription',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sub_intents_user ON subscription_intents(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sub_intents_created ON subscription_intents(created_at DESC)"
            )

            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_link ON jobs(link)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date_found ON jobs(date_found DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_job_link ON applications(job_link)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auto_apply_job_id ON auto_apply_attempts(job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auto_apply_status ON auto_apply_attempts(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auto_apply_timestamp ON auto_apply_attempts(timestamp DESC)")

        _commit(conn)
        logger.info("db_init_ok")
        return True

    except Exception as e:
        _rollback(conn)
        logger.error("db_init_failed: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def _truncate_description(description: Any, link: Any, max_len: int = 1000) -> str:
    text = str(description) if description else ''
    if len(text) > max_len:
        logger.warning("save_job: description truncated to %d chars link=%s", max_len, link)
        return text[:max_len]
    return text


def save_job(job: Dict[str, Any], score: int) -> bool:
    """Save a job to the database."""
    from src.services.job_link_trust import validate_job_url

    raw_link = job.get('link', '') or ''
    safe_link = validate_job_url(raw_link)
    if raw_link and not safe_link:
        logger.warning("db_save_job: rejected unsafe link='%s' title='%s'", raw_link[:100], (job.get('title') or '')[:80])

    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO jobs (title, company, location, link, description, score, match_reason, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO UPDATE SET
                    score = EXCLUDED.score,
                    match_reason = EXCLUDED.match_reason,
                    date_found = CURRENT_TIMESTAMP
            """, (
                job.get('title', '') or '',
                job.get('company', '') or '',
                job.get('location', '') or '',
                safe_link,
                _truncate_description(job.get('description'), safe_link),
                score,
                job.get('profile_explanation', '') or '',
                job.get('source', 'jobspy') or 'jobspy'
            ))

        _commit(conn)
        return True

    except Exception as e:
        _rollback(conn)
        logger.error("db_save_job_failed: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def get_seen_links(days_back: int = 90, limit: int = 8000) -> List[str]:
    """
    Get seen job links from the past `days_back` days.
    Bounded by `limit` to prevent loading unbounded rows into memory.
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT link FROM jobs
                WHERE date_found > NOW() - (%s * INTERVAL '1 day')
                ORDER BY date_found DESC
                LIMIT %s
                """,
                (days_back, limit),
            )
            return [row[0] for row in cursor.fetchall()]

    except Exception as e:
        logger.error("db_get_seen_links_failed: %s", e)
        return []
    finally:
        if conn:
            conn.close()


def mark_applied(job_link: str, notes: str = None) -> bool:
    """Mark a job as applied."""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cursor:
            # Update job as seen
            cursor.execute("UPDATE jobs SET seen = TRUE WHERE link = %s", (job_link,))

            # Add or update application record
            cursor.execute("""
                INSERT INTO applications (job_link, status, notes)
                VALUES (%s, 'applied', %s)
                ON CONFLICT (job_link) DO UPDATE SET
                    status = EXCLUDED.status,
                    applied_at = CURRENT_TIMESTAMP,
                    notes = CASE
                               WHEN %s IS NULL OR %s = '' THEN applications.notes
                               WHEN applications.notes IS NULL OR applications.notes = '' THEN %s
                               ELSE applications.notes || ' | ' || %s
                           END
            """, (job_link, notes, notes, notes, notes, notes))

        _commit(conn)
        return True

    except Exception as e:
        _rollback(conn)
        logger.error("db_mark_applied_failed: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def update_application_status(job_link: str, status: str, notes: str = None) -> bool:
    """Update application status."""
    conn = get_db_connection()
    if not conn:
        return False

    valid_statuses = ['saved', 'opened', 'opened_external', 'applied', 'interview', 'rejected', 'offer']
    # Map opened_external to opened for storage
    if status == 'opened_external':
        status = 'opened'
    if status not in valid_statuses:
        logger.warning("db_update_application_status_invalid: %s", status)
        return False

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE applications
                SET status = %s,
                    notes = COALESCE(notes, '') || CASE WHEN %s IS NOT NULL THEN ' | ' || %s ELSE '' END,
                    follow_up_date = CASE WHEN %s = 'interview' THEN CURRENT_TIMESTAMP ELSE follow_up_date END
                WHERE job_link = %s
            """, (status, notes, notes, status, job_link))
            # rowcount MUST be read inside the with-block; psycopg2 resets it on cursor close
            affected = cursor.rowcount

        _commit(conn)
        return affected > 0

    except Exception as e:
        _rollback(conn)
        logger.error("db_update_application_status_failed: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def get_top_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top scored jobs."""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT title, company, location, link, score, match_reason, date_found
                FROM jobs
                WHERE score >= 40
                ORDER BY score DESC, date_found DESC
                LIMIT %s
            """, (limit,))

            jobs = []
            for row in cursor.fetchall():
                jobs.append({
                    'title': row[0],
                    'company': row[1],
                    'location': row[2],
                    'link': row[3],
                    'score': row[4],
                    'match_reason': row[5],
                    'date_found': row[6].isoformat() if row[6] else None
                })

            return jobs

    except Exception as e:
        logger.error("db_get_top_jobs_failed: %s", e)
        return []
    finally:
        if conn:
            conn.close()


def get_application_stats() -> Dict[str, Any]:
    """Get application statistics."""
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        with conn.cursor() as cursor:
            # Get status counts
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM applications
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())

            # Calculate success rate
            total_applied = status_counts.get('applied', 0) + status_counts.get('interview', 0)
            interviews = status_counts.get('interview', 0)
            success_rate = (interviews / total_applied * 100) if total_applied > 0 else 0

            return {
                'total_applied': total_applied,
                'status_breakdown': status_counts,
                'interviews_scheduled': interviews,
                'rejections': status_counts.get('rejected', 0),
                'pending': status_counts.get('applied', 0),
                'success_rate': round(success_rate, 1)
            }

    except Exception as e:
        logger.error("db_get_application_stats_failed: %s", e)
        return {}
    finally:
        if conn:
            conn.close()


def is_db_available() -> bool:
    """Check if database is available."""
    return DB_ENABLED


def record_subscription_intent(
    plan: str,
    billing_mode: str = "manual",
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    source_page: str = "/subscription",
) -> bool:
    """Log a subscription upgrade intent. Fire-and-forget — never raises."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscription_intents (user_id, email, plan, billing_mode, source_page)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, email, plan, billing_mode, source_page),
            )
        _commit(conn)
        return True
    except Exception as exc:
        logger.warning("record_subscription_intent failed: %s", exc)
        _rollback(conn)
        return False
    finally:
        conn.close()


def get_subscription_intents(limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent subscription intents for admin review."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, email, plan, billing_mode, source_page, created_at
                FROM subscription_intents
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("get_subscription_intents failed: %s", exc)
        return []
    finally:
        conn.close()


def main():
    """Test database functions."""
    print("🧪 Testing Database Integration")

    if not DB_ENABLED:
        print("❌ DATABASE_URL not set or invalid")
        return

    # Test initialization
    print("\n1. Testing init_db():")
    if init_db():
        print("✅ Database initialized")
    else:
        print("❌ Database initialization failed")
        return

    # Test saving a job
    print("\n2. Testing save_job():")
    sample_job = {
        'title': 'Test Executive Assistant',
        'company': 'Test Company',
        'location': 'Dubai, UAE',
        'link': 'https://example.com/test',
        'description': 'Test job description',
        'profile_explanation': 'Test match reason'
    }

    if save_job(sample_job, 75):
        print("✅ Job saved successfully")
    else:
        print("❌ Failed to save job")

    # Test getting seen links
    print("\n3. Testing get_seen_links():")
    seen_links = get_seen_links()
    print(f"Seen links: {len(seen_links)}")

    # Test marking as applied
    print("\n4. Testing mark_applied():")
    if mark_applied('https://example.com/test', 'Test notes'):
        print("✅ Job marked as applied")
    else:
        print("❌ Failed to mark job as applied")

    # Test getting top jobs
    print("\n5. Testing get_top_jobs():")
    top_jobs = get_top_jobs(5)
    print(f"Top jobs: {len(top_jobs)}")

    # Test application stats
    print("\n6. Testing get_application_stats():")
    stats = get_application_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()
