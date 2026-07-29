#!/usr/bin/env python3
"""Fail-closed cleanup of rows left by Delivery Smoke synthetic accounts.

This script deletes only rows matching the exact synthetic-identity contract
used by ``scripts/audit_delivery_smoke_residuals.py``. It defaults to
``commit=false`` (dry run) and must be explicitly authorized with the
``CLEANUP_CONFIRM`` environment variable.

Safety contract:

- Reuses the audit's exact synthetic candidate predicate and table list.
- No date-only, domain-wide, wildcard, or heuristic deletion.
- Runs a read-only precheck against the expected fingerprint and aborts if
  any count or FK contract differs.
- Direct-email residuals are deleted explicitly; ``rico_users`` rows are
  deleted last so their ON DELETE CASCADE children are removed by the schema.
- Runs inside one transaction. On any mismatch or postcheck failure the
  transaction is rolled back and nothing is committed.
- Default is ``commit=false``; set ``CLEANUP_COMMIT=true`` to actually mutate
  production data.
- Logs aggregates only (table names and counts). No email, UUID, message,
  CV/job payload, or token is printed.

Required environment variables:
    CLEANUP_CONFIRM  Must equal ``CLEANUP-DELIVERY-RESIDUALS``.
    DATABASE_URL     Neon connection string.
    CLEANUP_COMMIT   ``true`` to commit; any other value (or absent) is dry-run.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2

# The audit module exits on import unless its confirmation gate is set.
os.environ.setdefault("AUDIT_CONFIRM", "AUDIT-DELIVERY-RESIDUALS")

# Import the audit module so we reuse its namespace, table contract, predicates,
# and cascade-verification logic verbatim.
import importlib.util

_AUDIT_SCRIPT = Path(__file__).resolve().parent / "audit_delivery_smoke_residuals.py"
_spec = importlib.util.spec_from_file_location("_audit_mod", _AUDIT_SCRIPT)
_AUDIT_MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_AUDIT_MOD)

CONFIRMATION = "CLEANUP-DELIVERY-RESIDUALS"
PATTERN = _AUDIT_MOD.PATTERN
TABLES = _AUDIT_MOD.TABLES
build_predicate = _AUDIT_MOD.build_predicate
zero_is_provable = _AUDIT_MOD.zero_is_provable
STATUS_CONTRACT = _AUDIT_MOD.STATUS_CONTRACT
STATUS_UNRESOLVABLE = _AUDIT_MOD.STATUS_UNRESOLVABLE

# Exact preflight fingerprint observed by audit run 30475312924.
EXPECTED_FINGERPRINT: dict[str, int] = {
    "users": 0,
    "email_verification_tokens": 0,
    "rico_onboarding_states": 8,
    "learning_signals": 3,
    "user_documents": 0,
    "rico_users": 8,
    "user_job_context": 5,
    "chat_operations": 3,
    "rico_profiles": 4,
    "rico_chat_history": 48,
    "rico_job_recommendations": 5,
}


class CleanupError(RuntimeError):
    """Raised when preflight, deletion, or postcheck fails closed."""


class _NoDsnError(CleanupError):
    pass


def _require_confirmation() -> None:
    if os.environ.get("CLEANUP_CONFIRM") != CONFIRMATION:
        print(
            f"Refusing to run: set CLEANUP_CONFIRM={CONFIRMATION} to confirm. "
            "This script may delete production data; read the source first.",
            file=sys.stderr,
        )
        sys.exit(2)


def _parse_commit() -> bool:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Actually delete rows. Without this flag the script rolls back.",
    )
    args = parser.parse_args()
    env_commit = os.environ.get("CLEANUP_COMMIT", "").lower() == "true"
    return args.commit or env_commit


def _open_read_only() -> psycopg2.extensions.connection:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise _NoDsnError("DATABASE_URL is not set")
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True, autocommit=False)
    return conn


def _open_read_write() -> psycopg2.extensions.connection:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise _NoDsnError("DATABASE_URL is not set")
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=False, autocommit=False)
    return conn


def _preflight(conn: psycopg2.extensions.connection) -> dict[str, int]:
    """Run the read-only audit and require the exact expected fingerprint."""
    rows = _AUDIT_MOD.run_audit(conn)
    observed: dict[str, int] = {}
    for row in rows:
        table = row["table"]
        status = row.get("status", "")
        if status in (STATUS_CONTRACT, STATUS_UNRESOLVABLE):
            raise CleanupError(
                f"Preflight INCONCLUSIVE for {table}: {status} — "
                "cleanup cannot proceed while the contract is unproven"
            )
        if "synthetic_row_count" not in row:
            raise CleanupError(
                f"Preflight could not count {table}: {row.get('detail', status)}"
            )
        observed[table] = int(row["synthetic_row_count"])

    if observed != EXPECTED_FINGERPRINT:
        diffs = []
        for table in EXPECTED_FINGERPRINT:
            exp = EXPECTED_FINGERPRINT[table]
            got = observed.get(table, "missing")
            if got != exp:
                diffs.append(f"{table}: expected {exp}, observed {got}")
        raise CleanupError(
            "Preflight fingerprint mismatch — cleanup aborted with no changes:\n  "
            + "\n  ".join(diffs)
        )
    return observed


def _delete_statements() -> list[tuple[str, str]]:
    """Return ordered (table, predicate) DELETE pairs for direct-email tables.

    ``rico_users`` is ordered last so its ON DELETE CASCADE children are
    removed by the live schema. UUID-child tables are not deleted manually.
    """
    direct = [
        (table, key_col, mode)
        for table, key_col, mode, _ in TABLES
        if mode in ("email_direct", "rico_self")
    ]
    # Move rico_users to the end.
    ordered: list[tuple[str, str, str]] = []
    rico_users_entry: tuple[str, str, str] | None = None
    for entry in direct:
        if entry[0] == "rico_users":
            rico_users_entry = entry
        else:
            ordered.append(entry)
    if rico_users_entry:
        ordered.append(rico_users_entry)
    return [
        (table, f"DELETE FROM {table} WHERE {build_predicate(key_col, mode)}")
        for table, key_col, mode in ordered
    ]


def _verify_cascade_contracts(cur) -> None:
    """Ensure every uuid_child table can be safely cascade-deleted."""
    for table, key_col, mode, _ in TABLES:
        if mode != "uuid_child":
            continue
        if not zero_is_provable(cur, table, key_col, mode):
            raise CleanupError(
                f"CASCADE contract missing for {table}.{key_col} — "
                "cannot delete rico_users and assume children vanish"
            )


def _postcheck(cur) -> dict[str, int]:
    """Count synthetic rows for every audited table inside the transaction."""
    remaining: dict[str, int] = {}
    for table, key_col, mode, _ in TABLES:
        predicate = build_predicate(key_col, mode)
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}", {"pat": PATTERN})
        remaining[table] = int(cur.fetchone()[0])
    return remaining


def run_cleanup(commit: bool) -> dict:
    """Execute preflight, delete, postcheck inside one transaction.

    Returns a report dict. If ``commit`` is False the transaction is rolled
    back. Raises CleanupError on any contract or count mismatch.
    """
    # 1. Preflight on a read-only connection.
    ro_conn = _open_read_only()
    try:
        preflight_counts = _preflight(ro_conn)
    finally:
        ro_conn.close()

    # 2. Open the mutation connection and run everything in one transaction.
    rw_conn = _open_read_write()
    deleted: dict[str, int] = {}
    try:
        with rw_conn.cursor() as cur:
            # Verify cascade FKs exist before relying on them.
            _verify_cascade_contracts(cur)

            # 3. Delete direct-email / rico_users rows explicitly.
            for table, sql in _delete_statements():
                expected = preflight_counts.get(table, 0)
                cur.execute(sql, {"pat": PATTERN})
                deleted[table] = cur.rowcount
                # Fail closed if the DELETE touched a different number of rows.
                if expected and cur.rowcount != expected:
                    raise CleanupError(
                        f"{table} DELETE rowcount mismatch: expected {expected}, got {cur.rowcount}"
                    )

            # 4. Postcheck: every audited table must show zero synthetic rows.
            remaining = _postcheck(cur)
            nonzero = {t: c for t, c in remaining.items() if c != 0}
            if nonzero:
                raise CleanupError(
                    "Postcheck failed — nonzero rows remain:\n  "
                    + "\n  ".join(f"{t}: {c}" for t, c in sorted(nonzero.items()))
                )

        if commit:
            rw_conn.commit()
            outcome = "committed"
        else:
            rw_conn.rollback()
            outcome = "dry-run (rolled back)"
    except Exception:
        rw_conn.rollback()
        raise
    finally:
        rw_conn.close()

    # Include cascade-removed children in the total; the postcheck proves them gone.
    total_deleted = sum(preflight_counts.values())
    return {
        "outcome": outcome,
        "commit": commit,
        "preflight_counts": preflight_counts,
        "deleted": deleted,
        "total_deleted": total_deleted,
        "postcheck_zero": True,
    }


def _report(report: dict) -> None:
    print("Delivery Smoke synthetic-residual cleanup")
    print(f"Namespace: {PATTERN}")
    print(f"Mode: {report['outcome']}")
    print()
    width = max(len(t) for t in EXPECTED_FINGERPRINT)
    print(f"{'table'.ljust(width)}  {'expected':>8}  {'deleted':>8}")
    for table in EXPECTED_FINGERPRINT:
        expected = report["preflight_counts"].get(table, 0)
        deleted = report["deleted"].get(table, 0)
        print(f"{table.ljust(width)}  {expected:>8}  {deleted:>8}")
    print()
    print(f"TOTAL rows {'that would be' if not report['commit'] else ''} deleted: {report['total_deleted']}")
    print("POSTCHECK: all 11 audited tables report zero synthetic rows")
    if not report["commit"]:
        print("No changes were committed. Set CLEANUP_COMMIT=true (or --commit) to apply.")


def main() -> int:
    _require_confirmation()
    commit = _parse_commit()
    report = run_cleanup(commit)
    _report(report)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except _NoDsnError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
    except CleanupError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
