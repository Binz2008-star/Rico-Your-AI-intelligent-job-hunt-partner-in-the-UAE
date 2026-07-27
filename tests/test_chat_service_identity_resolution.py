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

Coverage runs from the resolver out to the HTTP edge, because a service-level
refusal is only worth as much as the status the caller actually receives:

  * resolution is central, and a hit costs zero ad-hoc SQL;
  * ambiguity propagates instead of falling through to provisioning;
  * GET sessions, GET history and DELETE history all answer the existing 409;
  * POST /chat keeps its documented graceful 200 while still refusing the write —
    the turn is dropped, never filed under a guessed owner;
  * a store outage stays distinguishable from ownership ambiguity, in the HTTP
    status and in the logs.
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


# ---------------------------------------------------------------------------
# The refusal survives the whole stack, not just the service function
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client():
    """Authenticated TestClient. conftest supplies the healthy auth-store default."""
    from fastapi.testclient import TestClient

    from src.api.app import app
    from src.api.auth import create_access_token

    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(
        "access_token", create_access_token({"sub": OWNER, "role": "user"})
    )
    return client


def _assert_ambiguity_409(response):
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "ambiguous_account_ownership"
    assert body["ok"] is False
    # The refusal must not leak which rows collided, or whose they are.
    assert OWNER not in response.text


class TestChatRoutesRefuseAtTheEdge:
    """Every chat route answers the existing 409 when ownership is ambiguous.

    These patch `_resolve_db_user_id` rather than the service functions, so the real
    `chat_service` bodies run and the assertion covers the full path: resolver refusal
    -> service propagation -> app-level handler -> HTTP status. Patching the service
    function itself would only prove the handler is wired, which is the part that was
    never in doubt.
    """

    def test_get_chat_sessions_returns_409(self, auth_client):
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            _assert_ambiguity_409(auth_client.get("/api/v1/rico/chat/sessions"))

    def test_get_chat_history_returns_409(self, auth_client):
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            _assert_ambiguity_409(auth_client.get("/api/v1/rico/chat/history"))

    def test_get_chat_history_409_is_not_downgraded_to_an_empty_page(self, auth_client):
        """The JSON-memory fallback must not turn a refusal into a plausible 200."""
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            response = auth_client.get("/api/v1/rico/chat/history?limit=20")
        assert response.status_code == 409
        assert "messages" not in response.json()

    def test_delete_chat_history_returns_409_and_deletes_nothing(self, auth_client):
        store = MagicMock()
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_memory.RicoMemoryStore", return_value=store):
            response = auth_client.delete("/api/v1/rico/chat/history")
        _assert_ambiguity_409(response)
        # 204 is this route's success code; a refusal must not report one.
        assert response.status_code != 204
        store._chat_path.assert_not_called()

    def test_delete_scoped_to_one_thread_also_refuses(self, auth_client):
        """The session-scoped delete is the same destructive path with a narrower WHERE."""
        session = "11111111-2222-3333-4444-555555555555"
        store = MagicMock()
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_memory.RicoMemoryStore", return_value=store):
            response = auth_client.delete(
                f"/api/v1/rico/chat/history?session_id={session}"
            )
        _assert_ambiguity_409(response)
        store._chat_path.assert_not_called()


