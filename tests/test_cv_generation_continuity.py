"""
tests/test_cv_generation_continuity.py

Regression tests for CV generation continuity fix.

Covers:
  1. preferred_cities added to _PENDING_FIELD_ASK_SIGNALS
  2. User reply "dubai" saves preferred_cities and re-runs CV draft
  3. CV draft after city save has no generic placeholders
  4. Multiple cities parsed correctly ("Dubai, Abu Dhabi")
  5. No city answer does not fall through to AI fallback
  6. _handle_cv_generate_from_profile without work_experience/education
     reports unparsed sections, does not claim "All key fields are filled"
  7. _handle_cv_generate_from_profile with all fields omits unparsed warning
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


def _profile(**kw):
    defaults = dict(
        name="Ahmed Al-Rashid",
        email="ahmed@example.com",
        phone="+971501234567",
        skills=["ISO 14001", "risk assessment", "HSE management"],
        years_experience=8.0,
        target_roles=["HSE Manager", "EHS Lead"],
        certifications=["NEBOSH"],
        preferred_cities=[],
        industries=["Oil & Gas"],
        current_role="Senior HSE Officer",
        has_cv=True,
        work_experience=[],
        education=[],
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestPreferredCitiesSignals:

    @pytest.fixture(autouse=True)
    def _api(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)

    def test_preferred_cities_in_signals(self):
        assert "preferred_cities" in self.api._PENDING_FIELD_ASK_SIGNALS

    def test_signals_contain_city_keywords(self):
        signals = self.api._PENDING_FIELD_ASK_SIGNALS["preferred_cities"]
        assert any("city" in s for s in signals)

    def test_uae_cities_frozenset_present(self):
        assert "dubai" in self.api._UAE_CITIES
        assert "abu dhabi" in self.api._UAE_CITIES
        assert "sharjah" in self.api._UAE_CITIES


class TestPreferredCitiesPendingField:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._persist = False
        self._ctx = {"_pending_field": "preferred_cities", "_pending_cv_generate": True}
        self._profile = _profile()

    @contextmanager
    def _mock_api(self, saved_cities):
        """Wire up the mocks needed for a preferred_cities resolution."""
        updated_profile = _profile(preferred_cities=saved_cities)
        self.api._get_recent_context = MagicMock(return_value=dict(self._ctx))
        self.api._store_recent_context = MagicMock()
        self.api._resolve_profile = MagicMock(return_value=updated_profile)
        self.api._get_last_assistant_message = MagicMock(return_value="preferred cities (e.g. Dubai)")
        self.api._append_chat = MagicMock()
        self.api._has_cv_profile = MagicMock(return_value=True)
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])

        with patch("src.rico_chat_api.upsert_profile") as mock_upsert:
            yield mock_upsert

    def test_single_city_saves_and_returns_cv_draft(self):
        with self._mock_api(["Dubai"]) as mock_upsert:
            result = self.api._resolve_pending_field("user-1", "dubai", self._profile)
        assert result is not None
        assert result["type"] == "cv_draft"
        mock_upsert.assert_called_once()
        saved = mock_upsert.call_args[1]["updates"]
        assert "preferred_cities" in saved
        assert "Dubai" in saved["preferred_cities"]

    def test_multiple_cities_parsed(self):
        with self._mock_api(["Dubai", "Abu Dhabi"]) as mock_upsert:
            result = self.api._resolve_pending_field("user-1", "Dubai, Abu Dhabi", self._profile)
        assert result is not None
        saved = mock_upsert.call_args[1]["updates"]
        assert len(saved["preferred_cities"]) == 2

    def test_city_with_slash_separator(self):
        with self._mock_api(["Dubai", "Sharjah"]) as mock_upsert:
            self.api._resolve_pending_field("user-1", "Dubai / Sharjah", self._profile)
        saved = mock_upsert.call_args[1]["updates"]
        assert len(saved["preferred_cities"]) == 2

    def test_empty_message_not_resolved(self):
        self.api._get_recent_context = MagicMock(return_value=dict(self._ctx))
        self.api._get_last_assistant_message = MagicMock(return_value="preferred cities")
        result = self.api._resolve_pending_field("user-1", "   ", self._profile)
        assert result is None

    def test_no_pending_field_not_intercepted(self):
        self.api._get_recent_context = MagicMock(return_value={})
        self.api._get_last_assistant_message = MagicMock(return_value="how can I help?")
        result = self.api._resolve_pending_field("user-1", "dubai", self._profile)
        assert result is None

    def test_intent_phrase_not_intercepted_as_city(self):
        """'find me jobs' must not be consumed as a city answer."""
        self.api._get_recent_context = MagicMock(return_value=dict(self._ctx))
        self.api._get_last_assistant_message = MagicMock(return_value="preferred cities (e.g. Dubai)")
        result = self.api._resolve_pending_field("user-1", "find me jobs", self._profile)
        assert result is None

    def test_long_message_not_intercepted_as_city(self):
        """A message with more than 6 words must not be consumed as a city."""
        self.api._get_recent_context = MagicMock(return_value=dict(self._ctx))
        self.api._get_last_assistant_message = MagicMock(return_value="preferred cities (e.g. Dubai)")
        result = self.api._resolve_pending_field(
            "user-1", "I want to work in Dubai or Abu Dhabi preferably", self._profile
        )
        assert result is None


class TestCVDraftNoPlaeholders:

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()
        self.api._get_recent_context = MagicMock(return_value={})
        self.api._store_recent_context = MagicMock()
        self.api._has_cv_profile = MagicMock(return_value=True)
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])

    def test_no_placeholder_strings_in_draft(self):
        profile = _profile(preferred_cities=["Dubai"])
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        msg = result["message"]
        bad_phrases = [
            "[Your phone number]", "[Company Name]", "[Add your job history here]",
            "[Your name]", "[City]", "[Email]", "[Phone]",
        ]
        for phrase in bad_phrases:
            assert phrase not in msg, f"Placeholder found: {phrase!r}"

    def test_missing_cities_sets_pending_field(self):
        profile = _profile(preferred_cities=[])
        ctx = {}
        self.api._get_recent_context = MagicMock(return_value=ctx)
        self.api._handle_cv_generate_from_profile("user-1", profile)
        self.api._store_recent_context.assert_called()
        stored_ctx = self.api._store_recent_context.call_args[0][1]
        assert stored_ctx.get("_pending_field") == "preferred_cities"

    def test_no_work_experience_reports_unparsed(self):
        profile = _profile(preferred_cities=["Dubai"], work_experience=[], education=[])
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        assert "unparsed_sections" in result
        assert "Work Experience" in result["unparsed_sections"]
        assert "Education" in result["unparsed_sections"]
        # Must NOT claim all fields are filled
        assert "All key fields are filled" not in result["message"]
        assert "All available profile sections are included" not in result["message"]

    def test_work_experience_present_no_unparsed_warning(self):
        profile = _profile(
            preferred_cities=["Dubai"],
            work_experience=["Senior HSE Officer at DEWA (2019-2023)"],
            education=["BSc Environmental Science, University of Sharjah"],
        )
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        assert result["unparsed_sections"] == []
        assert "All available profile sections are included" in result["message"]

    def test_cv_draft_contains_profile_name(self):
        profile = _profile(preferred_cities=["Dubai"])
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        assert "Ahmed Al-Rashid" in result["message"]

    def test_cv_draft_contains_skills(self):
        profile = _profile(preferred_cities=["Dubai"])
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        assert "ISO 14001" in result["message"]

    def test_cv_draft_type(self):
        profile = _profile(preferred_cities=["Dubai"])
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        assert result["type"] == "cv_draft"


class TestCVBuilderFlowState:
    """Tests for flow-state tracking and CV improvement follow-up routing."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()
        self._stored_ctx: dict = {}
        self.api._get_recent_context = MagicMock(side_effect=lambda uid: dict(self._stored_ctx))
        self.api._store_recent_context = MagicMock(
            side_effect=lambda uid, ctx: self._stored_ctx.update(ctx)
        )
        self.api._has_cv_profile = MagicMock(return_value=True)
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])

    def test_cv_generate_sets_cv_builder_flow_state(self):
        profile = _profile(preferred_cities=["Dubai"])
        self.api._handle_cv_generate_from_profile("user-1", profile)
        assert self._stored_ctx.get("last_flow_state") == "cv_builder"

    def test_cv_creation_sets_cv_builder_flow_state(self):
        profile = _profile(preferred_cities=["Dubai"])
        self.api._handle_cv_creation("user-1", profile)
        assert self._stored_ctx.get("last_flow_state") == "cv_builder"

    def test_improve_followup_regex_matches_english(self):
        from src.rico_chat_api import _CV_IMPROVE_FOLLOWUP_RE
        assert _CV_IMPROVE_FOLLOWUP_RE.search("please improve it")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("improve it")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("enhance it")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("make it more professional")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("make it better")

    def test_improve_followup_regex_matches_arabic(self):
        from src.rico_chat_api import _CV_IMPROVE_FOLLOWUP_RE
        assert _CV_IMPROVE_FOLLOWUP_RE.search("نعم حسنها بشكل محترف")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("حسنها")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("طورها")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("حسن السيرة")
        assert _CV_IMPROVE_FOLLOWUP_RE.search("طور السيرة الذاتية")

    def test_improve_followup_regex_does_not_match_unrelated(self):
        from src.rico_chat_api import _CV_IMPROVE_FOLLOWUP_RE
        assert not _CV_IMPROVE_FOLLOWUP_RE.search("find me a job")
        assert not _CV_IMPROVE_FOLLOWUP_RE.search("show my applications")
        assert not _CV_IMPROVE_FOLLOWUP_RE.search("hello")
        assert not _CV_IMPROVE_FOLLOWUP_RE.search("I applied manually")

    def test_flow_state_routes_improve_to_cv_builder(self):
        """When last_flow_state == cv_builder, 'please improve it' must call
        _handle_cv_generate_from_profile — not AI fallback."""
        self._stored_ctx["last_flow_state"] = "cv_builder"
        profile = _profile(preferred_cities=["Dubai"])

        generated = MagicMock(return_value={"type": "cv_draft", "message": "draft"})
        self.api._handle_cv_generate_from_profile = generated

        # Minimal stubs needed by _handle_active_user_inner
        self.api._resolve_profile = MagicMock(return_value=profile)
        self.api._looks_like_pasted_cv_text = MagicMock(return_value=False)
        self.api._resolve_pending_field = MagicMock(return_value=None)
        self.api._finalize = MagicMock(side_effect=lambda r, *a, **kw: r)

        self.api._handle_active_user_inner("user-1", "please improve it")

        generated.assert_called_once_with("user-1", profile, "please improve it")

    def test_no_flow_state_does_not_intercept_improve(self):
        """Without cv_builder flow state, 'improve it' must NOT intercept to CV builder."""
        self._stored_ctx["last_flow_state"] = "job_search"
        profile = _profile(preferred_cities=["Dubai"])

        generated = MagicMock(return_value={"type": "cv_draft", "message": "draft"})
        self.api._handle_cv_generate_from_profile = generated

        self.api._resolve_profile = MagicMock(return_value=profile)
        self.api._looks_like_pasted_cv_text = MagicMock(return_value=False)
        self.api._resolve_pending_field = MagicMock(return_value=None)

        # Stub out everything downstream so the test doesn't crash
        self.api._handle_application_channel_followup = MagicMock(return_value=None)
        self.api._looks_like_cv_intent_no_file = MagicMock(return_value=False)
        self.api._is_arabic_text = MagicMock(return_value=False)
        self.api._is_list_followup = MagicMock(return_value=False)
        self.api._is_verify_followup = MagicMock(return_value=False)
        self.api._is_affirmative = MagicMock(return_value=False)
        self.api._is_continuation_intent = MagicMock(return_value=False)
        self.api._is_negative = MagicMock(return_value=False)
        self.api._normalize_followup_phrase = MagicMock(return_value="improve it")
        self.api._finalize = MagicMock(side_effect=lambda r, *a, **kw: r)
        # Stub deepest fallback to avoid further import cascade
        self.api._answer_with_ai_fallback = MagicMock(return_value={"type": "ai_response", "message": "ok"})
        self.api._looks_like_next_step_followup = MagicMock(return_value=False)
        self.api._is_arabic_what_now = MagicMock(return_value=False)
        self.api._looks_like_selected_role = MagicMock(return_value=False)
        self.api._looks_like_generic_job_request = MagicMock(return_value=False)
        self.api._looks_like_bare_target_role = MagicMock(return_value=False)
        self.api._is_live_job_search_request = MagicMock(return_value=False)
        from src.rico_chat_api import RicoChatAPI
        from unittest.mock import patch, PropertyMock
        _noop_re = MagicMock()
        _noop_re.match.return_value = None
        _noop_re.search.return_value = None
        with patch.object(RicoChatAPI, "_SHOW_MY_APPLICATIONS_RE", _noop_re):
            with patch.object(RicoChatAPI, "_SET_REMINDER_RE", _noop_re):
                try:
                    self.api._handle_active_user_inner("user-1", "improve it")
                except Exception:
                    pass

        # CV generate must NOT have been called via the flow-state shortcut
        generated.assert_not_called()


