"""Containment for the generic identity writer: a stored email is never replaced.

Production `rico_users` rows were found holding an email that does not belong to
their `external_user_id`. The historical writer that produced them
(`ON CONFLICT DO UPDATE SET email = EXCLUDED.email`) was replaced, but the
generic writer that succeeded it still overwrote a stored non-NULL email with
whatever non-NULL email happened to arrive, so the same corruption remained
reachable from every caller.

Three boundaries are pinned here:

1. `RicoDB.upsert_user`  — the generic writer every caller reaches `rico_users`
   through. Its ON CONFLICT branch must never replace a non-NULL stored email,
   and may fill a NULL one only on *proven ownership*: exact byte equality
   between the incoming email and the row's own `external_user_id`. No
   `LOWER()`, no trimming, no normalisation — a near-match is not proof.
2. `handle_jotform_submission` — a merge into a matched account must not carry
   the form's email into the identity payload.
3. `profile_repo.upsert_profile` — a non-email principal must not turn a
   request-derived email into account identity.

Behaviour that must NOT change is pinned alongside: inserting a new row still
sets its email, ordinary web registration is untouched, and the public/guest
trusted-field guard still drops every contact column.

The `upsert_user` cases execute the REAL statement emitted by production code
against an in-memory SQLite database rather than asserting on SQL text. A
mocked cursor cannot distinguish a guard that is present from one that works —
the outcome depends on the row already stored, which only an engine that
actually evaluates the ON CONFLICT branch can produce.

All fixtures are synthetic. No database server, no network.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# Synthetic principals. `.test` is reserved by RFC 2606 and can never resolve.
OWNER_EMAIL = "owner@synthetic.test"
UNRELATED_EMAIL = "unrelated@synthetic.test"
TELEGRAM_PRINCIPAL = "synthetic_telegram_handle"
PHONE_PRINCIPAL = "+9715000000000"


# ── SQLite harness: run the production statement, not a copy of it ────────────

pytestmark = pytest.mark.skipif(
    sqlite3.sqlite_version_info < (3, 35, 0),
    reason="needs SQLite >= 3.35 for RETURNING in the production statement",
)

_SCHEMA = """
CREATE TABLE rico_users (
    id INTEGER PRIMARY KEY,
    external_user_id TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    phone TEXT,
    telegram_username TEXT,
    telegram_chat_id TEXT,
    telegram_notifications_enabled INTEGER,
    source TEXT,
    updated_at TEXT
)
"""


def _to_sqlite(sql: str) -> str:
    """Dialect-only rewrite. The clause under test is left exactly as written."""
    return sql.replace("%s", "?").replace("now()", "CURRENT_TIMESTAMP")


class _SqliteCursor:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._cur = conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._cur.close()
        return False

    def execute(self, sql, params=None):
        self._cur.execute(_to_sqlite(sql), tuple(params or ()))

    def fetchone(self):
        return self._cur.fetchone()


class _SqliteConn:
    """Just enough of a psycopg2 connection for `upsert_user(conn=...)`."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def cursor(self):
        return _SqliteCursor(self._conn)

    def commit(self):
        self._conn.commit()

    def close(self):  # pragma: no cover - upsert_user must not close a passed conn
        raise AssertionError("upsert_user must not close a caller-owned connection")


@contextmanager
def _users_table(seed: dict | None = None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_SCHEMA)
        if seed:
            cols = ", ".join(seed)
            marks = ", ".join("?" for _ in seed)
            conn.execute(
                f"INSERT INTO rico_users ({cols}) VALUES ({marks})", tuple(seed.values())
            )
        conn.commit()
        yield conn
    finally:
        conn.close()


def _stored_email(conn: sqlite3.Connection, external_user_id: str):
    row = conn.execute(
        "SELECT email FROM rico_users WHERE external_user_id = ?", (external_user_id,)
    ).fetchone()
    return None if row is None else row["email"]


def _upsert(conn: sqlite3.Connection, payload: dict) -> dict:
    from src.rico_db import RicoDB

    return RicoDB.__new__(RicoDB).upsert_user(payload, conn=_SqliteConn(conn))


# ── 1. a stored email is never replaced through the generic path ──────────────


