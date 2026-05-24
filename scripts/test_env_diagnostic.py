"""
Test Stripe env diagnostic endpoint.
"""
import requests
import json

BASE_URL = "https://rico-job-automation-api.onrender.com"

def main():
    print("=" * 60)
    print("GET /api/v1/subscription/diagnostic/env-check")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/subscription/diagnostic/env-check", timeout=10)
        status_code = response.status_code
        data = response.json() if response.text else {}
        print(f"Status Code: {status_code}")
        print(f"Response:")
        for key, value in data.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
