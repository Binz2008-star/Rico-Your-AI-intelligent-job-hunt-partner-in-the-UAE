"""Read-only audit report: onboarding marked completed without a real career profile.

Finds rico_onboarding_states rows with status='completed' whose user has no
minimum career profile (per src.services.profile_context_resolver.evaluate_minimum_profile)
and prints a proposed downgrade to 'in_progress'.

This script NEVER writes to the database. It prints the proposed UPDATE
statements for manual review/approval only.

Usage:
    DATABASE_URL=... python -m scripts.report_onboarding_completed_without_profile
"""
from __future__ import annotations

import sys

from src.repositories.profile_repo import get_profile
from src.services.profile_context_resolver import (
    evaluate_minimum_profile,
    resolve_profile_context,
)


def main() -> int:
    from src.db import get_db_connection, is_db_available

    if not is_db_available():
        print("ERROR: DATABASE_URL not configured / DB unavailable. Aborting (read-only).")
        return 1

    conn = get_db_connection()
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

    flagged = []
    for user_id, completed_at in rows:
        ctx = resolve_profile_context(user_id, get_profile(user_id))
        complete, missing = evaluate_minimum_profile(ctx)
        if not complete:
            flagged.append((user_id, completed_at, missing))

    print(f"Checked {len(rows)} completed onboarding rows; {len(flagged)} lack a minimum career profile.\n")
    if not flagged:
        print("Nothing to downgrade.")
        return 0

    print("user_id | completed_at | missing_fields")
    print("-" * 80)
    for user_id, completed_at, missing in flagged:
        print(f"{user_id} | {completed_at} | {', '.join(missing)}")

    print("\nProposed downgrade (NOT executed — requires manual approval):\n")
    for user_id, _, _ in flagged:
        print(
            "UPDATE rico_onboarding_states "
            "SET status = 'in_progress', completed_at = NULL, updated_at = NOW() "
            f"WHERE user_id = '{user_id}' AND status = 'completed';"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