def test_stored_email_is_not_replaced_by_an_unrelated_incoming_email():
    """The corruption itself: a second writer supplying a different email.

    This is how the production cluster was created — a non-NULL stored email was
    silently swapped for whichever email the newest payload carried.
    """
    with _users_table(
        {"external_user_id": TELEGRAM_PRINCIPAL, "email": OWNER_EMAIL}
    ) as conn:
        _upsert(
            conn,
            {"external_user_id": TELEGRAM_PRINCIPAL, "email": UNRELATED_EMAIL},
        )
        assert _stored_email(conn, TELEGRAM_PRINCIPAL) == OWNER_EMAIL, (
            "a generic upsert must never replace a stored email"
        )


def test_stored_email_is_not_replaced_even_when_the_row_is_keyed_by_that_email():
    """An account row is no more overwritable than a Telegram-keyed one."""
    with _users_table({"external_user_id": OWNER_EMAIL, "email": OWNER_EMAIL}) as conn:
        _upsert(conn, {"external_user_id": OWNER_EMAIL, "email": UNRELATED_EMAIL})
        assert _stored_email(conn, OWNER_EMAIL) == OWNER_EMAIL


def test_non_identity_fields_still_update_while_the_email_is_held():
    """The guard is scoped to email; it must not freeze the rest of the row."""
    with _users_table(
        {"external_user_id": TELEGRAM_PRINCIPAL, "email": OWNER_EMAIL, "name": "Old"}
    ) as conn:
        row = _upsert(
            conn,
            {
                "external_user_id": TELEGRAM_PRINCIPAL,
                "email": UNRELATED_EMAIL,
                "name": "New",
            },
        )
        assert row["name"] == "New"
        assert _stored_email(conn, TELEGRAM_PRINCIPAL) == OWNER_EMAIL


# ── 2. a NULL email is filled only on proven ownership ────────────────────────


def test_null_email_is_filled_when_it_equals_the_rows_own_principal():
    """Proven ownership: the incoming email IS the row's external_user_id.

    This is how a legitimately email-keyed row that predates the email column
    being populated gets backfilled, and it must keep working.
    """
    with _users_table({"external_user_id": OWNER_EMAIL, "email": None}) as conn:
        _upsert(conn, {"external_user_id": OWNER_EMAIL, "email": OWNER_EMAIL})
        assert _stored_email(conn, OWNER_EMAIL) == OWNER_EMAIL


def test_null_email_is_not_filled_from_an_unproven_incoming_email():
    """A NULL email is an empty slot, not an open one."""
    with _users_table({"external_user_id": TELEGRAM_PRINCIPAL, "email": None}) as conn:
        _upsert(conn, {"external_user_id": TELEGRAM_PRINCIPAL, "email": UNRELATED_EMAIL})
        assert _stored_email(conn, TELEGRAM_PRINCIPAL) is None, (
            "an email unrelated to the row's principal is not proof of ownership"
        )


def test_ownership_proof_is_exact_bytes_and_not_case_insensitive():
    """No LOWER(), no normalisation: a near-match is not proof.

    Two addresses differing only by case are the same mailbox at most providers
    but not by specification, and the row's principal is the exact string other
    identity lookups were keyed on. Treating them as equal here would re-open
    the overwrite through a normalisation rule this layer cannot verify.
    """
    with _users_table({"external_user_id": "Owner@synthetic.test", "email": None}) as conn:
        _upsert(conn, {"external_user_id": "Owner@synthetic.test", "email": OWNER_EMAIL})
        assert _stored_email(conn, "Owner@synthetic.test") is None


# ── 3. preserved: creating rows and #445 identity ordering ────────────────────


def test_inserting_a_new_row_still_sets_its_email():
    """Account creation is untouched — the guard is on the conflict branch only."""
    with _users_table() as conn:
        row = _upsert(conn, {"external_user_id": OWNER_EMAIL, "email": OWNER_EMAIL})
        assert row["email"] == OWNER_EMAIL
        assert _stored_email(conn, OWNER_EMAIL) == OWNER_EMAIL


