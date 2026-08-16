"""Deterministic, ordered, concurrency-safe migration runner (Phase 3).

The repository's numbered migrations under ``migrations/`` were previously
applied by hand with applied-state *inferred* from object presence
(``scripts/check_migration_drift.py``). This module adds an explicit ledger:

  * ``schema_migrations(version, name, checksum, applied_at)`` records every
    numbered migration that has actually run.
  * A Postgres **advisory lock** serializes concurrent runners (two app
    instances / CI + manual) so a migration can never be applied twice or
    interleaved.
  * Migrations apply in numeric order, each in its own transaction; a failure
    aborts the run with a non-zero exit and a loud log — a half-migrated
    database is never reported as success.
  * Historical migrations are NOT rewritten. The ledger makes the previously
    non-idempotent files (011, 014, 015, 034) run exactly once. Migration 034
    (DROP INDEX CONCURRENTLY) additionally requires per-statement autocommit.

The application's runtime DDL (``src.db.init_db``, ``RicoDB._RICO_SCHEMA_DDL``,
and the four startup migrations) remains the schema base and runs first on a
fresh database — exactly as production boot does. This runner manages the
numbered-migration ledger on top of it.

Never log database credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("db_migrations")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Fixed advisory-lock key shared by every runner instance ("RICO").
_ADVISORY_LOCK_KEY = 0x5249434F

# Migrations that require per-statement autocommit (cannot run inside a
# transaction block).
_AUTOCOMMIT_MIGRATIONS = frozenset({"034"})

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT        PRIMARY KEY,
    name       TEXT        NOT NULL,
    checksum   TEXT        NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


def _dsn_from_env() -> str:
    dsn = os.getenv("DATABASE_URL") or os.getenv("RICO_TEST_DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL (or RICO_TEST_DATABASE_URL) is not set")
    return dsn


def _parse_migration(path: Path) -> Tuple[str, str]:
    """Return (version, name) from a migrations/NNN_snake_name.sql filename."""
    stem = path.name
    version = stem.split("_", 1)[0]
    return version, stem


def _list_migrations() -> List[Path]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    return sorted(
        p for p in MIGRATIONS_DIR.glob("*.sql") if p.name[:3].isdigit()
    )


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn, connect_timeout=10)


def _acquire_lock(conn) -> None:
    """Hold the runner's session-level advisory lock for this connection."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
    conn.commit()


def _release_lock(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))
        conn.commit()
    except Exception:
        pass


def _ensure_ledger(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_LEDGER_DDL)
    conn.commit()


def _read_applied(conn) -> Dict[str, dict]:
    applied: Dict[str, dict] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT version, name, checksum FROM schema_migrations")
        for version, name, checksum in cur.fetchall():
            applied[str(version)] = {"name": name, "checksum": checksum}
    return applied


def _apply_migration_file(conn, path: Path, version: str, autocommit: bool) -> None:
    sql = path.read_text(encoding="utf-8")

    if autocommit:
        # DROP INDEX CONCURRENTLY cannot run inside a transaction block. Run
        # each statement with autocommit on, exactly as the Neon-console manual
        # path did. IF EXISTS keeps each statement safe to (re)run.
        # Comment lines are stripped first so a `;` inside a comment cannot
        # split a statement in half.
        body = "\n".join(st for st in sql.splitlines() if not st.lstrip().startswith("--"))
        statements = [
            s.strip()
            for s in body.split(";")
            if s.strip() and not s.strip().startswith("--")
        ]
        prior = conn.autocommit
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                for statement in statements:
                    if not statement:
                        continue
                    cur.execute(statement)
        finally:
            conn.autocommit = prior
        return

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _bootstrap_runtime_ddl(dsn: str) -> None:
    """Apply the application's runtime DDL (production boot order).

    The numbered migrations assume the runtime-created base tables
    (rico_users, rico_profiles, settings, …) exist — a documented
    split-brain that previously made a FRESH production database
    impossible to migrate (migration 009 references rico_users). The
    runner therefore bootstraps the same idempotent runtime DDL the app
    would (CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS), then
    applies the numbered migrations. Safe to run on an existing database.
    """
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = dsn
    try:
        from src.db import init_db
        from src.rico_db import RicoDB

        init_db()
        RicoDB(database_url=dsn).init()
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev


