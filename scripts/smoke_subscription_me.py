"""Smoke test for /api/v1/subscription/me — Free fallback + Paddle-backed Rico Monthly.

Single-plan Paddle contract (DEC-20260713-005): the only paid plan is Rico Monthly
("pro"), USD 21.50/month. Stripe and the Premium tier are retired. Paid status is
resolved from the paddle_subscriptions table via
src.repositories.paddle_repo.get_paddle_subscription_by_user, so this smoke mocks
that call — it never opens a checkout, never posts a webhook, and never charges.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("JWT_SECRET", "smoketest" + "x" * 21)
os.environ.setdefault("ADMIN_EMAIL", "admin@rico.ai")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from src.api.app import app
from src.api.auth import create_access_token
import src.repositories.paddle_repo as paddle_repo

token = create_access_token({"sub": "smoke@rico.ai", "role": "user"})
client = TestClient(app, raise_server_exceptions=False)
client.cookies.set("access_token", token)

_FUTURE = datetime.now(timezone.utc) + timedelta(days=30)


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
    print(f"  {label}: OK — plan={plan}, is_active={is_active}" + (f", USD {price}" if price else ""))


print("\n--- /api/v1/subscription/plans ---")
r = client.get("/api/v1/subscription/plans")
assert r.status_code == 200
plans = r.json()["plans"]
# Single-plan scope: Rico Monthly only. Premium is retired and must not reappear.
assert [p["plan"] for p in plans] == ["pro"], f"unexpected plans: {[p['plan'] for p in plans]}"
assert [p["currency"] for p in plans] == ["USD"]
assert [p["price_monthly"] for p in plans] == [21.50]
print("  plans: OK —", [(p["plan"], p["currency"], p["price_monthly"]) for p in plans])

print("\n--- /api/v1/subscription/me ---")

import unittest.mock as mock

# 1. Free fallback (no Paddle row)
with mock.patch.object(paddle_repo, "get_paddle_subscription_by_user", return_value=None):
    r = client.get("/api/v1/subscription/me")
check("Free fallback", r, plan="free", is_active=False)

# 2. Active Rico Monthly (pro) from Paddle
with mock.patch.object(paddle_repo, "get_paddle_subscription_by_user", return_value={
    "user_id": "smoke@rico.ai", "plan": "pro", "status": "active",
    "paddle_customer_id": "ctm_smoke", "paddle_subscription_id": "sub_smoke",
    "current_period_start": None, "current_period_end": _FUTURE,
    "past_due_since": None, "cancel_at": None, "canceled_at": None,
}):
    r = client.get("/api/v1/subscription/me")
check("Active Pro", r, plan="pro", is_active=True, price=21.50, ai_limit=300, automation=False)

# 3. Canceled Pro — is_active must be False
with mock.patch.object(paddle_repo, "get_paddle_subscription_by_user", return_value={
    "user_id": "smoke@rico.ai", "plan": "pro", "status": "canceled",
    "paddle_customer_id": None, "paddle_subscription_id": None,
    "current_period_start": None, "current_period_end": None,
    "past_due_since": None, "cancel_at": None, "canceled_at": None,
}):
    r = client.get("/api/v1/subscription/me")
check("Canceled Pro", r, plan="pro", is_active=False)

print("\n--- All smoke checks PASSED ---\n")
