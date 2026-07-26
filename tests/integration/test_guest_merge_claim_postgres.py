"""
tests/integration/test_guest_merge_claim_postgres.py

Real-PostgreSQL proof of the one-time, account-bound guest merge claim
(#1070, locked design): migration 044's guest_identity_claims PRIMARY KEY is
the DURABLE single-owner authority, inserted in the same transaction and
connection as every data move. Two accounts claiming the SAME guest
concurrently yield exactly one committed owner; the loser copies no guest
profile data; the invariant holds even for a guest with NO rico_profiles row
(chat/upload-only guests); a consumed claim cannot be replayed into a second
account; a transient failure rolls claim + data back together and stays
retryable; an unproved claim never reaches the database.

Mock-layer tests cannot prove the lock/uniqueness serialization — only a real
server runs pg_try_advisory_xact_lock and the PRIMARY KEY across two
connections.

Requires RICO_TEST_DATABASE_URL (NOT the shared DATABASE_URL). Skips cleanly
when unset. In CI this runs in the postgres-integration job.
"""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

TEST_DATABASE_URL = os.environ.get("RICO_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or psycopg2 is None,
    reason="RICO_TEST_DATABASE_URL not set (or psycopg2 unavailable) — "
           "real-Postgres integration tests skipped.",
)


_MIGRATION_044_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "migrations", "044_guest_identity_claims.sql"
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    from src.rico_db import RicoDB

    RicoDB(database_url=TEST_DATABASE_URL).connect().close()
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with open(_MIGRATION_044_PATH) as f:
            with conn.cursor() as cur:
                cur.execute(f.read())
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _wire_to_test_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    yield
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM guest_identity_claims WHERE public_user_id LIKE 'public:web-claim%'")
            cur.execute(
                "DELETE FROM rico_profiles WHERE user_id IN "
                "(SELECT id FROM rico_users WHERE external_user_id LIKE 'claim-%' "
                " OR external_user_id LIKE 'public:web-claim%')"
            )
            cur.execute(
                "DELETE FROM rico_users WHERE external_user_id LIKE 'claim-%' "
                "OR external_user_id LIKE 'public:web-claim%'"
            )
        conn.commit()
    finally:
        conn.close()


