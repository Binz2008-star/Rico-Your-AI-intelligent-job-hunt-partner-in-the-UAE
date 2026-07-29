#!/usr/bin/env python3
"""Read-only audit: count rows left behind by Delivery Smoke synthetic accounts.

`scripts/delivery_smoke.py` resolves its Rico identity immediately after login,
but registration only creates a ``rico_users`` row when a display name is
supplied — which that smoke does not send. The row is auto-provisioned later
(onboarding, first chat), so the id is ``None`` by the time cleanup runs and the
identity-scoped deletes are skipped. That smoke also has no post-cleanup read,
so it prints success either way. This audit answers, from the database, whether
rows actually remain. It makes no cleanup claim and changes nothing.

Safety contract — this script is READ ONLY and structurally incapable of writing:

  * the connection is opened read-only and every statement runs inside an
    explicitly ``READ ONLY`` transaction, so a stray write fails at the server;
  * only ``SELECT`` is issued;
  * the identity namespace is a module constant, never a workflow input — no
    table name, pattern, or predicate can be supplied from outside;
  * output is aggregate counts and timestamps only. No email, user id, CV text,
    chat message, token, operation payload or profile field is ever printed;
  * a table or column that cannot be proven present is reported as
    INCONCLUSIVE rather than silently counted as zero.

Required environment variables:
    AUDIT_CONFIRM  Must equal ``AUDIT-DELIVERY-RESIDUALS``.
    DATABASE_URL   Neon connection string.

Exit code 0 = the audit completed and reported. Non-zero = the audit itself
could not run. A non-zero residual count is reported, not raised — deciding what
to do about residue is the owner's call, not this script's.
"""
from __future__ import annotations

import os
import sys

import psycopg2

CONFIRMATION = "AUDIT-DELIVERY-RESIDUALS"

if os.environ.get("AUDIT_CONFIRM") != CONFIRMATION:
    print(f"Refusing to run: set AUDIT_CONFIRM={CONFIRMATION} to confirm the read-only audit.")
    sys.exit(2)

DATABASE_URL = os.environ["DATABASE_URL"]

#: The exact synthetic namespace `scripts/delivery_smoke.py:51` generates.
#: A module constant, deliberately not an input: nothing outside this file can
#: widen the audit's reach.
PATTERN = "smoke-delivery-%@synthetic-rico.test"

#: Identity resolution. Every table below is keyed one of three proven ways.
#:   "email"    — the column stores the canonical user id, which for an
#:                authenticated user is the email (src/api/routers/files.py:161,
#:                src/api/routers/onboarding.py:104).
#:   "rico_uuid"— the column is a UUID FK to rico_users.id (src/rico_db.py:112).
#:   "text_id"  — the column is TEXT holding either users.id or rico_users.id
#:                (migrations/051_chat_operations.sql:37; the delete in
#:                delivery_smoke.py:349 unions both).
_EMAIL_SET = "SELECT email FROM users WHERE email LIKE %(pat)s"
_RICO_UUID_SET = (
    "SELECT id FROM rico_users WHERE email LIKE %(pat)s OR external_user_id LIKE %(pat)s"
)
_TEXT_ID_SET = (
    "SELECT id::text FROM users WHERE email LIKE %(pat)s"
    " UNION SELECT id::text FROM rico_users"
    "   WHERE email LIKE %(pat)s OR external_user_id LIKE %(pat)s"
)

#: (table, key_column, key_mode, timestamp_column_candidates)
#: Only tables provable from repository evidence as written by the Delivery
#: journey (register -> verify -> login -> onboarding submit -> authenticated
#: chat -> SSE stream -> real search).
TABLES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("users", "email", "email", ("created_at",)),
    ("rico_users", "email", "rico_self", ("created_at",)),
    ("email_verification_tokens", "user_email", "email", ("created_at",)),
    ("rico_onboarding_states", "user_id", "email", ("updated_at",)),
    ("learning_signals", "canonical_user_id", "email", ("created_at", "timestamp")),
    ("user_documents", "user_id", "email", ("created_at",)),
    ("rico_profiles", "user_id", "rico_uuid", ("created_at",)),
    ("rico_chat_history", "user_id", "rico_uuid", ("created_at",)),
    ("chat_operations", "user_id", "text_id", ("created_at",)),
]


def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return cur.fetchone()[0] is not None


