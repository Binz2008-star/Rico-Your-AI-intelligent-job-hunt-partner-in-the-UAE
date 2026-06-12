"""
scripts/report_onboarding_completed_without_profile.py

READ-ONLY audit: list users whose onboarding status is 'completed' in
rico_onboarding_states but whose career profile does not pass the minimum
career profile gate (evaluate_minimum_profile).

Prints:
  - affected user IDs and which gate fields are missing
  - proposed SQL UPDATE statements to downgrade them (NOT executed)

Usage:
    python -m scripts.report_onboarding_completed_without_profile

Requires DATABASE_URL to be set.  Never writes to the database.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    from src.db import get_db_connection, is_db_available
    from src.repositories.profile_repo import get_profile
    from src.services.profile_context_resolver import (
        evaluate_minimum_profile,
        resolve_profile_context,
    )

    if not is_db_available():
        print("ERROR: DATABASE_URL not set or DB unreachable.")
        sys.exit(1)

    conn = get_db_connection()
    if not conn:
        print("ERROR: could not connect to database.")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, completed_at
                FROM rico_onboarding_states
                WHERE status = 'completed'
                ORDER BY completed_at DESC NULLS LAST
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No users with status='completed' found.")
        return

    print(f"Found {len(rows)} user(s) with status='completed'. Evaluating gate...\n")

    affected: list[tuple[str, list[str]]] = []

    for row in rows:
        user_id = row[0]
        profile = get_profile(user_id)
        ctx = resolve_profile_context(user_id, profile)
        gate_ok, missing = evaluate_minimum_profile(ctx)
        if not gate_ok:
            affected.append((user_id, missing))

    if not affected:
        print("All completed users pass the minimum profile gate. No action needed.")
        return

    print(f"{len(affected)} user(s) fail the gate:\n")
    for user_id, missing in affected:
        print(f"  {user_id!r}  missing={missing}")

    print("\n-- Proposed SQL (NOT executed — review and run manually) --\n")
    for user_id, _ in affected:
        print(
            f"UPDATE rico_onboarding_states "
            f"SET status = 'in_progress', completed_at = NULL, updated_at = NOW() "
            f"WHERE user_id = '{user_id}';"
        )

    print(
        f"\n-- {len(affected)} row(s) would be downgraded. "
        "Copy the statements above and run them in a DB client after review. --"
    )


if __name__ == "__main__":
    main()