def _seed_user(external_id: str, profile: dict | None = None) -> str:
    from psycopg2.extras import Json

    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_users (external_user_id, email, name)
                VALUES (%s, %s, %s) RETURNING id::text
                """,
                (external_id, external_id if "@" in external_id else None, external_id),
            )
            uid = cur.fetchone()[0]
            if profile is not None:
                cur.execute(
                    "INSERT INTO rico_profiles (user_id, profile) VALUES (%s, %s)",
                    (uid, Json(profile)),
                )
        conn.commit()
        return uid
    finally:
        conn.close()


def _profile_of(db_uid: str) -> dict:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT profile FROM rico_profiles WHERE user_id = %s", (db_uid,))
            row = cur.fetchone()
            return row[0] if row else {}
    finally:
        conn.close()


def _claim_owner(public_id: str) -> str | None:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT claimed_by_user_id::text FROM guest_identity_claims WHERE public_user_id = %s",
                (public_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def _fresh_guest(tag: str) -> tuple[str, str, str]:
    """Seed a guest with CV-derived data. Returns (public_id, session_id, guest_uuid)."""
    from src.api.public_identity import make_guest_capability_for_sid  # noqa: F401

    session_id = f"web-claim{tag}-{uuid.uuid4().hex[:8]}"
    public_id = f"public:{session_id}"
    guest_uuid = _seed_user(
        public_id,
        profile={"skills": ["hse", "nebosh"], "target_roles": ["HSE Manager"]},
    )
    return public_id, session_id, guest_uuid


class TestConcurrentClaim:
    def test_two_accounts_yield_exactly_one_committed_owner(self):
        from src.api.public_identity import make_guest_capability_for_sid
        from src.services.identity_merge_service import merge_public_identity_into_auth

        public_id, session_id, guest_uuid = _fresh_guest("race")
        uid_a = _seed_user(f"claim-a-{uuid.uuid4().hex[:6]}@test.com", profile={})
        uid_b = _seed_user(f"claim-b-{uuid.uuid4().hex[:6]}@test.com", profile={})
        ext_a = _ext_of(uid_a)
        ext_b = _ext_of(uid_b)
        token = make_guest_capability_for_sid(session_id)

        barrier = threading.Barrier(2)

        def claim(auth_ext: str) -> bool:
            barrier.wait(timeout=10)
            return merge_public_identity_into_auth(
                public_user_id=public_id, auth_user_id=auth_ext, guest_capability_token=token
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(claim, ext_a)
            fut_b = pool.submit(claim, ext_b)
            results = {"a": fut_a.result(timeout=30), "b": fut_b.result(timeout=30)}

        assert sum(results.values()) == 1, f"exactly one owner expected, got {results}"

        winner_uid = uid_a if results["a"] else uid_b
        loser_uid = uid_b if results["a"] else uid_a

        # Winner carries the guest data; loser copied NOTHING.
        assert _profile_of(winner_uid).get("skills") == ["hse", "nebosh"]
        assert "skills" not in _profile_of(loser_uid)

        # The claim marker is bound to the winner…
        guest_profile = _profile_of(guest_uuid)
        assert guest_profile.get("profile_status") == "merged"
        assert guest_profile.get("merged_into_user_id") == winner_uid
        # …and so is the DURABLE claim row (DB-enforced single owner).
        assert _claim_owner(public_id) == winner_uid

    def test_consumed_claim_cannot_be_replayed_into_second_account(self):
        from src.api.public_identity import make_guest_capability_for_sid
        from src.services.identity_merge_service import merge_public_identity_into_auth

        public_id, session_id, guest_uuid = _fresh_guest("replay")
        uid_a = _seed_user(f"claim-first-{uuid.uuid4().hex[:6]}@test.com", profile={})
        uid_b = _seed_user(f"claim-second-{uuid.uuid4().hex[:6]}@test.com", profile={})
        token = make_guest_capability_for_sid(session_id)

        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=token
        ) is True
        # Second account, even WITH the proof: the claim is consumed.
        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_b), guest_capability_token=token
        ) is False
        assert "skills" not in _profile_of(uid_b)
        # Same owner replaying is an idempotent success, no data duplication.
        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=token
        ) is True

    def test_guest_without_profile_row_still_single_owner(self):
        """A chat/upload-only guest has NO rico_profiles row, so the profile
        marker cannot be the authority — the guest_identity_claims PRIMARY KEY
        must enforce exactly one owner regardless (#1070 correction 4)."""
        from src.api.public_identity import make_guest_capability_for_sid
        from src.services.identity_merge_service import merge_public_identity_into_auth

        session_id = f"web-claimnoprof-{uuid.uuid4().hex[:8]}"
        public_id = f"public:{session_id}"
        guest_uuid = _seed_user(public_id, profile=None)  # NO profile row
        # Guest still owns real data: chat rows.
        conn = psycopg2.connect(TEST_DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rico_chat_history (user_id, role, message) VALUES (%s, 'user', 'sentinel')",
                    (guest_uuid,),
                )
            conn.commit()
        finally:
            conn.close()

        uid_a = _seed_user(f"claim-np-a-{uuid.uuid4().hex[:6]}@test.com", profile={})
        uid_b = _seed_user(f"claim-np-b-{uuid.uuid4().hex[:6]}@test.com", profile={})
        token = make_guest_capability_for_sid(session_id)

        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=token
        ) is True
        # No profile marker exists to consult — the DURABLE claim row must
        # still reject the second account.
        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_b), guest_capability_token=token
        ) is False
        assert _claim_owner(public_id) == uid_a

    def test_unproved_claim_never_reaches_the_database(self):
        from src.services.identity_merge_service import merge_public_identity_into_auth

        public_id, _session_id, guest_uuid = _fresh_guest("unproved")
        uid_a = _seed_user(f"claim-noproof-{uuid.uuid4().hex[:6]}@test.com", profile={})

        assert merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=None
        ) is False
        assert _profile_of(guest_uuid).get("profile_status") != "merged"
        assert _claim_owner(public_id) is None
        assert "skills" not in _profile_of(uid_a)

    def test_transient_failure_rolls_back_claim_and_stays_retryable(self):
        from src.api.public_identity import make_guest_capability_for_sid
        from src.services import identity_merge_service as ims

        public_id, session_id, guest_uuid = _fresh_guest("retry")
        uid_a = _seed_user(f"claim-retry-{uuid.uuid4().hex[:6]}@test.com", profile={})
        token = make_guest_capability_for_sid(session_id)

        with patch.object(
            ims, "_migrate_user_scoped_rows", side_effect=RuntimeError("transient store failure")
        ):
            assert ims.merge_public_identity_into_auth(
                public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=token
            ) is False

        # Nothing committed: no claim ROW, no claim marker, no copied data —
        # the ownership claim and every data move rolled back TOGETHER.
        assert _claim_owner(public_id) is None
        assert _profile_of(guest_uuid).get("profile_status") != "merged"
        assert "skills" not in _profile_of(uid_a)

        # Retry succeeds cleanly.
        assert ims.merge_public_identity_into_auth(
            public_user_id=public_id, auth_user_id=_ext_of(uid_a), guest_capability_token=token
        ) is True
        assert _profile_of(uid_a).get("skills") == ["hse", "nebosh"]


