---
name: check-rico-db
description: Read-only database health check for Rico Hunt. Verify DATABASE_URL connectivity, key tables, and row counts without exposing user data or mutating anything.
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - exec
---

# check-rico-db

Read-only database health check for Rico Hunt. This skill never writes, deletes, or modifies rows, schemas, or migrations. It only reports connectivity and coarse structure.

## What it checks

1. `DATABASE_URL` env var is set.
2. Backend can connect to Neon PostgreSQL.
3. Key tables exist (e.g., `users`, `profiles`, `jobs`, `applications`, `action_logs`, `onboarding_state`).
4. Approximate row counts (no PII).
5. Connection pool / query latency is healthy.

## How to run it

Use the helper script:

```bash
python .devin/skills/check-rico-db/check.py
```

Or run inline:

```bash
python - <<'PY'
import os, sys
from urllib.parse import urlparse
url = os.environ.get("DATABASE_URL")
if not url:
    print("DATABASE_URL is not set")
    sys.exit(1)
print("DATABASE_URL is set")
PY
```

For a real connection test via the project's DB helper:

```bash
python - <<'PY'
import os, asyncio, sys
from src.db import get_db
async def main():
    try:
        db = await get_db()
        print("DB connected")
    except Exception as e:
        print(f"DB connection failed: {e}")
        sys.exit(1)
asyncio.run(main())
PY
```

## Safety constraints

- Read-only SELECTs only.
- Do not run `DELETE`, `UPDATE`, `INSERT`, `DROP`, `ALTER`, `TRUNCATE`.
- Do not print user emails, names, phone numbers, CV content, or saved searches.
- If the DB is unreachable, report the symptom and stop — do not retry with credentials or change connection settings.
