"""
Production smoke test for subscription endpoints.
Tests against https://rico-job-automation-api.onrender.com

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

    # Step 1: Login to get token
    print("=" * 60)
    print("STEP 1: Login")
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
        print("\n❌ CRITICAL: No auth token obtained. Cannot continue.")
        return 1

    headers = {"Cookie": f"access_token={token}"}

    # Step 2: GET /api/v1/subscription/plans
    print("\n" + "=" * 60)
    print("STEP 2: GET /api/v1/subscription/plans")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/subscription/plans", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        expected_keys = {"plans"}
        if status_code == 200 and expected_keys.issubset(set(data.keys())):
            pass_fail = "PASS"
            results.append(("GET /subscription/plans", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /subscription/plans", False))
        print_result("GET /subscription/plans", status_code, data, pass_fail)
    except Exception as e:
        print_result("GET /subscription/plans", "N/A", None, "FAIL", str(e))
        results.append(("GET /subscription/plans", False))

    # Step 3: GET /api/v1/subscription/me
    print("\n" + "=" * 60)
    print("STEP 3: GET /api/v1/subscription/me")
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

    # Step 4: POST /api/v1/subscription/checkout with plan=pro
    print("\n" + "=" * 60)
    print("STEP 4: POST /api/v1/subscription/checkout with plan=pro")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/subscription/checkout",
            headers=headers,
            json={"plan": "pro"},
            timeout=10
        )
        status_code = response.status_code
        data = response.json() if response.text else {}

        # Check for expected Stripe checkout response
        is_stripe = (
            status_code == 200 and
            data.get("provider") == "stripe" and
            data.get("status") == "ready" and
            data.get("checkout_url", "").startswith("https://checkout.stripe.com/")
        )

        if is_stripe:
            pass_fail = "PASS"
            results.append(("POST /subscription/checkout (pro)", True))
        else:
            pass_fail = "FAIL"
            results.append(("POST /subscription/checkout (pro)", False))
        print_result("POST /subscription/checkout (pro)", status_code, data, pass_fail)
    except Exception as e:
        print_result("POST /subscription/checkout (pro)", "N/A", None, "FAIL", str(e))
        results.append(("POST /subscription/checkout (pro)", False))

    # Step 5: POST /api/v1/subscription/checkout with plan=premium
    print("\n" + "=" * 60)
    print("STEP 5: POST /api/v1/subscription/checkout with plan=premium")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/subscription/checkout",
            headers=headers,
            json={"plan": "premium"},
            timeout=10
        )
        status_code = response.status_code
        data = response.json() if response.text else {}

        # Check for expected Stripe checkout response
        is_stripe = (
            status_code == 200 and
            data.get("provider") == "stripe" and
            data.get("status") == "ready" and
            data.get("checkout_url", "").startswith("https://checkout.stripe.com/")
        )

        if is_stripe:
            pass_fail = "PASS"
            results.append(("POST /subscription/checkout (premium)", True))
        else:
            pass_fail = "FAIL"
            results.append(("POST /subscription/checkout (premium)", False))
        print_result("POST /subscription/checkout (premium)", status_code, data, pass_fail)
    except Exception as e:
        print_result("POST /subscription/checkout (premium)", "N/A", None, "FAIL", str(e))
        results.append(("POST /subscription/checkout (premium)", False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    print(f"\nTotal: {passed}/{total} passed")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
