#!/usr/bin/env python3
"""#1070 production smoke gate — guest identity binding (owner-approved release check).

Runs the ten-point smoke list from the #1070 release sequence against the live
backend using ONLY synthetic users (smoke-1070-<run>-*@example.com) and cleans
every row it created before exiting. Items covered:

  a. new guest receives a capability cookie
  b. guest public chat works
  c. guest CV upload works
  d. guest CV confirmation works
  e. guest data merges into the authenticated account on login
  f. a second authenticated account cannot claim the same guest identity
  g. reload/session continuity (same cookie -> same identity, no re-mint)
  h. tampered capability fails closed (403 + cookie cleared, no 5xx)
  i. missing capability secret — NOT live-testable without breaking production;
     covered by CI test evidence (test_1070_guest_identity_binding.py), reported
     as CI-COVERED rather than exercised here.
  j. authenticated requests ignore caller-supplied public identity authority

Plus the step-8 verifications: no authoritative SID leakage in bodies/headers,
no unexpected 5xx, exactly one claim row created and only after the successful
merge, and no partial data migration on the rejected second claim.

Requires: requests, psycopg2-binary, DATABASE_URL env (production; used only to
verify synthetic-row state and to delete this run's synthetic rows afterwards).
Every DB write is keyed to this run's unique emails / guest sid — no pattern
matching that could touch a real user.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid

import psycopg2
import requests

BASE = os.environ.get("SMOKE_BASE_URL", "https://rico-job-automation-api.onrender.com")
API = f"{BASE}/api/v1"
GUEST_COOKIE = "rico_guest_proof"
JWT_COOKIE = "access_token"
TIMEOUT = 120

RUN = f"{os.environ.get('GITHUB_RUN_ID', 'local')}-{uuid.uuid4().hex[:6]}"
EMAIL_A = f"smoke-1070-{RUN}-a@example.com"
EMAIL_B = f"smoke-1070-{RUN}-b@example.com"
PASSWORD = f"Sm0ke-1070!{uuid.uuid4().hex[:8]}"
CORRELATION_SID = f"web-{uuid.uuid4()}"

RESULTS: list[tuple[str, str, str]] = []  # (item, PASS/FAIL/CI-COVERED, detail)
CAPTURED: list[tuple[str, dict, str]] = []  # (label, headers-sans-set-cookie, body)
FIVE_XX: list[str] = []
# Exact external identities this run may clean up (filled in as they appear).
CLEANUP_EXTERNAL_IDS: list[str] = [EMAIL_A, EMAIL_B]


def record(item: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    RESULTS.append((item, status, detail))
    print(f"[{status}] {item}: {detail}", flush=True)


def capture(label: str, resp: requests.Response) -> None:
    headers = {k: v for k, v in resp.headers.items() if k.lower() != "set-cookie"}
    CAPTURED.append((label, headers, resp.text))
    if resp.status_code >= 500:
        FIVE_XX.append(f"{label} -> HTTP {resp.status_code}")


def set_cookies_of(resp: requests.Response) -> list[str]:
    try:
        return resp.raw.headers.getlist("Set-Cookie")
    except Exception:
        raw = resp.headers.get("Set-Cookie", "")
        return [raw] if raw else []


def cookie_cleared(cookies: list[str]) -> bool:
    return any(
        c.startswith(f"{GUEST_COOKIE}=")
        and (
            "max-age=0" in c.lower()
            or f'{GUEST_COOKIE}="";' in c
            or f"{GUEST_COOKIE}=;" in c
        )
        for c in cookies
    )


def guest_sid_from_jar(sess: requests.Session) -> str | None:
    """Decode the capability payload the way page JavaScript never could
    (HttpOnly): the smoke script plays the network observer, not the page."""
    token = sess.cookies.get(GUEST_COOKIE)
    if not token or "." not in token:
        return None
    payload = token.split(".")[0]
    payload += "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload)).get("sid")
    except Exception:
        return None


def make_pdf(lines: list[str]) -> bytes:
    """Minimal valid one-page PDF with extractable Helvetica text."""
    parts = []
    y = 760
    for line in lines:
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        parts.append(f"BT /F1 11 Tf 50 {y} Td ({safe}) Tj ET")
        y -= 18
    stream = ("\n".join(parts)).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs)+1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF"
    ).encode()
    return bytes(out)


CV_LINES = [
    "Samira Smoke",
    "Senior Operations Coordinator - Dubai, UAE",
    "Email: smoke-cv-contact@example.com  Phone: +971500000000",
    "",
    "PROFESSIONAL SUMMARY",
    "Operations coordinator with 6 years of experience in logistics,",
    "vendor management and process improvement across UAE facilities.",
    "",
    "EXPERIENCE",
    "Operations Coordinator, Example Logistics LLC (2019-2025):",
    "coordinated 40+ weekly shipments, cut handling errors by 18 percent,",
    "led a team of 5 dispatchers and owned the monthly KPI reporting.",
    "",
    "SKILLS",
    "Excel, SAP, scheduling, inventory management, English, Arabic",
]


def db_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def db_one(sql: str, params: tuple):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def db_exec(sql: str, params: tuple) -> int:
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount


def main() -> int:
    guest = requests.Session()

    # ---- a + b: fresh guest chat mints capability & answers -----------------
    r1 = guest.post(
        f"{API}/rico/chat/public",
        json={"message": "Hello Rico, what can you help me with?",
              "session_id": CORRELATION_SID},
        timeout=TIMEOUT,
    )
    capture("chat_public_1", r1)
    mint_cookies = [c for c in set_cookies_of(r1) if c.startswith(f"{GUEST_COOKIE}=")]
    g_sid = guest_sid_from_jar(guest)
    if g_sid:
        CLEANUP_EXTERNAL_IDS.append(f"public:{g_sid}")
    record(
        "a. guest receives capability cookie",
        r1.status_code == 200
        and len(mint_cookies) == 1
        and "httponly" in mint_cookies[0].lower()
        and bool(g_sid)
        and g_sid.startswith("g-"),
        f"HTTP {r1.status_code}, {len(mint_cookies)} capability set-cookie, "
        f"HttpOnly={'httponly' in (mint_cookies[0].lower() if mint_cookies else '')}, "
        f"server-minted sid={bool(g_sid)}",
    )
    body1 = {}
    try:
        body1 = r1.json()
    except Exception:
        pass
    record(
        "b. guest public chat works",
        r1.status_code == 200 and bool(body1),
        f"HTTP {r1.status_code}, non-empty JSON reply={bool(body1)}",
    )

    time.sleep(3)

    # ---- g: continuity — same cookie, same identity, no re-mint -------------
    r2 = guest.post(
        f"{API}/rico/chat/public",
        json={"message": "What jobs suit an operations coordinator in Dubai?",
              "session_id": CORRELATION_SID},
        timeout=TIMEOUT,
    )
    capture("chat_public_2", r2)
    remint = [c for c in set_cookies_of(r2) if c.startswith(f"{GUEST_COOKIE}=")]
    record(
        "g. reload/session continuity",
        r2.status_code == 200 and not remint and guest_sid_from_jar(guest) == g_sid,
        f"HTTP {r2.status_code}, re-mint set-cookie={len(remint)} (want 0), sid stable",
    )

    time.sleep(3)

    # ---- h: tampered capability fails closed --------------------------------
    token = guest.cookies.get(GUEST_COOKIE) or ""
    payload_part, sig_part = token.rsplit(".", 1) if "." in token else (token, "")
    flipped = ("A" if sig_part[:1] != "A" else "B") + sig_part[1:]
    tampered = requests.Session()
    tampered.cookies.set(GUEST_COOKIE, f"{payload_part}.{flipped}")
    r3 = tampered.post(
        f"{API}/rico/chat/public",
        json={"message": "hello again", "session_id": CORRELATION_SID},
        timeout=TIMEOUT,
    )
    capture("chat_public_tampered", r3)
    record(
        "h. tampered capability fails closed",
        r3.status_code == 403
        and "guest_capability_invalid" in r3.text
        and cookie_cleared(set_cookies_of(r3)),
        f"HTTP {r3.status_code} (want 403), body flags invalid="
        f"{'guest_capability_invalid' in r3.text}, "
        f"clear-cookie={cookie_cleared(set_cookies_of(r3))}",
    )

    # ---- c: guest CV upload -------------------------------------------------
    r4 = guest.post(
        f"{API}/rico/upload-cv",
        files={"file": ("smoke_cv.pdf", make_pdf(CV_LINES), "application/pdf")},
        data={"user_id": f"public:{CORRELATION_SID}"},
        timeout=TIMEOUT,
    )
    capture("upload_cv_guest", r4)
    up = {}
    try:
        up = r4.json()
    except Exception:
        pass
    upload_ok = r4.status_code == 200 and up.get("status") == "preview_ready"
    record(
        "c. guest CV upload works",
        upload_ok,
        f"HTTP {r4.status_code}, status={up.get('status')!r}, "
        f"upload_id={'yes' if up.get('upload_id') else 'no'}",
    )

    # Snapshot the guest's internal identity BEFORE merge (read-only).
    row = db_one(
        "SELECT id::text FROM rico_users WHERE external_user_id = %s",
        (f"public:{g_sid}",),
    )
    guest_uuid = row[0] if row else None

    # ---- d: guest CV confirmation ------------------------------------------
    if upload_ok:
        r5 = guest.post(
            f"{API}/rico/confirm-cv-profile",
            json={
                "preview": up.get("preview") or {},
                "filename": up.get("filename") or "smoke_cv.pdf",
                "doc_type": up.get("document_type") or "cv",
                "upload_id": up.get("upload_id"),
            },
            timeout=TIMEOUT,
        )
        capture("confirm_cv_guest", r5)
        record("d. guest CV confirmation works", r5.status_code == 200,
               f"HTTP {r5.status_code}")
    else:
        record("d. guest CV confirmation works", False,
               "skipped: upload not preview_ready")

    pre_merge_guest_cookie = guest.cookies.get(GUEST_COOKIE)

    # ---- e: register A, verify (synthetic, DB-side), login -> merge ---------
    r6 = requests.post(
        f"{API}/auth/register",
        json={"email": EMAIL_A, "password": PASSWORD, "name": "Smoke 1070 A"},
        timeout=TIMEOUT,
    )
    capture("register_a", r6)
    reg_ok = r6.status_code == 201
    verified = 0
    if reg_ok:
        # Synthetic user only — keyed to this run's unique email. Production
        # verification normally happens via the emailed link; example.com
        # addresses receive nothing, so the smoke flips the flag directly.
        verified = db_exec(
            "UPDATE users SET email_verified = TRUE WHERE email = %s",
            (EMAIL_A,),
        )
    r7 = guest.post(
        f"{API}/auth/login",
        json={"email": EMAIL_A, "password": PASSWORD,
              "public_user_id_to_merge": f"public:{CORRELATION_SID}"},
        timeout=TIMEOUT,
    )
    capture("login_a_merge", r7)
    login_cookies = set_cookies_of(r7)
    jwt_set = any(c.startswith(f"{JWT_COOKIE}=") for c in login_cookies)
    cap_rotated = cookie_cleared(login_cookies)
    row = db_one(
        "SELECT id::text FROM rico_users WHERE external_user_id = %s OR email = %s LIMIT 1",
        (EMAIL_A, EMAIL_A),
    )
    a_uuid = row[0] if row else None
    claim = db_one(
        "SELECT claimed_by_user_id::text FROM guest_identity_claims WHERE public_user_id = %s",
        (f"public:{g_sid}",),
    )
    chat_moved = db_one(
        "SELECT COUNT(*) FROM rico_chat_history WHERE user_id::text = %s",
        (a_uuid or "-",),
    ) or (0,)
    guest_left = (
        db_one("SELECT COUNT(*) FROM rico_chat_history WHERE user_id::text = %s",
               (guest_uuid,))
        if guest_uuid else (0,)
    ) or (0,)
    record(
        "e. guest data merges into authenticated account",
        reg_ok and verified == 1 and r7.status_code == 200 and jwt_set and cap_rotated
        and claim is not None and a_uuid is not None and claim[0] == a_uuid
        and chat_moved[0] >= 1 and guest_left[0] == 0,
        f"register={r6.status_code}, verified_rows={verified}, login={r7.status_code}, "
        f"jwt_cookie={jwt_set}, capability_rotated={cap_rotated}, "
        f"claim_owner_is_A={bool(claim and a_uuid and claim[0] == a_uuid)}, "
        f"chat_rows_on_A={chat_moved[0]}, chat_rows_left_on_guest={guest_left[0]}",
    )

    # ---- f: second account cannot claim the same guest identity -------------
    r8 = requests.post(
        f"{API}/auth/register",
        json={"email": EMAIL_B, "password": PASSWORD, "name": "Smoke 1070 B"},
        timeout=TIMEOUT,
    )
    capture("register_b", r8)
    verified_b = 0
    if r8.status_code == 201:
        verified_b = db_exec(
            "UPDATE users SET email_verified = TRUE WHERE email = %s",
            (EMAIL_B,),
        )
    second = requests.Session()
    if pre_merge_guest_cookie:
        second.cookies.set(GUEST_COOKIE, pre_merge_guest_cookie)
    r9 = second.post(
        f"{API}/auth/login",
        json={"email": EMAIL_B, "password": PASSWORD,
              "public_user_id_to_merge": f"public:{CORRELATION_SID}"},
        timeout=TIMEOUT,
    )
    capture("login_b_replay", r9)
    claim_after = db_one(
        "SELECT claimed_by_user_id::text FROM guest_identity_claims WHERE public_user_id = %s",
        (f"public:{g_sid}",),
    )
    row = db_one(
        "SELECT id::text FROM rico_users WHERE external_user_id = %s OR email = %s LIMIT 1",
        (EMAIL_B, EMAIL_B),
    )
    b_uuid = row[0] if row else None
    b_rows = (
        db_one("SELECT COUNT(*) FROM rico_chat_history WHERE user_id::text = %s",
               (b_uuid,))
        if b_uuid else (0,)
    ) or (0,)
    claim_count = db_one(
        "SELECT COUNT(*) FROM guest_identity_claims "
        "WHERE claimed_by_user_id::text IN (%s, %s)",
        (a_uuid or "-", b_uuid or "-"),
    ) or (0,)
    record(
        "f. second account cannot claim the same guest",
        r9.status_code == 200 and verified_b == 1
        and claim_after is not None and claim_after[0] == a_uuid
        and b_rows[0] == 0 and claim_count[0] == 1,
        f"login_b={r9.status_code} (login itself allowed), claim_owner_still_A="
        f"{bool(claim_after and claim_after[0] == a_uuid)}, "
        f"b_chat_rows={b_rows[0]} (want 0 — no partial migration), "
        f"claim_rows_for_A_and_B={claim_count[0]} (want 1)",
    )

    # ---- j: authenticated requests ignore caller public identity ------------
    auth_sess = requests.Session()
    la = auth_sess.post(
        f"{API}/auth/login", json={"email": EMAIL_A, "password": PASSWORD},
        timeout=TIMEOUT,
    )
    capture("login_a_plain", la)
    evil = f"public:web-evil-{uuid.uuid4().hex[:8]}"
    r10 = auth_sess.post(
        f"{API}/rico/upload-cv",
        files={"file": ("smoke_cv2.pdf", make_pdf(CV_LINES), "application/pdf")},
        data={"user_id": evil},
        timeout=TIMEOUT,
    )
    capture("upload_cv_authed_evil_id", r10)
    evil_row = db_one(
        "SELECT COUNT(*) FROM rico_users WHERE external_user_id = %s", (evil,)
    ) or (0,)
    evil_claims = db_one(
        "SELECT COUNT(*) FROM guest_identity_claims WHERE public_user_id = %s", (evil,)
    ) or (0,)
    record(
        "j. authenticated ignores caller-supplied public identity",
        la.status_code == 200 and r10.status_code == 200
        and evil_row[0] == 0 and evil_claims[0] == 0,
        f"login={la.status_code}, upload={r10.status_code}, "
        f"rico_users_rows_for_evil_id={evil_row[0]} (want 0), "
        f"claims_for_evil_id={evil_claims[0]} (want 0)",
    )

    # ---- i: missing secret — CI-covered, not live-mutable -------------------
    RESULTS.append((
        "i. missing capability secret fails closed",
        "CI-COVERED",
        "cannot unset the production secret during release (owner forbade secret "
        "changes); enforced by tests/test_1070_guest_identity_binding.py "
        "(prod-missing-secret -> 503 guest_capability_unavailable, nothing minted)",
    ))
    print("[CI-COVERED] i. missing capability secret fails closed", flush=True)

    # ---- step-8 verifications ----------------------------------------------
    leaks = []
    for label, headers, body in CAPTURED:
        blob = json.dumps(headers) + body
        if g_sid and g_sid in blob:
            leaks.append(label)
    record(
        "8a. no authoritative SID leakage in bodies/non-cookie headers",
        not leaks,
        f"server sid absent from all {len(CAPTURED)} captured responses"
        if not leaks else f"LEAKED in: {leaks}",
    )
    record("8b. no unexpected 5xx", not FIVE_XX,
           "0 five-xx responses" if not FIVE_XX else f"5xx seen: {FIVE_XX}")

    # ---- summary ------------------------------------------------------------
    print("\n===== #1070 PRODUCTION SMOKE SUMMARY =====")
    failed = 0
    for item, status, detail in RESULTS:
        print(f"  {status:10s} {item}")
        if status == "FAIL":
            failed += 1
    print(f"===== {len(RESULTS)} checks, {failed} failed =====")
    return 1 if failed else 0


def cleanup() -> None:
    """Delete every synthetic row this run created. Deletion is keyed STRICTLY
    to this run's unique emails and this run's exact server guest sid — never a
    pattern that could match a real user or another guest."""
    print("\n===== CLEANUP (this run's synthetic rows only) =====")
    print(f"  identities: {CLEANUP_EXTERNAL_IDS}")
    try:
        with db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id::text FROM rico_users "
                "WHERE external_user_id = ANY(%s) OR email = ANY(%s)",
                (CLEANUP_EXTERNAL_IDS, [EMAIL_A, EMAIL_B]),
            )
            uuids = [r[0] for r in cur.fetchall()] or ["-"]
            for table in ("rico_chat_history", "cv_upload_artifacts", "rico_profiles",
                          "uploaded_document_context", "user_documents",
                          "search_context", "user_job_context", "rico_onboarding_states"):
                try:
                    cur.execute(
                        f"DELETE FROM {table} WHERE user_id::text = ANY(%s)", (uuids,)
                    )
                    print(f"  {table}: {cur.rowcount} rows")
                except Exception as exc:  # column shape differs — report, move on
                    conn.rollback()
                    print(f"  {table}: skipped ({type(exc).__name__})")
            cur.execute(
                "DELETE FROM guest_identity_claims "
                "WHERE public_user_id = ANY(%s) OR claimed_by_user_id::text = ANY(%s)",
                (CLEANUP_EXTERNAL_IDS, uuids),
            )
            print(f"  guest_identity_claims: {cur.rowcount} rows")
            cur.execute(
                "DELETE FROM rico_users "
                "WHERE external_user_id = ANY(%s) OR email = ANY(%s)",
                (CLEANUP_EXTERNAL_IDS, [EMAIL_A, EMAIL_B]),
            )
            print(f"  rico_users: {cur.rowcount} rows")
            try:
                # Schema (migrations/017): tokens key by user_email.
                cur.execute(
                    "DELETE FROM email_verification_tokens WHERE user_email = ANY(%s)",
                    ([EMAIL_A, EMAIL_B],),
                )
                print(f"  email_verification_tokens: {cur.rowcount} rows")
            except Exception as exc:
                conn.rollback()
                print(f"  email_verification_tokens: skipped ({type(exc).__name__})")
            cur.execute("DELETE FROM users WHERE email = ANY(%s)", ([EMAIL_A, EMAIL_B],))
            print(f"  users: {cur.rowcount} rows")
            conn.commit()
        print("===== CLEANUP DONE =====")
    except Exception:
        import traceback
        traceback.print_exc()
        print("::warning::cleanup incomplete — synthetic rows may remain "
              f"(emails {EMAIL_A}, {EMAIL_B})")


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        cleanup()
    sys.exit(code)
