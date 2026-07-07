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


class TestManualTrackNegationRegex(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RE = _mod()._MANUAL_TRACK_NEGATION_RE

    def test_dont_track_it(self):
        self.assertIsNotNone(self.RE.search("Position: X. Company: Y. Don't track it."))

    def test_do_not_track(self):
        self.assertIsNotNone(self.RE.search("please do not track this one"))

    def test_arabic_negation(self):
        self.assertIsNotNone(self.RE.search("لا تتبعها"))

    def test_plain_track_it_not_negated(self):
        self.assertIsNone(self.RE.search("Position: X. Company: Y. Track it."))

    def test_arabic_la_ureed_tatabu3(self):
        self.assertIsNotNone(self.RE.search("\u0644\u0627 \u0623\u0631\u064a\u062f \u062a\u062a\u0628\u0639\u0647\u0627"))

    def test_arabic_la_areed_no_hamza(self):
        self.assertIsNotNone(self.RE.search("\u0644\u0627 \u0627\u0631\u064a\u062f \u062a\u062a\u0628\u0639\u0647\u0627"))

    def test_arabic_la_tahfazha(self):
        self.assertIsNotNone(self.RE.search("\u0644\u0627 \u062a\u062d\u0641\u0638\u0647\u0627"))

    def test_arabic_la_tusajjilha(self):
        self.assertIsNotNone(self.RE.search("\u0644\u0627 \u062a\u0633\u062c\u0644\u0647\u0627"))

    def test_arabic_mish_biddi(self):
        self.assertIsNotNone(self.RE.search("\u0645\u0634 \u0628\u062f\u064a \u062a\u062a\u0628\u0639\u0647\u0627"))

    def test_arabic_bidoon_tatabu3(self):
        self.assertIsNotNone(self.RE.search("\u0628\u062f\u0648\u0646 \u062a\u062a\u0628\u0639"))

    def test_arabic_plain_track_not_negated(self):
        self.assertIsNone(
            self.RE.search("\u0627\u0644\u0648\u0638\u064a\u0641\u0629: \u0645\u0647\u0646\u062f\u0633 \u0633\u0644\u0627\u0645\u0629. \u0627\u0644\u0634\u0631\u0643\u0629: \u0634\u0631\u0643\u0629 \u0627\u0644\u062e\u0644\u064a\u062c. \u062a\u062a\u0628\u0639\u0647\u0627")
        )


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

    def test_unpunctuated_single_line_stops_at_next_label(self):
        msg = "Position: HSE Officer Company: Acme LLC Track it"
        self.assertEqual(self.TITLE_RE.search(msg).group(1).strip(), "HSE Officer")
        self.assertEqual(self.COMPANY_RE.search(msg).group(1).strip(), "Acme LLC")


class TestManualTrackPunctuationPreserved(unittest.TestCase):
    """Internal punctuation in titles/companies must survive extraction."""

    @classmethod
    def setUpClass(cls):
        mod = _mod()
        cls.TITLE_RE = mod._MANUAL_TRACK_TITLE_RE
        cls.COMPANY_RE = mod._MANUAL_TRACK_COMPANY_RE
        cls.field = staticmethod(mod._manual_track_field)

    def _title(self, msg):
        m = self.TITLE_RE.search(msg)
        self.assertIsNotNone(m, f"no title match: {msg!r}")
        return _mod()._manual_track_field(m, msg)

    def _company(self, msg):
        m = self.COMPANY_RE.search(msg)
        self.assertIsNotNone(m, f"no company match: {msg!r}")
        return _mod()._manual_track_field(m, msg)

    def test_abbreviated_title_sr(self):
        msg = "Position: Sr. HSE Officer. Company: Acme. Track it."
        self.assertEqual(self._title(msg), "Sr. HSE Officer")

    def test_title_with_comma(self):
        msg = "Position: Senior Manager, HSE. Company: Acme. Track it."
        self.assertEqual(self._title(msg), "Senior Manager, HSE")

    def test_title_with_hyphen_and_ampersand(self):
        msg = "Position: QHSE Manager - Oil & Gas. Company: Acme. Track it."
        self.assertEqual(self._title(msg), "QHSE Manager - Oil & Gas")

    def test_company_with_comma_and_abbrev_dot(self):
        msg = "Position: HSE Officer. Company: Acme, Inc. Track it."
        self.assertEqual(self._company(msg), "Acme, Inc.")

    def test_company_llc_keeps_no_trailing_dot(self):
        msg = "Position: HSE Officer. Company: Falcon Marine LLC. Track it."
        self.assertEqual(self._company(msg), "Falcon Marine LLC")

    def test_company_ltd_keeps_dot_at_end_of_message(self):
        msg = "Position: HSE Officer. Company: Gulf Safety Co. Track it."
        self.assertEqual(self._company(msg), "Gulf Safety Co.")


class TestManualTrackFirstTurnNoProfile(unittest.TestCase):
    """A structured track instruction on a fresh account's first turn must not
    be swallowed by onboarding — it routes straight to the active handler."""

    def _api(self):
        from src.rico_chat_api import RicoChatAPI

        api = RicoChatAPI.__new__(RicoChatAPI)
        api._append_chat = MagicMock()
        api._handle_file_list_query = MagicMock(return_value=None)
        api._get_recent_upload_document_reply = MagicMock(return_value=None)
        api._handle_uploaded_document_followup = MagicMock(return_value=None)
        api._handle_active_user = MagicMock(return_value={"type": "track_job"})
        return api

    def test_structured_track_bypasses_onboarding(self):
        api = self._api()
        with patch("src.rico_chat_api.is_onboarding_complete") as onboarding:
            result = api._process_message_inner(
                "u1", "Position: HSE Officer. Company: Acme. Track it."
            )
        api._handle_active_user.assert_called_once()
        onboarding.assert_not_called()
        self.assertEqual(result["type"], "track_job")

    def test_negated_track_does_not_bypass_onboarding(self):
        api = self._api()
        api._message_requires_job_profile = MagicMock(return_value=False)
        with patch("src.rico_chat_api.is_onboarding_complete", return_value=True) as onboarding:
            api._process_message_inner(
                "u1", "Position: HSE Officer. Company: Acme. Don't track it."
            )
        onboarding.assert_called_once()


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

    def test_saved_jobs_limit_402_returns_upgrade_cta(self):
        from fastapi import HTTPException

        with patch(
            "src.repositories.applications_repo.create_manual",
            side_effect=HTTPException(status_code=402, detail="limit"),
        ):
            result = self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.assertEqual(result["type"], "track_job_limit_reached")
        self.assertEqual(result["target_route"], "/subscription")
        self.assertNotIn("Tracked", result["message"])
        self.assertNotIn("try again shortly", result["message"])

    def test_non_402_http_exception_is_honest_failure(self):
        from fastapi import HTTPException

        with patch(
            "src.repositories.applications_repo.create_manual",
            side_effect=HTTPException(status_code=503, detail="db down"),
        ):
            result = self.api._handle_manual_application_track("u1", "HSE Officer", "Acme LLC")
        self.assertEqual(result["type"], "track_job_failed")
        self.assertNotIn("Tracked", result["message"])


if __name__ == "__main__":
    unittest.main()