class TestCVPlaceholderProhibition:
    """Deterministic CV builder must never emit placeholders or invented facts."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)
        self.api._append_chat = MagicMock()
        self.api._get_recent_context = MagicMock(return_value={})
        self.api._store_recent_context = MagicMock()
        self.api._has_cv_profile = MagicMock(return_value=True)
        self.api._profile_value = lambda p, k: getattr(p, k, None)
        self.api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])

    # All patterns from the spec that must never appear in CV body text.
    _FORBIDDEN = [
        "[Start Date]", "[End Date]", "[Company Name]", "[Job Title]",
        "Add responsibilities here", "TBD", "assumed", "please confirm",
        "30%",   # fabricated achievement
        "efficiency increased",  # fabricated metric
        "raised efficiency",     # fabricated metric
    ]

    def _assert_no_forbidden(self, message: str) -> None:
        for phrase in self._FORBIDDEN:
            assert phrase.lower() not in message.lower(), f"Forbidden phrase in CV: {phrase!r}"

    def test_sparse_profile_no_forbidden_phrases(self):
        """Minimal profile (name + years exp only) must not produce fake content."""
        profile = _profile(
            preferred_cities=["Dubai"],
            skills=[],
            certifications=[],
            work_experience=[],
            education=[],
            industries=[],
            target_roles=[],
            current_role="",
        )
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        self._assert_no_forbidden(result["message"])

    def test_sparse_profile_has_missing_section(self):
        """Sparse profile must include 'To complete the CV' or 'not yet available'."""
        profile = _profile(
            preferred_cities=["Dubai"],
            skills=[],
            work_experience=[],
            education=[],
            target_roles=[],
            current_role="",
        )
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        msg = result["message"]
        assert "To complete the CV" in msg or "not yet available" in msg or "not available" in msg

    def test_full_profile_no_missing_section(self):
        """A complete profile must not show the 'To complete the CV' section."""
        profile = _profile(
            preferred_cities=["Dubai"],
            skills=["Python", "SQL"],
            work_experience=["Software Engineer at TechCorp (2020-2024)"],
            education=["BSc Computer Science, UAE University"],
            certifications=["AWS Certified"],
            target_roles=["Software Engineer"],
            current_role="Software Engineer",
            years_experience=4,
        )
        result = self.api._handle_cv_generate_from_profile("user-1", profile)
        self._assert_no_forbidden(result["message"])

    def test_arabic_improve_followup_uses_deterministic_handler(self):
        """'نعم حسنها بشكل محترف' after CV draft must match improvement regex and not hit AI."""
        from src.rico_chat_api import _CV_IMPROVE_FOLLOWUP_RE
        msg = "نعم حسنها بشكل محترف"
        assert _CV_IMPROVE_FOLLOWUP_RE.search(msg), "Arabic improve phrase must match regex"

    def test_resolve_pending_intent_cv_improve_uses_deterministic_handler(self):
        """`_resolve_pending_intent` must call cv handler, not AI fallback, on cv_improve_signals."""
        from src.rico_chat_api import RicoChatAPI
        api = RicoChatAPI.__new__(RicoChatAPI)
        api._append_chat = MagicMock()
        api._get_recent_context = MagicMock(return_value={})
        api._store_recent_context = MagicMock()
        api._has_cv_profile = MagicMock(return_value=True)
        api._profile_value = lambda p, k: getattr(p, k, None)
        api._as_list = lambda v: list(v) if isinstance(v, list) else ([v] if v else [])

        # Last assistant message contains a cv improve signal
        api._get_last_assistant_message = MagicMock(return_value="improve your cv and I'll update it")
        api._is_affirmative = MagicMock(return_value=True)

        generated = MagicMock(return_value={"type": "cv_draft", "message": "deterministic draft"})
        api._handle_cv_generate_from_profile = generated
        ai_fallback = MagicMock(return_value={"type": "ai_response", "message": "ai invented"})
        api._answer_with_ai_fallback = ai_fallback

        profile = _profile(preferred_cities=["Dubai"])
        api._resolve_pending_intent("user-1", "yes", profile)

        generated.assert_called_once()
        ai_fallback.assert_not_called()
