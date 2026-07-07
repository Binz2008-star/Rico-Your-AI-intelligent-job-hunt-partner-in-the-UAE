"""TC-7 regression tests — structured plain-text application tracking.

"Position: X. Company: Y. Track it." must save to the pipeline without a UI
button (TASK-20260703-039). Covers:

1. Trigger regex — fires on explicit track/save instructions, never on plain
   searches or pasted postings.
2. Field extraction — title/company stop at sentence punctuation so a
   single-line message never swallows "Company: Y. Track it." into the title.
3. Handler honesty — never claims "Tracked" unless create_manual returns True.
4. Arabic reply path.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


def _mod():
    import importlib
    return importlib.import_module("src.rico_chat_api")


# ---------------------------------------------------------------------------
# Trigger regex
# ---------------------------------------------------------------------------

class TestManualTrackTriggerRegex(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RE = _mod()._MANUAL_TRACK_TRIGGER_RE

    def _match(self, text):
        self.assertIsNotNone(self.RE.search(text), f"Expected match: {text!r}")

    def _no_match(self, text):
        self.assertIsNone(self.RE.search(text), f"Expected NO match: {text!r}")

    def test_track_it(self):
        self._match("Position: HSE Officer. Company: Acme. Track it.")

    def test_track_this(self):
        self._match("Track this please")

    def test_add_it_to_pipeline(self):
        self._match("add it to my pipeline")

    def test_save_it_to_applications(self):
        self._match("save it to applications")

    def test_arabic_track(self):
        self._match("الوظيفة: مهندس. الشركة: أكمي. تتبعها")

    def test_no_match_plain_search(self):
        self._no_match("find me HSE Officer jobs in Dubai")

    def test_no_match_pasted_posting(self):
        self._no_match("Position: HSE Officer\nCompany: Acme\nLocation: Dubai")

    def test_no_match_track_record(self):
        self._no_match("I have a strong track record in safety")


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

class TestManualTrackFieldExtraction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        mod = _mod()
        cls.TITLE_RE = mod._MANUAL_TRACK_TITLE_RE
        cls.COMPANY_RE = mod._MANUAL_TRACK_COMPANY_RE

    def test_single_line_title_stops_at_period(self):
        msg = "Position: HSE Officer. Company: Acme LLC. Track it."
        self.assertEqual(self.TITLE_RE.search(msg).group(1).strip(), "HSE Officer")

    def test_single_line_company_stops_at_period(self):
        msg = "Position: HSE Officer. Company: Acme LLC. Track it."
        self.assertEqual(self.COMPANY_RE.search(msg).group(1).strip(), "Acme LLC")

    def test_multiline_fields(self):
        msg = "Position: QHSE Manager\nCompany: Emirates Steel\nTrack it"
        self.assertEqual(self.TITLE_RE.search(msg).group(1).strip(), "QHSE Manager")
        self.assertEqual(self.COMPANY_RE.search(msg).group(1).strip(), "Emirates Steel")

    def test_job_title_label(self):
        msg = "Job title: Safety Engineer. Employer: ADNOC. Track it."
        self.assertEqual(self.TITLE_RE.search(msg).group(1).strip(), "Safety Engineer")
        self.assertEqual(self.COMPANY_RE.search(msg).group(1).strip(), "ADNOC")

    def test_missing_company_returns_none(self):
        self.assertIsNone(self.COMPANY_RE.search("Position: HSE Officer. Track it."))

    def test_missing_title_returns_none(self):
        self.assertIsNone(self.TITLE_RE.search("Company: Acme. Track it."))


# ---------------------------------------------------------------------------
# Handler honesty — _handle_manual_application_track
# ---------------------------------------------------------------------------

def _make_chat_api():
    from src.rico_chat_api import RicoChatAPI
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._append_chat = MagicMock()
    api._store_recent_context = MagicMock()
    api._build_recent_application_context = MagicMock(return_value={})
    return api


class TestManualApplicationTrackHandler(unittest.TestCase):

    def setUp(self):
        self.api = _make_chat_api()

    def test_success_only_when_db_write_returns_true(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=True) as cm:
            result = self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        cm.assert_called_once_with(
            title="HSE Officer", company="Acme LLC", status="saved", user_id="u1"
        )
        self.assertEqual(result["type"], "track_job")
        self.assertEqual(result["job_status"], "saved")
        self.assertIn("Tracked", result["message"])
        self.assertEqual(result["target_route"], "/applications")

    def test_failure_when_db_write_returns_false(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=False):
            result = self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.assertEqual(result["type"], "track_job_failed")
        self.assertIsNone(result["job_status"])
        self.assertNotIn("Tracked", result["message"])

    def test_failure_when_db_write_raises(self):
        with patch(
            "src.repositories.applications_repo.create_manual",
            side_effect=RuntimeError("db down"),
        ):
            result = self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.assertEqual(result["type"], "track_job_failed")
        self.assertNotIn("Tracked", result["message"])

    def test_success_records_recent_context(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=True):
            self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.api._store_recent_context.assert_called_once()

    def test_failure_does_not_record_recent_context(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=False):
            self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.api._store_recent_context.assert_not_called()

    def test_arabic_success_reply(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=True):
            result = self.api._handle_manual_application_track(
                "u1", "مهندس سلامة", "أكمي", arabic=True
            )
        self.assertEqual(result["type"], "track_job")
        self.assertIn("تم", result["message"])

    def test_arabic_failure_reply_never_claims_success(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=False):
            result = self.api._handle_manual_application_track(
                "u1", "مهندس سلامة", "أكمي", arabic=True
            )
        self.assertEqual(result["type"], "track_job_failed")
        self.assertNotIn("تم —", result["message"])

    def test_append_chat_always_called(self):
        with patch("src.repositories.applications_repo.create_manual", return_value=True):
            self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.api._append_chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
