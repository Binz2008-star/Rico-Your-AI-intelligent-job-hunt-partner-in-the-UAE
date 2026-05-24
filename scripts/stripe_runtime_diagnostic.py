"""
Production Stripe runtime diagnostic.
Tests against https://rico-job-automation-api.onrender.com
"""
import requests
import json
import sys
import os

BASE_URL = "https://rico-job-automation-api.onrender.com"
TEST_EMAIL = "smoke_test_2026@ricohunt.com"
TEST_PASSWORD = "SmokeTest2026!"

def print_result(test_name, status_code, response_data, pass_fail, error=None):
    print(f"\n{test_name}")
    print(f"  Status Code: {status_code}")
    if response_data:
        # Filter out sensitive fields
        safe_data = {k: v for k, v in response_data.items() 
                    if k not in ['checkout_url', 'token', 'access_token']}
        print(f"  Response: {json.dumps(safe_data, indent=2)}")
    print(f"  Result: {pass_fail}")
    if error:
        print(f"  Error: {error}")

def main():
    results = []
    
    # Step 1: GET /version
    print("=" * 60)
    print("STEP 1: GET /version")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/version", timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        if status_code == 200:
            pass_fail = "PASS"
            results.append(("GET /version", True))
            print(f"  Deployed commit SHA: {data.get('commit_sha', 'N/A')}")
        else:
            pass_fail = "FAIL"
            results.append(("GET /version", False))
        print_result("GET /version", status_code, data, pass_fail)
    except Exception as e:
        print_result("GET /version", "N/A", None, "FAIL", str(e))
        results.append(("GET /version", False))
    
    # Step 2: Login
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
        print("\n❌ CRITICAL: No auth token obtained. Cannot continue.")
        return 1
    
    headers = {"Cookie": f"access_token={token}"}
    
    # Step 3: POST /api/v1/subscription/checkout plan=pro
    print("\n" + "=" * 60)
    print("STEP 3: POST /api/v1/subscription/checkout plan=pro")
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
        
        provider = data.get("provider", "unknown")
        status = data.get("status", "unknown")
        checkout_url = data.get("checkout_url", "")
        is_stripe = checkout_url.startswith("https://checkout.stripe.com/")
        
        print(f"  Status Code: {status_code}")
        print(f"  Provider: {provider}")
        print(f"  Status: {status}")
        print(f"  Checkout URL starts with https://checkout.stripe.com/: {is_stripe}")
        
        if status_code == 200 and provider == "stripe" and status == "ready" and is_stripe:
            pass_fail = "PASS"
            results.append(("POST /subscription/checkout (pro)", True))
        else:
            pass_fail = "FAIL"
            results.append(("POST /subscription/checkout (pro)", False))
        print(f"  Result: {pass_fail}")
    except Exception as e:
        print_result("POST /subscription/checkout (pro)", "N/A", None, "FAIL", str(e))
        results.append(("POST /subscription/checkout (pro)", False))
    
    # Step 4: POST /api/v1/subscription/checkout plan=premium
    print("\n" + "=" * 60)
    print("STEP 4: POST /api/v1/subscription/checkout plan=premium")
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
        
        provider = data.get("provider", "unknown")
        status = data.get("status", "unknown")
        checkout_url = data.get("checkout_url", "")
        is_stripe = checkout_url.startswith("https://checkout.stripe.com/")
        
        print(f"  Status Code: {status_code}")
        print(f"  Provider: {provider}")
        print(f"  Status: {status}")
        print(f"  Checkout URL starts with https://checkout.stripe.com/: {is_stripe}")
        
        if status_code == 200 and provider == "stripe" and status == "ready" and is_stripe:
            pass_fail = "PASS"
            results.append(("POST /subscription/checkout (premium)", True))
        else:
            pass_fail = "FAIL"
            results.append(("POST /subscription/checkout (premium)", False))
        print(f"  Result: {pass_fail}")
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
