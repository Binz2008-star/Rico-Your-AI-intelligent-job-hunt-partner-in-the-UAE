"""Smoke test for /api/v1/subscription/me — Free fallback + DB-backed Pro/Premium."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("JWT_SECRET", "smoketest" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "admin@rico.ai")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")

from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from src.api.app import app
from src.api.auth import create_access_token
import src.repositories.subscription_repo as repo

token = create_access_token({"sub": "smoke@rico.ai", "role": "user"})
client = TestClient(app, raise_server_exceptions=False)
client.cookies.set("access_token", token)

def check(label, r, *, plan, is_active, price=None, ai_limit=None, automation=None):
    assert r.status_code == 200, f"{label}: HTTP {r.status_code} - {r.text}"
    body = r.json()
    assert body["subscription"]["plan"] == plan, f"{label}: plan={body['subscription']['plan']!r}"
    assert body["is_active"] is is_active, f"{label}: is_active={body['is_active']!r}"
    if price is not None:
        assert body["plan"]["price_monthly"] == price, f"{label}: price={body['plan']['price_monthly']!r}"
    if ai_limit is not None:
        assert body["subscription"]["entitlements"]["monthly_ai_message_limit"] == ai_limit
    if automation is not None:
        assert body["subscription"]["entitlements"]["application_automation_enabled"] is automation
    print(f"  {label}: OK — plan={plan}, is_active={is_active}" + (f", AED {price}" if price else ""))

print("\n--- /api/v1/subscription/plans ---")
r = client.get("/api/v1/subscription/plans")
assert r.status_code == 200
plans = r.json()["plans"]
assert [p["plan"] for p in plans] == ["pro", "premium"]
assert [p["price_monthly"] for p in plans] == [50, 150]
print("  plans: OK —", [(p["plan"], p["price_monthly"]) for p in plans])

print("\n--- /api/v1/subscription/me ---")

# 1. Free fallback (no DB row)
import unittest.mock as mock
with mock.patch.object(repo, "get_subscription", return_value=None):
    r = client.get("/api/v1/subscription/me")
check("Free fallback", r, plan="free", is_active=False)

# 2. Active Pro from DB
with mock.patch.object(repo, "get_subscription", return_value={
    "user_id": "smoke@rico.ai", "plan": "pro", "status": "active",
    "stripe_customer_id": "cus_smoke", "stripe_subscription_id": "sub_smoke",
    "current_period_start": None, "current_period_end": None,
}):
    r = client.get("/api/v1/subscription/me")
check("Active Pro", r, plan="pro", is_active=True, price=50, ai_limit=300, automation=False)

# 3. Active Premium from DB
with mock.patch.object(repo, "get_subscription", return_value={
    "user_id": "smoke@rico.ai", "plan": "premium", "status": "active",
    "stripe_customer_id": "cus_smoke2", "stripe_subscription_id": "sub_smoke2",
    "current_period_start": None, "current_period_end": None,
}):
    r = client.get("/api/v1/subscription/me")
check("Active Premium", r, plan="premium", is_active=True, price=150, ai_limit=1500, automation=True)

# 4. Canceled Pro — is_active must be False
with mock.patch.object(repo, "get_subscription", return_value={
    "user_id": "smoke@rico.ai", "plan": "pro", "status": "canceled",
    "stripe_customer_id": None, "stripe_subscription_id": None,
    "current_period_start": None, "current_period_end": None,
}):
    r = client.get("/api/v1/subscription/me")
check("Canceled Pro", r, plan="pro", is_active=False)

# 5. Checkout mock still works
r = client.post("/api/v1/subscription/checkout", json={"plan": "pro"})
assert r.status_code == 200
body = r.json()
assert body["provider"] == "mock"
assert "plan=pro" in body["checkout_url"]
print("\n  Checkout mock: OK")

print("\n--- All smoke checks PASSED ---\n")
