"""Migration numbering invariants (duplicate-050 incident, 2026-07-21).

Two migrations landed the same day both numbered 050 (user_avatars via #1279,
chat_operations via #1285). Nothing broke — the drift guard checks object
presence, not filenames — but the numbering invariant is the only thing that
keeps "apply the missing migration" runbooks unambiguous. These tests pin it:

1. every numbered migration file has a UNIQUE numeric prefix;
2. every migration id referenced in scripts/check_migration_drift.py CHECKS
   corresponds to an existing migration file, so a renumber can never leave
   the drift guard pointing at a number that no file carries.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_MIGRATIONS = _REPO / "migrations"
_NUM_RE = re.compile(r"^(\d{3})_.+\.sql$")


def _numbered_files() -> list[tuple[str, str]]:
    out = []
    for f in sorted(_MIGRATIONS.iterdir()):
        m = _NUM_RE.match(f.name)
        if m:
            out.append((m.group(1), f.name))
    return out


def test_migration_numbers_are_unique():
    counts = Counter(num for num, _ in _numbered_files())
    duplicates = {num: [name for n, name in _numbered_files() if n == num]
                  for num, c in counts.items() if c > 1}
    assert not duplicates, f"duplicate migration numbers: {duplicates}"


def test_drift_guard_ids_all_map_to_existing_migration_files():
    sys.path.insert(0, str(_REPO / "scripts"))
    try:
        import check_migration_drift  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    file_numbers = {num for num, _ in _numbered_files()}
    referenced = {mig for mig, _, _ in check_migration_drift.CHECKS}
    orphaned = sorted(referenced - file_numbers)
    assert not orphaned, (
        f"drift-guard CHECKS reference migration numbers with no file: {orphaned}"
    )