def test_identity_ordering_still_derives_the_principal_from_the_email():
    """#445: external_user_id falls back to email before telegram_username."""
    with _users_table() as conn:
        row = _upsert(
            conn, {"email": OWNER_EMAIL, "telegram_username": TELEGRAM_PRINCIPAL}
        )
        assert row["external_user_id"] == OWNER_EMAIL
        assert row["email"] == OWNER_EMAIL


def test_public_principal_still_loses_every_trusted_identity_field():
    """#1398 must survive: a guest row writes no contact column at all."""
    from src.models.principal import PUBLIC_PRINCIPAL_PREFIX

    guest = f"{PUBLIC_PRINCIPAL_PREFIX}g-SYNTHETIC0000000000"
    with _users_table() as conn:
        row = _upsert(
            conn,
            {
                "external_user_id": guest,
                "email": OWNER_EMAIL,
                "phone": PHONE_PRINCIPAL,
                "telegram_username": TELEGRAM_PRINCIPAL,
                "telegram_chat_id": "1000000",
            },
        )
        assert row["external_user_id"] == guest
        for column in ("email", "phone", "telegram_username", "telegram_chat_id"):
            assert row[column] is None, f"a guest row must not carry {column}"


# ── 4. Jotform merge must not stamp the form email onto the matched account ───


def _jotform_db() -> MagicMock:
    db = MagicMock()
    db.upsert_user.return_value = {"id": "db-uuid-synthetic"}
    db.register_webhook_event.return_value = True
    return db


def _resolution(matched_user_id: str):
    from src.services.identity_flow_mapper import IdentityResolution

    return IdentityResolution(
        action="merge",
        confidence=1.0,
        matched_user_id=matched_user_id,
        reasons=["synthetic"],
        conflicts={},
        missing_fields=[],
    )


def _run_jotform(payload: dict, matched_user_id: str) -> dict:
    """Drive the webhook with identity resolution forced to merge.

    A merge into an EXISTING account now requires out-of-band ownership proof
    (launch-blocker closure): the webhook does NOT write to the account. It
    stores the pending payload for confirmation and emails the owner. This
    helper captures that pending payload so the email-containment invariant
    (the form email must not be carried into the deferred identity write) is
    still verified — while asserting no account write happens before proof.
    """
    from src.rico_jotform_webhook import handle_jotform_submission

    db = _jotform_db()
    env = {k: v for k, v in os.environ.items() if k != "JOTFORM_FORM_ID"}
    captured: dict = {}

    def _fake_create(account_email, pending):
        captured["account"] = account_email
        captured["pending"] = pending
        return True

    with patch("src.rico_jotform_webhook.RicoDB", return_value=db), \
         patch.dict(os.environ, env, clear=True), \
         patch("src.rico_jotform_webhook.find_identity_candidates", return_value=[]), \
         patch(
             "src.rico_jotform_webhook.map_identity_flow",
             return_value=_resolution(matched_user_id),
         ), \
         patch("src.repositories.onboarding_repo.mark_onboarding_complete"), \
         patch(
             "src.services.account_confirmation_service.create_jotform_merge_confirmation",
             side_effect=_fake_create,
         ):
        handle_jotform_submission(payload)

    # A merge never writes the account before the owner confirms.
    db.upsert_user.assert_not_called()
    db.upsert_profile.assert_not_called()
    return captured["pending"]["user"]


def test_phone_only_merge_does_not_carry_the_form_email_into_identity():
    """A submission matched on phone must not restate the account's email.

    The form email is not evidence of who the matched account is; the match was
    made on a different signal entirely.
    """
    user_payload = _run_jotform(
        {
            "submissionID": "sub-synthetic-phone",
            "phone": PHONE_PRINCIPAL,
            "email": UNRELATED_EMAIL,
            "consent": True,
        },
        matched_user_id=TELEGRAM_PRINCIPAL,
    )
    assert user_payload["external_user_id"] == TELEGRAM_PRINCIPAL
    assert user_payload.get("email") is None, (
        "a merge must not send the form email to the identity writer"
    )


