"""Structure tests for scripts/check_migration_drift.py (no DB required)."""
import re
from pathlib import Path

from scripts.check_migration_drift import CHECKS

_VALID_KINDS = {"table", "view", "index", "column", "constraint", "trigger"}
_MIGRATIONS_DIR = Path("migrations")


def test_checks_are_well_formed():
    assert CHECKS, "CHECKS must not be empty"
    for migration, kind, ident in CHECKS:
        assert re.fullmatch(r"\d{3}", migration), f"bad migration id: {migration!r}"
        assert kind in _VALID_KINDS, f"bad kind: {kind!r}"
        if kind == "column":
            assert isinstance(ident, tuple) and len(ident) == 2, f"column ident must be (table, col): {ident!r}"
        else:
            assert isinstance(ident, str) and ident, f"ident must be a non-empty str: {ident!r}"


def test_every_checked_migration_file_exists():
    on_disk = {p.name[:3] for p in _MIGRATIONS_DIR.glob("*.sql")}
    for migration, _, _ in CHECKS:
        assert migration in on_disk, f"migration {migration} referenced in CHECKS but no .sql file found"


def test_covers_known_drift_migrations():
    covered = {m for m, _, _ in CHECKS}
    # The migrations that actually drifted in prod must be guarded.
    for m in ("005", "011", "021", "030"):
        assert m in covered, f"drift-prone migration {m} is not covered by CHECKS"


def test_030_checks_both_column_and_trigger():
    objs = {(kind, ident) for migration, kind, ident in CHECKS if migration == "030"}
    assert ("column", ("action_audit_log", "event_type")) in objs
    assert ("trigger", "trg_action_audit_log_append_only") in objs


# Migrations with no DB-detectable object (comment/doc-only) — legitimately not
# in CHECKS. Everything else MUST be covered, or the daily drift job would go
# green while the migration was never applied to Neon.
_NO_OBJECT_MIGRATIONS = {
    "020",  # 020_user_job_context_gap_filler: comment-only
    "034",  # 034_drop_redundant_indexes: DROP-only, creates no detectable object
}


def test_every_migration_file_is_covered():
    on_disk = {p.name[:3] for p in _MIGRATIONS_DIR.glob("*.sql")}
    covered = {m for m, _, _ in CHECKS}
    uncovered = on_disk - covered - _NO_OBJECT_MIGRATIONS
    assert not uncovered, (
        f"migration file(s) {sorted(uncovered)} have no CHECKS entry — the drift "
        "job would pass even if they were never applied to Neon. Add a signature "
        "object to scripts/check_migration_drift.py (or, if comment-only, to "
        "_NO_OBJECT_MIGRATIONS here)."
    )
