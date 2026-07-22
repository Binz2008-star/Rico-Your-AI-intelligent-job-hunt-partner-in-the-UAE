#!/usr/bin/env python3
"""Delivery smoke — real-domain verification of the user-facing surfaces.

Complements session_smoke_1197.py (which owns the /version SHA check, the
sessions API, and Neon row verification). This smoke covers the remaining
owner checklist items ON THE REAL DOMAINS:

  1. Frontend routes serve on ricohunt.com: /, /command, /profile, /jobs,
     /applications, /upload, /login → HTTP 200 text/html.
  2. Public (unauthenticated) chat works: POST /api/v1/rico/chat/public.
  3. Auth works end-to-end: register a synthetic user, verify directly in the
     DB (owner-approved production-smoke pattern), log in (JWT cookie).
  4. Authenticated SSE works: POST /api/v1/rico/chat/stream returns
     text/event-stream, at least one `data:` frame, and a terminal frame that
     parses as JSON with type=done (exercises the #1239 total encoder live).
  5. A REAL job search completes and reaches the user (slice-4 re-verification,
     TASK-20260721-016 conditions 3/5/6/7): the authenticated chat runs a real
     provider search, the reply carries verified jobs, and the chat_operations
     ownership store shows exactly ONE operation row for this user with
     status=completed and attempt=1 — no duplicate cascade, no stale-owner
     terminal write, and the row's existence proves the Postgres-backed
     operation store is active.
  6. Cleanup: always removes the synthetic user and every row it created
     (chat rows, chat_operations rows, rico_users, verification tokens,
     users) — mirrors the session_smoke_1197 cleanup exactly.

Secrets (DATABASE_URL) come from env and are never printed.
Refuses to run unless SMOKE_CONFIRM=DELIVERY-SMOKE (APPLY-712 gate pattern).
Exit code 0 = all checks PASS, 1 = any FAIL.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import secrets as pysecrets
import sys
import urllib.error
import urllib.request

import psycopg2

FRONTEND = os.environ.get("RICO_FRONTEND_BASE", "https://ricohunt.com")
BACKEND = os.environ.get("RICO_API_BASE", "https://rico-job-automation-api.onrender.com")
DATABASE_URL = os.environ["DATABASE_URL"]

if os.environ.get("SMOKE_CONFIRM") != "DELIVERY-SMOKE":
    print("Refusing to run: set SMOKE_CONFIRM=DELIVERY-SMOKE to confirm the production smoke.")
    sys.exit(2)

EMAIL = f"smoke-delivery-{pysecrets.token_hex(4)}@synthetic-rico.test"
PASSWORD = "Smoke#Del-" + pysecrets.token_hex(8)

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# The production auth cookie is domain-scoped to .ricohunt.com (auth.py
# _cookie_domain). This smoke talks to the backend host directly, so the
# cookiejar cannot be trusted to round-trip it — same failure #1264 fixed in
# session_smoke_1197.py. Capture the raw Set-Cookie at login and replay it as
# an explicit Cookie header on every authenticated call (incl. the SSE step).
_auth_cookie: str | None = None


def _capture_auth_cookie(resp) -> None:
    global _auth_cookie
    try:
        set_cookies = resp.headers.get_all("Set-Cookie") or []
    except Exception:
        return
    for sc in set_cookies:
        first = sc.split(";", 1)[0].strip()
        if first.startswith("access_token=") and len(first) > len("access_token=") + 8:
            _auth_cookie = first

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


def call(method: str, url: str, body: dict | None = None, timeout: int = 90):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "rico-delivery-smoke/1.0")
    if _auth_cookie:
        req.add_header("Cookie", _auth_cookie)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, data=data, timeout=timeout) as resp:
            _capture_auth_cookie(resp)
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    rico_uid = None
    try:
        # ── 1. frontend routes on the real domain ─────────────────────────
        for path in ("/", "/command", "/profile", "/jobs", "/applications", "/upload", "/login"):
            code, headers, _ = call("GET", f"{FRONTEND}{path}")
            ctype = headers.get("Content-Type", "")
            record(
                f"frontend {path}",
                code == 200 and "text/html" in ctype,
                f"HTTP {code} content-type={ctype.split(';')[0]}",
            )

        # ── 2. public chat (unauthenticated) ──────────────────────────────
        sid = "smoke-delivery-" + pysecrets.token_hex(6)
        code, _, body = call(
            "POST",
            f"{BACKEND}/api/v1/rico/chat/public",
            {"message": "hello", "session_id": sid},
            timeout=120,
        )
        ok = code == 200
        try:
            ok = ok and isinstance(json.loads(body.decode(errors="replace")), dict)
        except Exception:
            ok = False
        record("public chat responds", ok, f"HTTP {code} bytes={len(body)}")

        # ── 3. auth: register → DB-verify → login ─────────────────────────
        code, _, _ = call("POST", f"{BACKEND}/api/v1/auth/register", {"email": EMAIL, "password": PASSWORD})
        record("register synthetic user", code in (200, 201), f"HTTP {code}")
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email_verified = TRUE WHERE email = %s", (EMAIL,))
            record("verify synthetic user in DB", cur.rowcount == 1, f"rows={cur.rowcount}")
        code, _, _ = call("POST", f"{BACKEND}/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
        record("login sets session", code == 200, f"HTTP {code}")
        code, _, body = call("GET", f"{BACKEND}/api/v1/me")
        record("/me authenticated", code == 200 and b"true" in body.lower(), f"HTTP {code}")
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rico_users WHERE email = %s", (EMAIL,))
            row = cur.fetchone()
            rico_uid = str(row[0]) if row else None

        # ── 3b. complete the minimum profile through the REAL onboarding funnel ──
        # The chat deliberately gates job-search requests on a minimum profile
        # (evaluate_minimum_profile downgrade → type=onboarding) and gates
        # off-profile roles behind the role-fit clarification. The probe follows
        # the product funnel exactly like a real user: complete onboarding
        # first, then search a role that IS the profile's target role — so the
        # search must run the real provider cascade with no gate in the way.
        code, _, _ = call(
            "POST",
            f"{BACKEND}/api/v1/onboarding/submit",
            {
                "target_roles": ["Accountant"],
                "preferred_cities": ["Dubai"],
                "years_experience": 5,
                "skills": ["Accounting", "Financial Reporting", "Excel"],
            },
            timeout=60,
        )
        record("onboarding submit completes profile", code == 200, f"HTTP {code}")

        # ── 4a. control probes: isolate cookie transport vs the stream route ──
        # Evidence for the 2026-07-21 SSE 'Unauthorized' frame: (1) does the jar
        # still hold access_token? (2) does a NON-stream authenticated POST on
        # the same connection succeed? Together these separate a smoke-side
        # cookie-transport fault from a stream-route-specific auth fault.
        has_token = any(c.name == "access_token" for c in jar)
        record(
            "auth cookie present before stream",
            bool(_auth_cookie) or has_token,
            f"explicit={'yes' if _auth_cookie else 'no'} jar_cookies={[c.name for c in jar]}",
        )
        code, _, body = call(
            "POST",
            f"{BACKEND}/api/v1/rico/chat",
            {"message": "SMOKE-DELIVERY control ping"},
            timeout=120,
        )
        record("authenticated JSON chat (control)", code == 200, f"HTTP {code} bytes={len(body)}")

        # ── 4. authenticated SSE stream ───────────────────────────────────
        req = urllib.request.Request(f"{BACKEND}/api/v1/rico/chat/stream", method="POST")
        req.add_header("User-Agent", "rico-delivery-smoke/1.0")
        if _auth_cookie:
            req.add_header("Cookie", _auth_cookie)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "text/event-stream")
        payload = json.dumps({"message": "SMOKE-DELIVERY ping"}).encode()
        frames = 0
        done_ok = False
        ctype = ""
        status = 0
        try:
            with opener.open(req, data=payload, timeout=120) as resp:
                status = resp.status
                ctype = resp.headers.get("Content-Type", "")
                raw = b""
                # Bounded read: SSE terminates with the done event on this API.
                while len(raw) < 512_000:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    raw += chunk
                frame_types: list[str] = []
                last_error = ""
                for line in raw.decode(errors="replace").splitlines():
                    if line.startswith("data:"):
                        frames += 1
                        try:
                            evt = json.loads(line[5:].strip())
                            ftype = str(evt.get("type"))
                            frame_types.append(ftype)
                            if ftype == "done":
                                done_ok = True
                            elif ftype == "error":
                                # Diagnostic evidence only — the server's generic
                                # error string, never user content.
                                last_error = str(evt.get("message", ""))[:120]
                        except Exception:
                            frame_types.append("unparseable")
        except Exception as exc:
            record("authenticated SSE stream", False, f"{type(exc).__name__}: {exc}")
        else:
            # Evidence-grade summary: the exact frame-type sequence tells apart a
            # provider-side error frame from a transport cut before the done event.
            seq = ",".join(frame_types[:12]) or "none"
            extra = f" first_error={last_error!r}" if last_error else ""
            record(
                "authenticated SSE stream",
                status == 200 and "text/event-stream" in ctype and frames >= 1 and done_ok,
                f"HTTP {status} content-type={ctype.split(';')[0]} data_frames={frames} done_json={done_ok} frame_types={seq}{extra}",
            )

        # ── 5. real job search + ownership-store evidence ─────────────────
        # TASK-20260721-016 re-verification conditions 3/5/6/7. The message is
        # a plain English search request so the intent path runs the REAL
        # provider cascade for this synthetic (profile-less) user.
        code, _, body = call(
            "POST",
            f"{BACKEND}/api/v1/rico/chat",
            {"message": "Find accountant jobs in Dubai"},
            timeout=180,
        )
        def _find_jobs(node):
            if isinstance(node, dict):
                j = node.get("jobs")
                if isinstance(j, list):
                    return j
                for v in node.values():
                    found = _find_jobs(v)
                    if found is not None:
                        return found
            elif isinstance(node, list):
                for v in node:
                    found = _find_jobs(v)
                    if found is not None:
                        return found
            return None

        def _reply_evidence(raw: bytes):
            """(jobs_count, top_type, shape) for a chat reply body."""
            try:
                parsed = json.loads(raw.decode(errors="replace"))
            except Exception:
                return -1, "", "unparseable"
            jobs = _find_jobs(parsed)
            count = len(jobs) if jobs is not None else -1
            top_type = ""
            shape = ""
            if isinstance(parsed, dict):
                top_type = str(parsed.get("type") or "")
                snip = ""
                for key in ("message", "reply", "response", "text"):
                    val = parsed.get(key)
                    if isinstance(val, str) and val.strip():
                        snip = " ".join(val.split())[:180]
                        break
                shape = f"type={top_type} snippet={snip!r}"
            return count, top_type, shape

        jobs_count, top_type, resp_shape = _reply_evidence(body)
        # The role-fit guard may ask ONE clarification before spending a real
        # provider search on a role that does not match the CV profile (the
        # synthetic user has none) — intended product behavior. Follow the
        # conversational contract like a real user: confirm, then re-evaluate.
        clarified = False
        if code == 200 and top_type == "clarification":
            clarified = True
            code, _, body = call(
                "POST",
                f"{BACKEND}/api/v1/rico/chat",
                {"message": "YES"},
                timeout=180,
            )
            jobs_count, top_type, resp_shape = _reply_evidence(body)
        record(
            "real search completes and reaches the user",
            code == 200 and jobs_count >= 1,
            f"HTTP {code} jobs_in_reply={jobs_count} clarification_confirmed={clarified} {resp_shape}",
        )

        auth_uid = None
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (EMAIL,))
            row = cur.fetchone()
            auth_uid = str(row[0]) if row else None
        probe_ids = [uid for uid in (rico_uid, auth_uid) if uid]
        ops: list = []
        if probe_ids:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT operation_id, status, attempt, result_count "
                    "FROM chat_operations WHERE user_id = ANY(%s) ORDER BY created_at",
                    (probe_ids,),
                )
                ops = cur.fetchall()
        statuses = [(o[1], int(o[2])) for o in ops]
        record(
            "no duplicate cascade (single operation row)",
            len(ops) == 1,
            f"operation_rows={len(ops)} status_attempt={statuses}",
        )
        record(
            "operation completed by original owner (attempt=1)",
            len(ops) == 1 and ops[0][1] == "completed" and int(ops[0][2]) == 1,
            (
                f"status={ops[0][1]} attempt={ops[0][2]} result_count={ops[0][3]}"
                if ops
                else "no operation row found"
            ),
        )
        record(
            "postgres operation store active (auto mode, DB-backed)",
            len(ops) >= 1,
            f"rows_in_chat_operations={len(ops)}",
        )

    finally:
        # ── 6. cleanup — always (mirrors session_smoke_1197) ──────────────
        try:
            with conn.cursor() as cur:
                if rico_uid:
                    cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,))
                    cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
                cur.execute(
                    "DELETE FROM chat_operations WHERE user_id IN "
                    "(SELECT id::text FROM users WHERE email = %s UNION SELECT %s)",
                    (EMAIL, rico_uid or ""),
                )
                cur.execute("DELETE FROM email_verification_tokens WHERE user_email = %s", (EMAIL,))
                cur.execute("DELETE FROM users WHERE email = %s", (EMAIL,))
            print("[CLEANUP] synthetic user and all its rows removed")
        except Exception as exc:
            print(f"[CLEANUP-WARN] {type(exc).__name__}: manual cleanup may be needed for {EMAIL}")
        conn.close()

    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"RESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    print("SMOKE: ALL GREEN" if not failed else f"SMOKE: FAILURES: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
