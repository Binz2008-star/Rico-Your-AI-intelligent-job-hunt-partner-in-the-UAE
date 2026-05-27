"""
Safe test-user cleanup script.

Deletes ONLY users that match known test-account patterns.
Defaults to dry-run — no changes made unless --confirm-delete-test-users is passed.
Production DATABASE_URL requires --allow-production-test-cleanup in addition.

Usage examples:
  # Dry-run (safe, prints what would be deleted):
  python scripts/cleanup_test_users.py

  # Delete test users from dev/local DB:
  python scripts/cleanup_test_users.py --confirm-delete-test-users

  # Delete specific email only (dry-run first):
  python scripts/cleanup_test_users.py --email test@example.com

  # Delete specific email for real:
  python scripts/cleanup_test_users.py --email test@example.com --confirm-delete-test-users

  # Production database (requires both flags):
  python scripts/cleanup_test_users.py --confirm-delete-test-users --allow-production-test-cleanup
"""

import argparse
import os
import sys
from typing import Optional

# Safe test-account patterns (lowercase match)
TEST_EMAIL_SUBSTRINGS = ["+rico-test", "+test"]
TEST_EMAIL_PREFIXES = ["test.", "testuser.", "rico-test.", "autotest."]
TEST_EMAIL_DOMAINS = ["test.local", "example.com", "mailtest.dev", "testmail.io"]

PRODUCTION_DB_INDICATORS = [
    "render.com",
    "neon.tech",
    ".neon.tech",
    "ricohunt",
    "render-postgres",
]


def is_production_db(url: str) -> bool:
    lower = url.lower()
    return any(indicator in lower for indicator in PRODUCTION_DB_INDICATORS)


def is_test_email(email: str, extra_email: Optional[str] = None) -> bool:
    lower = email.lower().strip()
    if extra_email and lower == extra_email.lower().strip():
        return True
    for substring in TEST_EMAIL_SUBSTRINGS:
        if substring in lower:
            return True
    local_part = lower.split("@")[0]
    for prefix in TEST_EMAIL_PREFIXES:
        if local_part.startswith(prefix):
            return True
    if "@" in lower:
        domain = lower.split("@", 1)[1]
        if domain in TEST_EMAIL_DOMAINS:
            return True
    return False


def find_test_users(conn, extra_email: Optional[str]) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT user_id, email, created_at, role FROM users ORDER BY created_at")
        rows = cur.fetchall()

    test_users = []
    for row in rows:
        user_id, email, created_at, role = row[0], row[1], row[2], row[3]
        if is_test_email(email, extra_email):
            test_users.append({
                "user_id": user_id,
                "email": email,
                "created_at": created_at,
                "role": role,
            })
    return test_users


def delete_users(conn, user_ids: list[str]) -> int:
    if not user_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM users WHERE user_id = ANY(%s)",
            (user_ids,),
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe test-user cleanup. Dry-run by default."
    )
    parser.add_argument(
        "--confirm-delete-test-users",
        action="store_true",
        help="Actually delete matched test users. Without this flag, only prints what would be deleted.",
    )
    parser.add_argument(
        "--allow-production-test-cleanup",
        action="store_true",
        help="Required when DATABASE_URL points to a production database.",
    )
    parser.add_argument(
        "--email",
        metavar="EMAIL",
        help="Also match this specific email address (in addition to pattern matching).",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL is not set.")
        sys.exit(1)

    prod = is_production_db(database_url)
    if prod:
        print("WARNING: DATABASE_URL appears to point to a PRODUCTION database.")
        print("         Only test-pattern emails will be targeted — never real users.")
        if args.confirm_delete_test_users and not args.allow_production_test_cleanup:
            print(
                "ERROR: --allow-production-test-cleanup is required when targeting production."
            )
            print("       Re-run with both --confirm-delete-test-users AND --allow-production-test-cleanup.")
            sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 is required. Install with: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database_url)
    except Exception as exc:
        print(f"ERROR: Could not connect to database: {exc}")
        sys.exit(1)

    try:
        test_users = find_test_users(conn, args.email)
    except Exception as exc:
        print(f"ERROR: Could not query users table: {exc}")
        conn.close()
        sys.exit(1)

    if not test_users:
        print("No test users found matching the configured patterns.")
        conn.close()
        return

    print(f"\nFound {len(test_users)} test user(s):")
    print(f"{'Email':<45} {'Role':<10} {'Created'}")
    print("-" * 80)
    for u in test_users:
        print(f"{u['email']:<45} {u['role']:<10} {u['created_at']}")

    if not args.confirm_delete_test_users:
        print("\n[DRY-RUN] No users deleted.")
        print("Pass --confirm-delete-test-users to delete the users listed above.")
        if prod:
            print("Also pass --allow-production-test-cleanup for production databases.")
        conn.close()
        return

    user_ids = [u["user_id"] for u in test_users]
    try:
        deleted = delete_users(conn, user_ids)
    except Exception as exc:
        print(f"ERROR: Deletion failed: {exc}")
        conn.close()
        sys.exit(1)

    print(f"\nDeleted {deleted} test user(s).")
    conn.close()


if __name__ == "__main__":
    main()
