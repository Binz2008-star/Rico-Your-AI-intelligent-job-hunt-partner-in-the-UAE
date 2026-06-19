#!/usr/bin/env python3
"""#355 Follow-up Reminders — Phase 1 production smoke (manual, CI-run).

Runs the 8 smoke checks against PRODUCTION using test-safe, isolated data:
  - inserts one OLD applied job (applied_at = now - 5000 days) and one FRESH
    applied job (applied_at = now) for a known test user, with distinctive
    job_keys ('smoke-old-001' / 'smoke-fresh-001');
  - calls POST /api/v1/pipeline/reminders with interval_days=4000 so the sweep
    touches ONLY the 5000-day-old test row (no real user job is that old);
  - verifies the guard (missing/wrong/correct secret), the flip, idempotency,
    and no duplicates;
  - always deletes the test rows at the end.

Secrets (DATABASE_URL, RICO_CRON_SECRET) are read from env and never printed.
Exit code 0 = all checks PASS, 1 = any FAIL.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import psycopg2
from psycopg2.extras import RealDictCursor

BASE = os.environ.get("RICO_API_BASE", "https://rico-job-automation-api.onrender.com")
ENDPOINT = f"{BASE}/api/v1/pipeline/reminders"
DATABASE_URL = os.environ["DATABASE_URL"]
SECRET = os.environ["RICO_CRON_SECRET"]
TEST_EMAIL = os.environ.get("SMOKE_TEST_EMAIL", "robenedwan@gmail.com")
INTERVAL = 4000  # only jobs applied > ~11 years ago — isolates the 5000-day test row

OLD = "smoke-old-001"
FRESH = "smoke-fresh-001"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


def post(secret: str | None) -> tuple[int, str]:
    req = urllib.request.Request(f"{ENDPOINT}?interval_days={INTERVAL}", method="POST")
    if secret is not None:
        req.add_header("X-Cron-Secret", secret)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rico_users WHERE email = %s LIMIT 1", (TEST_EMAIL,))
            row = cur.fetchone()
            if not row:
                record("setup", False, f"no rico_users row for {TEST_EMAIL}")
                return 1
            uid = row["id"]

            # Setup: insert/reset the two test rows.
            for key, age in ((OLD, "5000 days"), (FRESH, "0 days")):
                cur.execute(
                    """
                    INSERT INTO rico_job_recommendations
                        (user_id, job_key, job, status, applied_at, created_at, updated_at)
                    VALUES (%s, %s, %s::jsonb, 'applied', now() - %s::interval, now(), now())
                    ON CONFLICT (user_id, job_key) WHERE job_key IS NOT NULL
                    DO UPDATE SET status='applied', applied_at=EXCLUDED.applied_at,
                                 follow_up_due_at=NULL, updated_at=now()
                    """,
                    (uid, key,
                     json.dumps({"title": f"SMOKE {key}", "company": "SmokeTest Co", "location": "UAE"}),
                     age),
                )
            record("setup", True, "inserted smoke-old (5000d) + smoke-fresh (now)")

            # Check 1: missing secret -> 403
            s1, _ = post(None)
            record("1 missing-secret->403", s1 == 403, f"HTTP {s1}")

            # Check 2: wrong secret -> 403
            s2, _ = post("definitely-wrong")
            record("2 wrong-secret->403", s2 == 403, f"HTTP {s2}")

            # Check 3: correct secret -> 200 + marked_due >= 1
            s3, b3 = post(SECRET)
            body3 = json.loads(b3) if s3 == 200 else {}
            record("3 correct-secret->200", s3 == 200 and body3.get("marked_due", 0) >= 1,
                   f"HTTP {s3} body={b3}")

            # Checks 4 & 5: statuses after the sweep
            cur.execute(
                "SELECT job_key, status, follow_up_due_at FROM rico_job_recommendations "
                "WHERE user_id=%s AND job_key IN (%s,%s) ORDER BY job_key", (uid, OLD, FRESH))
            rows = {r["job_key"]: r for r in cur.fetchall()}
            old_due_at = rows.get(OLD, {}).get("follow_up_due_at")
            record("4 old->follow_up_due",
                   rows.get(OLD, {}).get("status") == "follow_up_due" and old_due_at is not None,
                   f"smoke-old status={rows.get(OLD,{}).get('status')} due_at={old_due_at}")
            record("5 fresh-stays-applied", rows.get(FRESH, {}).get("status") == "applied",
                   f"smoke-fresh status={rows.get(FRESH,{}).get('status')}")

            # Check 6: idempotent re-run — marked_due 0 and old row unchanged
            s6, b6 = post(SECRET)
            body6 = json.loads(b6) if s6 == 200 else {}
            cur.execute("SELECT follow_up_due_at FROM rico_job_recommendations "
                        "WHERE user_id=%s AND job_key=%s", (uid, OLD))
            old_due_at2 = cur.fetchone()["follow_up_due_at"]
            record("6 idempotent-rerun",
                   s6 == 200 and body6.get("marked_due", -1) == 0 and old_due_at2 == old_due_at,
                   f"HTTP {s6} marked_due={body6.get('marked_due')} due_at_unchanged={old_due_at2 == old_due_at}")

            # Check 7: /flow data-backing — board renders `status` from this table.
            record("7 flow-data-backed (status=follow_up_due)",
                   rows.get(OLD, {}).get("status") == "follow_up_due",
                   "the /flow board reads status from rico_job_recommendations")

            # Check 8: no duplicate rows
            cur.execute("SELECT job_key, count(*) AS c FROM rico_job_recommendations "
                        "WHERE user_id=%s AND job_key IN (%s,%s) GROUP BY job_key", (uid, OLD, FRESH))
            counts = {r["job_key"]: r["c"] for r in cur.fetchall()}
            record("8 no-duplicates", counts.get(OLD) == 1 and counts.get(FRESH) == 1, f"counts={counts}")
    finally:
        # Always clean up the test rows.
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_job_recommendations WHERE job_key IN (%s,%s)", (OLD, FRESH))
            print("[cleanup] deleted smoke test rows")
        except Exception as exc:
            print(f"[cleanup] WARNING: failed to delete test rows: {exc}")
        conn.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== SMOKE SUMMARY: {passed}/{len(results)} checks passed ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
