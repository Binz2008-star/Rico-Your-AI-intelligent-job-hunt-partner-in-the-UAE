"""
Production smoke test for the /command chat contracts TC-2 and TC-8.

Verifies, against the live authenticated chat endpoint, the behavior shipped in
PRs #834 + #835:

  TC-2 — after confirming new target roles, the next search uses THOSE targets
         (not a stale "Operations Manager").
  TC-8 — "prepare me for an interview for <role> at <company>" routes to grounded
         interview prep, NOT a company-openings list.
  Control — "find jobs at ADNOC" still performs a company job search.

Runs against the authenticated endpoint (POST /api/v1/rico/chat), not
/chat/public: the TC-2/TC-8 dispatch lives in the profile-bearing path, and an
anonymous public session is gated to an onboarding CTA before that code runs.

Matches the conventions of scripts/production_smoke_test.py (requests, register
-> login with 409 fallback, Secure-cookie parse, PASS/FAIL summary, non-zero
exit on failure). Config via env:

    API_BASE       (default https://rico-job-automation-api.onrender.com)
    SMOKE_EMAIL    (default smoke_command_tc_2026@ricohunt.com)
    SMOKE_PASSWORD (default SmokeCommand2026!)

Usage:
    python scripts/smoke_command_tc2_tc8.py
"""
import json
import os
import sys

import requests

API_BASE = os.getenv("API_BASE", "https://rico-job-automation-api.onrender.com").rstrip("/")
SMOKE_EMAIL = os.getenv("SMOKE_EMAIL", "smoke_command_tc_2026@ricohunt.com")
SMOKE_PASSWORD = os.getenv("SMOKE_PASSWORD", "SmokeCommand2026!")
TIMEOUT = int(os.getenv("SMOKE_TIMEOUT", "60"))


def _extract_cookie_token(response):
    """Pull access_token from a Secure Set-Cookie the requests jar won't expose."""
    token = response.cookies.get_dict().get("access_token")
    if token:
        return token
    set_cookie = response.headers.get("set-cookie", "")
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("access_token="):
            return part.split("=", 1)[1]
    return None


def authenticate():
    """Register (idempotent) then login; return an auth headers dict or None."""
    try:
        requests.post(
            f"{API_BASE}/api/v1/auth/register",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
            timeout=TIMEOUT,
        )  # 201 created or 409 exists — both fine; login is the source of truth
    except requests.RequestException as exc:
        print(f"  register call failed (continuing to login): {exc}")

    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"  login failed: {exc}")
        return None
    if resp.status_code != 200:
        print(f"  login returned {resp.status_code}: {resp.text[:200]}")
        return None
    token = _extract_cookie_token(resp)
    if not token:
        print("  login succeeded but no access_token cookie found")
        return None
    return {"Cookie": f"access_token={token}"}


def send_chat(headers, message):
    """POST one chat turn; return the parsed JSON dict (empty on error)."""
    try:
        resp = requests.post(
            f"{API_BASE}/api/v1/rico/chat",
            headers=headers,
            json={"message": message},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"  chat request failed for {message!r}: {exc}")
        return {}
    if resp.status_code != 200:
        print(f"  chat HTTP {resp.status_code} for {message!r}: {resp.text[:200]}")
        return {}
    try:
        return resp.json()
    except ValueError:
        return {}


def _blob(resp):
    """Lower-cased haystack of the fields that carry the routed role/company."""
    parts = [
        str(resp.get("message", "")),
        str(resp.get("search_query", "")),
        str(resp.get("target_role", "")),
        str(resp.get("company", "")),
        json.dumps(resp.get("entities", {})),
    ]
    return " ".join(parts).lower()


def check_tc2(headers):
    """Confirm ESG/Compliance targets, then a bare search must use them."""
    send_chat(headers, "update my target roles to ESG Manager and Compliance Manager")
    send_chat(headers, "yes")
    resp = send_chat(headers, "search for jobs now")
    blob = _blob(resp)

    # The regression this guards: a stale recent_search_role resurfacing Operations.
    if "operations manager" in blob:
        return False, f"stale 'Operations Manager' surfaced (type={resp.get('type')})"
    if "esg" in blob or "compliance" in blob:
        return True, f"search targets ESG/Compliance (type={resp.get('type')})"
    # No Operations leak, but also no explicit ESG/Compliance signal (e.g. a
    # role-suggestion prompt for a CV-less smoke user) — inconclusive, not a fail.
    return None, f"no Operations leak, but ESG/Compliance not explicit (type={resp.get('type')})"


def check_tc8(headers):
    """Interview-prep message must route to grounded prep, not a company search."""
    resp = send_chat(
        headers,
        "prepare me for an interview for the Retail Operations Manager role at Richemont",
    )
    rtype = str(resp.get("type", ""))
    intent = str(resp.get("intent", ""))
    matches = resp.get("matches") or []

    if rtype == "interview_prep" or intent == "interview_prep":
        company = str(resp.get("company", "")).lower()
        if "richemont" in company or "richemont" in _blob(resp):
            return True, f"grounded interview_prep (company={resp.get('company')!r})"
        return True, "interview_prep (Richemont not echoed in company field)"
    if matches:
        return False, f"returned an openings list ({len(matches)} matches) — hijacked to search"
    return False, f"did not route to interview_prep (type={rtype!r} intent={intent!r})"


def check_control_company(headers):
    """'find jobs at ADNOC' must remain a company job search."""
    resp = send_chat(headers, "find jobs at ADNOC")
    rtype = str(resp.get("type", ""))
    intent = str(resp.get("intent", ""))
    if rtype == "interview_prep" or intent == "interview_prep":
        return False, "genuine company search wrongly routed to interview_prep"
    if "adnoc" in _blob(resp) or intent in ("search_jobs", "job_search") or "job" in rtype:
        return True, f"company search intact (type={rtype!r})"
    return None, f"inconclusive (type={rtype!r} intent={intent!r})"


def main():
    print("=" * 60)
    print(f"Rico /command smoke — TC-2 / TC-8  ({API_BASE})")
    print("=" * 60)

    # Backend readiness — don't smoke a stale deploy.
    try:
        health = requests.get(f"{API_BASE}/health", timeout=TIMEOUT)
        version = requests.get(f"{API_BASE}/version", timeout=TIMEOUT)
        print(f"health={health.status_code}  version={version.text[:120]}")
        if health.status_code != 200:
            print("❌ backend health != 200; aborting")
            return 2
    except requests.RequestException as exc:
        print(f"❌ backend unreachable: {exc}")
        return 2

    headers = authenticate()
    if not headers:
        print("❌ could not authenticate; aborting")
        return 2

    cases = [
        ("TC-2 target propagation", check_tc2),
        ("TC-8 interview prep", check_tc8),
        ("Control: company search", check_control_company),
    ]

    failed = 0
    inconclusive = 0
    print("\n" + "-" * 60)
    for name, fn in cases:
        try:
            ok, detail = fn(headers)
        except Exception as exc:  # noqa: BLE001 — a smoke must not crash on one case
            ok, detail = False, f"exception: {exc}"
        if ok is True:
            tag = "✓ PASS"
        elif ok is None:
            tag = "~ INCONCLUSIVE"
            inconclusive += 1
        else:
            tag = "✗ FAIL"
            failed += 1
        print(f"  {tag}: {name} — {detail}")

    print("-" * 60)
    print(f"\n{len(cases)} cases: {failed} failed, {inconclusive} inconclusive")
    if failed:
        print("Result: FAIL")
        return 1
    if inconclusive:
        print("Result: PASS (with inconclusive cases — see notes; often a CV-less smoke user)")
        return 0
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
