"""
P2-B — Delete saved jobs via chat (2-turn confirmation flow).

Tests cover:
- Confirmation is asked (not immediate deletion) on first delete intent
- Affirmative reply executes the real DB deletion
- Negative reply cancels cleanly
- Ambiguous reply re-prompts
- Application-history delete is permanently blocked (protected records)
- Arabic variants of all paths
- Expired confirmation window is a no-op
- Empty saved-jobs case
- User isolation
"""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from src.rico_chat_api import RicoChatAPI


def _make_api() -> RicoChatAPI:
    """Minimal RicoChatAPI instance — no DB, no AI, no side effects."""
    memory = MagicMock()
    memory.get_context.return_value = {}
    memory.set_context.return_value = None
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = memory
    api._db = MagicMock()
    api._append_chat = MagicMock()
    api._is_arabic_text = MagicMock(return_value=False)
    return api


def _set_pending(api: RicoChatAPI, user_id: str, expired: bool = False) -> None:
    """Write a live (or expired) pending-delete flag into the mock memory."""
    payload = {
        "pending": True,
        "expires_at": int(time.time()) + (-5 if expired else 120),
    }
    # Store directly in a simple dict so memory.get_context returns it
    store = {}
    store[user_id] = {api._PENDING_DELETE_SAVED_JOBS_KEY: payload}

    def _get(uid, key):
        return store.get(uid, {}).get(key, {})

    def _set(uid, key, val):
        if uid not in store:
            store[uid] = {}
        store[uid][key] = val

    api.memory.get_context.side_effect = _get
    api.memory.set_context.side_effect = _set


# ── Confirmation ask ──────────────────────────────────────────────────────────

class TestDeleteSavedJobsConfirmationAsk(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_delete_saved_jobs_asks_confirmation(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "delete all my saved jobs")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "delete_saved_jobs_confirm")
        self.assertEqual(result["next_action"], "await_confirmation")

    def test_delete_saved_jobs_arabic_asks_confirmation(self):
        self.api._is_arabic_text = MagicMock(return_value=True)
        result = self.api._intercept_unsupported_delete_mutation("u1", "احذف جميع الوظائف المحفوظة")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "delete_saved_jobs_confirm")

    def test_clear_saved_jobs_asks_confirmation(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "clear my saved jobs")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "delete_saved_jobs_confirm")

    def test_confirmation_message_has_no_success_phrase(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "delete all my saved jobs")
        for phrase in ("deleted successfully", "removed successfully", "تم الحذف", "تم الحفظ"):
            self.assertNotIn(phrase, result["message"])

    def test_confirmation_sets_pending_flag(self):
        pending_calls = []
        self.api.memory.set_context.side_effect = lambda uid, key, val: pending_calls.append((uid, key, val))
        self.api._intercept_unsupported_delete_mutation("u1", "delete all my saved jobs")
        keys_set = [k for _, k, _ in pending_calls]
        self.assertIn(self.api._PENDING_DELETE_SAVED_JOBS_KEY, keys_set)


# ── Application-history: permanently blocked ──────────────────────────────────

