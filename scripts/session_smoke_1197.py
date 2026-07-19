#!/usr/bin/env python3
"""#1197 Multi-session chat threads — production smoke (manual, CI-run).

Executes the owner's production-verification checklist against PRODUCTION
using ONE synthetic user with distinctive markers, mirroring the
followup_smoke.py precedent (test-safe isolated data, always cleans up):

  1. /version + /health — the deployed commit matches EXPECTED_SHA (passed
     by the workflow at dispatch time; defaults to the tip of main). When
     Render has no COMMIT_SHA and /version reports "unknown", an EXPLICIT
     per-run DEPLOY_FLOOR_ISO may accept started_at >= floor — there is no
     permanent time-based acceptance.
  2. Register a synthetic user, verify it directly in the DB (owner-approved
     production smoke), log in.
  3. GET /chat/sessions is 200 (not 404).
  4. Seed: one legacy turn (no session_id), thread A "اختبار ألفا", thread B
     "اختبار بيتا".
  5. Fresh reads (= reload): each thread shows ONLY its own message; the
     sessions list shows A, B and default.
  6. DELETE thread A: B and the legacy/default history remain.
  7. Neon rows: this user's rico_chat_history rows carry EXACTLY the sent
     thread UUIDs (B + default after deletion; no empty messages).
  8. Cleanup: delete the synthetic user's chat rows, rico_users row,
     verification tokens, and users row.

Secrets (DATABASE_URL) are read from env and never printed.
Refuses to run unless SMOKE_CONFIRM=SMOKE-1197 (APPLY-712 gate pattern).
Exit code 0 = all checks PASS, 1 = any FAIL.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import secrets as pysecrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

BASE = os.environ.get("RICO_API_BASE", "https://rico-job-automation-api.onrender.com")
DATABASE_URL = os.environ["DATABASE_URL"]
# The commit production is EXPECTED to serve. Passed by the workflow at
# dispatch time (defaults to github.sha = the tip of the dispatched ref), so
# the check always compares against CURRENT main — never a constant that goes
# stale as main advances (owner correction, 2026-07-19).
EXPECTED_SHA = os.environ["EXPECTED_SHA"].strip().lower()
# Optional fallback floor for deployments where Render has no COMMIT_SHA env
# and /version reports commit="unknown": an explicit ISO-8601 time the
# operator asserts the expected deploy went live. Provided per-run only —
# there is no permanent time-based acceptance.
DEPLOY_FLOOR_ISO = os.environ.get("DEPLOY_FLOOR_ISO", "").strip()

if os.environ.get("SMOKE_CONFIRM") != "SMOKE-1197":
    print("Refusing to run: set SMOKE_CONFIRM=SMOKE-1197 to confirm the production smoke.")
    sys.exit(2)

EMAIL = f"smoke-1197-{pysecrets.token_hex(4)}@synthetic-rico.test"
PASSWORD = "Smoke#1197-" + pysecrets.token_hex(8)
THREAD_A = str(uuid.uuid4())
THREAD_B = str(uuid.uuid4())

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


def call(method: str, path: str, body: dict | None = None, timeout: int = 90) -> tuple[int, str]:
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, data=data, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    rico_uid: str | None = None
    try:
        # ── 1. deployed version matches EXPECTED_SHA (current main) ──────
        code, body = call("GET", "/version")
        commit = "?"
        started_raw = ""
        floor_ok = None
        try:
            v = json.loads(body)
            commit = str(v.get("commit", "unknown")).strip().lower()
            started_raw = str(v.get("started_at", ""))
        except Exception:
            pass
        sha_match = commit not in ("", "unknown", "?") and (
            EXPECTED_SHA.startswith(commit) or commit.startswith(EXPECTED_SHA)
        )
        if not sha_match and commit == "unknown" and DEPLOY_FLOOR_ISO:
            # Explicit per-run fallback only (no COMMIT_SHA on Render).
            try:
                started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
                floor = datetime.fromisoformat(DEPLOY_FLOOR_ISO.replace("Z", "+00:00"))
                floor_ok = started >= floor
            except Exception:
                floor_ok = False
        version_pass = code == 200 and (sha_match or floor_ok is True)
        record(
            "deployed version matches EXPECTED_SHA",
            version_pass,
            f"HTTP {code} commit={commit} expected={EXPECTED_SHA[:12]} "
            f"sha_match={sha_match} started_at={started_raw} floor_ok={floor_ok}",
        )
        code, _ = call("GET", "/health")
        record("backend /health", code == 200, f"HTTP {code}")

        # ── 2. synthetic user ─────────────────────────────────────────────
        code, body = call("POST", "/api/v1/auth/register", {"email": EMAIL, "password": PASSWORD})
        record("register synthetic user", code in (200, 201), f"HTTP {code}")
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email_verified = TRUE WHERE email = %s", (EMAIL,))
            record("verify synthetic user in DB", cur.rowcount == 1, f"rows={cur.rowcount}")
        code, _ = call("POST", "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
        record("login", code == 200, f"HTTP {code}")

        # ── 3. sessions endpoint exists ───────────────────────────────────
        code, _ = call("GET", "/api/v1/rico/chat/sessions")
        record("GET /chat/sessions is 200 (not 404)", code == 200, f"HTTP {code}")

        # ── 4. seed legacy + thread A + thread B ─────────────────────────
        code, _ = call("POST", "/api/v1/rico/chat", {"message": "LEGACY-OMEGA baseline note"})
        record("legacy turn accepted", code == 200, f"HTTP {code}")
        code, _ = call("POST", "/api/v1/rico/chat", {"message": "اختبار ألفا PROJECT-ALPHA", "session_id": THREAD_A})
        record("thread A turn accepted", code == 200, f"HTTP {code}")
        code, _ = call("POST", "/api/v1/rico/chat", {"message": "اختبار بيتا PROJECT-BETA", "session_id": THREAD_B})
        record("thread B turn accepted", code == 200, f"HTTP {code}")

        # ── 5. fresh reads = reload; isolation ────────────────────────────
        _, ha = call("GET", f"/api/v1/rico/chat/history?session_id={THREAD_A}&limit=50")
        _, hb = call("GET", f"/api/v1/rico/chat/history?session_id={THREAD_B}&limit=50")
        _, hd = call("GET", "/api/v1/rico/chat/history?session_id=default&limit=50")
        record("history(A) contains ALPHA only",
               "PROJECT-ALPHA" in ha and "PROJECT-BETA" not in ha and "LEGACY-OMEGA" not in ha,
               f"alpha={'PROJECT-ALPHA' in ha} beta_leak={'PROJECT-BETA' in ha} legacy_leak={'LEGACY-OMEGA' in ha}")
        record("history(B) contains BETA only",
               "PROJECT-BETA" in hb and "PROJECT-ALPHA" not in hb,
               f"beta={'PROJECT-BETA' in hb} alpha_leak={'PROJECT-ALPHA' in hb}")
        record("history(default) keeps the legacy turn", "LEGACY-OMEGA" in hd, f"legacy={'LEGACY-OMEGA' in hd}")
        _, sess = call("GET", "/api/v1/rico/chat/sessions")
        default_listed = '"default"' in sess
        record("sessions list shows A, B and default",
               THREAD_A in sess and THREAD_B in sess and default_listed,
               f"A={THREAD_A in sess} B={THREAD_B in sess} default={default_listed}")

        # ── DB proof BEFORE deletion: real thread UUIDs on the rows ──────
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id::text AS id FROM rico_users WHERE external_user_id = %s OR email = %s "
                "ORDER BY updated_at DESC LIMIT 1",
                (EMAIL, EMAIL),
            )
            row = cur.fetchone()
            rico_uid = row["id"] if row else None
            threads: dict[str, int] = {}
            empties = -1
            if rico_uid:
                cur.execute(
                    "SELECT COALESCE(session_id::text,'default') AS sid, count(*) AS n "
                    "FROM rico_chat_history WHERE user_id = %s::uuid GROUP BY 1",
                    (rico_uid,),
                )
                threads = {r["sid"]: int(r["n"]) for r in cur.fetchall()}
                cur.execute(
                    "SELECT count(*) FROM rico_chat_history WHERE user_id = %s::uuid "
                    "AND (message IS NULL OR btrim(message) = '')",
                    (rico_uid,),
                )
                empties = int(cur.fetchone()["count"])
        record(
            "Neon rows carry the exact sent thread UUIDs",
            rico_uid is not None and THREAD_A in threads and THREAD_B in threads and "default" in threads,
            f"threads={sorted(threads)}",
        )
        record("no empty persistent rows", empties == 0, f"empty_rows={empties}")

        # ── 6. delete A; B + legacy remain ────────────────────────────────
        code, _ = call("DELETE", f"/api/v1/rico/chat/history?session_id={THREAD_A}")
        record("DELETE thread A", code == 204, f"HTTP {code}")
        _, ha2 = call("GET", f"/api/v1/rico/chat/history?session_id={THREAD_A}&limit=50")
        _, hb2 = call("GET", f"/api/v1/rico/chat/history?session_id={THREAD_B}&limit=50")
        _, hd2 = call("GET", "/api/v1/rico/chat/history?session_id=default&limit=50")
        record("thread A empty after delete", "PROJECT-ALPHA" not in ha2, f"alpha_gone={'PROJECT-ALPHA' not in ha2}")
        record("thread B intact after deleting A", "PROJECT-BETA" in hb2, f"beta={'PROJECT-BETA' in hb2}")
        record("legacy/default intact after deleting A", "LEGACY-OMEGA" in hd2, f"legacy={'LEGACY-OMEGA' in hd2}")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT count(*) FROM rico_chat_history WHERE user_id = %s::uuid AND session_id = %s::uuid",
                (rico_uid, THREAD_A),
            )
            a_rows = int(cur.fetchone()["count"])
        record("Neon: zero rows remain for deleted thread A", a_rows == 0, f"rows={a_rows}")

    finally:
        # ── 8. cleanup — always ───────────────────────────────────────────
        try:
            with conn.cursor() as cur:
                if rico_uid:
                    cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,))
                    cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
                cur.execute("DELETE FROM email_verification_tokens WHERE user_email = %s", (EMAIL,))
                cur.execute("DELETE FROM users WHERE email = %s", (EMAIL,))
            print("[CLEANUP] synthetic user and all its rows removed")
        except Exception as exc:  # cleanup must never mask results
            print(f"[CLEANUP-WARN] {type(exc).__name__}: manual cleanup may be needed for {EMAIL}")
        conn.close()

    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"RESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    print("SMOKE: ALL GREEN" if not failed else f"SMOKE: FAILURES: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
