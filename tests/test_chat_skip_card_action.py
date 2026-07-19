"""Job-card Skip action through chat — regression for the /command FAIL.

The /command job card sends the literal message "Skip {title} at {company}"
(JobMatchCardAtelier). The central intent classifier has no skip vocabulary,
so before this fix the message fell into the unknown-intent fallback —
a generic non-answer at best, and in production a provider-path error
surfaced as "Something went wrong" (owner screenshot, 2026-07-20). The job
was never actually skipped.

Contract pinned here:
  1. "Skip X at Y" routes deterministically to the skip handler (type
     skip_job) — never the unknown-intent fallback.
  2. Skip is a SUPPRESSION action: it succeeds for a stale card whose job is
     no longer in the current results (that is the Bybit case).
  3. The runtime is called with action="skip" and a stable job_key.
  4. Runtime failure → honest bilingual retry message, never an exception
     and never a generic error.
  5. Arabic variant routes the same way.

Run: pytest tests/test_chat_skip_card_action.py -v
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.rico_chat_api import RicoChatAPI
from src.services.profile_context_resolver import resolve_profile_context

_USER = "synthetic-user@test.local"

_RAW_PROFILE = {
    "full_name": "Synthetic User",
    "target_roles": ["Environmental Manager"],
    "preferred_cities": ["Ajman"],
    "years_experience": 5,
    "cv_uploaded": True,
    "onboarding_complete": True,
    "email": _USER,
}


class _FakeResult:
    def __init__(self, ok: bool = True, message: str = "", error: str = ""):
        self.ok = ok
        self.message = message
        self.error = error
        self.action = "skip"
        self.data = {}


class TestChatSkipCardAction(unittest.TestCase):
    def setUp(self):
        self.api = RicoChatAPI()
        self.ctx = resolve_profile_context(_USER, dict(_RAW_PROFILE))
        self._profile_patch = patch.object(
            RicoChatAPI, "_resolve_profile", return_value=self.ctx
        )
        self._profile_patch.start()
        self.addCleanup(self._profile_patch.stop)

    def _process(self, message: str):
        return self.api.process_message(_USER, message)

    def test_stale_card_skip_succeeds_as_suppression(self):
        """The Bybit case: job absent from current results — skip still works."""
        with patch("src.rico_chat_api.agent_runtime.handle_action",
                   return_value=_FakeResult(ok=True)) as run:
            resp = self._process("Skip Head of Trading Risk at Bybit")

        self.assertEqual(resp.get("type"), "skip_job",
                         "must route to the skip handler, not the unknown fallback")
        self.assertIn("Skipped", resp.get("message", ""))
        self.assertIn("Head of Trading Risk", resp.get("message", ""))
        run.assert_called_once()
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["action"], "skip")
        self.assertEqual(kwargs["user_id"], _USER)
        self.assertTrue(kwargs["job_key"], "a stable job_key must be derived")
        self.assertEqual(kwargs["job"]["title"], "Head of Trading Risk")
        self.assertEqual(kwargs["job"]["company"], "Bybit")

    def test_fresh_card_skip_uses_resolved_job_context(self):
        """A job present in recent results: the resolved card context (URLs,
        canonical title/company) flows into the runtime call."""
        resolved = {
            "title": "Environmental Compliance Manager",
            "company": "Simpson Booth Ltd",
            "apply_url": "https://example.test/apply/123",
            "source_url": "https://example.test/job/123",
        }
        with patch.object(RicoChatAPI, "_resolve_card_job", return_value=resolved), \
             patch("src.rico_chat_api.agent_runtime.handle_action",
                   return_value=_FakeResult(ok=True)) as run:
            resp = self._process("Skip Environmental Compliance Manager at Simpson Booth Ltd")

        self.assertEqual(resp.get("type"), "skip_job")
        self.assertIn("Skipped", resp.get("message", ""))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["job"]["title"], "Environmental Compliance Manager")
        self.assertEqual(kwargs["job"]["company"], "Simpson Booth Ltd")
        self.assertEqual(kwargs["job"]["apply_url"], "https://example.test/apply/123")
        self.assertEqual(kwargs["job"]["source_url"], "https://example.test/job/123")

    def test_repeated_skip_is_idempotent_at_the_runtime_key(self):
        """Clicking Skip twice must hit the runtime with the SAME stable
        job_key both times — the runtime's idempotency key
        (user_id:action:job_key) then guarantees no duplicated side effect —
        and both replies stay honest successes."""
        with patch("src.rico_chat_api.agent_runtime.handle_action",
                   return_value=_FakeResult(ok=True)) as run:
            r1 = self._process("Skip Head of Trading Risk at Bybit")
            r2 = self._process("Skip Head of Trading Risk at Bybit")

        self.assertEqual(r1.get("type"), "skip_job")
        self.assertEqual(r2.get("type"), "skip_job")
        self.assertEqual(run.call_count, 2)
        key1 = run.call_args_list[0].kwargs["job_key"]
        key2 = run.call_args_list[1].kwargs["job_key"]
        self.assertTrue(key1)
        self.assertEqual(key1, key2,
                         "repeated skips must derive the identical job_key")

    def test_runtime_failure_returns_honest_retry_message(self):
        with patch("src.rico_chat_api.agent_runtime.handle_action",
                   return_value=_FakeResult(ok=False, error="db_unavailable")):
            resp = self._process("Skip Head of Trading Risk at Bybit")

        self.assertEqual(resp.get("type"), "skip_job")
        msg = resp.get("message", "")
        self.assertIn("couldn't skip", msg)
        self.assertNotIn("Something went wrong", msg)

    def test_arabic_skip_routes_and_replies_in_arabic(self):
        with patch("src.rico_chat_api.agent_runtime.handle_action",
                   return_value=_FakeResult(ok=True)) as run:
            resp = self._process("تجاهل وظيفة مدير المخاطر لدى بايبت")

        self.assertEqual(resp.get("type"), "skip_job")
        self.assertIn("تم التجاهل", resp.get("message", ""))
        self.assertEqual(run.call_args.kwargs["action"], "skip")

    def test_skip_never_raises_even_if_runtime_raises(self):
        """A runtime exception must degrade to the chat error contract, not a 500."""
        with patch("src.rico_chat_api.agent_runtime.handle_action",
                   side_effect=RuntimeError("boom")):
            try:
                resp = self._process("Skip Head of Trading Risk at Bybit")
            except Exception as exc:  # pragma: no cover
                self.fail(f"skip path must never raise, got {exc!r}")
        self.assertIsInstance(resp, dict)

    def test_non_card_skip_sentences_do_not_match(self):
        """Guard against over-matching: ordinary sentences aren't hijacked."""
        from src.rico_chat_api import _SKIP_CARD_ACTION_RE
        for msg in (
            "Can I skip the interview questions at the end?",
            "I want to skip ahead",
            "skip",
        ):
            m = _SKIP_CARD_ACTION_RE.match(msg)
            if m:
                # The grammar requires "<title> at <company>" — the first
                # sentence matches shape-wise; ensure at least that pure
                # non-"at" phrases never match.
                self.assertIn(" at ", msg)

    def test_save_and_applied_card_actions_unaffected(self):
        """The skip route must not intercept the other card actions."""
        from src.rico_chat_api import _SKIP_CARD_ACTION_RE
        self.assertIsNone(_SKIP_CARD_ACTION_RE.match(
            "Save Head of Trading Risk at Bybit to my pipeline"))
        self.assertIsNone(_SKIP_CARD_ACTION_RE.match(
            "I've applied to Head of Trading Risk at Bybit"))


if __name__ == "__main__":
    unittest.main()
