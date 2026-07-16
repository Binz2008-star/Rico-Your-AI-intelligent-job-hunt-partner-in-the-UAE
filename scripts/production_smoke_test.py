"""
Production smoke test script for API endpoints.
Tests against https://rico-job-automation-api.onrender.com

Usage:
  export RICO_SMOKE_TEST_EMAIL="your-test-account@example.com"
  export RICO_SMOKE_TEST_PASSWORD="your-test-account-password"
  python scripts/production_smoke_test.py

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

def print_result(test_name, status_code, response_keys, pass_fail, error=None):
    print(f"\n{test_name}")
    print(f"  Status Code: {status_code}")
    print(f"  Response Keys: {response_keys}")
    print(f"  Result: {pass_fail}")
    if error:
        print(f"  Error: {error}")

def main():
    results = []

    # Test 1: Register test user
    print("=" * 60)
    print("TEST 1: POST /api/v1/auth/register")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10
        )
        status_code = response.status_code
        response_keys = list(response.json().keys()) if response.text else []
        if status_code in (201, 409):  # 201 = created, 409 = already exists
            pass_fail = "PASS"
            results.append(("Register", True))
        else:
            pass_fail = "FAIL"
            results.append(("Register", False))
        print_result("Register", status_code, response_keys, pass_fail, response.text if status_code != 201 else None)
        token = response.cookies.get_dict().get("access_token")
    except Exception as e:
        print_result("Register", "N/A", [], "FAIL", str(e))
        results.append(("Register", False))
        token = None

    # Test 2: Login (if register failed or for token refresh)
    print("\n" + "=" * 60)
    print("TEST 2: POST /api/v1/auth/login")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10
        )
        status_code = response.status_code
        response_keys = list(response.json().keys()) if response.text else []
        if status_code == 200:
            pass_fail = "PASS"
            results.append(("Login", True))
            # Extract token from Set-Cookie header (Secure cookie not parsed by requests)
            if "set-cookie" in response.headers:
                set_cookie = response.headers["set-cookie"]
                # Parse access_token from Set-Cookie
                for part in set_cookie.split(";"):
                    part = part.strip()
                    if part.startswith("access_token="):
                        token = part.split("=", 1)[1]
                        break
        else:
            pass_fail = "FAIL"
            results.append(("Login", False))
        print_result("Login", status_code, response_keys, pass_fail, response.text if status_code != 200 else None)
    except Exception as e:
        print_result("Login", "N/A", [], "FAIL", str(e))
        results.append(("Login", False))

    if not token:
        print("\n❌ CRITICAL: No auth token obtained. Cannot continue with authenticated tests.")
        return 1

    headers = {"Cookie": f"access_token={token}"}

    # Test 3: GET /api/v1/me
    print("\n" + "=" * 60)
    print("TEST 3: GET /api/v1/me")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/me", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        response_keys = list(data.keys())
        expected_keys = {"email", "role", "authenticated"}
        if status_code == 200 and expected_keys.issubset(set(response_keys)):
            pass_fail = "PASS"
            results.append(("GET /me", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /me", False))
        print_result("GET /me", status_code, response_keys, pass_fail)
    except Exception as e:
        print_result("GET /me", "N/A", [], "FAIL", str(e))
        results.append(("GET /me", False))

    # Test 4: GET /api/v1/rico/profile
    print("\n" + "=" * 60)
    print("TEST 4: GET /api/v1/rico/profile")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/rico/profile", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        response_keys = list(data.keys())
        expected_profile_keys = {"profile_exists", "user_id", "email", "target_roles", "skills", "completeness_score"}
        if status_code == 200 and expected_profile_keys.issubset(set(response_keys)):
            pass_fail = "PASS"
            results.append(("GET /rico/profile", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /rico/profile", False))
        print_result("GET /rico/profile", status_code, response_keys, pass_fail)
    except Exception as e:
        print_result("GET /rico/profile", "N/A", [], "FAIL", str(e))
        results.append(("GET /rico/profile", False))

    # Test 5: GET /api/v1/rico/chat/history?limit=6
    print("\n" + "=" * 60)
    print("TEST 5: GET /api/v1/rico/chat/history?limit=6")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/rico/chat/history?limit=6", headers=headers, timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        response_keys = list(data.keys())
        expected_chat_keys = {"messages", "total", "has_more"}
        if status_code == 200 and expected_chat_keys.issubset(set(response_keys)):
            pass_fail = "PASS"
            results.append(("GET /rico/chat/history", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /rico/chat/history", False))
        print_result("GET /rico/chat/history", status_code, response_keys, pass_fail)
    except Exception as e:
        print_result("GET /rico/chat/history", "N/A", [], "FAIL", str(e))
        results.append(("GET /rico/chat/history", False))

    # Test 6: POST /api/v1/rico/chat with message "hello"
    print("\n" + "=" * 60)
    print("TEST 6: POST /api/v1/rico/chat with message 'hello'")
    print("=" * 60)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rico/chat",
            headers=headers,
            json={"message": "hello"},
            timeout=30
        )
        status_code = response.status_code
        data = response.json() if response.text else {}
        response_keys = list(data.keys())
        if status_code == 200:
            pass_fail = "PASS"
            results.append(("POST /rico/chat", True))
        else:
            pass_fail = "FAIL"
            results.append(("POST /rico/chat", False))
        print_result("POST /rico/chat", status_code, response_keys, pass_fail)
    except Exception as e:
        print_result("POST /rico/chat", "N/A", [], "FAIL", str(e))
        results.append(("POST /rico/chat", False))

    # Test 7: GET /api/v1/jobs?page=1&limit=20&min_score=0
    print("\n" + "=" * 60)
    print("TEST 7: GET /api/v1/jobs?page=1&limit=20&min_score=0")
    print("=" * 60)
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/jobs?page=1&limit=20&min_score=0",
            headers=headers,
            timeout=30
        )
        status_code = response.status_code
        data = response.json() if response.text else {}
        response_keys = list(data.keys())
        expected_jobs_keys = {"jobs", "total", "page", "limit", "pages"}
        if status_code == 200 and expected_jobs_keys.issubset(set(response_keys)):
            pass_fail = "PASS"
            results.append(("GET /jobs", True))
        else:
            pass_fail = "FAIL"
            results.append(("GET /jobs", False))
        print_result("GET /jobs", status_code, response_keys, pass_fail)
    except Exception as e:
        print_result("GET /jobs", "N/A", [], "FAIL", str(e))
        results.append(("GET /jobs", False))

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
