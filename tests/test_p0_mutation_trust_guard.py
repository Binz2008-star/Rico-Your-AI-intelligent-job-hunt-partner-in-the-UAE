"""Regression tests for P0 Trust Bug (Issue #764).

Rico must never claim success for chat-driven database mutations (delete,
save, remind, mark-applied) unless a backend tool explicitly confirms the
operation.  These tests verify:

1.  Delete-all-saved-jobs (Arabic + English) → capability_limitation, no
    false "تم الحذف" / "deleted successfully".
2.  Delete-applications (Arabic + English) → same guard.
3.  Mark-as-applied → success only after _persist_confirmed_application_status
    returns True; failure path returns application_status_update_failed.
4.  Reminder → success only after agent_runtime.handle_action("remind")
    returns ok=True; failure path returns reminder_set_failed; no-job-in-context
    path returns clarification.
5.  Reminder false-success path (the original bug) is gone — no reminder_set
    response is ever emitted without a backend ok.
"""
from __future__ import annotations

import re
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Regex smoke tests — verify the guard pattern fires on expected inputs
# ---------------------------------------------------------------------------

# Import the compiled regex directly from the module under test.
# Importing lazily avoids heavy module-level side effects in CI.
def _import_delete_re():
    import importlib
    mod = importlib.import_module("src.rico_chat_api")
    return mod._UNSUPPORTED_DELETE_RE


