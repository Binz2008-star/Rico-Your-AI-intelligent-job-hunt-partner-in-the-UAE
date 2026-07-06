#!/usr/bin/env python3
"""Read-only Rico Hunt database health check."""
import os
import sys
import urllib.parse

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.")
        return 1

    parsed = urllib.parse.urlparse(db_url)
    print(f"INFO: DATABASE_URL host={parsed.hostname or 'unknown'} dbname={parsed.path.lstrip('/') or 'unknown'}")

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        return 1

    print("OK: Database connection succeeded.")

    cur = conn.cursor()

    # Read-only check: list key Rico tables and row counts.
    key_tables = [
        "users",
        "profiles",
        "jobs",
        "applications",
        "action_logs",
        "onboarding_state",
    ]

    print("\nTable counts (read-only, no PII):")
    for table in key_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table:<20} {count:>8}")
        except Exception as e:
            print(f"  {table:<20} ERROR: {e}")

    cur.close()
    conn.close()
    print("\nINFO: Check complete. No writes performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
