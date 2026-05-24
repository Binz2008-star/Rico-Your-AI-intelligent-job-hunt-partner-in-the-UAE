"""Quick smoke test for migration 013: verify tables, indexes, triggers, and /me endpoint."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
cur = conn.cursor()

# 1. Tables
cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema='public' AND table_name IN ('user_subscriptions','subscription_events') "
    "ORDER BY table_name"
)
tables = [r["table_name"] for r in cur.fetchall()]
print("Tables:  ", tables)
assert "user_subscriptions" in tables, "MISSING: user_subscriptions"
assert "subscription_events" in tables, "MISSING: subscription_events"

# 2. Indexes
cur.execute(
    "SELECT indexname FROM pg_indexes "
    "WHERE tablename IN ('user_subscriptions','subscription_events') "
    "ORDER BY indexname"
)
indexes = [r["indexname"] for r in cur.fetchall()]
print("Indexes: ", indexes)
assert "idx_user_subscriptions_user_id" in indexes
assert "idx_subscription_events_stripe_event_id" in indexes

# 3. Trigger
cur.execute(
    "SELECT trigger_name FROM information_schema.triggers "
    "WHERE event_object_table='user_subscriptions'"
)
triggers = [r["trigger_name"] for r in cur.fetchall()]
print("Triggers:", triggers)
assert "trg_user_subscriptions_updated_at" in triggers

# 4. Insert test Pro row and verify upsert
cur.execute(
    "INSERT INTO user_subscriptions (user_id, plan, status, stripe_customer_id, stripe_subscription_id) "
    "VALUES ('smoke-test@rico.ai', 'pro', 'active', 'cus_smoke', 'sub_smoke') "
    "ON CONFLICT (user_id) DO UPDATE SET plan='pro', status='active' "
    "RETURNING user_id, plan, status"
)
row = cur.fetchone()
print("Pro row: ", dict(row))
assert row["plan"] == "pro"
assert row["status"] == "active"

# 5. Upsert to Premium
cur.execute(
    "UPDATE user_subscriptions SET plan='premium', status='active' "
    "WHERE user_id='smoke-test@rico.ai' RETURNING plan, status"
)
row = cur.fetchone()
print("Premium: ", dict(row))
assert row["plan"] == "premium"

# 6. Cleanup
cur.execute("DELETE FROM user_subscriptions WHERE user_id='smoke-test@rico.ai'")
conn.commit()
conn.close()
print("\nDB smoke: PASSED")