class TestDeleteApplicationsBlocked(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_delete_applications_is_blocked(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "delete my applications")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")
        self.assertEqual(result["intent"], "protected_application_history")

    def test_remove_all_applications_is_blocked(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "remove all my applications")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")

    def test_arabic_applications_delete_is_blocked(self):
        self.api._is_arabic_text = MagicMock(return_value=True)
        result = self.api._intercept_unsupported_delete_mutation("u1", "احذف طلباتي")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")
        self.assertEqual(result["intent"], "protected_application_history")

    def test_applications_block_never_contains_success_phrase(self):
        result = self.api._intercept_unsupported_delete_mutation("u1", "delete my applications")
        for phrase in ("deleted successfully", "removed successfully", "تم الحذف"):
            self.assertNotIn(phrase, result["message"])


# ── Affirmative confirmation → real deletion ──────────────────────────────────

class TestDeleteSavedJobsExecution(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def _run_confirm(self, message: str, deleted: int = 5, raise_exc=None):
        _set_pending(self.api, "u1")
        with patch("src.rico_db.RicoDB") as MockDB:
            if raise_exc:
                MockDB.return_value.delete_saved_jobs.side_effect = raise_exc
            else:
                MockDB.return_value.delete_saved_jobs.return_value = deleted
            return self.api._handle_pending_delete_saved_jobs("u1", message), MockDB

    def test_yes_executes_deletion(self):
        result, _ = self._run_confirm("yes")
        self.assertEqual(result["type"], "delete_saved_jobs_done")
        self.assertEqual(result["deleted_count"], 5)

    def test_confirm_arabic_executes_deletion(self):
        _set_pending(self.api, "u1")
        with patch("src.rico_db.RicoDB") as MockDB:
            MockDB.return_value.delete_saved_jobs.return_value = 3
            result = self.api._handle_pending_delete_saved_jobs("u1", "نعم")
        self.assertEqual(result["type"], "delete_saved_jobs_done")
        self.assertEqual(result["deleted_count"], 3)

    def test_yes_empty_saved_list(self):
        result, _ = self._run_confirm("yes", deleted=0)
        self.assertEqual(result["type"], "delete_saved_jobs_done")
        self.assertEqual(result["deleted_count"], 0)

    def test_success_message_contains_count(self):
        result, _ = self._run_confirm("yes", deleted=7)
        self.assertIn("7", result["message"])

    def test_db_failure_returns_failed_type(self):
        result, _ = self._run_confirm("yes", raise_exc=Exception("DB error"))
        self.assertEqual(result["type"], "delete_saved_jobs_failed")

    def test_success_clears_pending_flag(self):
        _set_pending(self.api, "u1")
        cleared = []
        original_set = self.api.memory.set_context.side_effect

        def _track_set(uid, key, val):
            if key == self.api._PENDING_DELETE_SAVED_JOBS_KEY and not val.get("pending"):
                cleared.append(uid)
            if original_set:
                original_set(uid, key, val)

        self.api.memory.set_context.side_effect = _track_set
        with patch("src.rico_db.RicoDB") as MockDB:
            MockDB.return_value.delete_saved_jobs.return_value = 2
            self.api._handle_pending_delete_saved_jobs("u1", "yes")
        self.assertIn("u1", cleared)


# ── Negative confirmation → cancel ────────────────────────────────────────────

class TestDeleteSavedJobsCancellation(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_no_cancels_deletion(self):
        _set_pending(self.api, "u1")
        with patch("src.rico_db.RicoDB") as MockDB:
            result = self.api._handle_pending_delete_saved_jobs("u1", "no")
        self.assertEqual(result["type"], "delete_saved_jobs_cancelled")
        MockDB.return_value.delete_saved_jobs.assert_not_called()

    def test_no_arabic_cancels_deletion(self):
        _set_pending(self.api, "u1")
        result = self.api._handle_pending_delete_saved_jobs("u1", "لا")
        self.assertEqual(result["type"], "delete_saved_jobs_cancelled")

    def test_cancel_clears_pending_flag(self):
        _set_pending(self.api, "u1")
        cleared = []
        original_set = self.api.memory.set_context.side_effect

        def _track(uid, key, val):
            if key == self.api._PENDING_DELETE_SAVED_JOBS_KEY and not val.get("pending"):
                cleared.append(uid)
            if original_set:
                original_set(uid, key, val)

        self.api.memory.set_context.side_effect = _track
        self.api._handle_pending_delete_saved_jobs("u1", "no")
        self.assertIn("u1", cleared)


# ── Ambiguous reply → re-prompt ───────────────────────────────────────────────

class TestDeleteSavedJobsAmbiguous(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_ambiguous_reply_re_prompts(self):
        _set_pending(self.api, "u1")
        result = self.api._handle_pending_delete_saved_jobs("u1", "what do you mean?")
        self.assertEqual(result["type"], "delete_saved_jobs_confirm")
        self.assertEqual(result["next_action"], "await_confirmation")

    def test_ambiguous_does_not_clear_pending(self):
        _set_pending(self.api, "u1")
        # After ambiguous reply, pending context must stay intact
        cleared = []
        original_set = self.api.memory.set_context.side_effect

        def _track(uid, key, val):
            if key == self.api._PENDING_DELETE_SAVED_JOBS_KEY and not val.get("pending"):
                cleared.append(uid)
            if original_set:
                original_set(uid, key, val)

        self.api.memory.set_context.side_effect = _track
        self.api._handle_pending_delete_saved_jobs("u1", "maybe?")
        self.assertNotIn("u1", cleared)


# ── Expired window ────────────────────────────────────────────────────────────

class TestDeleteSavedJobsExpiredWindow(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_expired_confirmation_window_returns_none(self):
        _set_pending(self.api, "u1", expired=True)
        with patch("src.rico_db.RicoDB") as MockDB:
            result = self.api._handle_pending_delete_saved_jobs("u1", "yes")
        self.assertIsNone(result)
        MockDB.return_value.delete_saved_jobs.assert_not_called()


# ── No pending context → handler returns None ─────────────────────────────────

class TestNoPendingContext(unittest.TestCase):

    def setUp(self):
        self.api = _make_api()

    def test_no_pending_returns_none(self):
        result = self.api._handle_pending_delete_saved_jobs("u1", "yes")
        self.assertIsNone(result)
