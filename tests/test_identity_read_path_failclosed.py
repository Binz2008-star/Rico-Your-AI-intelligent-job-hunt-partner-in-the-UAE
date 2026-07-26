"""The chat read path must refuse an ambiguous owner, not rank one.

#1404 closed the identity WRITE path: a wrong email can no longer be stamped
onto a row that does not own it. A read path was still open.
``chat_service._resolve_db_user_id`` resolved a web session to a `rico_users`
row by ordering candidates and taking `LIMIT 1`. While a collision cluster
exists, that hands the session a row whose user may not own it — and every
subsequent chat write then lands on that row. Ranking is how new damage enters
after the write path was sealed.

Two sites in that function ranked instead of refusing:

1. the primary lookup (`external_user_id` / `email` / `id` predicate), which
   ordered by match-kind then `updated_at DESC` and took one row;
2. the post-conflict email fallback, which ordered by `updated_at DESC` alone —
   an arbitrary pick between equally-strong candidates.

Both must raise the EXISTING typed exception, `IdentityOwnershipAmbiguous`, so
the EXISTING app-level handler answers `409 ambiguous_account_ownership`. No new
exception type, no new response shape, no new error code.

The refusal must also survive the function's own error handling. Two broad
`except Exception` handlers sat between the raise and the caller, and each
converted any exception into `None` — which callers read as "store unavailable"
and degrade on. A refusal that returns `None` is not a refusal; it is a silent
downgrade, and the 409 contract never fires. That is the same reason
`api/routers/user.py` and `api/routers/rico_chat.py` re-raise this type ahead of
their own broad handlers.

Pinned alongside is what must NOT change: a single unambiguous candidate still
resolves, #445's match-kind ordering survives, a public/guest principal is still
never auto-provisioned (#1398), and a genuine store outage still degrades to
`None` — so an outage stays distinguishable from a refusal and cannot be served
as a 409.

All fixtures are synthetic. No database, no network.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models.principal import PUBLIC_PRINCIPAL_PREFIX, IdentityOwnershipAmbiguous

# Synthetic identifiers. `.test` is reserved by RFC 2606 and can never resolve.
WEB_PRINCIPAL = "web-principal@synthetic.test"
GUEST_PRINCIPAL = f"{PUBLIC_PRINCIPAL_PREFIX}g-SYNTHETIC0000000000"

ROW_OWNED = {"id": "00000000-0000-4000-8000-00000000000a"}
ROW_FOREIGN = {"id": "00000000-0000-4000-8000-00000000000b"}


# ── harness ───────────────────────────────────────────────────────────────────
#
# The fake cursor answers BOTH `fetchone()` and `fetchmany(n)` from the same
# scripted rows, so one harness drives the code before and after the fix. If it
# only implemented the post-fix call, the pre-fix run would fail on a missing
# attribute rather than on the behaviour under test, and an AttributeError is
# not evidence that the read path ranks.


class _Cursor:
    def __init__(self, script: dict, log: list) -> None:
        self._script = script
        self._log = log
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._log.append((" ".join(sql.split()), tuple(params or ())))
        if "INSERT INTO rico_users" in sql:
            self._rows = list(self._script.get("insert", []))
        elif "WHERE email = %s" in " ".join(sql.split()):
            self._rows = list(self._script.get("email_lookup", []))
        else:
            self._rows = list(self._script.get("primary", []))
        if isinstance(self._rows, BaseException):  # pragma: no cover - guard
            raise self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchmany(self, size=1):
        return self._rows[:size]


class _Conn:
    def __init__(self, script: dict, log: list) -> None:
        self._script = script
        self._log = log
        self.closed = False

    def cursor(self):
        return _Cursor(self._script, self._log)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def _resolve(script: dict, user_id: str = WEB_PRINCIPAL, connect_error=None):
    """Drive the real `_resolve_db_user_id` against a scripted store.

    Returns `(result, executed_sql_log)`; raises whatever the function raises.
    """
    from src.services import chat_service

    log: list = []
    db = MagicMock()
    db.available = True
    if connect_error is not None:
        db.connect.side_effect = connect_error
    else:
        db.connect.side_effect = lambda: _Conn(script, log)

    with patch("src.rico_db.RicoDB", return_value=db):
        result = chat_service._resolve_db_user_id(user_id)
    return result, log


# ── 1. the refusal ────────────────────────────────────────────────────────────


def test_two_candidate_rows_refuse_instead_of_returning_one():
    """The defect itself: a collision cluster resolved to a ranked winner.

    Returning either row attaches the session to an account it may not own, and
    every write that follows lands there.
    """
    with pytest.raises(IdentityOwnershipAmbiguous):
        _resolve({"primary": [ROW_OWNED, ROW_FOREIGN]})


def test_the_refusal_carries_the_candidate_count_the_handler_reports():
    """The app-level handler logs `candidate_count`; it must be populated."""
    with pytest.raises(IdentityOwnershipAmbiguous) as excinfo:
        _resolve({"primary": [ROW_OWNED, ROW_FOREIGN]})
    assert excinfo.value.candidate_count >= 2


def test_the_post_conflict_email_fallback_also_refuses():
    """The second ranking site: `ORDER BY updated_at DESC LIMIT 1` on email.

    Reached when the primary lookup finds nothing and the provisioning INSERT
    hits a conflict. It ordered by recency alone — an arbitrary pick between
    two equally-strong email matches, with no match-kind preference to justify
    it.
    """
    with pytest.raises(IdentityOwnershipAmbiguous):
        _resolve(
            {
                "primary": [],
                "insert": [],  # ON CONFLICT DO NOTHING -> no row returned
                "email_lookup": [ROW_OWNED, ROW_FOREIGN],
            }
        )


def test_the_refusal_is_not_swallowed_into_a_none_result():
    """Explicit: the function's own broad handlers must not absorb the refusal.

    `None` is this function's "store unavailable" signal, so converting the
    refusal into `None` would degrade an ownership conflict into a retryable
    outage and the 409 contract would never fire. Asserting the raise reaches
    the caller is a different property from asserting the raise happens.
    """
    for script in (
        {"primary": [ROW_OWNED, ROW_FOREIGN]},
        {"primary": [], "insert": [], "email_lookup": [ROW_OWNED, ROW_FOREIGN]},
    ):
        with pytest.raises(IdentityOwnershipAmbiguous):
            _resolve(script)


def test_an_ambiguous_account_never_gets_a_chat_row_written_against_it():
    """The consequence the refusal exists to prevent.

    Refusing to RETURN a row matters only if it also stops the WRITE. This drives
    the real `db_append_chat` and asserts `append_chat` is never reached: before
    the fix the ranked winner was handed straight to it, so a chat turn was
    persisted against a row the session may not own.

    Note what this also documents: `db_append_chat` catches broadly, so the
    refusal degrades to a silent no-op here rather than a 409. The write no
    longer lands on a foreign row — which is the damage route — but the caller is
    not told. Surfacing it would have to happen in `rico_chat_api._append_chat`,
    which is outside this change's file scope and swallows the exception too.
    """
    from src.services import chat_service

    log: list = []
    script = {"primary": [ROW_OWNED, ROW_FOREIGN]}
    db = MagicMock()
    db.available = True
    db.connect.side_effect = lambda: _Conn(script, log)

    with patch("src.rico_db.RicoDB", return_value=db):
        chat_service.db_append_chat(WEB_PRINCIPAL, "user", "synthetic message")

    db.append_chat.assert_not_called()


# ── 2. preserved: the unambiguous case still resolves ─────────────────────────


def test_a_single_candidate_still_resolves_exactly_as_before():
    result, _ = _resolve({"primary": [ROW_OWNED]})
    assert result == ROW_OWNED["id"]


def test_a_single_email_fallback_candidate_still_resolves():
    result, _ = _resolve(
        {"primary": [], "insert": [], "email_lookup": [ROW_OWNED]}
    )
    assert result == ROW_OWNED["id"]


def test_provisioning_a_brand_new_web_user_still_works():
    """No existing row, no conflict: the INSERT provisions and returns."""
    result, log = _resolve({"primary": [], "insert": [ROW_OWNED]})
    assert result == ROW_OWNED["id"]
    assert any("INSERT INTO rico_users" in sql for sql, _ in log)


def test_445_match_kind_ordering_is_still_emitted():
    """TRIPWIRE, not behavioural proof.

    The mocked cursor returns whatever the script hands it, so ORDER BY cannot
    change the outcome here — this asserts only that the ranking clauses are
    still PRESENT in the emitted SQL. It catches deletion of the preference,
    which is the thing the fix must not do: the match-kind ranking is what keeps
    a web user off a Jotform/Telegram row keyed on their own email address. It
    proves nothing about which row wins.
    """
    _resolve({"primary": [ROW_OWNED]})
    _, log = _resolve({"primary": [ROW_OWNED]})
    primary_sql = log[0][0]
    assert "CASE WHEN id::text = %s THEN 0 ELSE 1 END" in primary_sql
    assert "CASE WHEN email = %s THEN 0 ELSE 1 END" in primary_sql
    assert "CASE WHEN external_user_id = %s THEN 0 ELSE 1 END" in primary_sql


# ── 3. preserved: #1398 guest/public exclusion ────────────────────────────────


def test_a_public_principal_is_never_auto_provisioned():
    """#1398: a guest principal must not gain an authenticated account row."""
    result, log = _resolve({"primary": [], "insert": [ROW_OWNED]}, user_id=GUEST_PRINCIPAL)
    assert result is None
    assert not any("INSERT INTO rico_users" in sql for sql, _ in log), (
        "a public principal must never be provisioned an account row"
    )


