#!/usr/bin/env python3
"""Read-only audit: count rows left behind by Delivery Smoke synthetic accounts.

`scripts/delivery_smoke.py` resolves its Rico identity immediately after login,
but registration only creates a ``rico_users`` row when a display name is
supplied — which that smoke does not send. The row is auto-provisioned later
(onboarding, first chat), so the id is ``None`` by the time cleanup runs and the
identity-scoped deletes are skipped. That smoke also has no post-cleanup read,
so it prints success either way. This audit answers, from the database, whether
rows actually remain. It makes no cleanup claim and changes nothing.

Scope: **all historical Delivery Smoke synthetic accounts**, not one run. Rows
are never attributed to a specific workflow run — nothing in the schema records
which run created a row, so earliest/latest timestamps are reported as
observations and no run attribution is claimed.

Finding an orphan is the whole point, so the audit must not depend on the
parent identity surviving. Cleanup deletes the ``users`` row, and several
tables key on the canonical email with **no foreign key** to ``users`` — an
audit that resolved emails through ``users`` would report zero for exactly the
rows it exists to find. Email-keyed tables are therefore matched directly on
their own key column, and a count of zero is only reported as VERIFIED when
absence is actually provable:

  * email-keyed table            -> zero is provable (matched directly)
  * child of ``rico_users`` with a proven ``ON DELETE CASCADE`` foreign key
                                 -> zero is provable (the parent's removal
                                    guarantees the child's)
  * child without that guarantee, or keyed on an opaque parent id
                                 -> zero is NOT provable once the parent is
                                    gone: reported INCONCLUSIVE

A non-zero count is always authoritative: rows found are rows present.

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

#: The exact synthetic namespace `scripts/delivery_smoke.py:51` generates.
#: A module constant, deliberately not an input: nothing outside this file can
#: widen the audit's reach.
PATTERN = "smoke-delivery-%@synthetic-rico.test"

STATUS_ZERO = "VERIFIED ZERO RESIDUALS"
STATUS_PRESENT = "VERIFIED RESIDUALS PRESENT"
STATUS_CONTRACT = "INCONCLUSIVE — TABLE OR COLUMN CONTRACT MISMATCH"
STATUS_UNRESOLVABLE = "INCONCLUSIVE — SYNTHETIC ID CANNOT BE RECONSTRUCTED"

#: Resolves the surviving Rico identity rows. Used only by child tables; it is
#: deliberately NOT used for email-keyed tables, whose orphans must stay visible
#: after the parent is deleted.
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
    # Directly keyed on the canonical synthetic email — orphan-visible.
    ("users", "email", "email_direct", ("created_at",)),
    ("email_verification_tokens", "user_email", "email_direct", ("created_at",)),
    ("rico_onboarding_states", "user_id", "email_direct", ("updated_at",)),
    ("learning_signals", "canonical_user_id", "email_direct", ("created_at", "timestamp")),
    ("user_documents", "user_id", "email_direct", ("created_at",)),
    # rico_users carries the namespace on its own columns.
    ("rico_users", "email", "rico_self", ("created_at",)),
    # Children of rico_users, keyed by its UUID.
    ("rico_profiles", "user_id", "uuid_child", ("created_at",)),
    ("rico_chat_history", "user_id", "uuid_child", ("created_at",)),
    # Keyed on an opaque parent id (users.id or rico_users.id) as TEXT.
    ("chat_operations", "user_id", "text_id_child", ("created_at",)),
]

#: Child tables whose zero is only provable when this FK, with ON DELETE
#: CASCADE, is present in the live schema: (table, column) -> parent table.
_CASCADE_PARENT = {
    ("rico_profiles", "user_id"): "rico_users",
    ("rico_chat_history", "user_id"): "rico_users",
}


def build_predicate(key_col: str, mode: str) -> str:
    """Return the WHERE fragment for a key mode.

    Pure and identifier-only so the composition can be asserted in tests: the
    email-keyed branches must never reference the ``users`` table, or an orphan
    row would become invisible the moment its parent was deleted.
    """
    if mode == "email_direct":
        return f"{key_col} LIKE %(pat)s"
    if mode == "rico_self":
        return f"({key_col} LIKE %(pat)s OR external_user_id LIKE %(pat)s)"
    if mode == "uuid_child":
        return f"{key_col} IN ({_RICO_UUID_SET})"
    if mode == "text_id_child":
        return f"{key_col} IN ({_TEXT_ID_SET})"
    raise ValueError(f"unknown key mode: {mode!r}")


def zero_is_provable(cur, table: str, key_col: str, mode: str) -> bool:
    """Can a count of zero be trusted as real absence?

    For directly-keyed tables, yes: the query does not depend on a parent. For a
    child table, only when the live schema really enforces ON DELETE CASCADE
    from the parent — that is what makes "parent gone" imply "child gone".
    """
    if mode in ("email_direct", "rico_self"):
        return True
    if mode == "uuid_child":
        parent = _CASCADE_PARENT.get((table, key_col))
        if not parent:
            return False
        cur.execute(
            "SELECT c.confdeltype FROM pg_constraint c "
            "JOIN pg_class child ON child.oid = c.conrelid "
            "JOIN pg_class parent ON parent.oid = c.confrelid "
            "JOIN pg_attribute a ON a.attrelid = child.oid AND a.attnum = ANY(c.conkey) "
            "WHERE c.contype = 'f' AND child.relname = %s "
            "  AND parent.relname = %s AND a.attname = %s",
            (table, parent, key_col),
        )
        rows = cur.fetchall()
        # 'c' is ON DELETE CASCADE. Anything else (or no FK) cannot guarantee it.
        return any(r[0] == "c" for r in rows)
    # text_id_child: once the parent row is deleted its id is unrecoverable, so
    # absence can never be proven.
    return False


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
        return {"table": table, "status": STATUS_CONTRACT, "detail": "table not present"}

    cols = columns_of(cur, table)
    if key_col not in cols:
        return {"table": table, "status": STATUS_CONTRACT,
                "detail": f"key column '{key_col}' absent"}
    if mode == "rico_self" and "external_user_id" not in cols:
        return {"table": table, "status": STATUS_CONTRACT,
                "detail": "external_user_id absent"}

    ts_col = next((c for c in ts_candidates if c in cols), None)
    ts_select = f"MIN({ts_col})::text, MAX({ts_col})::text" if ts_col else "NULL::text, NULL::text"

    cur.execute(
        f"SELECT COUNT(*), COUNT(DISTINCT {key_col}), {ts_select} "  # noqa: S608 - identifiers are module constants
        f"FROM {table} WHERE {build_predicate(key_col, mode)}",
        {"pat": PATTERN},
    )
    total, distinct_keys, earliest, latest = cur.fetchone()
    total = int(total)

    if total > 0:
        status = STATUS_PRESENT          # finding rows is always authoritative
    elif zero_is_provable(cur, table, key_col, mode):
        status = STATUS_ZERO
    else:
        status = STATUS_UNRESOLVABLE     # absence cannot be proven — say so

    return {
        "table": table,
        "synthetic_row_count": total,
        "distinct_synthetic_users": int(distinct_keys),
        "earliest_created_at": earliest or "-",
        "latest_created_at": latest or "-",
        "status": status,
        "ts_column": ts_col or "(none)",
    }


def run_audit(conn) -> list[dict]:
    rows: list[dict] = []
    # One transaction per table: a contract mismatch aborts only its own
    # transaction, so the remaining tables are still audited on a clean one
    # instead of the whole run dying on the first mismatch.
    for table, key_col, mode, ts in TABLES:
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                rows.append(audit_table(cur, table, key_col, mode, ts))
        except Exception as exc:
            rows.append({"table": table, "status": STATUS_CONTRACT, "detail": type(exc).__name__})
        finally:
            conn.rollback()
    return rows


def report(rows: list[dict]) -> None:
    width = max(len(r["table"]) for r in rows)
    print("Delivery Smoke synthetic-residual audit")
    print("Namespace: smoke-delivery-*@synthetic-rico.test (ALL historical runs)")
    print("Rows are not attributed to any specific workflow run.")
    print()
    print(f"{'table'.ljust(width)}  {'rows':>6}  {'users':>6}  "
          f"{'earliest':<20}  {'latest':<20}  status")
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
    unproven = [r for r in rows if r["status"] in (STATUS_CONTRACT, STATUS_UNRESOLVABLE)]

    print()
    print(f"TOTAL synthetic rows observed: {residual_total}")
    print(f"Tables audited: {len(counted)}  |  Not provable: {len(unproven)}")
    if unproven:
        print("Not provable: " + ", ".join(f"{r['table']} [{r['status']}]" for r in unproven))
    if residual_total > 0:
        print("AUDIT: VERIFIED RESIDUALS PRESENT — no deletion performed, "
              "owner authorization required")
    elif unproven:
        print("AUDIT: INCONCLUSIVE — zero observed, but absence is not provable for every table")
    else:
        print("AUDIT: VERIFIED ZERO RESIDUALS")
    print()
    print("This audit performed no writes and makes no cleanup claim.")


def main() -> int:
    try:
        # Read-only at the connection level, then again per transaction. Either
        # alone would do; both together mean a write cannot slip through.
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.set_session(readonly=True, autocommit=False)
    except Exception as exc:
        # Never print the exception text: psycopg2 connection errors embed the
        # host and username from the DSN.
        print(f"Audit could not connect to the database: {type(exc).__name__}")
        return 2
    try:
        rows = run_audit(conn)
    finally:
        conn.close()
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
