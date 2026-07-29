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
    SMOKE_TIMEOUT   Per-request timeout in seconds; defaults to 45.

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
# 45s default, 90s for the four slow calls (upload, confirm, two chat turns).
# Worst case is 14*45 + 4*90 = 990s ~= 16.5 min of requests, against the
# workflow's 25-minute budget — so the runner cannot cancel the job mid-journey
# and skip the cleanup in `finally`, which is where the safety guarantee lives.
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "45"))
SLOW_TIMEOUT = TIMEOUT * 2
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

#: Every table this journey can write that is keyed on the canonical email.
#: None of them has a foreign key to `users`, so none is swept by deleting the
#: user — each has to be named explicitly in cleanup AND counted afterwards.
#:   cv_upload_artifacts      <- POST /rico/upload-cv (carries the parsed CV text)
#:   user_documents           <- POST /rico/confirm-cv-profile
#:   rico_onboarding_states   <- confirm-cv-profile -> set_onboarding_status
#:   learning_signals         <- profile-optimization usage recording
#:   email_verification_tokens<- registration
#:   chat_operations          <- only if an analysis ask regressed into a search
#:   user_job_context         <- only if such a search surfaced matches
_EMAIL_KEYED_TABLES: tuple[tuple[str, str], ...] = (
    ("cv_upload_artifacts", "user_id"),
    ("user_documents", "user_id"),
    ("rico_onboarding_states", "user_id"),
    ("learning_signals", "canonical_user_id"),
    ("email_verification_tokens", "user_email"),
    ("chat_operations", "user_id"),
    ("user_job_context", "user_id"),
)

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
    """Assert the reply is a real answer that is not a job search.

    The negative alone is not enough. ``rico_chat`` catches every exception and
    still answers HTTP 200 with ``type="error"``/``success=False``, so a total
    chat-pipeline outage would satisfy "did not route to job search" and score a
    PASS on a broken product. The reply must therefore also be a substantive
    non-error answer.
    """
    payload = as_json(raw)
    rtype = str(payload.get("type") or "")
    intent = str(payload.get("intent") or "")
    routed_to_search = rtype in JOB_SEARCH_TYPES or intent in JOB_SEARCH_INTENTS
    # Carrying results is independent proof a search ran, whatever the reply
    # called itself. The field is `matches` — that is what the search paths
    # populate and what the response model declares; `jobs` appears only on a
    # few cached-list replies. Checking `jobs` alone was an inert backstop that
    # printed 0 no matter what happened.
    results = payload.get("matches")
    if not isinstance(results, list):
        results = payload.get("jobs")
    carried_jobs = isinstance(results, list) and len(results) > 0
    answered = (
        payload.get("success") is not False
        and rtype != "error"
        and bool(str(payload.get("message") or "").strip())
    )
    record(
        f"{label} is answered and does not route to job search",
        status == 200 and answered and not routed_to_search and not carried_jobs,
        f"HTTP {status} type={rtype or '-'} intent={intent or '-'} "
        f"results={len(results) if isinstance(results, list) else 0} answered={answered}",
    )


def _finish() -> int:
    """Print the summary and return the exit code.

    Shared by the normal end of the journey and by the early abort, so an abort
    still reports everything recorded up to that point instead of exiting mute.
    """
    failed = [n for n, ok, _ in results if not ok]
    print()
    print(f"RESULT: {len(results) - len(failed)} passed, {len(failed)} failed")
    print("SMOKE: ALL GREEN" if not failed else f"SMOKE: FAILURES: {failed}")
    return 0 if not failed else 1


