#!/usr/bin/env python3
"""CV golden-journey production smoke (manual, CI-run).

Proves the current CV product journey end to end against PRODUCTION using one
disposable synthetic account, then removes every row it created:

  1. the deployed commit is the one under test (``EXPECTED_SHA``) and /health is ok;
  2. a synthetic user registers, is email-verified, and logs in;
  3. a small valid PDF CV uploads through the real parse path
     (``POST /api/v1/rico/upload-cv``) and is confirmed into the profile
     (``POST /api/v1/rico/confirm-cv-profile``);
  4. the CV appears in My Files (``GET /api/v1/user/files``) — the #1425 surface
     that must distinguish an unavailable store (503) from a verified empty list;
  5. an English CV-analysis ask does NOT route to job search (#1426);
  6. an Arabic CV-analysis ask does NOT route to job search (#1426);
  7. the CV and profile survive logout → login;
  8. the document deletes cleanly and My Files reports it gone;
  9. cleanup removes the synthetic user and every dependent row, and the smoke
     re-reads the database to prove no residual row survives.

Safety contract:
  * one dedicated synthetic account per run (``@synthetic-rico.test``), never a
    real user, and no owner/test account is referenced;
  * the only SQL writes are the one email-verification update and the final
    cleanup deletes — the exact narrow pattern already used by
    ``scripts/delivery_smoke.py``; no ownership repair, no schema change,
    no broad SQL;
  * credentials, cookies and reply bodies are never printed;
  * a cleanup failure, or any residual row, fails the smoke.

Required environment variables:
    SMOKE_CONFIRM   Must equal ``SMOKE-CV-JOURNEY``.
    EXPECTED_SHA    Commit production must currently serve.
    DATABASE_URL    Neon connection string (verification + cleanup only).

Optional environment variables:
    RICO_API_BASE   Defaults to the Render production backend.
    SMOKE_TIMEOUT   Per-request timeout in seconds; defaults to 90.

Exit code 0 = every check and cleanup passed. Any uncertainty fails closed.
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

BACKEND = os.environ.get("RICO_API_BASE", "https://rico-job-automation-api.onrender.com").rstrip("/")
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "90"))
CONFIRMATION = "SMOKE-CV-JOURNEY"

if os.environ.get("SMOKE_CONFIRM") != CONFIRMATION:
    print(f"Refusing to run: set SMOKE_CONFIRM={CONFIRMATION} to confirm the production smoke.")
    sys.exit(2)

EXPECTED_SHA = os.environ.get("EXPECTED_SHA", "").strip()
if not EXPECTED_SHA:
    print("Refusing to run: EXPECTED_SHA is required so the smoke names the commit it tested.")
    sys.exit(2)

DATABASE_URL = os.environ["DATABASE_URL"]

EMAIL = f"smoke-cv-{pysecrets.token_hex(4)}@synthetic-rico.test"
PASSWORD = "Smoke#CV-" + pysecrets.token_hex(8)
CV_FILENAME = "synthetic-cv.pdf"

#: The English and Arabic analysis asks under the #1426 contract. Both must be
#: answered as a CV analysis and neither may start a job search.
EN_ANALYSIS_ASK = "analyse my cv please"
AR_ANALYSIS_ASK = "حلل سيرتي الذاتية"

#: A reply that means "we ran a job search". #1426 is precisely the defect where
#: an analysis ask fell through to the bare-role gate and became a search.
JOB_SEARCH_TYPES = frozenset({"job_matches", "job_list", "search_results"})
JOB_SEARCH_INTENTS = frozenset({"search_jobs", "job_search"})

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# The production auth cookie is domain-scoped to .ricohunt.com (auth.py
# _cookie_domain). This smoke talks to the backend host directly, so the
# cookiejar cannot be trusted to round-trip it — the same transport fault #1264
# fixed in session_smoke_1197.py. Capture the raw Set-Cookie at login and replay
# it explicitly on every authenticated call.
_auth_cookie: str | None = None

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {evidence}")


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


def call(method: str, url: str, body: dict | None = None, timeout: int = TIMEOUT):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "rico-cv-journey-smoke/1.0")
    if _auth_cookie:
        req.add_header("Cookie", _auth_cookie)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, data=data, timeout=timeout) as resp:
            _capture_auth_cookie(resp)
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def call_multipart(url: str, field: str, filename: str, payload: bytes, timeout: int = TIMEOUT):
    boundary = "----RicoCVSmoke" + pysecrets.token_hex(8)
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/pdf\r\n\r\n",
        payload,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(url, method="POST", data=body)
    req.add_header("User-Agent", "rico-cv-journey-smoke/1.0")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if _auth_cookie:
        req.add_header("Cookie", _auth_cookie)
    try:
        with opener.open(req, timeout=timeout) as resp:
            _capture_auth_cookie(resp)
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def as_json(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw.decode(errors="replace"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def build_pdf() -> bytes:
    """A small, structurally valid single-page PDF carrying readable CV text.

    Offsets in the xref table are computed from the real byte positions, so the
    file parses with a strict reader rather than only passing the magic-byte gate.
    """
    lines = [
        "Sara Al Mansoori",
        "Accountant - Dubai, UAE",
        "Experience: 5 years in financial reporting and reconciliation.",
        "Skills: Accounting, Financial Reporting, Excel, IFRS.",
        "Education: BSc Accounting.",
    ]
    text_ops = "BT /F1 12 Tf 72 760 Td 16 TL\n" + "".join(
        f"({line}) Tj T*\n" for line in lines
    ) + "ET"
    stream = text_ops.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def assert_not_job_search(label: str, status: int, raw: bytes) -> None:
    payload = as_json(raw)
    rtype = str(payload.get("type") or "")
    intent = str(payload.get("intent") or "")
    routed_to_search = rtype in JOB_SEARCH_TYPES or intent in JOB_SEARCH_INTENTS
    # `jobs` carrying results is independent proof a search ran, whatever the
    # reply called itself.
    jobs = payload.get("jobs")
    carried_jobs = isinstance(jobs, list) and len(jobs) > 0
    record(
        f"{label} does not route to job search",
        status == 200 and not routed_to_search and not carried_jobs,
        f"HTTP {status} type={rtype or '-'} intent={intent or '-'} jobs={len(jobs) if isinstance(jobs, list) else 0}",
    )


def main() -> int:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    rico_uid = None
    doc_id = None
    try:
        # ── 1. the commit under test ──────────────────────────────────────
        status, raw = call("GET", f"{BACKEND}/version")
        served = str(as_json(raw).get("commit") or "")
        record(
            "deployed version matches EXPECTED_SHA",
            status == 200 and served == EXPECTED_SHA,
            f"HTTP {status} served={served[:12]} expected={EXPECTED_SHA[:12]} match={served == EXPECTED_SHA}",
        )
        status, raw = call("GET", f"{BACKEND}/health")
        record("backend /health", status == 200 and as_json(raw).get("status") == "ok", f"HTTP {status}")

        # ── 2. synthetic identity ─────────────────────────────────────────
        status, _ = call("POST", f"{BACKEND}/api/v1/auth/register", {"email": EMAIL, "password": PASSWORD})
        record("register synthetic user", status in (200, 201), f"HTTP {status}")
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email_verified = TRUE WHERE email = %s", (EMAIL,))
            record("verify synthetic user in DB", cur.rowcount == 1, f"rows={cur.rowcount}")
        status, _ = call("POST", f"{BACKEND}/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
        record("login sets session", status == 200, f"HTTP {status}")
        status, raw = call("GET", f"{BACKEND}/api/v1/me")
        me = as_json(raw)
        record(
            "/me authenticated",
            status == 200 and me.get("authenticated") is True and bool(me.get("guest")) is False,
            f"HTTP {status} authenticated={me.get('authenticated')} guest={bool(me.get('guest'))}",
        )
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rico_users WHERE email = %s", (EMAIL,))
            row = cur.fetchone()
            rico_uid = str(row[0]) if row else None

        # ── 3. upload the CV through the real parse path ──────────────────
        pdf = build_pdf()
        status, raw = call_multipart(f"{BACKEND}/api/v1/rico/upload-cv", "file", CV_FILENAME, pdf, timeout=120)
        upload = as_json(raw)
        preview = upload.get("preview") or upload.get("profile_preview") or {}
        upload_id = upload.get("upload_id")
        record(
            "upload CV (PDF) accepted",
            status == 200 and isinstance(preview, dict),
            f"HTTP {status} bytes={len(pdf)} has_preview={bool(preview)} has_upload_id={bool(upload_id)}",
        )

        # ── 4. confirm it into the profile so it becomes a stored document ─
        status, raw = call(
            "POST",
            f"{BACKEND}/api/v1/rico/confirm-cv-profile",
            {"preview": preview, "filename": CV_FILENAME, "doc_type": "cv", "upload_id": upload_id},
            timeout=120,
        )
        record("confirm CV into profile", status == 200, f"HTTP {status} cv_status={as_json(raw).get('cv_status') or '-'}")

        # ── 5. My Files shows it (#1425: 503 ≠ empty list) ────────────────
        status, raw = call("GET", f"{BACKEND}/api/v1/user/files")
        files = as_json(raw).get("files") or []
        cvs = [f for f in files if isinstance(f, dict) and f.get("doc_type") == "cv"]
        doc_id = next((str(f.get("id")) for f in cvs if f.get("id") not in (None, "profile-cv")), None)
        record(
            "CV appears in My Files",
            status == 200 and len(cvs) >= 1,
            f"HTTP {status} files={len(files)} cv_entries={len(cvs)}",
        )

        # ── 6. analysis asks must not become job searches (#1426) ─────────
        status, raw = call("POST", f"{BACKEND}/api/v1/rico/chat", {"message": EN_ANALYSIS_ASK}, timeout=120)
        assert_not_job_search("EN CV analysis ask", status, raw)
        status, raw = call("POST", f"{BACKEND}/api/v1/rico/chat", {"message": AR_ANALYSIS_ASK}, timeout=120)
        assert_not_job_search("AR CV analysis ask", status, raw)

        # ── 7. persistence across logout → login ──────────────────────────
        status, _ = call("POST", f"{BACKEND}/api/v1/auth/logout")
        record("logout", status == 200, f"HTTP {status}")
        globals()["_auth_cookie"] = None
        jar.clear()
        status, _ = call("POST", f"{BACKEND}/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
        record("re-login", status == 200, f"HTTP {status}")
        status, raw = call("GET", f"{BACKEND}/api/v1/user/files")
        files_after = as_json(raw).get("files") or []
        cvs_after = [f for f in files_after if isinstance(f, dict) and f.get("doc_type") == "cv"]
        record(
            "CV persists after logout/login",
            status == 200 and len(cvs_after) >= 1,
            f"HTTP {status} cv_entries={len(cvs_after)}",
        )
        status, raw = call("GET", f"{BACKEND}/api/v1/rico/profile")
        profile = as_json(raw)
        record(
            "profile persists after logout/login",
            status == 200 and bool(profile),
            f"HTTP {status} cv_status={profile.get('cv_status') or profile.get('cv_state') or '-'}",
        )

        # ── 8. the user can delete their document ─────────────────────────
        if doc_id:
            status, _ = call("DELETE", f"{BACKEND}/api/v1/user/files/{doc_id}")
            record("delete synthetic CV document", status in (200, 204), f"HTTP {status}")
        else:
            record("delete synthetic CV document", False, "no deletable document id returned by My Files")
        status, raw = call("GET", f"{BACKEND}/api/v1/user/files")
        remaining = [
            f for f in (as_json(raw).get("files") or [])
            if isinstance(f, dict) and f.get("doc_type") == "cv" and str(f.get("id")) != "profile-cv"
        ]
        record(
            "My Files reports the document gone",
            status == 200 and not remaining,
            f"HTTP {status} stored_cv_rows_left={len(remaining)}",
        )

    finally:
        # ── 9. cleanup, then prove the cleanup ────────────────────────────
        cleaned = False
        try:
            with conn.cursor() as cur:
                if rico_uid:
                    cur.execute("DELETE FROM user_documents WHERE user_id = %s", (EMAIL,))
                    cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,))
                    cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
                else:
                    cur.execute("DELETE FROM user_documents WHERE user_id = %s", (EMAIL,))
                cur.execute("DELETE FROM email_verification_tokens WHERE user_email = %s", (EMAIL,))
                cur.execute("DELETE FROM users WHERE email = %s", (EMAIL,))
            cleaned = True
            print("[CLEANUP] synthetic user and all its rows removed")
        except Exception as exc:
            print(f"[CLEANUP-WARN] {type(exc).__name__}: manual cleanup may be needed for {EMAIL}")

        # A cleanup that reports success but leaves rows behind is still a FAIL.
        residual = -1
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT (SELECT COUNT(*) FROM users WHERE email = %s) "
                    "     + (SELECT COUNT(*) FROM user_documents WHERE user_id = %s) "
                    "     + (SELECT COUNT(*) FROM rico_users WHERE email = %s)",
                    (EMAIL, EMAIL, EMAIL),
                )
                residual = int(cur.fetchone()[0])
        except Exception as exc:
            print(f"[CLEANUP-WARN] residual check failed: {type(exc).__name__}")
        record("cleanup verified — no residual synthetic rows", cleaned and residual == 0, f"residual_rows={residual}")
        conn.close()

    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"RESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    print("SMOKE: ALL GREEN" if not failed else f"SMOKE: FAILURES: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
