"""
Tests for P0 bugs found during adversarial QA of the /command chat.

Root cause: intent classification runs before entity/state resolution, and
the resolver does not read the last rendered result set when in-process
memory context is empty (RICO_MEMORY_BACKEND=postgres mode).

Bugs covered:
  BUG-A: Ordinal follow-up ("Open the second one") fails with "No recent job search"
         when recent_search_matches is absent from in-process memory context.
         Fix: DB fallback in _handle_job_detail() via get_recent_matches().

  BUG-B: Bare company name ("Majid Al Futtaim") is treated as an unknown job role.
         Fix: _classified_role_search() checks recent match companies before
         emitting the "not a job role" error.

  BUG-C: Natural language URL request ("give me the URL") is misrouted — does not
         reach the open_apply_link handler.
         Fix: _OPEN_APPLY_LINK_RE extended to match common URL request phrases.

  BUG-D: job_detail response silently omits the apply link when it is missing.
         Fix: _handle_job_detail() now shows an explicit "No apply link" note.
"""
from __future__ import annotations

import re
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# BUG-C: Intent classifier must route URL requests to open_apply_link
# ---------------------------------------------------------------------------

class TestOpenApplyLinkIntentExtended:
    """_OPEN_APPLY_LINK_RE must match natural language URL requests."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.agent.intelligence.intent_classifier import _OPEN_APPLY_LINK_RE
        self.re = _OPEN_APPLY_LINK_RE

    def _matches(self, text: str) -> bool:
        return bool(self.re.search(text))

    # --- New patterns that should match ---
    def test_give_me_the_url(self):
        assert self._matches("give me the URL")

    def test_give_me_the_link(self):
        assert self._matches("give me the link")

    def test_send_me_the_link(self):
        assert self._matches("send me the link")

    def test_share_the_apply_link(self):
        assert self._matches("share the apply link")

    def test_show_me_the_url(self):
        assert self._matches("show me the URL")

    def test_whats_the_link(self):
        assert self._matches("what's the link")

    def test_what_is_the_apply_link(self):
        assert self._matches("what is the apply link")

    def test_where_can_i_apply(self):
        assert self._matches("where can I apply")

    def test_where_do_i_apply(self):
        assert self._matches("where do I apply")

    def test_apply_link_please(self):
        assert self._matches("apply link please")

    # --- Original pattern still matches ---
    def test_open_apply_link_original(self):
        assert self._matches("open apply link")

    def test_open_apply_link_with_title(self):
        assert self._matches("open apply link for HSE Manager at ADNOC")

    # --- Should NOT match unrelated messages ---
    def test_no_match_search(self):
        assert not self._matches("search for HSE jobs")

    def test_no_match_tell_me_more(self):
        assert not self._matches("tell me more about that job")

    def test_no_match_apply_to_all(self):
        # "where" appears in the message but not with "can I apply" / "do I apply"
        # The regex should not over-fire on job search messages
        assert not self._matches("where are jobs in Dubai")


# ---------------------------------------------------------------------------
# BUG-A: _handle_job_detail() must fall back to DB when in-memory context empty
# ---------------------------------------------------------------------------

def _make_rico_api():
    """Construct a RicoChatAPI instance with all external deps mocked."""
    from src.rico_chat_api import RicoChatAPI
    with (
        patch("src.rico_memory.RicoMemoryStore.__init__", return_value=None),
        patch("src.rico_agent.RicoAgent.__init__", return_value=None),
        patch("src.rico_openai_agent.RicoOpenAIAgent.__init__", return_value=None),
        patch("src.rico_repo_adapter.RicoSystem.__init__", return_value=None),
    ):
        api = object.__new__(RicoChatAPI)
    # Minimal memory mock
    api.memory = MagicMock()
    api.memory.get_context.return_value = None
    api.memory.append_chat_message = MagicMock()
    api._persist = False
    return api


class TestHandleJobDetailDBFallback:
    """_handle_job_detail() must use DB matches when in-memory context is empty."""

    def test_returns_job_detail_from_db_when_memory_empty(self):
        """When recent_search_matches is absent from memory, DB fallback supplies data."""
        api = _make_rico_api()
        db_matches = [
            {"title": "HSE Manager", "company": "ADNOC", "location": "Abu Dhabi",
             "apply_url": "https://example.com/apply", "source_url": "", "link": "https://example.com/apply",
             "verification_status": "live"},
            {"title": "QHSE Officer", "company": "Emirates Steel", "location": "Dubai",
             "apply_url": "", "source_url": "https://emiratessteel.com/jobs", "link": "",
             "verification_status": "lead_needs_verification"},
        ]

        with patch("src.repositories.user_job_context_repo.get_recent_matches",
                   return_value=db_matches):
            result = api._handle_job_detail("user@test.com", None, "tell me more about the first job")

        assert result["type"] == "job_detail"
        assert "HSE Manager" in result["message"]
        assert "ADNOC" in result["message"]

    def test_ordinal_second_uses_db_index_1(self):
        """'Open the second one' with DB fallback must resolve to index 1."""
        api = _make_rico_api()
        db_matches = [
            {"title": "HSE Manager", "company": "ADNOC", "location": "Abu Dhabi",
             "apply_url": "https://adnoc.ae/apply", "source_url": "", "link": "",
             "verification_status": "live"},
            {"title": "QHSE Officer", "company": "Emirates Steel", "location": "Dubai",
             "apply_url": "https://emiratessteel.com/apply", "source_url": "", "link": "",
             "verification_status": "live"},
        ]

        with patch("src.repositories.user_job_context_repo.get_recent_matches",
                   return_value=db_matches):
            result = api._handle_job_detail(
                "user@test.com", None, "open the second one", ordinal_hint="2"
            )

        assert result["type"] == "job_detail"
        assert "QHSE Officer" in result["message"]
        assert "Emirates Steel" in result["message"]

    def test_returns_clarification_when_db_also_empty(self):
        """When both memory and DB are empty, returns 'No recent job search' clarification."""
        api = _make_rico_api()

        with patch("src.repositories.user_job_context_repo.get_recent_matches", return_value=[]):
            result = api._handle_job_detail("user@test.com", None, "tell me more")

        assert result["type"] == "clarification"
        assert "recent job search" in result["message"].lower() or "بحث حديث" in result["message"]


# ---------------------------------------------------------------------------
# BUG-D: job_detail must show explicit "no apply link" instead of silent skip
# ---------------------------------------------------------------------------

class TestHandleJobDetailNoLinkMessage:

    def test_shows_source_url_when_apply_url_missing(self):
        """When apply_url is empty but source_url exists, show source link."""
        api = _make_rico_api()
        db_matches = [
            {"title": "Finance Analyst", "company": "DP World", "location": "Dubai",
             "apply_url": "", "source_url": "https://dpworld.com/jobs/123",
             "link": "", "verification_status": "lead_needs_verification"},
        ]

        with patch("src.repositories.user_job_context_repo.get_recent_matches",
                   return_value=db_matches):
            result = api._handle_job_detail("user@test.com", None, "tell me more")

        assert "dpworld.com" in result["message"]
        assert "source listing" in result["message"].lower()

    def test_shows_no_link_message_when_both_missing(self):
        """When both apply_url and source_url are empty, show explicit no-link notice."""
        api = _make_rico_api()
        db_matches = [
            {"title": "Project Engineer", "company": "DEWA", "location": "Dubai",
             "apply_url": "", "source_url": "", "link": "",
             "verification_status": "lead_needs_verification"},
        ]

        with patch("src.repositories.user_job_context_repo.get_recent_matches",
                   return_value=db_matches):
            result = api._handle_job_detail("user@test.com", None, "tell me more")

        assert result["type"] == "job_detail"
        # Must say something about no link — not silently omit
        msg_lower = result["message"].lower()
        assert "no apply link" in msg_lower or "careers page" in msg_lower or "no direct" in msg_lower


# ---------------------------------------------------------------------------
# BUG-B: _classified_role_search() must detect bare company names
# ---------------------------------------------------------------------------

class TestClassifiedRoleSearchCompanyFallback:

    def test_bare_company_name_from_recent_memory_routes_to_company_search(self):
        """'Majid Al Futtaim' matches a company in recent memory → company search."""
        api = _make_rico_api()
        # recent_search_matches has "Majid Al Futtaim" as a company
        ctx_with_company = {
            "recent_search_matches": [
                {"title": "Retail Manager", "company": "Majid Al Futtaim",
                 "location": "Dubai", "apply_url": ""},
            ]
        }
        api.memory.get_context.return_value = ctx_with_company

        company_search_result = {"type": "job_matches", "message": "Found jobs at Majid Al Futtaim", "matches": []}

        with patch.object(api, "_handle_company_search", return_value=company_search_result) as mock_co:
            # Signature: (self, user_id, role_text, profile, ...)
            result = api._classified_role_search("user@test.com", "Majid Al Futtaim", None)

        mock_co.assert_called_once()
        call_args = mock_co.call_args
        # The constructed message should include "jobs at Majid Al Futtaim"
        assert "Majid Al Futtaim" in call_args[0][2]
        assert result == company_search_result

    def test_bare_company_name_from_db_routes_to_company_search(self):
        """Bare company name from DB fallback (memory empty) → company search."""
        api = _make_rico_api()
        # Memory context is empty
        api.memory.get_context.return_value = {}
        db_matches = [
            {"title": "Accountant", "company": "Etisalat", "location": "Abu Dhabi",
             "apply_url": "", "source_url": ""},
        ]

        company_search_result = {"type": "job_matches", "message": "Found jobs at Etisalat", "matches": []}

        with (
            patch("src.repositories.user_job_context_repo.get_recent_matches", return_value=db_matches),
            patch.object(api, "_handle_company_search", return_value=company_search_result) as mock_co,
        ):
            result = api._classified_role_search("user@test.com", "Etisalat", None)

        mock_co.assert_called_once()
        assert result == company_search_result

    def test_unknown_role_not_company_emits_clarification(self):
        """Genuinely unknown role (not in recent matches) → clarification message."""
        api = _make_rico_api()
        api.memory.get_context.return_value = {}

        with patch("src.repositories.user_job_context_repo.get_recent_matches", return_value=[]):
            result = api._classified_role_search("user@test.com", "XYZUnknownRole", None)

        assert result["type"] == "clarification"
        assert "XYZUnknownRole" in result["message"]
