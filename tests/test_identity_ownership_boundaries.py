"""Identity-ownership invariants, enforced at the repository boundary.

Five behaviours are pinned here. All fixtures are synthetic; no database, no network.

1. two-account      — each authenticated subject resolves to its own row
2. collision        — a guest row carrying an account's contact value never wins
3. guest-artifact   — tripwire: if guests ever gain upload artifacts, the write guard
                      must already be in place (see the test's own docstring)
4. legacy-account   — accounts whose external identifier was never populated still resolve
5. guest-conversion — the explicit authenticated claim flow remains the only conversion path

The invariants live below the routes on purpose. Route-level guards existed before this
change and were correct, but a guard on a route protects only that route; the repository
is the boundary every caller passes through.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models.principal import (
    PUBLIC_PRINCIPAL_PREFIX,
    TRUSTED_IDENTITY_FIELDS,
    IdentityOwnershipAmbiguous,
    is_public_principal,
    rejected_trusted_identity_fields,
)

ACCOUNT_A = "account-a@synthetic.test"
ACCOUNT_B = "account-b@synthetic.test"
from datetime import datetime, timezone
_WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
GUEST = f"{PUBLIC_PRINCIPAL_PREFIX}g-SYNTHETIC0000000000"


def _bundle_rows(cur, rows):
    """Point a mocked cursor at a fixed result set."""
    cur.fetchmany.return_value = rows
    cur.fetchone.return_value = rows[0] if rows else None


def _guest_flag_binding(cur):
    """The value actually bound to the guest-scope placeholder.

    Derived from the SQL rather than assumed to be at a fixed index. Asserting on a
    hardcoded position passes even when the parameter tuple is ordered wrongly, which
    is a defect a mocked cursor cannot otherwise surface -- the query never runs, so a
    misaligned binding looks identical to a correct one.
    """
    sql, params = cur.execute.call_args[0][0], cur.execute.call_args[0][1]
    marker = "AND (%s OR "
    preceding = sql[: sql.index(marker)] + "AND ("
    return params[preceding.replace("%%", "").count("%s")]


def _db_with_rows(rows):
    from src.rico_db import RicoDB

    cur = MagicMock()
    _bundle_rows(cur, rows)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = RicoDB.__new__(RicoDB)
    return db, conn, cur


# ── 1. two-account ────────────────────────────────────────────────────────────

def test_two_accounts_each_resolve_to_their_own_row():
    """Each subject's own identifier is what the query is bound to.

    Asserting on the returned row alone would pass against `WHERE 1=1`, so this checks
    the parameters actually sent: every bind value must be the caller's identifier and
    nothing else, which is what makes cross-account resolution impossible.
    """
    for subject, row_id in ((ACCOUNT_A, "row-a"), (ACCOUNT_B, "row-b")):
        db, conn, cur = _db_with_rows([{"id": row_id, "external_user_id": subject}])
        assert db.get_user_bundle(subject, conn=conn)["id"] == row_id
        # Identifier bindings only -- the one non-string parameter is the
        # caller-is-guest boolean that scopes the guest exclusion, not an identity value.
        params = [p for p in cur.execute.call_args[0][1] if isinstance(p, str)]
        assert set(params) == {subject}, (
            "resolution must bind only to the caller's own identifier"
        )


# ── 2. collision ──────────────────────────────────────────────────────────────

def test_guest_rows_are_excluded_on_both_resolution_branches():
    """TRIPWIRE, not behavioural acceptance evidence for A2.

    This asserts only that the string `NOT LIKE 'public:` appears in the emitted SQL.
    It proves the predicate is PRESENT; it proves nothing about whether any row is
    EXCLUDED. A predicate that is present but ineffective passes it, and a harmless
    reformatting of the query fails it. It cannot be strengthened here either: the
    mocked cursor returns whatever rows the test hands it, so filtering is
    unobservable by construction in this file.

    Kept because it still catches deletion of the predicate and query reformatting,
    which is worth having -- but it must never stand in for the invariant itself.

    The behavioural proof of A2 lives in
    `tests/integration/test_guest_merge_claim_postgres.py::TestGuestExclusionOnRealPostgres`,
    which executes the real predicate against PostgreSQL with guest rows deliberately
    constructed to be candidates but for the guard.

    Original rationale, still true: both the email and the non-email predicate must
    carry the exclusion. An earlier revision had it on the email branch only, so a
    non-email identifier could still resolve to a guest row -- this exercises both.
    """
    for subject in (ACCOUNT_A, "internal-identifier-0001"):  # email and non-email
        db, conn, cur = _db_with_rows([{"id": "row-a", "external_user_id": subject}])
        db.get_user_bundle(subject, conn=conn)
        sql = cur.execute.call_args[0][0]
        assert "NOT LIKE 'public:" in sql, (
            f"guest rows must be excluded for identifier kind: {subject!r}"
        )


def test_ambiguous_ownership_fails_closed_rather_than_ranking():
    """Two surviving candidates must raise, never silently pick one."""
    db, conn, _ = _db_with_rows(
        [
            {"id": "row-1", "external_user_id": ACCOUNT_A},
            {"id": "row-2", "external_user_id": None},
        ]
    )
    with pytest.raises(IdentityOwnershipAmbiguous) as exc:
        db.get_user_bundle(ACCOUNT_A, conn=conn)
    assert exc.value.candidate_count == 2
    # The error must be safe to log: no identifier, no row content.
    assert ACCOUNT_A not in str(exc.value)

    # Not gated on the identifier kind. external_user_id carries no uniqueness
    # guarantee either, so a non-email identifier resolving to two owner rows is the
    # same ambiguity and must fail the same way rather than silently taking the first.
    db, conn, _ = _db_with_rows(
        [{"id": "row-1", "external_user_id": "u-1"}, {"id": "row-2", "external_user_id": "u-1"}]
    )
    with pytest.raises(IdentityOwnershipAmbiguous):
        db.get_user_bundle("non-email-identifier", conn=conn)


def test_guest_principal_cannot_write_trusted_identity_fields():
    for field in sorted(TRUSTED_IDENTITY_FIELDS):
        assert rejected_trusted_identity_fields(GUEST, {field: "synthetic-value"}) == {field}
    # ...but ordinary profile data from a guest is untouched.
    assert rejected_trusted_identity_fields(GUEST, {"current_role": "Engineer"}) == set()
    # ...and an authenticated principal is unaffected entirely.
    assert rejected_trusted_identity_fields(ACCOUNT_A, {"email": ACCOUNT_B}) == set()


def test_public_principal_detection_is_prefix_based_and_conservative():
    assert is_public_principal(GUEST) is True
    assert is_public_principal(f"{PUBLIC_PRINCIPAL_PREFIX}!!malformed!!") is True, (
        "a malformed guest id must still be treated as a guest by the write guard"
    )
    assert is_public_principal(ACCOUNT_A) is False
    assert is_public_principal(None) is False


# ── 3. guest-artifact tripwire ────────────────────────────────────────────────

def test_tripwire_guest_artifact_guard_not_deleted():
    """TRIPWIRE, not an acceptance test.

    Its only job is to fail loudly if the guard is deleted. It inspects source text,
    so it proves nothing about runtime behaviour and must never be counted as evidence
    for an acceptance criterion. The behavioural proof is
    `test_guest_principal_cannot_write_trusted_identity_fields_through_the_chokepoint`.

    Original rationale for a plausible future feature.

    Today guests do not receive CV upload artifacts, and that is one of the reasons the
    wider concern is not reachable. Granting guests artifacts is a reasonable product
    idea. If it happens, the repository-level write guard must already be in place --
    otherwise a guest principal gains a path to trusted identity columns.

    This test fails if the guard is ever removed, so the feature breaks the test rather
    than production.
    """
    assert rejected_trusted_identity_fields(GUEST, {"email": "x@synthetic.test"}) == {"email"}

    from src.repositories import profile_repo

    src = __import__("inspect").getsource(profile_repo.upsert_profile)
    assert "rejected_trusted_identity_fields" in src, (
        "profile_repo.upsert_profile must enforce the trusted-identity write guard"
    )


# ── 4. legacy-account ─────────────────────────────────────────────────────────

def test_legacy_account_without_external_identifier_still_resolves():
    """Named regression risk: accounts predating the external-identifier convention.

    The contact column stays in the predicate for exactly this case. What changed is
    that it can no longer, on its own, select a row belonging to somebody else.
    """
    db, conn, cur = _db_with_rows([{"id": "legacy-row", "external_user_id": None}])
    assert db.get_user_bundle(ACCOUNT_A, conn=conn)["id"] == "legacy-row"
    sql = cur.execute.call_args[0][0]
    assert "u.email" in sql, "legacy accounts must remain resolvable"


# ── 5. guest-conversion ───────────────────────────────────────────────────────

def test_guest_conversion_still_flows_through_the_explicit_claim_transaction():
    """Conversion must remain available, and only through the authenticated claim path.

    That service is deliberately untouched by this change: it takes its source from the
    signed token rather than the request body, serialises on a guest-scoped lock, and
    enforces single ownership inside one transaction.
    """
    from src.rico_db import RicoDB

    # An authenticated principal writing its own contact details is untouched by the
    # guard -- this is the conversion path's write, and it must still go through.
    db = RicoDB.__new__(RicoDB)
    payload = {"external_user_id": ACCOUNT_A, "email": ACCOUNT_A, "phone": "+000000000"}
    captured = {}

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params): captured["params"] = params
        def fetchone(self): return {"id": "converted-row"}

    class _Conn:
        def cursor(self): return _Cur()
        def commit(self): pass
        def close(self): pass

    db.upsert_user(payload, conn=_Conn())
    assert ACCOUNT_A in captured["params"], (
        "an authenticated principal must still be able to write its own contact details"
    )


def test_guest_cannot_hold_authenticated_onboarding_completion():
    from src.models.onboarding import ONBOARDING_COMPLETED
    from src.repositories import onboarding_repo

    with patch.object(onboarding_repo, "_get_conn") as conn_factory:
        onboarding_repo.set_onboarding_status(GUEST, ONBOARDING_COMPLETED)
        conn_factory.assert_not_called()  # rejected before touching the store

    with pytest.raises(onboarding_repo.OnboardingStateUnavailable):
        onboarding_repo.set_onboarding_status(GUEST, ONBOARDING_COMPLETED, require_db=True)


# ── enforcing guard at the chokepoint ─────────────────────────────────────────

def _capture_upsert_user(payload):
    """Run RicoDB.upsert_user against a fake connection and return the bound params."""
    from src.rico_db import RicoDB

    captured = {}

    class _Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params): captured["params"] = params
        def fetchone(self): return {"id": "row"}

    class _Conn:
        def cursor(self): return _Cur()
        def commit(self): pass
        def close(self): pass

    RicoDB.__new__(RicoDB).upsert_user(payload, conn=_Conn())
    return captured.get("params", ())


def test_guest_principal_cannot_write_trusted_identity_fields_through_the_chokepoint():
    """Behavioural proof at the enforcing boundary, not at one caller.

    Eight of eleven writers reach `rico_users` without passing through
    `profile_repo`, so a guard placed only there would enforce a property the
    codebase does not have. This drives `upsert_user` directly and asserts the
    contact values never reach the bound SQL parameters.
    """
    victim = "someone-else@synthetic.test"
    params = _capture_upsert_user(
        {
            "external_user_id": GUEST,
            "email": victim,
            "phone": "+971500000000",
            "telegram_username": "@victim",
            "telegram_chat_id": "12345",
        }
    )
    for leaked in (victim, "+971500000000", "@victim", "12345"):
        assert leaked not in params, (
            f"a guest principal must not write a trusted identity value: {leaked!r}"
        )
    # The guest principal's own identity is still written -- it is the row's identity,
    # not a claim about anybody else.
    assert GUEST in params


def test_authenticated_principal_writes_its_own_contact_details_unimpeded():
    """The guard must not break ordinary account writes, including conversion."""
    params = _capture_upsert_user({"external_user_id": ACCOUNT_A, "email": ACCOUNT_A})
    assert ACCOUNT_A in params


def test_explicit_guest_resolution_still_returns_the_guest_its_own_row():
    """D19: the exclusion scopes to AUTHENTICATED ownership resolution only.

    A guest resolving its own public row must still get it. An earlier revision applied
    the exclusion unconditionally, which silently broke every guest read.
    """
    db, conn, cur = _db_with_rows([{"id": "guest-row", "external_user_id": GUEST}])
    assert db.get_user_bundle(GUEST, conn=conn)["id"] == "guest-row"
    assert _guest_flag_binding(cur) is True, (
        "a guest caller must disable the guest exclusion for its own row"
    )


def test_authenticated_resolution_keeps_the_guest_exclusion_active():
    db, conn, cur = _db_with_rows([{"id": "row-a", "external_user_id": ACCOUNT_A}])
    db.get_user_bundle(ACCOUNT_A, conn=conn)
    assert _guest_flag_binding(cur) is False, (
        "an authenticated caller must keep the guest exclusion active"
    )


# ── behavioural evidence at the API boundary ──────────────────────────────────
#
# The unit checks above prove the repository refuses. These two prove what the
# caller actually receives, driving the real ASGI app through the real
# `profile_repo.upsert_profile` — the layer where a refusal could still be
# converted into a mirrored success. No database is touched.

@pytest.fixture
def _boundary(monkeypatch):
    """Real route + real profile_repo, with ownership resolution refusing."""
    import contextlib

    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.rate_limit import limiter
    import src.api.routers.rico_chat as rico_chat_router
    from src.repositories import profile_repo

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    def _mock_get_user(request):
        user = {"email": ACCOUNT_A, "role": "user"}
        request.state.current_user = user
        request.state.user_id = ACCOUNT_A
        return user

    monkeypatch.setattr(rico_chat_router, "get_current_user", _mock_get_user)

    db = MagicMock()
    db.available = True
    db.get_user_bundle.side_effect = IdentityOwnershipAmbiguous(2)
    monkeypatch.setattr(profile_repo, "_db", lambda: db)

    conn = MagicMock()

    @contextlib.contextmanager
    def _txn():
        yield conn

    monkeypatch.setattr(profile_repo, "_db_transaction", _txn)

    mirror = MagicMock()
    monkeypatch.setattr(profile_repo, "_memory", lambda: mirror)

    try:
        yield TestClient(app), conn, mirror
    finally:
        limiter.enabled = prev_enabled


def test_ownership_refusal_surfaces_as_409_at_the_api_boundary(_boundary):
    """The refusal must reach the caller as the contract's conflict response.

    A 503 would read as "retry, the database is having a moment", and the client
    would retry a write that must never succeed. A 2xx would be worse.
    """
    client, _conn, _mirror = _boundary
    response = client.patch("/api/v1/rico/profile", json={"current_role": "Engineer"})

    assert response.status_code == 409, (
        f"ownership refusal must surface as 409, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("error") == "ambiguous_account_ownership"
    # Safe to surface: no identifier, no row content.
    assert ACCOUNT_A not in response.text


def test_ownership_refusal_returns_no_mirror_success_and_writes_nothing(_boundary):
    """Same call: no success shape, and no partial write anywhere.

    The status is pinned exactly, not merely asserted to be outside 2xx. "Not 2xx" is
    satisfied by any failure at all -- a 401 from a broken auth patch, a 422 from a
    changed request model -- so a loose assertion here would keep passing while proving
    nothing, and would quietly become the only surviving check if the 409 test above
    were ever deleted on its own.
    """
    client, conn, mirror = _boundary
    response = client.patch("/api/v1/rico/profile", json={"current_role": "Engineer"})

    assert response.status_code == 409, (
        "a refused write must be reported as the ownership conflict, not as any other "
        f"failure: got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("error") == "ambiguous_account_ownership"
    assert "profile" not in body and body.get("ok") is not True, (
        f"refusal must not carry a success payload: {body}"
    )
    mirror.upsert_profile_from_dict.assert_not_called()
    conn.cursor.assert_not_called()


def test_ownership_refusal_is_never_converted_into_a_mirrored_success(_boundary):
    """The default (``require_db=False``) path is where the hazard actually lives.

    That path answers from the JSON mirror when the database write fails, which is
    correct for a transient fault and wrong for an ownership refusal: returning a
    mirror here hands the caller a success-shaped object for a write that must never
    land, and leaves mirror state a later fallback read can serve as though it did.

    Driven through the real ``upsert_profile`` rather than a helper, because the
    conversion happens inside that function's own exception handling.
    """
    from src.repositories import profile_repo

    _client, conn, mirror = _boundary

    with pytest.raises(IdentityOwnershipAmbiguous):
        profile_repo.upsert_profile(ACCOUNT_A, {"current_role": "Engineer"})

    mirror.upsert_profile_from_dict.assert_not_called()
    conn.cursor.assert_not_called()


# ── declaration/enforcement drift ─────────────────────────────────────────────

def test_declared_and_enforced_trusted_identity_sets_cannot_drift():
    """The declaration and what the write boundary actually drops must be equal.

    Two failure directions, both silent without this test:

    * declared but not enforced — a field is added to ``TRUSTED_IDENTITY_FIELDS``
      and reads as protected while no site drops it. That is the worse direction:
      the guarantee is claimed but absent.
    * enforced but not declared — a site drops a field nobody declared, so the
      declaration stops describing the system.

    Measured behaviourally: drive the write chokepoint with a guest principal and
    a value in every column it writes, then compare what survived against the
    declared set. A restated local copy at any enforcement site fails this.
    """
    every_writable_column = {
        "name": "Synthetic Name",
        "email": "someone-else@synthetic.test",
        "phone": "+000000000",
        "telegram_username": "@someone",
        "telegram_chat_id": "9999",
        "source": "synthetic",
    }
    params = _capture_upsert_user({"external_user_id": GUEST, **every_writable_column})

    dropped = {k for k, v in every_writable_column.items() if v not in params}
    assert dropped == set(TRUSTED_IDENTITY_FIELDS), (
        "the set the write boundary drops must equal the declared set exactly; "
        f"declared={sorted(TRUSTED_IDENTITY_FIELDS)} dropped={sorted(dropped)}"
    )


# ── classified false-not-found paths ──────────────────────────────────────────
#
# Three sites where a swallowed refusal reached the caller as absence of data.
# Independent classification labelled the first a user-visible false not-found and
# the other two mutation guards. Each is driven behaviourally; none is satisfied by
# a log line, because a warning does not change what the caller returns.

def test_me_never_answers_200_when_identity_resolution_refuses(monkeypatch):
    """`/me` must not present an ownership refusal as an account with no data.

    The endpoint's own contract is that a store outage stays a retryable error and
    identity is never guessed. A refusal answered as ``200 {"name": null}`` breaks
    that in the most consequential direction: every consumer of `/me` reads it as
    "this account exists and simply has no name", and a client that writes the field
    back then persists that emptiness over the stored value.
    """
    from fastapi.testclient import TestClient

    from src.api import deps
    from src.api.app import app
    from src.api.auth import create_access_token
    from src.api.rate_limit import limiter
    import src.rico_db as rico_db_module

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    class _RefusingDB:
        def __init__(self, *a, **k):
            self.available = True

        def get_user_bundle(self, *a, **k):
            raise IdentityOwnershipAmbiguous(2)

    monkeypatch.setattr(
        deps, "get_current_user", lambda request: {"email": ACCOUNT_A, "role": "user"}
    )
    monkeypatch.setattr("src.db.is_db_available", lambda: True)
    monkeypatch.setattr(rico_db_module, "RicoDB", _RefusingDB)

    try:
        client = TestClient(app)
        client.cookies.set("access_token", create_access_token({"sub": ACCOUNT_A, "role": "user"}))
        response = client.get("/api/v1/me")
    finally:
        limiter.enabled = prev_enabled

    assert response.status_code != 200, (
        f"a refusal must never be answered as a successful identity read: {response.text}"
    )
    assert response.status_code == 409, (
        f"expected the ownership conflict, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("error") == "ambiguous_account_ownership"
    # And specifically not the empty-data success shape.
    assert "name" not in body and body.get("authenticated") is not True


def test_delete_profile_refuses_rather_than_reporting_a_failed_delete(_boundary):
    """Mutation guard: a refusal must not read as "delete failed" or "nothing there".

    Unreachable today — `delete_profile` has no production caller — which is exactly
    why it is cheap to pin now. The moment it gains one, the broad handler's
    ``return False`` would turn a refusal into a silent failed delete, and a caller
    that retries or reports success on ``False`` would act on a row it does not own.
    """
    from src.repositories import profile_repo

    _client, conn, mirror = _boundary

    with pytest.raises(IdentityOwnershipAmbiguous):
        profile_repo.delete_profile(ACCOUNT_A)

    conn.cursor.assert_not_called()  # no DELETE issued
    mirror.delete_profile.assert_not_called()


# ── quota gating: fail closed, and reach the client as one explicit contract ───
#
# The quota path is the one place where a refusal answered as absence is worse than
# an outage: falling back to the in-process counter under-counts, so an ambiguous
# account is granted messages it has not paid for. Fail-open on quota and cost.

def _refusing_db():
    class _DB:
        available = True

        def get_user_bundle(self, *a, **k):
            raise IdentityOwnershipAmbiguous(2)

    return _DB()


def test_quota_never_falls_back_to_the_in_process_counter_on_a_refusal(monkeypatch):
    """Four negatives in one call: no memory fallback, no count, no send, no write."""
    from src.rico_memory import RicoMemoryStore
    from src.services import subscription_gating

    memory_reads: list[str] = []
    monkeypatch.setattr(
        RicoMemoryStore,
        "load_chat_history",
        lambda self, uid, *a, **k: memory_reads.append(uid) or [],
    )
    monkeypatch.setattr(subscription_gating, "RicoDB", _refusing_db, raising=False)
    monkeypatch.setattr("src.rico_db.RicoDB", lambda *a, **k: _refusing_db())

    with pytest.raises(IdentityOwnershipAmbiguous):
        subscription_gating.count_monthly_ai_messages(ACCOUNT_A, _WINDOW_START)

    assert memory_reads == [], (
        "the in-process counter must not be consulted for an ambiguous account: "
        "it under-counts, which grants messages the account has not paid for"
    )


def test_quota_refusal_does_not_allow_the_request_or_restate_the_plan(monkeypatch):
    """No send enablement, and no plan claim that could read as a downgrade."""
    from src.services import subscription_gating

    monkeypatch.setattr("src.rico_db.RicoDB", lambda *a, **k: _refusing_db())

    with pytest.raises(IdentityOwnershipAmbiguous):
        subscription_gating.check_ai_message_allowed_for_user(ACCOUNT_A)

    # The refusal contract carries no usage, no limit, no remaining, no plan —
    # nothing a client could render as consumption or as a tier.
    payload = subscription_gating.account_conflict_response()
    for forbidden in ("usage", "limit", "remaining", "plan", "reset_at"):
        assert forbidden not in payload, (
            f"the conflict contract must not carry {forbidden!r}: a refusal knows "
            "neither the consumption nor the tier"
        )
    assert payload["type"] == "account_conflict"
    assert payload["error"] == "ambiguous_account_ownership"


def test_quota_refusal_reaches_the_client_as_the_explicit_conflict_contract(monkeypatch):
    """It must not land in the generic chat handler.

    Both top-level chat handlers answer 200 with "I couldn't process your request",
    which is indistinguishable from a transient fault. The preflight resolves the
    refusal into the typed contract itself, so the generic handler is never reached.
    """
    from src.schemas.chat import RicoSessionContext
    from src.services import chat_service

    def _refuse(_ctx):
        raise IdentityOwnershipAmbiguous(2)

    monkeypatch.setattr(chat_service, "check_ai_message_allowed", _refuse, raising=False)
    monkeypatch.setattr(
        "src.services.subscription_gating.check_ai_message_allowed", _refuse
    )

    ctx = RicoSessionContext(user_id=ACCOUNT_A, auth_type="authenticated")
    pre = chat_service.run_chat_preflight(ctx, "how many messages do I have left?")

    assert pre.terminal is not None, "the refusal must resolve to a terminal response"
    assert pre.terminal["type"] == "account_conflict", (
        f"expected the explicit conflict contract, got {pre.terminal.get('type')!r}"
    )
    assert pre.terminal["error"] == "ambiguous_account_ownership"
    assert pre.gate is None, "no gate decision may be carried forward from a refusal"
    # No usage figure may reach the client.
    for forbidden in ("usage", "limit", "remaining"):
        assert forbidden not in pre.terminal


def test_provisioning_never_creates_a_row_for_an_ambiguous_identity(monkeypatch):
    """`_provision_db_user_id` auto-creates a user row when resolution returns nothing.

    A refusal must never reach that call: creating a row for an identity that already
    resolves ambiguously adds another candidate and deepens the ambiguity.
    """
    from src.repositories import applications_repo

    upserts: list[dict] = []

    class _DB:
        available = True

        def get_user_bundle(self, *a, **k):
            raise IdentityOwnershipAmbiguous(2)

        def upsert_user(self, payload, *a, **k):
            upserts.append(payload)
            return {"id": "should-never-be-created"}

    with pytest.raises(IdentityOwnershipAmbiguous):
        applications_repo._provision_db_user_id(_DB(), ACCOUNT_A)

    assert upserts == [], "a refused identity must never be auto-provisioned"


def test_quota_refusal_writes_no_usage_and_never_enables_the_send(monkeypatch):
    """The fourth negative, proven at the send boundary rather than inferred.

    Usage is counted from persisted chat rows, so "no usage write" means no turn is
    appended. Driving `send_message` proves the refusal is terminal: the contract is
    returned, the provider is never reached, and nothing is recorded that a later
    count would bill for.
    """
    from src.schemas.chat import RicoSessionContext
    from src.services import chat_service

    appended: list[tuple] = []
    monkeypatch.setattr(
        chat_service, "db_append_chat", lambda *a, **k: appended.append(a), raising=False
    )

    def _refuse(_ctx):
        raise IdentityOwnershipAmbiguous(2)

    monkeypatch.setattr("src.services.subscription_gating.check_ai_message_allowed", _refuse)

    ctx = RicoSessionContext(user_id=ACCOUNT_A, auth_type="authenticated")
    result = chat_service.send_message(ctx, "how many messages do I have left?")

    assert result["type"] == "account_conflict", "the send must terminate on the contract"
    assert appended == [], "a refused turn must not be recorded as consumption"
    # No send enablement: nothing that reads as an allowance decision came back.
    for forbidden in ("usage", "limit", "remaining", "plan"):
        assert forbidden not in result


# ── HTTP mapping on the remaining read/upload surfaces ────────────────────────
#
# The refusal already reaches the client as 409 on `/me` and the profile writes.
# These two surfaces did not: each wraps its work in a broad handler that
# predates the typed exception, so an ownership refusal was re-labelled as
# something the client is invited to retry. Both mappings are pinned here
# because the wrong answer is indistinguishable from a healthy outcome:
# `/onboarding/status` said "the store is down, try again", and `upload-cv`
# said "the upload failed" after the file had in fact been read perfectly.

def test_onboarding_status_answers_the_conflict_and_never_a_transient_503(monkeypatch):
    """A refusal on this route must not be dressed as a store outage.

    `/onboarding/status` is the endpoint the frontend routes the whole logged-in
    experience on. Its broad handler maps every failure to 503 with "please try
    again" — correct for a database that is briefly unreachable, and wrong here:
    retrying resolves nothing, and the setup screen tells the user the product is
    merely having a moment when the account actually needs support.
    """
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.rate_limit import limiter
    import src.api.routers.onboarding as onboarding_router
    from src.repositories import onboarding_repo, profile_repo

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    monkeypatch.setattr(
        onboarding_router, "get_current_user", lambda request: {"email": ACCOUNT_A, "role": "user"}
    )
    # The persisted-status read succeeds. The refusal therefore comes from profile
    # resolution alone, so nothing else in this route can account for a 503.
    monkeypatch.setattr(onboarding_repo, "get_onboarding_state_readonly", lambda user_id: None)

    db = MagicMock()
    db.available = True
    db.get_user_bundle.side_effect = IdentityOwnershipAmbiguous(2)
    monkeypatch.setattr(profile_repo, "_db", lambda: db)

    try:
        response = TestClient(app).get("/api/v1/onboarding/status")
    finally:
        limiter.enabled = prev_enabled

    assert response.status_code != 503, (
        "an ownership refusal must never be reported as a transient store failure: "
        f"{response.text}"
    )
    assert response.status_code == 409, (
        f"expected the ownership conflict, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("error") == "ambiguous_account_ownership"
    # Not a readiness answer: a derived "pending" would push the user back through
    # onboarding, and a derived "completed" would let the app proceed on a row
    # nobody could attribute.
    assert "status" not in body and "complete" not in body, (
        f"a refusal must not carry an onboarding-readiness verdict: {body}"
    )
    assert "try again" not in response.text.lower(), (
        f"a refusal must not invite a retry: {response.text}"
    )
    assert ACCOUNT_A not in response.text


def test_upload_cv_refusal_after_a_successful_parse_is_the_conflict_not_a_500(monkeypatch):
    """Parsing succeeded; only ownership resolution refused.

    The distinction matters because the route's broad handler answers 500 "CV upload
    failed", which blames the file. The user re-exports the CV, re-uploads it, and
    every attempt fails identically — while the durable upload artifact must never be
    written for an account that cannot be attributed.
    """
    import io

    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.rate_limit import limiter
    import src.api.routers.rico_chat as rico_chat_router
    import src.services.chat_service as chat_service
    import src.services.subscription_gating as subscription_gating
    from src.repositories import cv_upload_artifact_repo, profile_repo

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    monkeypatch.setattr(rico_chat_router, "get_current_user_id", lambda request: ACCOUNT_A)

    parsed_filenames: list[str] = []

    def _fake_parse(data, filename="cv.pdf"):
        parsed_filenames.append(filename)
        # Readable text: the #1118 parse-quality gate must pass, so the request
        # reaches ownership resolution instead of returning a parse verdict.
        return {
            "document_type": "resume",
            "text": (
                "Jane Roe — Software Engineer with Python, FastAPI and cloud "
                "experience. Skills: python, testing, CI. Based in Dubai, UAE."
            ),
            "extraction_quality": "high",
            "extracted_chars": 100,
            "skills": ["python"],
        }

    monkeypatch.setattr(chat_service, "parse_cv", _fake_parse)

    quota_gate = MagicMock(return_value=None)
    monkeypatch.setattr(subscription_gating, "enforce_document_quota", quota_gate)

    artifact_write = MagicMock()
    monkeypatch.setattr(cv_upload_artifact_repo, "create_cv_upload_artifact", artifact_write)
    profile_write = MagicMock()
    monkeypatch.setattr(rico_chat_router, "upsert_profile", profile_write)

    db = MagicMock()
    db.available = True
    db.get_user_bundle.side_effect = IdentityOwnershipAmbiguous(2)
    monkeypatch.setattr(profile_repo, "_db", lambda: db)

    try:
        response = TestClient(app).post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake cv"), "application/pdf")},
        )
    finally:
        limiter.enabled = prev_enabled

    assert parsed_filenames == ["cv.pdf"], (
        "the parse must have run and succeeded — otherwise this test would pass on a "
        "refusal raised before parsing and prove nothing about the post-parse path"
    )
    assert response.status_code == 409, (
        f"expected the ownership conflict, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("error") == "ambiguous_account_ownership"

    # Nothing durable for an account that could not be attributed.
    artifact_write.assert_not_called()
    profile_write.assert_not_called()

    # Not a parse verdict, and no invitation to spend another upload on it. A
    # consumed allowance would compound the refusal with a real cost.
    assert body.get("status") not in ("parse_failed", "error"), (
        f"an ownership refusal must not be reported as a parsing outcome: {body}"
    )
    assert body.get("ok") is not True
    lowered = response.text.lower()
    for forbidden in ("try again", "re-upload", "reupload", "upload again", "could not read"):
        assert forbidden not in lowered, (
            f"a refusal must not instruct the user to retry the upload: {response.text}"
        )
    assert ACCOUNT_A not in response.text


def test_onboarding_status_still_reports_a_genuine_store_outage_as_503(monkeypatch):
    """The narrowing must not swallow the case the broad handler exists for.

    A real store failure is retryable and must keep its 503 — otherwise this change
    would trade one wrong answer for another, and the frontend's Retry path would
    lose the only signal that justifies it.
    """
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.rate_limit import limiter
    import src.api.routers.onboarding as onboarding_router
    from src.repositories import onboarding_repo

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    def _store_down(user_id):
        raise RuntimeError("onboarding state store unreachable")

    monkeypatch.setattr(
        onboarding_router, "get_current_user", lambda request: {"email": ACCOUNT_A, "role": "user"}
    )
    monkeypatch.setattr(onboarding_repo, "get_onboarding_state_readonly", _store_down)

    try:
        response = TestClient(app).get("/api/v1/onboarding/status")
    finally:
        limiter.enabled = prev_enabled

    assert response.status_code == 503, (
        f"a genuine outage must stay retryable, got {response.status_code}: {response.text}"
    )


def test_upload_cv_still_reports_an_unrelated_failure_as_the_generic_upload_error(monkeypatch):
    """Same narrowing check on the upload route: only the typed refusal is re-raised."""
    import io

    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.rate_limit import limiter
    import src.api.routers.rico_chat as rico_chat_router
    import src.services.chat_service as chat_service
    import src.services.subscription_gating as subscription_gating

    limiter.reset()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    def _fake_parse(data, filename="cv.pdf"):
        return {
            "document_type": "resume",
            "text": (
                "Jane Roe — Software Engineer with Python, FastAPI and cloud "
                "experience. Skills: python, testing, CI. Based in Dubai, UAE."
            ),
            "extraction_quality": "high",
            "extracted_chars": 100,
            "skills": ["python"],
        }

    def _store_down(user_id):
        raise RuntimeError("profile store unreachable")

    monkeypatch.setattr(rico_chat_router, "get_current_user_id", lambda request: ACCOUNT_A)
    monkeypatch.setattr(chat_service, "parse_cv", _fake_parse)
    monkeypatch.setattr(subscription_gating, "enforce_document_quota", MagicMock(return_value=None))
    monkeypatch.setattr(rico_chat_router, "get_profile", _store_down)

    try:
        response = TestClient(app).post(
            "/api/v1/rico/upload-cv",
            files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 fake cv"), "application/pdf")},
        )
    finally:
        limiter.enabled = prev_enabled

    assert response.status_code == 500, (
        "an unrelated failure must keep the route's existing generic mapping, got "
        f"{response.status_code}: {response.text}"
    )
    assert "ambiguous_account_ownership" not in response.text
