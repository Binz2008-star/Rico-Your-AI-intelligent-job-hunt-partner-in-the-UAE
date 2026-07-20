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
  5. Cleanup: always removes the synthetic user and every row it created
     (chat rows, rico_users, verification tokens, users) — mirrors the
     session_smoke_1197 cleanup exactly.

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

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


def call(method: str, url: str, body: dict | None = None, timeout: int = 90):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "rico-delivery-smoke/1.0")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, data=data, timeout=timeout) as resp:
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

        # ── 4. authenticated SSE stream ───────────────────────────────────
        req = urllib.request.Request(f"{BACKEND}/api/v1/rico/chat/stream", method="POST")
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
                for line in raw.decode(errors="replace").splitlines():
                    if line.startswith("data:"):
                        frames += 1
                        try:
                            evt = json.loads(line[5:].strip())
                            if evt.get("type") == "done":
                                done_ok = True
                        except Exception:
                            pass
        except Exception as exc:
            record("authenticated SSE stream", False, f"{type(exc).__name__}: {exc}")
        else:
            record(
                "authenticated SSE stream",
                status == 200 and "text/event-stream" in ctype and frames >= 1 and done_ok,
                f"HTTP {status} content-type={ctype.split(';')[0]} data_frames={frames} done_json={done_ok}",
            )

    finally:
        # ── 5. cleanup — always (mirrors session_smoke_1197) ──────────────
        try:
            with conn.cursor() as cur:
                if rico_uid:
                    cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,))
                    cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
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