class TestPostChatNeverPersistsToTheWrongAccount:
    """POST /chat is the one chat route that does NOT surface 409, by design.

    Its handler catches every non-HTTPException and returns a graceful 200 error
    envelope so a chat turn never hard-fails in the UI. That documented behaviour is
    preserved here rather than "fixed" — but the safety property has to hold anyway:
    the turn must not be filed against a guessed owner on the way out.
    """

    def test_route_keeps_its_documented_graceful_200(self, auth_client):
        with patch("src.services.chat_service.send_message",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            response = auth_client.post(
                "/api/v1/rico/chat", json={"message": "hello"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["type"] == "error"
        assert body["success"] is False
        assert body["error_ref"]
        # The refusal is internal: no ownership detail reaches the chat surface.
        assert "ambiguous_account_ownership" not in response.text

    def test_turn_is_dropped_rather_than_written_to_a_guessed_owner(self, auth_client):
        """The write a real turn performs must not land while the route serves 200."""
        db = MagicMock()
        type(db).available = property(lambda self: True)

        def _turn_that_persists(**kwargs):
            chat_service.db_append_chat(OWNER, "user", "hello")
            return {"type": "assistant", "message": "hi"}

        with patch("src.services.chat_service.send_message",
                   side_effect=_turn_that_persists), \
             patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_db.RicoDB", return_value=db):
            response = auth_client.post(
                "/api/v1/rico/chat", json={"message": "hello"}
            )

        assert response.status_code == 200
        db.append_chat.assert_not_called()

    def test_a_resolved_turn_is_written_only_under_its_own_owner(self):
        """The complement: when resolution succeeds, the id written is the resolved one.

        Without this, `append_chat.assert_not_called()` above would still pass against a
        persistence layer that never writes at all.
        """
        db = MagicMock()
        type(db).available = property(lambda self: True)
        with patch("src.services.chat_service._resolve_db_user_id",
                   return_value="owned-uuid"), \
             patch("src.rico_db.RicoDB", return_value=db):
            chat_service.db_append_chat(OWNER, "user", "hello")
        db.append_chat.assert_called_once()
        assert db.append_chat.call_args.args[0] == "owned-uuid"


class TestStoreFailureStaysDistinctFromAmbiguity:
    """A store that is down is a retryable non-answer; ambiguity is a terminal refusal.

    Collapsing the two would be a regression in either direction: a 409 for an outage
    tells the user to contact support about a transient blip, and an outage-shaped
    degrade for real ambiguity is precisely the silent cross-account read this branch
    exists to stop.
    """

    def test_unresolvable_store_degrades_to_the_fallback_not_a_refusal(self):
        """`get_user_bundle` failing for transport reasons must not raise."""
        db = _mock_db(bundle_side_effect=RuntimeError("connection reset"))
        db.connect.side_effect = RuntimeError("connection reset")
        with patch("src.rico_db.RicoDB", return_value=db):
            assert chat_service._resolve_db_user_id(OWNER) is None

    def test_history_serves_the_fallback_on_store_failure(self, auth_client):
        api = MagicMock()
        api.memory.get_chat_messages.return_value = [
            {"role": "user", "content": "earlier turn", "timestamp": None}
        ]
        with patch("src.services.chat_service._resolve_db_user_id", return_value=None), \
             patch("src.rico_chat_api.RicoChatAPI", return_value=api):
            response = auth_client.get("/api/v1/rico/chat/history")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_history_refusal_and_store_failure_do_not_share_a_status(self, auth_client):
        """Same route, same caller — the two failure modes must be told apart."""
        api = MagicMock()
        api.memory.get_chat_messages.return_value = []
        with patch("src.services.chat_service._resolve_db_user_id", return_value=None), \
             patch("src.rico_chat_api.RicoChatAPI", return_value=api):
            degraded = auth_client.get("/api/v1/rico/chat/history")
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)):
            refused = auth_client.get("/api/v1/rico/chat/history")
        assert degraded.status_code == 200
        assert refused.status_code == 409

    def test_append_logs_ambiguity_with_its_own_reason(self, caplog):
        """An operator must be able to separate the two in the logs, not just in code."""
        db = MagicMock()
        type(db).available = property(lambda self: True)
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=IdentityOwnershipAmbiguous(2)), \
             patch("src.rico_db.RicoDB", return_value=db):
            with caplog.at_level("WARNING", logger=chat_service.logger.name):
                chat_service.db_append_chat(OWNER, "user", "hello")
        assert any(
            "ambiguous_account_ownership" in record.getMessage()
            for record in caplog.records
        )

    def test_append_does_not_label_a_store_failure_as_ambiguity(self, caplog):
        db = MagicMock()
        type(db).available = property(lambda self: True)
        with patch("src.services.chat_service._resolve_db_user_id",
                   side_effect=RuntimeError("connection reset")), \
             patch("src.rico_db.RicoDB", return_value=db):
            with caplog.at_level("WARNING", logger=chat_service.logger.name):
                chat_service.db_append_chat(OWNER, "user", "hello")
        assert "ambiguous_account_ownership" not in caplog.text
        db.append_chat.assert_not_called()