def test_telegram_only_merge_does_not_carry_the_form_email_into_identity():
    user_payload = _run_jotform(
        {
            "submissionID": "sub-synthetic-telegram",
            "telegram_username": TELEGRAM_PRINCIPAL,
            "email": UNRELATED_EMAIL,
            "consent": True,
        },
        matched_user_id=OWNER_EMAIL,
    )
    assert user_payload["external_user_id"] == OWNER_EMAIL
    assert user_payload.get("email") is None


def test_a_submission_that_creates_a_new_user_still_carries_its_email():
    """No merge, no matched account: ordinary intake is unchanged."""
    from src.rico_jotform_webhook import handle_jotform_submission
    from src.services.identity_flow_mapper import IdentityResolution

    db = _jotform_db()
    env = {k: v for k, v in os.environ.items() if k != "JOTFORM_FORM_ID"}
    resolution = IdentityResolution(
        action="create",
        confidence=1.0,
        matched_user_id=None,
        reasons=["synthetic"],
        conflicts={},
        missing_fields=[],
    )
    with patch("src.rico_jotform_webhook.RicoDB", return_value=db), \
         patch.dict(os.environ, env, clear=True), \
         patch("src.rico_jotform_webhook.find_identity_candidates", return_value=[]), \
         patch("src.rico_jotform_webhook.map_identity_flow", return_value=resolution), \
         patch("src.repositories.onboarding_repo.mark_onboarding_complete"):
        handle_jotform_submission(
            {"submissionID": "sub-synthetic-new", "email": OWNER_EMAIL, "consent": True}
        )

    payload = db.upsert_user.call_args[0][0]
    assert payload["external_user_id"] == OWNER_EMAIL
    assert payload["email"] == OWNER_EMAIL


# ── 5. a non-email profile principal cannot stamp an email ────────────────────


def _run_upsert_profile(user_id: str, updates: dict, bundle=None) -> dict:
    """Drive `profile_repo.upsert_profile` and return the identity payload."""
    from src.repositories.profile_repo import upsert_profile

    db = MagicMock()
    db.available = True
    db.get_user_bundle.return_value = bundle
    db.upsert_user.return_value = {"id": "db-uuid-synthetic"}
    conn = MagicMock()

    @contextmanager
    def _transaction():
        yield conn

    with patch("src.repositories.profile_repo._db", return_value=db), \
         patch("src.repositories.profile_repo._memory"), \
         patch("src.repositories.profile_repo._db_transaction", _transaction):
        upsert_profile(user_id, updates)

    db.upsert_user.assert_called_once()
    return db.upsert_user.call_args[0][0]


def test_non_email_principal_cannot_promote_a_request_email_to_identity():
    """A Telegram-keyed principal supplying an email in the request body.

    The value is request-derived: nothing has verified that this principal owns
    that mailbox, so it must not reach the identity writer.
    """
    payload = _run_upsert_profile(
        TELEGRAM_PRINCIPAL, {"name": "Synthetic", "email": UNRELATED_EMAIL}
    )
    assert payload["external_user_id"] == TELEGRAM_PRINCIPAL
    assert "email" not in payload, (
        "a non-email principal must not send a request-derived email to the writer"
    )


def test_non_email_principal_still_writes_its_ordinary_profile_fields():
    """The refusal is scoped to email — the rest of the write proceeds."""
    payload = _run_upsert_profile(
        TELEGRAM_PRINCIPAL, {"name": "Synthetic", "email": UNRELATED_EMAIL}
    )
    assert payload["name"] == "Synthetic"


def test_email_principal_still_writes_its_own_email_as_identity():
    """Ordinary web registration: the principal IS the email — unchanged."""
    payload = _run_upsert_profile(OWNER_EMAIL, {"name": "Synthetic"})
    assert payload["external_user_id"] == OWNER_EMAIL
    assert payload["email"] == OWNER_EMAIL


def test_guest_principal_writes_no_email_through_upsert_profile():
    """#1398 at the repository boundary, unchanged."""
    from src.models.principal import PUBLIC_PRINCIPAL_PREFIX

    guest = f"{PUBLIC_PRINCIPAL_PREFIX}g-SYNTHETIC0000000000"
    payload = _run_upsert_profile(guest, {"name": "Synthetic", "email": OWNER_EMAIL})
    assert payload["external_user_id"] == guest
    assert "email" not in payload
