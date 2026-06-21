"""
tests/test_letter_choice_routing.py

Regression tests for BUG-02 — letter-choice option routing.

Problem:
  When Rico presents options A/B/C/D and the user types "A", Rico was executing
  option B (index off-by-one or wrong mapping).

Covers:
  1. _resolve_letter_choice unit tests:
     - A maps to index 0 (first option)
     - B maps to index 1 (second option)
     - C maps to index 2 (third option)
     - D maps to index 3 (fourth option)
     - lowercase a/b/c/d works identically
     - letter with trailing punctuation ("A." / "B:") works
     - out-of-range index (e.g. D when only 2 options) returns None
     - empty options list returns None
     - no stored options returns None
  2. Strict guard: messages that contain "a" but are not single-letter choices
     (e.g. "apple", "a b", "AB", long sentences) must NOT match.
  3. End-to-end routing: after Rico returns a response with options,
     the user typing "A" dispatches the first option's message, not the second.
  4. _save_pending_options round-trip.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import RicoChatAPI, _LETTER_CHOICE_RE, _NUMBER_CHOICE_RE

USER = "bug02-test@example.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    api.memory.get_context.return_value = None
    api.memory.set_context.return_value = None
    return api


def _api_with_options(options: list) -> RicoChatAPI:
    """Return an API instance whose recent context already contains _pending_options."""
    api = _make_api()
    # Pre-store options so _resolve_letter_choice can find them.
    ctx = {"_pending_options": [
        {"action": o.get("action", ""), "message": o.get("message", ""), "label": o.get("label", "")}
        for o in options
    ]}
    api.memory.get_context.return_value = ctx
    return api


SAMPLE_OPTIONS = [
    {"action": "draft_cover_letter", "label": "Draft cover letter", "message": "draft cover letter for HSE Manager at Dutco Group"},
    {"action": "open_apply_link",    "label": "Open apply link",    "message": "open apply link for HSE Manager at Dutco Group"},
    {"action": "both",               "label": "Both",               "message": "both cover letter and apply link for HSE Manager at Dutco Group"},
    {"action": "search_more",        "label": "Search more",        "message": "find more HSE Manager jobs in UAE"},
]


# ---------------------------------------------------------------------------
# 1. _LETTER_CHOICE_RE regex unit tests
# ---------------------------------------------------------------------------

class TestLetterChoiceRegex:

    def test_uppercase_A_matches(self):
        assert _LETTER_CHOICE_RE.match("A")

    def test_uppercase_B_matches(self):
        assert _LETTER_CHOICE_RE.match("B")

    def test_uppercase_C_matches(self):
        assert _LETTER_CHOICE_RE.match("C")

    def test_uppercase_D_matches(self):
        assert _LETTER_CHOICE_RE.match("D")

    def test_lowercase_a_matches(self):
        assert _LETTER_CHOICE_RE.match("a")

    def test_lowercase_b_matches(self):
        assert _LETTER_CHOICE_RE.match("b")

    def test_lowercase_c_matches(self):
        assert _LETTER_CHOICE_RE.match("c")

    def test_lowercase_d_matches(self):
        assert _LETTER_CHOICE_RE.match("d")

    def test_letter_with_period_matches(self):
        assert _LETTER_CHOICE_RE.match("A.")

    def test_letter_with_colon_matches(self):
        assert _LETTER_CHOICE_RE.match("B:")

    def test_letter_with_trailing_space_matches(self):
        assert _LETTER_CHOICE_RE.match("C ")

    # Negative cases — must NOT match

    def test_apple_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("apple")

    def test_two_letters_AB_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("AB")

    def test_letter_space_letter_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("a b")

    def test_letter_E_outside_range_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("E")

    def test_number_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("1")

    def test_full_sentence_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("apply for the job")

    def test_arabic_does_not_match(self):
        assert not _LETTER_CHOICE_RE.match("نعم")


# ---------------------------------------------------------------------------
# 2. _resolve_letter_choice unit tests
# ---------------------------------------------------------------------------

class TestResolveLetterChoice:

    def test_A_returns_first_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "A")
        assert result == SAMPLE_OPTIONS[0]["message"]

    def test_B_returns_second_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "B")
        assert result == SAMPLE_OPTIONS[1]["message"]

    def test_C_returns_third_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "C")
        assert result == SAMPLE_OPTIONS[2]["message"]

    def test_D_returns_fourth_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "D")
        assert result == SAMPLE_OPTIONS[3]["message"]

    def test_lowercase_a_returns_first_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "a")
        assert result == SAMPLE_OPTIONS[0]["message"]

    def test_lowercase_b_returns_second_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "b")
        assert result == SAMPLE_OPTIONS[1]["message"]

    def test_lowercase_c_returns_third_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "c")
        assert result == SAMPLE_OPTIONS[2]["message"]

    def test_lowercase_d_returns_fourth_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "d")
        assert result == SAMPLE_OPTIONS[3]["message"]

    def test_out_of_range_returns_none(self):
        # Only 2 options stored, "D" (index 3) is out of range
        api = _api_with_options(SAMPLE_OPTIONS[:2])
        result = api._resolve_letter_choice(USER, "D")
        assert result is None

    def test_no_options_returns_none(self):
        api = _make_api()
        api.memory.get_context.return_value = {}
        result = api._resolve_letter_choice(USER, "A")
        assert result is None

    def test_empty_options_returns_none(self):
        api = _api_with_options([])
        result = api._resolve_letter_choice(USER, "A")
        assert result is None

    def test_unrelated_text_returns_none(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "apple")
        assert result is None

    def test_long_sentence_returns_none(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "apply for the job please")
        assert result is None

    def test_options_consumed_after_use(self):
        """After resolving A, a second call with A returns None (options cleared)."""
        stored_ctx: dict = {"_pending_options": [
            {"action": o.get("action", ""), "message": o.get("message", ""), "label": o.get("label", "")}
            for o in SAMPLE_OPTIONS
        ]}
        api = _make_api()
        # Simulate real context round-trip so clear actually sticks
        _ctx_store: dict = {}

        def _fake_get(user, key):
            return _ctx_store.get(key)

        def _fake_set(user, key, value):
            _ctx_store[key] = value

        api.memory.get_context.side_effect = _fake_get
        api.memory.set_context.side_effect = _fake_set
        # Pre-populate context
        _ctx_store["recent_context"] = stored_ctx

        first = api._resolve_letter_choice(USER, "A")
        assert first == SAMPLE_OPTIONS[0]["message"]

        second = api._resolve_letter_choice(USER, "A")
        assert second is None  # consumed


# ---------------------------------------------------------------------------
# 3. _save_pending_options round-trip
# ---------------------------------------------------------------------------

class TestSavePendingOptions:

    def test_options_stored_correctly(self):
        _ctx_store: dict = {}

        def _fake_get(user, key):
            return _ctx_store.get(key)

        def _fake_set(user, key, value):
            _ctx_store[key] = value

        api = _make_api()
        api.memory.get_context.side_effect = _fake_get
        api.memory.set_context.side_effect = _fake_set

        api._save_pending_options(USER, SAMPLE_OPTIONS)
        stored = _ctx_store.get("recent_context", {}).get("_pending_options", [])
        assert len(stored) == 4
        assert stored[0]["action"] == "draft_cover_letter"
        assert stored[1]["action"] == "open_apply_link"
        assert stored[2]["action"] == "both"
        assert stored[3]["action"] == "search_more"

    def test_empty_options_not_stored(self):
        _ctx_store: dict = {}

        def _fake_get(user, key):
            return _ctx_store.get(key)

        def _fake_set(user, key, value):
            _ctx_store[key] = value

        api = _make_api()
        api.memory.get_context.side_effect = _fake_get
        api.memory.set_context.side_effect = _fake_set

        api._save_pending_options(USER, [])
        assert "recent_context" not in _ctx_store


# ---------------------------------------------------------------------------
# 4. End-to-end routing: "A" dispatches first option, not second
# ---------------------------------------------------------------------------

def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True,
        name="Ahmed Al-Rashid",
        preferred_cities=["Dubai"],
        location="Dubai",
        years_experience=5,
        skills=["HSE", "safety"],
        certifications=[],
        target_roles=["HSE Manager"],
        current_role="HSE Officer",
    )


class TestEndToEndLetterChoice:

    def _run(self, api: RicoChatAPI, message: str) -> dict:
        with (
            patch.object(api, "_resolve_profile", return_value=_profile()),
            patch.object(api, "_get_openai_agent", return_value=MagicMock(
                openai_available=False, deepseek_available=False,
                hf_available=False, provider_available=False, model=""
            )),
            patch("src.rico_env.get_ai_provider", return_value="none"),
        ):
            return api._handle_active_user(message=message, user_id=USER)

    def test_A_dispatches_first_option_not_second(self):
        """
        BUG-02 regression: after a response with options, typing "A" must
        invoke the FIRST option (index 0), not the second (index 1).
        """
        _ctx_store: dict = {"recent_context": {"_pending_options": [
            {"action": "draft_cover_letter", "message": "draft cover letter for HSE Manager at Dutco Group", "label": "Draft cover letter"},
            {"action": "open_apply_link",    "message": "open apply link for HSE Manager at Dutco Group",    "label": "Open apply link"},
            {"action": "both",               "message": "both cover letter and apply link",                  "label": "Both"},
            {"action": "search_more",        "message": "find more HSE Manager jobs in UAE",                 "label": "Search more"},
        ]}}

        api = _make_api()
        api.memory.get_context.side_effect = lambda u, k: _ctx_store.get(k)
        api.memory.set_context.side_effect = lambda u, k, v: _ctx_store.update({k: v})

        dispatched: list[str] = []
        original_inner = api._handle_active_user_inner

        def _spy(user_id, message):
            dispatched.append(message)
            return original_inner(user_id, message)

        with patch.object(api, "_handle_active_user_inner", side_effect=_spy):
            self._run(api, "A")

        # First call is "A" itself; second call must be the first option (cover letter)
        # and must NOT be the second option (apply link).
        assert len(dispatched) >= 2, f"Expected re-dispatch, got: {dispatched}"
        second_dispatch = dispatched[1]
        assert "draft cover letter" in second_dispatch.lower(), (
            f"Expected first option (draft cover letter) to be dispatched, got: {second_dispatch!r}"
        )
        assert "open apply link" not in second_dispatch.lower(), (
            f"BUG-02 still present: 'A' dispatched apply link instead of cover letter: {second_dispatch!r}"
        )

    def test_B_dispatches_second_option(self):
        _ctx_store: dict = {"recent_context": {"_pending_options": [
            {"action": "draft_cover_letter", "message": "draft cover letter for HSE Manager at Dutco Group", "label": "Draft cover letter"},
            {"action": "open_apply_link",    "message": "open apply link for HSE Manager at Dutco Group",    "label": "Open apply link"},
            {"action": "both",               "message": "both cover letter and apply link",                  "label": "Both"},
            {"action": "search_more",        "message": "find more HSE Manager jobs in UAE",                 "label": "Search more"},
        ]}}

        api = _make_api()
        api.memory.get_context.side_effect = lambda u, k: _ctx_store.get(k)
        api.memory.set_context.side_effect = lambda u, k, v: _ctx_store.update({k: v})

        dispatched: list[str] = []
        original_inner = api._handle_active_user_inner

        def _spy(user_id, message):
            dispatched.append(message)
            return original_inner(user_id, message)

        with patch.object(api, "_handle_active_user_inner", side_effect=_spy):
            self._run(api, "B")

        assert len(dispatched) >= 2, f"Expected re-dispatch, got: {dispatched}"
        assert "open apply link" in dispatched[1].lower(), (
            f"Expected second option (open apply link) for B, got: {dispatched[1]!r}"
        )

    def test_unrelated_message_not_dispatched_as_choice(self):
        """A message containing 'a' but not matching the regex must NOT trigger choice resolution."""
        _ctx_store: dict = {"recent_context": {"_pending_options": [
            {"action": "draft_cover_letter", "message": "draft cover letter", "label": "Draft cover letter"},
            {"action": "open_apply_link",    "message": "open apply link",    "label": "Open apply link"},
        ]}}

        api = _make_api()
        api.memory.get_context.side_effect = lambda u, k: _ctx_store.get(k)
        api.memory.set_context.side_effect = lambda u, k, v: _ctx_store.update({k: v})

        dispatched: list[str] = []
        original_inner = api._handle_active_user_inner

        def _spy(user_id, message):
            dispatched.append(message)
            return original_inner(user_id, message)

        with patch.object(api, "_handle_active_user_inner", side_effect=_spy):
            self._run(api, "find me a job in Abu Dhabi")

        # Should only be called once (no re-dispatch to a choice message)
        choice_messages = [d for d in dispatched if d in ("draft cover letter", "open apply link")]
        assert not choice_messages, (
            f"Letter-choice resolver incorrectly fired for 'find me a job in Abu Dhabi': {dispatched}"
        )


# ---------------------------------------------------------------------------
# 5. _NUMBER_CHOICE_RE regex unit tests (numeric option routing)
# ---------------------------------------------------------------------------

class TestNumberChoiceRegex:

    def test_1_matches(self):
        assert _NUMBER_CHOICE_RE.match("1")

    def test_2_matches(self):
        assert _NUMBER_CHOICE_RE.match("2")

    def test_3_matches(self):
        assert _NUMBER_CHOICE_RE.match("3")

    def test_4_matches(self):
        assert _NUMBER_CHOICE_RE.match("4")

    def test_digit_with_period_matches(self):
        assert _NUMBER_CHOICE_RE.match("3.")

    def test_digit_with_colon_matches(self):
        assert _NUMBER_CHOICE_RE.match("2:")

    def test_digit_with_trailing_space_matches(self):
        assert _NUMBER_CHOICE_RE.match("1 ")

    # Negative cases — must NOT match

    def test_two_digit_30_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("30")

    def test_sentence_with_number_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("3 years of experience")

    def test_decimal_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("3.5")

    def test_zero_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("0")

    def test_letter_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("A")

    def test_arabic_does_not_match(self):
        assert not _NUMBER_CHOICE_RE.match("٣")


# ---------------------------------------------------------------------------
# 6. _resolve_letter_choice with numeric inputs (BUG: number→option routing)
# ---------------------------------------------------------------------------

class TestResolveNumberChoice:

    def test_1_returns_first_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "1")
        assert result == SAMPLE_OPTIONS[0]["message"]

    def test_2_returns_second_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "2")
        assert result == SAMPLE_OPTIONS[1]["message"]

    def test_3_returns_third_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "3")
        assert result == SAMPLE_OPTIONS[2]["message"]

    def test_4_returns_fourth_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "4")
        assert result == SAMPLE_OPTIONS[3]["message"]

    def test_3_with_period_returns_third_option(self):
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "3.")
        assert result == SAMPLE_OPTIONS[2]["message"]

    def test_number_out_of_range_returns_none(self):
        # Only 2 options stored, "4" (index 3) is out of range
        api = _api_with_options(SAMPLE_OPTIONS[:2])
        result = api._resolve_letter_choice(USER, "4")
        assert result is None

    def test_no_options_returns_none_for_number(self):
        api = _make_api()
        api.memory.get_context.return_value = {}
        result = api._resolve_letter_choice(USER, "3")
        assert result is None

    def test_number_options_consumed_after_use(self):
        """After resolving "3", a second call with "3" returns None (options cleared)."""
        stored_ctx: dict = {"_pending_options": [
            {"action": o.get("action", ""), "message": o.get("message", ""), "label": o.get("label", "")}
            for o in SAMPLE_OPTIONS
        ]}
        api = _make_api()
        _ctx_store: dict = {}

        def _fake_get(user, key):
            return _ctx_store.get(key)

        def _fake_set(user, key, value):
            _ctx_store[key] = value

        api.memory.get_context.side_effect = _fake_get
        api.memory.set_context.side_effect = _fake_set
        _ctx_store["recent_context"] = stored_ctx

        first = api._resolve_letter_choice(USER, "3")
        assert first == SAMPLE_OPTIONS[2]["message"]

        second = api._resolve_letter_choice(USER, "3")
        assert second is None  # consumed

    def test_30_not_treated_as_option(self):
        """'30' must NOT trigger numeric choice routing."""
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "30")
        assert result is None

    def test_sentence_with_3_not_treated_as_option(self):
        """'I have 3 years experience' must NOT trigger numeric choice routing."""
        api = _api_with_options(SAMPLE_OPTIONS)
        result = api._resolve_letter_choice(USER, "I have 3 years experience")
        assert result is None


# ---------------------------------------------------------------------------
# 7. End-to-end numeric choice routing (the mobile bug scenario)
# ---------------------------------------------------------------------------

class TestEndToEndNumberChoice:

    def _run(self, api: RicoChatAPI, message: str) -> dict:
        with (
            patch.object(api, "_resolve_profile", return_value=_profile()),
            patch.object(api, "_get_openai_agent", return_value=MagicMock(
                openai_available=False, deepseek_available=False,
                hf_available=False, provider_available=False, model=""
            )),
            patch("src.rico_env.get_ai_provider", return_value="none"),
        ):
            return api._handle_active_user(message=message, user_id=USER)

    def test_3_dispatches_third_option_not_ai_fabrication(self):
        """
        Regression for mobile bug: user sees options 1/2/3/4, types "3",
        Rico must route to the third option — not fabricate an AI response.
        """
        NEWS_OPTIONS = [
            {"action": "uae_job_news",      "message": "show UAE job market news",          "label": "UAE Job Market News"},
            {"action": "esg_news",          "message": "show ESG and sustainability news",  "label": "Environmental/ESG News"},
            {"action": "rico_platform_news","message": "show Rico Hunt platform updates",   "label": "News from Rico Hunt"},
            {"action": "industry_news",     "message": "show industry news for compliance", "label": "Industry-Specific News"},
        ]
        _ctx_store: dict = {"recent_context": {"_pending_options": [
            {"action": o["action"], "message": o["message"], "label": o["label"]}
            for o in NEWS_OPTIONS
        ]}}

        api = _make_api()
        api.memory.get_context.side_effect = lambda u, k: _ctx_store.get(k)
        api.memory.set_context.side_effect = lambda u, k, v: _ctx_store.update({k: v})

        dispatched: list[str] = []
        original_inner = api._handle_active_user_inner

        def _spy(user_id, message):
            dispatched.append(message)
            return original_inner(user_id, message)

        with patch.object(api, "_handle_active_user_inner", side_effect=_spy):
            self._run(api, "3")

        assert len(dispatched) >= 2, f"Expected re-dispatch, got: {dispatched}"
        # Must dispatch the third option (Rico platform news), not CV or anything else
        assert dispatched[1] == NEWS_OPTIONS[2]["message"], (
            f"Expected '{NEWS_OPTIONS[2]['message']}' but got: {dispatched[1]!r}"
        )