def test_a_non_email_principal_is_never_auto_provisioned():
    """Unchanged: provisioning is for verified web (email) principals only."""
    result, log = _resolve({"primary": [], "insert": [ROW_OWNED]}, user_id="synthetic-handle")
    assert result is None
    assert not any("INSERT INTO rico_users" in sql for sql, _ in log)


# ── 4. preserved: an outage is not a refusal ──────────────────────────────────


def test_a_store_outage_still_degrades_to_none_and_does_not_raise():
    """The two failure classes must stay distinguishable.

    A refusal raises and the app answers 409 — do not retry, the account is
    ambiguous. An outage returns `None`, which callers degrade on and routers
    surface as a retryable failure. If an outage could raise this type, a
    transient database fault would be reported to the user as a permanent
    account conflict.
    """
    result, _ = _resolve({"primary": [ROW_OWNED]}, connect_error=RuntimeError("store down"))
    assert result is None


def test_an_outage_mid_query_is_not_reported_as_an_ownership_conflict():
    class _ExplodingCursor(_Cursor):
        def execute(self, sql, params=None):
            raise RuntimeError("connection reset")

    from src.services import chat_service

    conn = MagicMock()
    conn.cursor.return_value = _ExplodingCursor({}, [])
    db = MagicMock()
    db.available = True
    db.connect.return_value = conn

    with patch("src.rico_db.RicoDB", return_value=db):
        assert chat_service._resolve_db_user_id(WEB_PRINCIPAL) is None