def main() -> int:
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as exc:
        # psycopg2 connection errors embed the host and username from the DSN;
        # print the class only so a failure cannot leak them into CI logs.
        print(f"Smoke could not connect to the database: {type(exc).__name__}")
        return 2
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
        if status not in (200, 201):
            # Nothing was created, so stop before the verify/cleanup statements
            # can touch a row this run did not make. `finally` still runs and
            # finds nothing to delete.
            return _finish()
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
        # NOTE: the rico_users row is not created by registration here (no
        # display name is sent), so it is deliberately resolved in cleanup
        # rather than now — see the comment there.

        # ── 3. upload the CV through the real parse path ──────────────────
        pdf = build_pdf()
        status, raw = call_multipart(f"{BACKEND}/api/v1/rico/upload-cv", "file", CV_FILENAME, pdf, timeout=SLOW_TIMEOUT)
        upload = as_json(raw)
        preview = upload.get("preview") or upload.get("profile_preview") or {}
        upload_id = upload.get("upload_id")
        # The upload route answers 200 for refusals too (e.g. status=
        # "invalid_signature" with ok=False), so the status code alone proves
        # nothing. Require the success shape the route documents.
        record(
            "upload CV (PDF) accepted",
            status == 200
            and upload.get("ok") is True
            and upload.get("status") == "preview_ready"
            and bool(preview)
            and bool(upload_id),
            f"HTTP {status} bytes={len(pdf)} ok={upload.get('ok')} "
            f"status={upload.get('status') or '-'} has_preview={bool(preview)} "
            f"has_upload_id={bool(upload_id)}",
        )

        # ── 4. confirm it into the profile so it becomes a stored document ─
        status, raw = call(
            "POST",
            f"{BACKEND}/api/v1/rico/confirm-cv-profile",
            {"preview": preview, "filename": CV_FILENAME, "doc_type": "cv", "upload_id": upload_id},
            timeout=SLOW_TIMEOUT,
        )
        record("confirm CV into profile", status == 200, f"HTTP {status} cv_status={as_json(raw).get('cv_status') or '-'}")

        # ── 5. My Files shows it (#1425: 503 ≠ empty list) ────────────────
        status, raw = call("GET", f"{BACKEND}/api/v1/user/files")
        files = as_json(raw).get("files") or []
        cvs = [f for f in files if isinstance(f, dict) and f.get("doc_type") == "cv"]
        doc_id = next((str(f.get("id")) for f in cvs if f.get("id") not in (None, "profile-cv")), None)
        # `profile-cv` is a synthetic card the route injects from the parsed
        # profile whenever no real primary CV document exists — counting it as a
        # hit would pass this check on the exact #1425 failure mode it covers.
        # Only a genuinely stored document proves the inventory.
        record(
            "CV appears in My Files as a stored document",
            status == 200 and doc_id is not None,
            f"HTTP {status} files={len(files)} cv_entries={len(cvs)} stored_doc={doc_id is not None}",
        )

        # ── 6. analysis asks must not become job searches (#1426) ─────────
        status, raw = call("POST", f"{BACKEND}/api/v1/rico/chat", {"message": EN_ANALYSIS_ASK}, timeout=SLOW_TIMEOUT)
        assert_not_job_search("EN CV analysis ask", status, raw)
        status, raw = call("POST", f"{BACKEND}/api/v1/rico/chat", {"message": AR_ANALYSIS_ASK}, timeout=SLOW_TIMEOUT)
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
        stored_after = [
            f for f in files_after
            if isinstance(f, dict) and f.get("doc_type") == "cv" and str(f.get("id")) != "profile-cv"
        ]
        record(
            "CV persists after logout/login",
            status == 200 and len(stored_after) >= 1,
            f"HTTP {status} stored_cv_entries={len(stored_after)}",
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
                # The rico_users row does NOT exist at login: registration only
                # creates one when a display name is supplied, and this smoke
                # registers with email/password alone. It is auto-provisioned
                # later, at confirm-cv-profile (upsert_profile) or at the first
                # chat turn. Re-resolve it HERE — reusing an id read earlier
                # would always be None and would silently leave rico_users,
                # rico_profiles (which holds the parsed CV text) and
                # rico_chat_history behind in production.
                cur.execute(
                    "SELECT id FROM rico_users WHERE email = %s OR external_user_id = %s",
                    (EMAIL, EMAIL),
                )
                row = cur.fetchone()
                if row:
                    rico_uid = str(row[0])

                # Email-keyed tables. NONE of these has a foreign key to users,
                # so deleting the user sweeps nothing here — each must be named.
                for table, column in _EMAIL_KEYED_TABLES:
                    cur.execute(
                        f"DELETE FROM {table} WHERE {column} = %s",  # noqa: S608 - identifiers are module constants
                        (EMAIL,),
                    )
                if rico_uid:
                    cur.execute("DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,))
                    # rico_profiles / rico_agent_settings / rico_job_recommendations
                    # are ON DELETE CASCADE children of this row.
                    cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
                cur.execute("DELETE FROM users WHERE email = %s", (EMAIL,))
            cleaned = True
            print("[CLEANUP] synthetic user and all its rows removed")
        except Exception as exc:
            print(f"[CLEANUP-WARN] {type(exc).__name__}: retrying once on a fresh connection")
            # A dropped Neon connection mid-run must not be the reason rows are
            # left in production; one reconnect is cheap and often decisive.
            try:
                conn = psycopg2.connect(DATABASE_URL)
                conn.autocommit = True
                with conn.cursor() as cur:
                    for table, column in _EMAIL_KEYED_TABLES:
                        cur.execute(
                            f"DELETE FROM {table} WHERE {column} = %s",  # noqa: S608
                            (EMAIL,),
                        )
                    if rico_uid:
                        cur.execute(
                            "DELETE FROM rico_chat_history WHERE user_id = %s::uuid", (rico_uid,)
                        )
                        cur.execute("DELETE FROM rico_users WHERE id = %s::uuid", (rico_uid,))
                    cur.execute("DELETE FROM users WHERE email = %s", (EMAIL,))
                cleaned = True
                print("[CLEANUP] synthetic user removed on retry")
            except Exception as exc2:
                print(f"[CLEANUP-WARN] {type(exc2).__name__}: manual cleanup needed for {EMAIL}")

        # A cleanup that reports success but leaves rows behind is still a FAIL.
        # Every table this journey can write is re-read by its own key. A table
        # that cannot be counted leaves the verdict unproven, not clean.
        residual = 0
        unresolved: list[str] = []
        for table, column in _EMAIL_KEYED_TABLES + (("users", "email"),):
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {column} = %s",  # noqa: S608
                        (EMAIL,),
                    )
                    residual += int(cur.fetchone()[0])
            except Exception as exc:
                unresolved.append(f"{table}:{type(exc).__name__}")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM rico_users WHERE email = %s OR external_user_id = %s",
                    (EMAIL, EMAIL),
                )
                residual += int(cur.fetchone()[0])
        except Exception as exc:
            unresolved.append(f"rico_users:{type(exc).__name__}")

        record(
            "cleanup verified — no residual synthetic rows",
            cleaned and residual == 0 and not unresolved,
            f"residual_rows={residual} unresolved={','.join(unresolved) if unresolved else 'none'}",
        )
        conn.close()

    return _finish()


if __name__ == "__main__":
    sys.exit(main())