def _ext_of(db_uid: str) -> str:
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT external_user_id FROM rico_users WHERE id = %s", (db_uid,))
            return cur.fetchone()[0]
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# A2 — guest rows are excluded from AUTHENTICATED ownership resolution.
#
# This is the invariant the identity work exists to guarantee, and until these
# tests it had no behavioural backing: the only check was a string match
# asserting `NOT LIKE 'public:` appears in the emitted SQL. That proves the
# predicate is PRESENT, not that it EXCLUDES anything — a predicate that is
# present but ineffective passes it, and reformatting the query fails it. It
# cannot be fixed with a mocked cursor either: a fake returns whatever rows the
# test feeds it, so filtering is unobservable by construction. Only a real
# server executes the predicate.
#
# Fixture design is the load-bearing part. It is not enough to seed a guest row
# that would not have matched anyway — that passes for the wrong reason and
# proves nothing. Every guest row below is built so it WOULD be a candidate
# through the branch under test, and is excluded only by the guard.
#
# Path under test: `RicoDB.get_user_bundle` (src/rico_db.py) has ONE query
# construction path with two branches, selected by `"@" in user_id`. Both carry
# the guard. `count_identity_rows` carries similar predicate text without the
# caller-is-guest disjunct, but it is a different function (a diagnostic COUNT
# with a single caller) and is deliberately not exercised here.
# ─────────────────────────────────────────────────────────────────────────────

def _seed_identity_row(
    external_user_id: str,
    email: str | None = None,
    telegram_username: str | None = None,
) -> str:
    """Insert a rico_users row with explicit resolution keys."""
    conn = psycopg2.connect(TEST_DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rico_users (external_user_id, email, telegram_username, name)
                VALUES (%s, %s, %s, %s) RETURNING id::text
                """,
                (external_user_id, email, telegram_username, "synthetic"),
            )
            uid = cur.fetchone()[0]
        conn.commit()
        return uid
    finally:
        conn.close()


def _bundle(user_id: str):
    from src.rico_db import RicoDB

    return RicoDB(database_url=TEST_DATABASE_URL).get_user_bundle(user_id)


class TestGuestExclusionOnRealPostgres:
    """A2: a public row is never a candidate for an authenticated lookup."""

    def test_email_branch_excludes_a_guest_row_sharing_the_account_address(self):
        """Both rows match the email predicate; only the account row may survive.

        The guest row carries the SAME address as the account, so without the guard
        the email disjunct selects both and resolution becomes ambiguous. With the
        guard exactly one candidate remains.
        """
        tag = uuid.uuid4().hex[:12]
        address = f"claim-acct-{tag}@synthetic.test"
        account_id = _seed_identity_row(f"claim-acct-{tag}@synthetic.test", email=address)
        _seed_identity_row(f"public:web-claim-{tag}", email=address)  # same address

        bundle = _bundle(address)

        assert bundle is not None, "the account row must still resolve"
        assert bundle["id"] == account_id
        assert not str(bundle["external_user_id"]).startswith("public:"), (
            "authenticated resolution returned a public row"
        )

    def test_email_branch_returns_nothing_when_only_a_guest_row_holds_the_address(self):
        """The sharpest form: a guest row alone must not answer an account lookup.

        Without the guard this returns the guest row — a public session served as
        though it were the account. With it, the correct answer is "no such account".
        """
        tag = uuid.uuid4().hex[:12]
        address = f"claim-orphan-{tag}@synthetic.test"
        _seed_identity_row(f"public:web-claim-{tag}", email=address)

        assert _bundle(address) is None, (
            "a guest row must never be served for an authenticated email lookup"
        )

    def test_non_email_branch_excludes_a_guest_row_sharing_the_telegram_handle(self):
        """Same invariant on the branch selected when the identifier has no '@'."""
        tag = uuid.uuid4().hex[:12]
        handle = f"tg_{tag}"
        account_id = _seed_identity_row(f"claim-tg-acct-{tag}", telegram_username=handle)
        _seed_identity_row(f"public:web-claim-{tag}", telegram_username=handle)  # same handle

        bundle = _bundle(handle)

        assert bundle is not None, "the account row must still resolve"
        assert bundle["id"] == account_id
        assert not str(bundle["external_user_id"]).startswith("public:"), (
            "authenticated resolution returned a public row on the non-email branch"
        )

    def test_non_email_branch_returns_nothing_when_only_a_guest_row_holds_the_handle(self):
        tag = uuid.uuid4().hex[:12]
        handle = f"tg_orphan_{tag}"
        _seed_identity_row(f"public:web-claim-{tag}", telegram_username=handle)

        assert _bundle(handle) is None, (
            "a guest row must never be served for an authenticated handle lookup"
        )

    def test_a_guest_still_resolves_its_own_row(self):
        """The exclusion is scoped to AUTHENTICATED resolution, not applied blindly.

        Without this, the guard could be "fixed" by dropping the caller-is-guest
        disjunct entirely — which would pass every test above while silently
        breaking every guest read in production.
        """
        tag = uuid.uuid4().hex[:12]
        principal = f"public:web-claim-{tag}"
        guest_id = _seed_identity_row(principal, email=f"claim-guest-{tag}@synthetic.test")

        bundle = _bundle(principal)

        assert bundle is not None, "a guest resolving its own principal must get its row"
        assert bundle["id"] == guest_id
