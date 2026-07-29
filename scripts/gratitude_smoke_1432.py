#!/usr/bin/env python3
"""Manual production smoke for #1432: gratitude must not redeem a pending search.

The smoke uses one pre-provisioned dedicated account and one disposable chat
session. It never registers users, changes profiles, writes SQL, or prints
credentials/cookies/response messages.

Required environment variables:
    SMOKE_CONFIRM          Must equal ``SMOKE-1432``.
    EXPECTED_SHA           Commit production must currently serve.
    RICO_SMOKE_TEST_EMAIL  Dedicated smoke-account email.
    RICO_SMOKE_TEST_PASSWORD Dedicated smoke-account password.

Optional environment variables:
    API_BASE               Defaults to the Render production backend.
    SMOKE_OFF_PROFILE_ROLE Defaults to ``Data Scientist``. The role must be a
                           real role outside the smoke account's target roles.
    SMOKE_TIMEOUT          Per-request timeout in seconds; defaults to 90.

Exit code 0 means the behavior and cleanup both passed. Any uncertainty fails
closed with a non-zero exit code.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

API_BASE = os.getenv(
    "API_BASE", "https://rico-job-automation-api.onrender.com"
).rstrip("/")
TIMEOUT = 90
SESSION_ID = str(uuid.uuid4())
CONFIRMATION = "SMOKE-1432"


class SmokeFailure(RuntimeError):
    """A deterministic smoke failure safe to print without response bodies."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SmokeFailure(f"missing required environment value: {name}")
    return value


EXPECTED_SHA = ""
SMOKE_EMAIL = ""
SMOKE_PASSWORD = ""
OFF_PROFILE_ROLE = ""


def _load_config() -> None:
    global EXPECTED_SHA, SMOKE_EMAIL, SMOKE_PASSWORD, OFF_PROFILE_ROLE, TIMEOUT
    if os.getenv("SMOKE_CONFIRM", "") != CONFIRMATION:
        raise SmokeFailure(f"refusing to run: SMOKE_CONFIRM must equal {CONFIRMATION}")
    EXPECTED_SHA = _required("EXPECTED_SHA").lower()
    SMOKE_EMAIL = _required("RICO_SMOKE_TEST_EMAIL")
    SMOKE_PASSWORD = _required("RICO_SMOKE_TEST_PASSWORD")
    OFF_PROFILE_ROLE = os.getenv("SMOKE_OFF_PROFILE_ROLE", "Data Scientist").strip()
    if not OFF_PROFILE_ROLE:
        raise SmokeFailure("SMOKE_OFF_PROFILE_ROLE must not be empty")
    try:
        TIMEOUT = int(os.getenv("SMOKE_TIMEOUT", "90"))
    except ValueError as exc:
        raise SmokeFailure("SMOKE_TIMEOUT must be an integer") from exc
    if TIMEOUT < 1:
        raise SmokeFailure("SMOKE_TIMEOUT must be positive")


_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_auth_cookie: str | None = None


def _capture_auth_cookie(response: Any) -> None:
    """Capture the Secure auth cookie without ever logging it."""
    global _auth_cookie
    try:
        set_cookies = response.headers.get_all("Set-Cookie") or []
    except Exception:
        return
    for header in set_cookies:
        first = header.split(";", 1)[0].strip()
        if first.startswith("access_token="):
            token = first.split("=", 1)[1]
            if len(token) > 8:
                _auth_cookie = f"access_token={token}"


