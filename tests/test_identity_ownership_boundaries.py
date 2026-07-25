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
    """The exclusion is a property of authenticated resolution, not of one branch.

    Both the email and the non-email predicate must carry it. An earlier revision had
    it on the email branch only, so a non-email identifier could still resolve to a
    guest row -- this exercises both.
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
    """Same call: no success shape, and no partial write anywhere."""
    client, conn, mirror = _boundary
    response = client.patch("/api/v1/rico/profile", json={"current_role": "Engineer"})

    assert not (200 <= response.status_code < 300), "a refused write must not report success"
    body = response.json()
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