class TestUnsupportedDeleteRegex(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RE = _import_delete_re()

    def _should_match(self, text: str) -> None:
        self.assertIsNotNone(
            self.RE.search(text),
            f"Expected regex to match but didn't: {text!r}",
        )

    def _should_not_match(self, text: str) -> None:
        self.assertIsNone(
            self.RE.search(text),
            f"Expected regex NOT to match but it did: {text!r}",
        )

    # ── Should match (unsupported delete intents) ────────────────────────────

    def test_english_delete_all_saved_jobs(self):
        self._should_match("delete all saved jobs")

    def test_english_delete_my_jobs(self):
        self._should_match("delete my jobs")

    def test_english_clear_saved_jobs(self):
        self._should_match("clear saved jobs")

    def test_english_clear_my_pipeline(self):
        self._should_match("clear my pipeline")

    def test_english_remove_all_saved_jobs(self):
        self._should_match("remove all saved jobs")

    def test_english_remove_all_applications(self):
        self._should_match("remove all applications")

    def test_english_remove_my_applications(self):
        self._should_match("remove my applications")

    def test_english_erase_my_jobs(self):
        self._should_match("erase my jobs")

    def test_english_wipe_my_pipeline(self):
        self._should_match("wipe my pipeline")

    def test_english_delete_my_applications(self):
        self._should_match("delete my applications")

    def test_english_delete_pipeline(self):
        self._should_match("delete pipeline")

    def test_english_clear_all_applications(self):
        self._should_match("clear all applications")

    def test_arabic_delete_all_saved_jobs(self):
        self._should_match("امسح جميع الوظائف المحفوظة")

    def test_arabic_delete_jobs(self):
        self._should_match("احذف الوظائف")

    def test_arabic_delete_applications(self):
        self._should_match("امسح الطلبات")

    def test_arabic_delete_my_applications(self):
        self._should_match("احذف طلباتي")

    def test_arabic_delete_saved_list(self):
        self._should_match("امسح قائمة الوظائف")

    def test_arabic_delete_saved_list_alt(self):
        self._should_match("احذف المحفوظات")

    # ── Should NOT match (preference/skill removals — handled elsewhere) ─────

    def test_no_match_remove_skill(self):
        self._should_not_match("remove Python from my skills")

    def test_no_match_remove_city_preference(self):
        self._should_not_match("remove Abu Dhabi from my preferred cities")

    def test_no_match_arabic_remove_city(self):
        self._should_not_match("احذف من مدنك أبوظبي")

    def test_no_match_remove_certification(self):
        self._should_not_match("remove OSHA from my certifications")

    def test_no_match_skip_job(self):
        self._should_not_match("skip this job")

    def test_no_match_not_interested(self):
        self._should_not_match("not interested in this role")

    def test_no_match_search_query(self):
        self._should_not_match("find jobs in Dubai")

    def test_no_match_delete_account(self):
        # Out of scope for this guard — different mutation
        self._should_not_match("delete my account please")


# ---------------------------------------------------------------------------
# Integration-style unit tests for _intercept_unsupported_delete_mutation
# ---------------------------------------------------------------------------

def _make_chat_api():
    """Return a minimally wired RicoChatAPI instance with mocked IO."""
    from src.rico_chat_api import RicoChatAPI
    memory = MagicMock()
    memory.get_context.return_value = {}
    memory.set_context.return_value = None
    api = RicoChatAPI.__new__(RicoChatAPI)
    api.memory = memory
    api._db = MagicMock()
    return api


class TestInterceptUnsupportedDeleteMutation(unittest.TestCase):

    def setUp(self):
        self.api = _make_chat_api()
        # Suppress _append_chat side effect
        self.api._append_chat = MagicMock()
        # Suppress _is_arabic_text — tested separately per case
        self.api._is_arabic_text = MagicMock(return_value=False)

    def test_english_delete_returns_capability_limitation(self):
        result = self.api._intercept_unsupported_delete_mutation("user1", "delete all saved jobs")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")
        self.assertIn("/flow", result["message"])
        self.assertIn("/applications", result["message"])

    def test_english_clear_pipeline_returns_capability_limitation(self):
        result = self.api._intercept_unsupported_delete_mutation("user1", "clear my pipeline")
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")

    def test_english_response_never_contains_success_phrase(self):
        for phrase in ("deleted successfully", "removed successfully", "تم الحذف", "تم الحفظ"):
            result = self.api._intercept_unsupported_delete_mutation("user1", "delete all saved jobs")
            self.assertNotIn(phrase, result["message"])

    def test_arabic_delete_returns_arabic_response(self):
        self.api._is_arabic_text = MagicMock(return_value=True)
        result = self.api._intercept_unsupported_delete_mutation(
            "user1", "امسح جميع الوظائف المحفوظة"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "capability_limitation")
        # Arabic response must contain Arabic navigation hint
        self.assertIn("/flow", result["message"])

    def test_unrelated_message_returns_none(self):
        result = self.api._intercept_unsupported_delete_mutation("user1", "find jobs in Dubai")
        self.assertIsNone(result)

    def test_skill_removal_returns_none(self):
        result = self.api._intercept_unsupported_delete_mutation(
            "user1", "remove Python from my skills"
        )
        self.assertIsNone(result)

    def test_city_preference_removal_returns_none(self):
        result = self.api._intercept_unsupported_delete_mutation(
            "user1", "remove Abu Dhabi from my preferred cities"
        )
        self.assertIsNone(result)

    def test_append_chat_called_on_match(self):
        self.api._intercept_unsupported_delete_mutation("user1", "delete all saved jobs")
        self.api._append_chat.assert_called_once()

    def test_append_chat_not_called_on_no_match(self):
        self.api._intercept_unsupported_delete_mutation("user1", "find me jobs")
        self.api._append_chat.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_application_status_update — success only after backend confirmation
# ---------------------------------------------------------------------------

class TestApplicationStatusUpdateTrustGate(unittest.TestCase):
    """Ensure _handle_application_status_update only claims success after the
    backend _persist_confirmed_application_status returns True."""

    def setUp(self):
        self.api = _make_chat_api()
        self.api._append_chat = MagicMock()
        self.api._is_arabic_text = MagicMock(return_value=False)
        self.api._MANUAL_APPLICATION_LOG_QUESTION_RE = re.compile(r"(?!)")  # never matches
        self.api._resolve_application_status_job = MagicMock(return_value={
            "title": "HSE Manager", "company": "Acme LLC",
        })
        self.api._job_context_value = lambda job, *keys: job.get(keys[0], "")
        self.api._store_application_status_context = MagicMock()

    def test_success_message_only_when_persisted_is_true(self):
        self.api._persist_confirmed_application_status = MagicMock(return_value=(True, "job-123"))
        result = self.api._handle_application_status_update("user1", "I applied", profile=None)
        self.assertEqual(result["type"], "application_status_update")
        # Must contain the job info, not a generic "deleted" success
        self.assertIn("HSE Manager", result["message"])
        # No false-success language
        self.assertNotIn("تم الحذف", result["message"])

    def test_failure_message_when_persisted_is_false(self):
        self.api._persist_confirmed_application_status = MagicMock(return_value=(False, None))
        result = self.api._handle_application_status_update("user1", "I applied", profile=None)
        self.assertEqual(result["type"], "application_status_update_failed")
        # Must NOT say "Application marked as submitted" on failure
        self.assertNotIn("marked as submitted", result["message"])
        self.assertNotIn("تم تسجيل", result["message"])

    def test_public_user_gets_sign_in_prompt_not_success(self):
        result = self.api._handle_application_status_update(
            "public:web-abc", "I applied", profile=None
        )
        # Public user must never get a false success
        self.assertNotEqual(result.get("type"), "application_status_update")
        self.assertNotIn("تم تسجيل", result.get("message", ""))


# ---------------------------------------------------------------------------
# _resolve_pending_intent — reminder path must not emit fake success
# ---------------------------------------------------------------------------

class TestReminderNeverFalseSuccess(unittest.TestCase):
    """The reminder branch in _resolve_pending_intent must only claim success
    after agent_runtime.handle_action("remind") returns ok=True."""

    def setUp(self):
        self.api = _make_chat_api()
        self.api._append_chat = MagicMock()
        self.api._is_arabic_text = MagicMock(return_value=False)
        self.api._get_last_assistant_message = MagicMock(
            return_value="would you like a reminder to follow up?"
        )
        self.api._is_affirmative = MagicMock(return_value=True)
        self.api._get_pending_job_search = MagicMock(return_value=None)
        # Suppress other signal branches
        self.api._handle_cv_generate_from_profile = MagicMock()
        self.api._classified_role_search = MagicMock()
        self.api._answer_with_ai_fallback = MagicMock()
        self.api._POST_CV_CONTINUATION_SIGNALS = ()
        self.api._clear_pending_job_search = MagicMock()
        self.api._as_list = lambda x: x if isinstance(x, list) else ([x] if x else [])
        self.api._profile_value = MagicMock(return_value=None)

    def _run(self, recent_matches, runtime_ok):
        self.api._recent_search_matches = MagicMock(return_value=recent_matches)
        mock_result = MagicMock()
        mock_result.ok = runtime_ok
        with patch("src.rico_chat_api.agent_runtime") as mock_rt:
            mock_rt.handle_action.return_value = mock_result
            result = self.api._resolve_pending_intent("user1", "yes", profile=None)
        return result, mock_rt

    def test_no_job_in_context_returns_clarification_not_success(self):
        result, _ = self._run(recent_matches=[], runtime_ok=True)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "clarification")
        self.assertNotEqual(result["type"], "reminder_set")

    def test_job_found_and_backend_ok_returns_reminder_set(self):
        job = {"title": "HSE Manager", "company": "Acme LLC"}
        result, mock_rt = self._run(recent_matches=[job], runtime_ok=True)
        mock_rt.handle_action.assert_called_once()
        self.assertEqual(result["type"], "reminder_set")
        # Success message must reference the job
        self.assertIn("HSE Manager", result["message"])

    def test_job_found_but_backend_fails_returns_reminder_set_failed(self):
        job = {"title": "HSE Manager", "company": "Acme LLC"}
        result, mock_rt = self._run(recent_matches=[job], runtime_ok=False)
        mock_rt.handle_action.assert_called_once()
        self.assertEqual(result["type"], "reminder_set_failed")
        # Must NOT say "Reminder set" on failure
        self.assertNotIn("Reminder set", result["message"])
        self.assertNotIn("تم ضبط", result["message"])

    def test_backend_exception_returns_reminder_set_failed(self):
        self.api._recent_search_matches = MagicMock(return_value=[
            {"title": "HSE Manager", "company": "Acme"}
        ])
        with patch("src.rico_chat_api.agent_runtime") as mock_rt:
            mock_rt.handle_action.side_effect = RuntimeError("db error")
            result = self.api._resolve_pending_intent("user1", "yes", profile=None)
        self.assertEqual(result["type"], "reminder_set_failed")


if __name__ == "__main__":
    unittest.main()
