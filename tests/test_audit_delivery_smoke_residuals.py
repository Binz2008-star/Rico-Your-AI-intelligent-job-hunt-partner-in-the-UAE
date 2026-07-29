"""The residual audit must stay read-only and stay inside its namespace.

These are guards on the harness itself, not on product behaviour. The audit
holds production database credentials, so the properties that make it safe —
SELECT-only, no external input reaching SQL, one fixed synthetic namespace —
are asserted here rather than left to review to re-check by eye each time.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_delivery_smoke_residuals.py"

#: Statements that would make this anything other than an audit.
_WRITE_VERBS = (
    "delete", "update", "insert", "upsert", "truncate", "drop", "alter",
    "create", "grant", "revoke", "call", "do ", "merge",
)


@pytest.fixture(scope="module")
def module():
    # Restored afterwards: the confirmation gate is a global, and leaving it set
    # would arm any later import of the audit in the same session.
    previous = os.environ.get("AUDIT_CONFIRM")
    os.environ["AUDIT_CONFIRM"] = "AUDIT-DELIVERY-RESIDUALS"
    spec = importlib.util.spec_from_file_location("audit_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    if previous is None:
        os.environ.pop("AUDIT_CONFIRM", None)
    else:
        os.environ["AUDIT_CONFIRM"] = previous


@pytest.fixture(scope="module")
def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_refuses_to_run_without_confirmation():
    """The confirmation gate is the only thing standing between a dispatch and
    a production credential being used, so it must not be optional."""
    assert 'os.environ.get("AUDIT_CONFIRM") != CONFIRMATION' in SCRIPT.read_text(encoding="utf-8")


def test_namespace_is_exactly_the_delivery_smoke_synthetic_pattern(module):
    assert module.PATTERN == "smoke-delivery-%@synthetic-rico.test"
    # A bare '%' or a pattern without the synthetic TLD would reach real users.
    assert module.PATTERN.endswith("@synthetic-rico.test")
    assert module.PATTERN.startswith("smoke-delivery-")


def test_session_is_opened_read_only(source: str):
    assert "set_session(readonly=True" in source
    assert "SET TRANSACTION READ ONLY" in source


def test_no_write_statement_anywhere_in_the_sql(source: str):
    """No string literal in the module may carry a write statement.

    Parsed with ``ast`` rather than a regex: the SQL is built from implicit
    multi-line concatenation and f-strings, so a regex that grabs the first
    quoted chunk of each ``execute(...)`` silently skips every continuation
    fragment — and would miss a write hiding in one.
    """
    import ast

    def _flatten(node) -> str | None:
        """Recover the literal text of an execute() argument.

        Python merges adjacent string literals at parse time, so the multi-line
        implicit concatenations arrive as a single Constant. f-strings arrive as
        JoinedStr; only their constant parts are SQL text (the interpolated
        parts are module-constant identifiers, asserted separately).
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(
                v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        return None

    executed = [
        text
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("execute", "executemany", "copy_expert")
        and node.args
        for text in [_flatten(node.args[0])]
        if text is not None
    ]
    assert len(executed) >= 4, f"expected every execute() site to be literal SQL, found {len(executed)}"
    for stmt in executed:
        lowered = stmt.lower()
        for verb in _WRITE_VERBS:
            assert not re.search(rf"\b{re.escape(verb.strip())}\b", lowered), (
                f"write verb {verb!r} appears in executed SQL: {stmt!r}"
            )


def test_only_read_only_statements_are_executed(source: str):
    """Every execute() call site must issue a SELECT or a session directive."""
    executed = re.findall(r"cur\.execute\(\s*\n?\s*(?:f?[\"'])([^\"']+)", source)
    assert executed, "no executed SQL found — the extraction regex needs updating"
    for stmt in executed:
        lowered = stmt.strip().lower()
        assert lowered.startswith(("select", "set transaction")), (
            f"non-read statement executed: {stmt!r}"
        )


def test_sql_fragments_contain_no_write_verbs(module):
    """The composed predicates are built from module constants; check them too."""
    for frag in (module._RICO_UUID_SET, module._TEXT_ID_SET):
        lowered = frag.lower()
        assert lowered.strip().startswith("select")
        for verb in ("delete", "update", "insert", "drop", "truncate", "alter"):
            assert verb not in lowered


def test_email_keyed_tables_do_not_resolve_through_the_users_table(module):
    """An orphan's parent is gone by definition — resolving through ``users``
    would hide exactly the rows this audit exists to find."""
    for table, key_col, mode, _ in module.TABLES:
        if mode not in ("email_direct", "rico_self"):
            continue
        predicate = module.build_predicate(key_col, mode)
        assert "select" not in predicate.lower(), f"{table} predicate runs a subquery"
        assert "users" not in predicate.lower(), (
            f"{table} would go invisible once its parent row is deleted"
        )
        assert "LIKE %(pat)s" in predicate


def test_zero_is_only_provable_for_directly_keyed_tables(module):
    """A count of zero from an unresolvable child must not read as VERIFIED."""
    class _NoFkCursor:
        def execute(self, *_a, **_k):
            pass

        def fetchall(self):
            return []

    cur = _NoFkCursor()
    assert module.zero_is_provable(cur, "users", "email", "email_direct") is True
    assert module.zero_is_provable(cur, "rico_users", "email", "rico_self") is True
    # No cascade FK discoverable -> absence is not provable.
    assert module.zero_is_provable(cur, "rico_profiles", "user_id", "uuid_child") is False
    assert module.zero_is_provable(cur, "chat_operations", "user_id", "text_id_child") is False


def test_every_audited_table_uses_a_known_key_mode(module):
    known = {"email_direct", "rico_self", "uuid_child", "text_id_child"}
    assert module.TABLES, "the audit must cover at least one table"
    for table, key_col, mode, ts_candidates in module.TABLES:
        assert mode in known, f"{table} uses unknown key mode {mode!r}"
        assert key_col and isinstance(key_col, str)
        assert isinstance(ts_candidates, tuple)
        # Identifiers are interpolated into SQL, so they must be plain names —
        # this is what keeps the f-strings injection-free.
        assert re.fullmatch(r"[a-z_][a-z0-9_]*", table), table
        assert re.fullmatch(r"[a-z_][a-z0-9_]*", key_col), key_col


def test_covers_the_tables_reachable_from_the_authenticated_surface(module):
    """Regression guard on audit coverage.

    Most of these are written by the Delivery journey itself; `user_documents`
    and `learning_signals` are not (the smoke uploads no CV and sends no
    feedback) but stay audited because they are reachable from the same
    authenticated identity and cost nothing to count.

    `rico_onboarding_states` and `user_job_context` matter most: neither has a
    foreign key to `users`, so deleting the user does not sweep them.
    """
    audited = {t[0] for t in module.TABLES}
    for required in (
        "users",
        "rico_users",
        "rico_profiles",
        "rico_chat_history",
        "chat_operations",
        "email_verification_tokens",
        "learning_signals",
        "user_documents",
        "rico_onboarding_states",
        "user_job_context",
        "rico_job_recommendations",
    ):
        assert required in audited, f"{required} is reachable but not audited"


def test_chat_operations_is_keyed_on_the_canonical_email(module):
    """chat_operations.user_id stores the email, not an opaque row id.

    RicoSessionContext.for_authenticated(user["email"]) flows unchanged into
    the operation row. Auditing it as an id-keyed child would resolve through
    users/rico_users, match nothing, and report a clean zero for the one table
    delivery_smoke.py's own cleanup provably fails to clear.
    """
    modes = {t[0]: t[2] for t in module.TABLES}
    assert modes["chat_operations"] == "email_direct"
    assert modes["user_job_context"] == "email_direct"


def test_audit_takes_no_sql_bearing_input_from_the_environment(source: str):
    """Only the confirmation token and the DSN may come from outside."""
    env_reads = set(re.findall(r"os\.environ(?:\.get)?[\[\(]\s*[\"']([A-Z_]+)[\"']", source))
    assert env_reads <= {"AUDIT_CONFIRM", "DATABASE_URL"}, (
        f"unexpected environment input could reach the audit: {env_reads}"
    )