def test_an_unavailable_store_still_returns_none_before_any_query():
    from src.services import chat_service

    db = MagicMock()
    db.available = False
    with patch("src.rico_db.RicoDB", return_value=db):
        assert chat_service._resolve_db_user_id(WEB_PRINCIPAL) is None
    db.connect.assert_not_called()


# ── 5. the contract this refusal is required to reach ─────────────────────────
#
# These assert the EXISTING contract is intact and is what the refusal lands on.
# They must not be read as evidence for the fix — they pass before it.


def test_the_existing_409_contract_is_registered_for_this_exception():
    from src.api.app import app

    assert IdentityOwnershipAmbiguous in app.exception_handlers, (
        "the refusal must land on the existing handler, not a new one"
    )


def test_the_existing_handler_answers_409_with_the_stable_reason_code():
    import json

    from src.api.app import identity_ownership_ambiguous_handler

    response = identity_ownership_ambiguous_handler(
        MagicMock(), IdentityOwnershipAmbiguous(2)
    )
    assert response.status_code == 409
    body = json.loads(bytes(response.body))
    assert body["error"] == "ambiguous_account_ownership"
    assert body["ok"] is False
    # No identifier, no row content, no address may appear in the response.
    assert WEB_PRINCIPAL not in json.dumps(body)


def test_the_canonical_resolver_already_refuses_the_same_shape():
    """Evidence that this fix ALIGNS the chat path rather than inventing a rule.

    `RicoDB.get_user_bundle` (#1398) already raises on two candidate rows for
    the same identifier. The chat read path was the outlier, resolving a shape
    the canonical resolver refuses — which is why the same account could be
    served by chat and refused by profile.
    """
    from src.rico_db import RicoDB

    cur = MagicMock()
    cur.fetchmany.return_value = [ROW_OWNED, ROW_FOREIGN]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    with pytest.raises(IdentityOwnershipAmbiguous):
        RicoDB.__new__(RicoDB).get_user_bundle(WEB_PRINCIPAL, conn=conn)