def _decode_json(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {"_value": value}


def _call(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    authenticated: bool = True,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(f"{API_BASE}{path}", method=method)
    if authenticated and _auth_cookie:
        request.add_header("Cookie", _auth_cookie)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request.add_header("Content-Type", "application/json")
    try:
        with _opener.open(request, data=data, timeout=TIMEOUT) as response:
            _capture_auth_cookie(response)
            return response.status, _decode_json(response.read())
    except urllib.error.HTTPError as exc:
        _capture_auth_cookie(exc)
        return exc.code, _decode_json(exc.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmokeFailure(f"request failed: {method} {path}: {type(exc).__name__}") from exc


def _text(payload: dict[str, Any]) -> str:
    return str(payload.get("message") or payload.get("response") or "").strip()


def _sequence_count(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return len(value) if isinstance(value, list) else None


def _safe_summary(label: str, status: int, payload: dict[str, Any]) -> None:
    """Print only non-identifying routing evidence, never messages or secrets."""
    rtype = str(payload.get("type") or "")
    intent = str(payload.get("intent") or "")
    source = str(payload.get("response_source") or "")
    matches = _sequence_count(payload, "matches")
    jobs = _sequence_count(payload, "jobs")
    print(
        f"[{label}] HTTP={status} type={rtype or '-'} intent={intent or '-'} "
        f"source={source or '-'} matches={matches} jobs={jobs}"
    )


def _is_search_execution(payload: dict[str, Any]) -> bool:
    rtype = str(payload.get("type") or "").lower()
    intent = str(payload.get("intent") or "").lower()
    source = str(payload.get("response_source") or "").lower()
    if source == "search_contract":
        return True
    if rtype in {"job_matches", "job_list", "job_results"}:
        return True
    if payload.get("search_query") or payload.get("target_role"):
        return True
    if intent in {"job_search", "search_jobs", "job_search_explicit"} and (
        "matches" in payload or "jobs" in payload
    ):
        return True
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _verify_public_boundary() -> None:
    status, version = _call("GET", "/version", authenticated=False)
    served = str(version.get("commit") or "").strip().lower()
    sha_match = bool(served) and served not in {"unknown", "?"} and (
        EXPECTED_SHA.startswith(served) or served.startswith(EXPECTED_SHA)
    )
    print(
        f"[version] HTTP={status} served={served[:12] or '-'} "
        f"expected={EXPECTED_SHA[:12]} match={sha_match}"
    )
    _require(status == 200 and sha_match, "production does not serve EXPECTED_SHA")

    status, health = _call("GET", "/health", authenticated=False)
    health_state = str(health.get("status") or "")
    print(f"[health] HTTP={status} status={health_state or '-'}")
    _require(status == 200 and health_state == "ok", "backend health is not ok")


def _authenticate() -> None:
    status, _ = _call(
        "POST",
        "/api/v1/auth/login",
        {"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        authenticated=False,
    )
    print(f"[login] HTTP={status} cookie_captured={bool(_auth_cookie)}")
    _require(status == 200 and bool(_auth_cookie), "dedicated smoke-account login failed")

    status, me = _call("GET", "/api/v1/me")
    print(
        f"[me] HTTP={status} authenticated={bool(me.get('authenticated'))} "
        f"guest={bool(me.get('guest'))} role={str(me.get('role') or '-') }"
    )
    _require(status == 200, "/me failed")
    _require(me.get("authenticated") is True, "smoke account is not authenticated")
    _require(me.get("guest") is False, "smoke account resolved as guest")
    _require(me.get("role") == "user", "smoke account role is not user")


def _chat(message: str) -> tuple[int, dict[str, Any]]:
    return _call(
        "POST",
        "/api/v1/rico/chat",
        {"message": message, "session_id": SESSION_ID},
    )


def _cleanup_session() -> bool:
    encoded = urllib.parse.quote(SESSION_ID, safe="")
    try:
        status, _ = _call("DELETE", f"/api/v1/rico/chat/history?session_id={encoded}")
    except SmokeFailure as exc:
        print(f"[cleanup] FAIL request_error={type(exc).__name__}")
        return False
    ok = status in {200, 204}
    print(f"[cleanup] HTTP={status} session_deleted={ok}")
    return ok


def _logout() -> None:
    try:
        status, _ = _call("POST", "/api/v1/auth/logout")
        print(f"[logout] HTTP={status}")
    except SmokeFailure:
        print("[logout] warning=request_failed")


def main() -> int:
    _load_config()
    authenticated = False
    session_touched = False
    pending_may_be_armed = False
    failure: SmokeFailure | None = None
    cleanup_ok = True

    try:
        _verify_public_boundary()
        _authenticate()
        authenticated = True

        arm_message = f"Find {OFF_PROFILE_ROLE} jobs in Dubai"
        session_touched = True
        pending_may_be_armed = True
        status, arm = _chat(arm_message)
        _safe_summary("arm", status, arm)
        _require(status == 200, "pending-search arm turn failed")
        _require(
            str(arm.get("type") or "").lower() == "clarification",
            "off-profile role did not produce the expected clarification; choose a different role",
        )
        _require(
            not _is_search_execution(arm),
            "arm turn executed a search instead of arming confirmation",
        )
        _require(bool(_text(arm)), "arm clarification had no user-visible message")

        status, gratitude = _chat("شكرًا")
        _safe_summary("gratitude", status, gratitude)
        _require(status == 200, "gratitude turn failed")
        _require(bool(_text(gratitude)), "gratitude turn had no user-visible response")
        _require(
            not _is_search_execution(gratitude),
            "gratitude redeemed the pending search",
        )
        print("[assert] gratitude dispatched no user-visible search result: PASS")

        status, confirmed = _chat("نعم")
        _safe_summary("confirm", status, confirmed)
        _require(status == 200, "explicit confirmation turn failed")
        _require(
            _is_search_execution(confirmed),
            "explicit confirmation did not redeem the still-pending search",
        )
        pending_may_be_armed = False
        print("[assert] pending offer survived gratitude and redeemed on explicit confirmation: PASS")

    except SmokeFailure as exc:
        failure = exc
    finally:
        # Best-effort state drain: if the arm turn may have succeeded but the normal
        # confirmation was never attempted, consume the 15-minute pending slot on
        # the dedicated smoke account before deleting the disposable transcript.
        if authenticated and pending_may_be_armed:
            try:
                status, drained = _chat("نعم")
                _safe_summary("cleanup-drain", status, drained)
            except SmokeFailure:
                print("[cleanup-drain] warning=request_failed; pending slot expires by TTL")
        if authenticated and session_touched:
            cleanup_ok = _cleanup_session()
        if authenticated:
            _logout()

    if failure is not None:
        print(f"RESULT=FAIL reason={failure}")
        return 1
    if not cleanup_ok:
        print("RESULT=FAIL reason=disposable session cleanup failed")
        return 1
    print("RESULT=PASS #1432 production behavior verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"RESULT=FAIL reason={exc}")
        raise SystemExit(2)
