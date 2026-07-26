"""P0 regression: the chat paths must not run a second, weaker identity resolver.

`src/services/chat_service.py` used to resolve a principal to its `rico_users` row
with its own ranked SELECT (`id` > `email` > `external_user_id` > `updated_at DESC`,
`LIMIT 1`) instead of the central `RicoDB.get_user_bundle`. Two properties were
missing from that parallel query and both are cross-account defects:

  * it never excluded `public:` guest rows, so a guest row carrying an account's
    contact value was a candidate and could win the ordering;
  * it ranked candidates instead of refusing them, so ambiguity resolved silently to
    whichever row sorted first.

The auto-provision path repeated the same mistake twice more: an `ORDER BY
updated_at DESC LIMIT 1` email lookup, and a `web:<email>` insert that minted a
second row for one address — manufacturing the very ambiguity the resolver refuses
to guess through.

These tests pin the fix as behaviour, not as SQL text: resolution goes through the
central resolver, and every chat path fails closed on refusal. Fixtures are
synthetic; nothing here touches a real store.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models.principal import IdentityOwnershipAmbiguous  # noqa: E402
from src.services import chat_service  # noqa: E402

OWNER = "owner@synthetic.test"
GUEST = "public:synthetic-session-1"


def _mock_db(bundle=None, bundle_side_effect=None):
    """A RicoDB stand-in whose only ownership answer is get_user_bundle."""
    db = MagicMock()
    type(db).available = property(lambda self: True)
    if bundle_side_effect is not None:
        db.get_user_bundle.side_effect = bundle_side_effect
    else:
        db.get_user_bundle.return_value = bundle
    return db


def _cursor_returning(row):
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = row
    return cur


# ---------------------------------------------------------------------------
# Resolution goes through the central resolver
# ---------------------------------------------------------------------------


class TestResolutionIsCentral:
    def test_resolved_row_comes_from_get_user_bundle(self):
        db = _mock_db(bundle={"id": "owned-uuid"})
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) == "owned-uuid"
        db.get_user_bundle.assert_called_once_with(OWNER)

    def test_no_parallel_ranking_query_is_executed(self):
        """A hit must cost zero ad-hoc SQL — the resolver is the only reader."""
        db = _mock_db(bundle={"id": "owned-uuid"})
        with patch("src.rico_db.RicoDB", return_value=db):
            chat_service._resolve_db_user_id(OWNER)
        db.connect.assert_not_called()

    def test_guest_principal_resolves_its_own_row(self):
        """Guest flows still work: a public principal reads its own public row."""
        db = _mock_db(bundle={"id": "guest-uuid"})
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(GUEST) == "guest-uuid"
        db.get_user_bundle.assert_called_once_with(GUEST)

    def test_guest_principal_is_never_auto_provisioned(self):
        db = _mock_db(bundle=None)
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(GUEST) is None
        db.connect.assert_not_called()

    def test_non_email_identifier_is_never_auto_provisioned(self):
        db = _mock_db(bundle=None)
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id("telegram_handle") is None
        db.connect.assert_not_called()

    def test_unavailable_store_resolves_to_none_not_a_guess(self):
        db = MagicMock()
        type(db).available = property(lambda self: False)
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) is None
        db.get_user_bundle.assert_not_called()


# ---------------------------------------------------------------------------
# Ambiguity is refused, never ranked
# ---------------------------------------------------------------------------


class TestAmbiguityFailsClosed:
    def test_resolver_propagates_the_refusal(self):
        db = _mock_db(bundle_side_effect=IdentityOwnershipAmbiguous(2))
        with patch("src.rico_db.RicoDB", return_value=db):
            with pytest.raises(IdentityOwnershipAmbiguous):
                chat_service._resolve_db_user_id(OWNER)

    def test_refusal_does_not_fall_through_to_provisioning(self):
        """The old code's escape hatch: a miss minted a row. A refusal must not."""
        db = _mock_db(bundle_side_effect=IdentityOwnershipAmbiguous(2))
        with patch("src.rico_db.RicoDB", return_value=db):
            with pytest.raises(IdentityOwnershipAmbiguous):
                chat_service._resolve_db_user_id(OWNER)
        db.connect.assert_not_called()

    def test_get_chat_history_refuses_instead_of_serving_json_fallback(self):
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            with pytest.raises(IdentityOwnershipAmbiguous):
                chat_service.get_chat_history(OWNER, limit=50)

    def test_list_chat_sessions_refuses(self):
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            with pytest.raises(IdentityOwnershipAmbiguous):
                chat_service.list_chat_sessions(OWNER)

    def test_clear_chat_history_aborts_every_delete(self):
        """Destructive path: neither the DB delete nor the local JSON clear may run."""
        store = MagicMock()
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_memory.RicoMemoryStore", return_value=store):
            with pytest.raises(IdentityOwnershipAmbiguous):
                chat_service.clear_chat_history(OWNER)
        store._chat_path.assert_not_called()

    def test_db_append_chat_drops_the_turn_without_writing(self):
        """A write fails closed rather than filing the turn under a guessed owner."""
        db = MagicMock()
        type(db).available = property(lambda self: True)
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_db.RicoDB", return_value=db):
            chat_service.db_append_chat(OWNER, "user", "hello")  # must not raise
        db.append_chat.assert_not_called()


# ---------------------------------------------------------------------------
# Auto-provisioning: no ranking fallback, no duplicate row
# ---------------------------------------------------------------------------


class TestAutoProvisioning:
    def test_new_web_user_is_provisioned_once(self):
        db = _mock_db(bundle=None)
        conn = MagicMock()
        conn.cursor.return_value = _cursor_returning({"id": "fresh-uuid"})
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) == "fresh-uuid"
        assert conn.cursor.call_count == 1
        conn.commit.assert_called_once()

    def test_insert_conflict_re_resolves_centrally(self):
        """A concurrent writer won the insert — re-ask the resolver, do not rank."""
        db = _mock_db(bundle_side_effect=[None, {"id": "racer-uuid"}])
        conn = MagicMock()
        conn.cursor.return_value = _cursor_returning(None)  # DO NOTHING fired
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) == "racer-uuid"
        assert db.get_user_bundle.call_count == 2
        # One cursor: the insert. No email-keyed `updated_at DESC` lookup, and no
        # second `web:<email>` insert.
        assert conn.cursor.call_count == 1

    def test_insert_conflict_that_still_resolves_to_nothing_refuses(self):
        db = _mock_db(bundle_side_effect=[None, None])
        conn = MagicMock()
        conn.cursor.return_value = _cursor_returning(None)
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) is None
        assert conn.cursor.call_count == 1

    def test_insert_conflict_never_mints_a_web_namespaced_duplicate(self):
        """`web:<email>` created a second row for one address: permanent ambiguity."""
        db = _mock_db(bundle_side_effect=[None, None])
        conn = MagicMock()
        conn.cursor.return_value = _cursor_returning(None)
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            chat_service._resolve_db_user_id(OWNER)

        bound = [
            call.args[1]
            for call in conn.cursor.return_value.execute.call_args_list
            if len(call.args) > 1
        ]
        flattened = [str(value) for params in bound for value in params]
        assert not any(v.startswith("web:") for v in flattened)

    def test_provisioning_failure_rolls_back_and_returns_none(self):
        db = _mock_db(bundle=None)
        conn = MagicMock()
        conn.cursor.side_effect = RuntimeError("insert exploded")
        db.connect.return_value = conn

        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) is None
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()
