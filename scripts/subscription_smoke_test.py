"""Read-only billing preflight for the current manual/Paddle contract.

Replaces the retired Stripe checkout smoke. Validates the LIVE billing surface
WITHOUT creating a charge or exercising a checkout/webhook lifecycle:

  1. GET  /api/v1/billing/config      (unauthenticated) — billing mode + sandbox flag
  2. POST /api/v1/auth/login          — obtain a session cookie
  3. GET  /api/v1/subscription/plans  — single paid plan (Rico Monthly, USD)
  4. GET  /api/v1/subscription/me     — authenticated subscription status

Stripe is fully removed (DEC-20260713-005). Paddle is the paid-subscription
source of truth; BILLING_MODE=manual is the safe default until explicit owner
activation. Any real checkout/webhook lifecycle test is isolated Paddle Sandbox
work and is intentionally NOT performed here — this preflight never opens a
checkout, never posts to a webhook, and never creates a charge.

Usage:
  export RICO_SMOKE_TEST_EMAIL="your-test-account@example.com"
  export RICO_SMOKE_TEST_PASSWORD="your-test-account-password"
  python scripts/subscription_smoke_test.py

Never commit credentials. Both env vars are required.
"""
import requests
import json
import os
import sys

BASE_URL = os.environ.get("RICO_SMOKE_API_BASE", "https://rico-job-automation-api.onrender.com")
TEST_EMAIL = os.environ.get("RICO_SMOKE_TEST_EMAIL")
TEST_PASSWORD = os.environ.get("RICO_SMOKE_TEST_PASSWORD")

if not TEST_EMAIL or not TEST_PASSWORD:
    missing = []
    if not TEST_EMAIL:
        missing.append("RICO_SMOKE_TEST_EMAIL")
    if not TEST_PASSWORD:
        missing.append("RICO_SMOKE_TEST_PASSWORD")
    print(f"ERROR: {', '.join(missing)} environment variable(s) not set. Aborting.", file=sys.stderr)
    sys.exit(2)


def print_result(test_name, status_code, response_data, pass_fail, error=None):
    print(f"\n{test_name}")
    print(f"  Status Code: {status_code}")
    if response_data:
        print(f"  Response: {json.dumps(response_data, indent=2)}")
    print(f"  Result: {pass_fail}")
    if error:
        print(f"  Error: {error}")


def main():
    results = []

    # Step 1: GET /api/v1/billing/config  (unauthenticated, no secrets exposed)
    print("=" * 60)
    print("STEP 1: GET /api/v1/billing/config (public)")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/billing/config", timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        # Non-secret config flags: billing_mode + paddle_active + sandbox.
        expected_keys = {"billing_mode", "paddle_active", "sandbox"}
        if status_code == 200 and expected_keys.issubset(set(data.keys())):
            pass_fail = "PASS"
            results.append(("GET /billing/config", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /billing/config", False))
        print_result("GET /billing/config", status_code, data, pass_fail)
    except Exception as e:
        print_result("GET /billing/config", "N/A", None, "FAIL", str(e))
        results.append(("GET /billing/config", False))

    # Step 2: Login to get session cookie
    print("\n" + "=" * 60)
    print("STEP 2: Login")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10
        )
        status_code = response.status_code
        if status_code == 200:
            pass_fail = "PASS"
            results.append(("Login", True))
            # Extract token from Set-Cookie header
            token = None
            if "set-cookie" in response.headers:
                set_cookie = response.headers["set-cookie"]
                for part in set_cookie.split(";"):
                    part = part.strip()
                    if part.startswith("access_token="):
                        token = part.split("=", 1)[1]
                        break
        else:
            pass_fail = "FAIL"
            results.append(("Login", False))
            token = None
        print_result("Login", status_code, None, pass_fail, response.text if status_code != 200 else None)
    except Exception as e:
        print_result("Login", "N/A", None, "FAIL", str(e))
        results.append(("Login", False))
        token = None

    if not token:
        print("\nCRITICAL: No auth token obtained. Cannot continue authenticated checks.")
        return 1

    headers = {"Cookie": f"access_token={token}"}

    # Step 3: GET /api/v1/subscription/plans — single Paddle plan (Rico Monthly, USD)
    print("\n" + "=" * 60)
    print("STEP 3: GET /api/v1/subscription/plans")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/subscription/plans", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        plans = data.get("plans", []) if isinstance(data, dict) else []
        plan_keys = [p.get("plan") for p in plans]
        currencies = {p.get("currency") for p in plans}
        # Current contract: single paid plan (Rico Monthly / "pro"), priced in USD.
        # Premium is retired — its presence here is a regression, not a pass.
        single_plan_ok = (
            status_code == 200
            and "plans" in (data if isinstance(data, dict) else {})
            and "pro" in plan_keys
            and "premium" not in plan_keys
            and currencies == {"USD"}
        )
        if single_plan_ok:
            pass_fail = "PASS"
            results.append(("GET /subscription/plans (single USD plan)", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /subscription/plans (single USD plan)", False))
        print_result("GET /subscription/plans", status_code, data, pass_fail)
    except Exception as e:
        print_result("GET /subscription/plans", "N/A", None, "FAIL", str(e))
        results.append(("GET /subscription/plans (single USD plan)", False))

    # Step 4: GET /api/v1/subscription/me — authenticated status (no charge)
    print("\n" + "=" * 60)
    print("STEP 4: GET /api/v1/subscription/me")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/subscription/me", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        expected_keys = {"subscription", "is_active"}
        if status_code == 200 and expected_keys.issubset(set(data.keys())):
            pass_fail = "PASS"
            results.append(("GET /subscription/me", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /subscription/me", False))
        print_result("GET /subscription/me", status_code, data, pass_fail)
    except Exception as e:
        print_result("GET /subscription/me", "N/A", None, "FAIL", str(e))
        results.append(("GET /subscription/me", False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test_name}")
    print(f"\nTotal: {passed}/{total} passed")
    print("\nNote: this preflight is read-only. Checkout, webhook, and activation")
    print("lifecycle testing is isolated Paddle Sandbox work — see")
    print("AI_WORKSPACE/HANDOFFS/paddle_billing_setup_rollback.md.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