def apply_all(dsn: str, target: Optional[str] = None) -> Dict[str, str]:
    """Apply all pending numbered migrations in order; return applied map.

    A fresh database is first bootstrapped with the runtime DDL (idempotent),
    then the numbered migrations apply in numeric order. Raises on any failure
    after logging the failing migration. The advisory lock is held for the whole
    run, and acquired BEFORE the ledger is created so two simultaneous
    first-runs cannot race the CREATE TABLE.
    """
    conn = _connect(dsn)
    try:
        _acquire_lock(conn)
        _ensure_ledger(conn)

        # Fresh or existing database alike: ensure the runtime base schema the
        # numbered migrations assume. Idempotent; see _bootstrap_runtime_ddl.
        _bootstrap_runtime_ddl(dsn)

        applied = _read_applied(conn)
        pending = []
        for path in _list_migrations():
            version, name = _parse_migration(path)
            if target is not None and version > target:
                continue
            if version in applied:
                if applied[version]["checksum"] != _checksum(path):
                    logger.error(
                        "migration_checksum_mismatch version=%s name=%s — the "
                        "historical file changed after it was applied; refusing "
                        "to re-run (write a forward migration instead)",
                        version, name,
                    )
                    raise RuntimeError(f"checksum mismatch for migration {version}")
                continue
            pending.append((version, name, path))

        for version, name, path in pending:
            logger.info("migration_apply version=%s name=%s", version, name)
            try:
                _apply_migration_file(
                    conn, path, version, autocommit=version in _AUTOCOMMIT_MIGRATIONS
                )
            except Exception as exc:
                logger.exception(
                    "migration_failed version=%s name=%s — schema is partially "
                    "migrated; the failing migration is NOT recorded",
                    version, name,
                )
                raise RuntimeError(f"migration {version} failed: {exc}") from exc

            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    "VALUES (%s, %s, %s)",
                    (version, name, _checksum(path)),
                )
            conn.commit()
            logger.info("migration_applied version=%s name=%s", version, name)

        return {v: a["name"] for v, a in _read_applied(conn).items()}
    finally:
        _release_lock(conn)
        conn.close()


def check(dsn: str) -> List[str]:
    """Read-only drift report: list of problems (empty == clean). Never mutates.

    Takes the advisory lock so a concurrent ``apply_all`` cannot race the
    ledger creation.
    """
    conn = _connect(dsn)
    try:
        _acquire_lock(conn)
        _ensure_ledger(conn)
        applied = _read_applied(conn)
        problems: List[str] = []

        disk_versions = {_parse_migration(p)[0]: p for p in _list_migrations()}
        for version, path in sorted(disk_versions.items()):
            if version not in applied:
                problems.append(f"pending migration {version} ({path.name})")
            elif applied[version]["checksum"] != _checksum(path):
                problems.append(
                    f"checksum mismatch migration {version}: file changed after apply"
                )
        for version in sorted(set(applied) - set(disk_versions)):
            problems.append(
                f"applied migration {version} ({applied[version]['name']}) "
                "no longer exists on disk"
            )
        return problems
    finally:
        _release_lock(conn)
        conn.close()


def status(dsn: str) -> None:
    conn = _connect(dsn)
    try:
        _ensure_ledger(conn)
        applied = _read_applied(conn)
        disk = {_parse_migration(p)[0]: p for p in _list_migrations()}
        for version in sorted(set(disk) | set(applied)):
            marker = "applied" if version in applied else "pending"
            print(f"{version:>4}  {marker:8} {applied.get(version, {}).get('name') or disk[version].name}")
        print(f"\n{len(applied)} applied / {len(disk)} on disk")
    finally:
        conn.close()


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rico migration runner")
    parser.add_argument("--dsn", help="DATABASE_URL (defaults to env)")
    parser.add_argument("--target", help="apply up to and including this version")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apply")
    sub.add_parser("check")
    sub.add_parser("status")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    dsn = args.dsn or _dsn_from_env()

    if args.command == "apply":
        apply_all(dsn, target=args.target)
        return 0
    if args.command == "check":
        problems = check(dsn)
        for p in problems:
            logger.error("drift: %s", p)
        return 1 if problems else 0
    if args.command == "status":
        status(dsn)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_main())