def columns_of(cur, table: str) -> set[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    return {r[0] for r in cur.fetchall()}


def audit_table(cur, table: str, key_col: str, mode: str, ts_candidates: tuple[str, ...]) -> dict:
    if not table_exists(cur, table):
        return {"table": table, "status": "INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH",
                "detail": "table not present"}

    cols = columns_of(cur, table)
    if key_col not in cols:
        return {"table": table, "status": "INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH",
                "detail": f"key column '{key_col}' absent"}

    ts_col = next((c for c in ts_candidates if c in cols), None)

    if mode == "email":
        predicate = f"{key_col} IN ({_EMAIL_SET})"
    elif mode == "rico_self":
        predicate = f"({key_col} LIKE %(pat)s OR external_user_id LIKE %(pat)s)"
    elif mode == "rico_uuid":
        predicate = f"{key_col} IN ({_RICO_UUID_SET})"
    elif mode == "text_id":
        predicate = f"{key_col} IN ({_TEXT_ID_SET})"
    else:  # pragma: no cover - guarded by the literal table map above
        return {"table": table, "status": "INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH",
                "detail": "unknown key mode"}

    ts_select = (
        f"MIN({ts_col})::text, MAX({ts_col})::text" if ts_col else "NULL::text, NULL::text"
    )
    cur.execute(
        f"SELECT COUNT(*), COUNT(DISTINCT {key_col}), {ts_select} "  # noqa: S608 - all identifiers are module constants
        f"FROM {table} WHERE {predicate}",
        {"pat": PATTERN},
    )
    total, distinct_keys, earliest, latest = cur.fetchone()
    return {
        "table": table,
        "synthetic_row_count": int(total),
        "distinct_synthetic_users": int(distinct_keys),
        "earliest_created_at": earliest or "-",
        "latest_created_at": latest or "-",
        "status": ("VERIFIED ZERO RESIDUALS" if total == 0 else "VERIFIED RESIDUALS PRESENT"),
        "ts_column": ts_col or "(none)",
    }


def main() -> int:
    # Read-only at the connection level, then again per transaction. Either alone
    # would do; both together mean a write cannot slip through a reconnect.
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_session(readonly=True, autocommit=False)
    rows: list[dict] = []
    try:
        # One transaction per table: a contract mismatch aborts only its own
        # transaction, so the remaining tables are still audited on a clean one
        # instead of the whole run dying on the first mismatch.
        for table, key_col, mode, ts in TABLES:
            try:
                with conn.cursor() as cur:
                    cur.execute("SET TRANSACTION READ ONLY")
                    rows.append(audit_table(cur, table, key_col, mode, ts))
            except Exception as exc:
                rows.append({
                    "table": table,
                    "status": "INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH",
                    "detail": type(exc).__name__,
                })
            finally:
                conn.rollback()
    finally:
        conn.close()

    width = max(len(r["table"]) for r in rows)
    print("Delivery Smoke synthetic-residual audit (namespace: smoke-delivery-*@synthetic-rico.test)")
    print()
    print(f"{'table'.ljust(width)}  {'rows':>6}  {'users':>6}  earliest              latest                status")
    for r in rows:
        if "synthetic_row_count" not in r:
            print(f"{r['table'].ljust(width)}  {'-':>6}  {'-':>6}  {'-':<20}  {'-':<20}  "
                  f"{r['status']} ({r.get('detail', '')})")
            continue
        print(
            f"{r['table'].ljust(width)}  {r['synthetic_row_count']:>6}  "
            f"{r['distinct_synthetic_users']:>6}  {r['earliest_created_at'][:19]:<20}  "
            f"{r['latest_created_at'][:19]:<20}  {r['status']}"
        )

    counted = [r for r in rows if "synthetic_row_count" in r]
    residual_total = sum(r["synthetic_row_count"] for r in counted)
    inconclusive = [r for r in rows if "synthetic_row_count" not in r]

    print()
    print(f"TOTAL synthetic rows observed: {residual_total}")
    print(f"Tables audited: {len(counted)}  |  Inconclusive: {len(inconclusive)}")
    if inconclusive:
        print("Inconclusive tables: " + ", ".join(r["table"] for r in inconclusive))
    if residual_total == 0 and not inconclusive:
        print("AUDIT: VERIFIED ZERO RESIDUALS")
    elif residual_total > 0:
        print("AUDIT: VERIFIED RESIDUALS PRESENT — no deletion performed, owner authorization required")
    else:
        print("AUDIT: INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH")
    print()
    print("This audit performed no writes and makes no cleanup claim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
