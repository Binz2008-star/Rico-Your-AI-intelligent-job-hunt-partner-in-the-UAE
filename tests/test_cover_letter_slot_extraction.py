"""
tests/test_cover_letter_slot_extraction.py

Regression tests for TASK-20260617-002 — cover-letter intent slot extraction.

Problem:
  A single message that already contains role + company + city, e.g.
    "اكتب لي خطاب تقديم لوظيفة ESG Manager في شركة Aldar Properties في أبوظبي"
  was extracted with English-only regexes, so the slots came back empty and
  Rico fell through to the clarification prompt — asking again for role/company.

Covers:
  1. _extract_explicit_draft_job_from_message extracts role/company/city/language
     from the exact Arabic Aldar ESG Manager example, the English equivalent,
     and the Arabic role-only / company-only partial cases.
  2. End-to-end chat flow: a complete Arabic request generates an Arabic cover
     letter directly; a complete English request generates an English letter.
  3. A request missing role (company-only) or missing company (role-only) asks
     only for the missing field.
"""
from __future__ import annotations

import os
import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import RicoChatAPI

USER = "slot-user@example.com"

_ARABIC_RE = re.compile(r"[؀-ۿ]")

ARABIC_ALDAR = "اكتب لي خطاب تقديم لوظيفة ESG Manager في شركة Aldar Properties في أبوظبي"
ENGLISH_ALDAR = "Write a cover letter for ESG Manager at Aldar Properties in Abu Dhabi"


# ---------------------------------------------------------------------------
# 1. Slot extraction unit tests
# ---------------------------------------------------------------------------

class TestSlotExtraction:

    def test_arabic_aldar_esg_full_slots(self):
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(ARABIC_ALDAR)
        assert slots.get("title") == "ESG Manager"
        assert slots.get("company") == "Aldar Properties"
        assert slots.get("location") == "أبوظبي"
        assert slots.get("language") == "ar"

    def test_english_aldar_esg_full_slots(self):
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(ENGLISH_ALDAR)
        assert slots.get("title") == "ESG Manager"
        assert slots.get("company") == "Aldar Properties"
        assert slots.get("location") == "Abu Dhabi"
        assert slots.get("language") == "en"

    def test_arabic_role_only_has_no_company(self):
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(
            "اكتب لي خطاب تقديم لوظيفة ESG Manager"
        )
        assert slots.get("title") == "ESG Manager"
        assert not slots.get("company")
        assert slots.get("language") == "ar"

    def test_arabic_company_only_has_no_role(self):
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(
            "اكتب لي خطاب تقديم لشركة Aldar Properties في دبي"
        )
        assert slots.get("company") == "Aldar Properties"
        assert slots.get("location") == "دبي"
        assert not slots.get("title")
        assert slots.get("language") == "ar"

    def test_arabic_native_role_and_company(self):
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(
            "اكتب لي خطاب تقديم لوظيفة مدير عمليات في شركة إعمار في دبي"
        )
        assert slots.get("title") == "مدير عمليات"
        assert slots.get("company") == "إعمار"
        assert slots.get("location") == "دبي"

    def test_non_draft_message_returns_empty(self):
        assert RicoChatAPI._extract_explicit_draft_job_from_message(
            "find me ESG jobs in Abu Dhabi"
        ) == {}

    def test_arabic_bank_inquiry_mid_sentence(self):
        """Production regression (2026-07-21): «لبنك …» with the sentence
        continuing past the company. The connectors (في شركة/لدى/لشركة) missed
        the bare institution form, and the end-anchored patterns failed on the
        continuation — the user got a generic which-company question after
        naming the company."""
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(
            "اكتبلي ايميل لبنك دبي الاسلامي استعلم به عن وظائف واعرض مهاراتي وخبراتي"
        )
        assert slots.get("company") == "بنك دبي الاسلامي"
        assert slots.get("language") == "ar"

    def test_arabic_institution_variants(self):
        for msg, company in [
            ("اكتب لي خطاب لمصرف الإمارات المركزي.", "مصرف الإمارات المركزي"),
            ("اكتب لي رسالة إلى هيئة الطرق والمواصلات عن وظائف", "هيئة الطرق والمواصلات"),
        ]:
            slots = RicoChatAPI._extract_explicit_draft_job_from_message(msg)
            assert slots.get("company") == company, msg

    def test_trailing_backslash_stripped(self):
        # Production shape: «اكتبلي ايميل لبنك دبي الاسلامي\» (stray key smash).
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(
            "اكتبلي ايميل لبنك دبي الاسلامي\\"
        )
        assert slots.get("company") == "بنك دبي الاسلامي"


# ---------------------------------------------------------------------------
# 1c. Generic cover-letter request (production loop fix, 2026-07-21)
# ---------------------------------------------------------------------------

class TestGenericDraftDetection:
    """«اكتب واحد عام غير محدد» after a clarification used to get the SAME
    clarification verbatim — an infinite re-ask loop. The generic marker now
    routes to a general-letter generation instead."""

    def test_generic_phrases_detected(self):
        from src.rico_chat_api import _GENERIC_DRAFT_RE
        for m in ("اكتب واحد عام غير محدد", "لاشيء محدد بصوره عامه",
                  "لا شيء محدد بصورة عامة", "اكتب خطاب عام",
                  "رسالة عامة بدون شركة", "بدون شركة محددة",
                  "write me a general cover letter", "a general letter please",
                  "make me a generic one", "not for a specific company",
                  "cover letter for any company", "no specific company"):
            assert _GENERIC_DRAFT_RE.search(m), m

    def test_specific_role_phrases_not_detected(self):
        # "عام"/"general" as part of a ROLE title must never count as a
        # genericness marker (pattern tightened via the #1278 harvest — the
        # first cut fired on "general accountant").
        from src.rico_chat_api import _GENERIC_DRAFT_RE
        for m in ("اكتب خطاب لوظيفة مدير عام في شركة إعمار",
                  "cover letter for General Manager at Aldar",
                  "cover letter for the general accountant position",
                  "write a cover letter for ADNOC",
                  "اكتب خطاب تقديم لشركة الإمارات",
                  "اكتبلي كفر لترر"):
            assert not _GENERIC_DRAFT_RE.search(m), m


class TestGenericLetterOutput:
    """The general letter is DETERMINISTIC — built only from real profile
    fields, MSA register, no dialect, no vocatives, no fabrication."""

    def _profile(self, **over):
        base = dict(
            name="Roben Edwan", years_experience=8, current_role="General Manager",
            skills=["iso 14001", "compliance"], certifications=["ISO 14001 Lead Auditor"],
        )
        base.update(over)
        return SimpleNamespace(**base)

    def _api(self):
        return RicoChatAPI.__new__(RicoChatAPI)

    def test_arabic_letter_is_msa_no_dialect_no_vocative(self):
        letter = self._api()._generic_cover_letter(self._profile(), arabic=True)
        assert "8" in letter and "iso 14001" in letter and "Roben Edwan" in letter
        for banned in ("شنو", "وش ", "تبي", "دلوقتي", "يا Roben", "😊", "🚀"):
            assert banned not in letter, banned

    def test_english_letter_uses_real_profile_only(self):
        letter = self._api()._generic_cover_letter(self._profile(), arabic=False)
        assert "8 years" in letter and "General Manager" in letter
        assert "Roben Edwan" in letter

    def test_empty_profile_never_fabricates(self):
        empty = SimpleNamespace(
            name=None, years_experience=None, current_role=None,
            skills=[], certifications=[],
        )
        for arabic in (True, False):
            letter = self._api()._generic_cover_letter(empty, arabic=arabic)
            assert "None" not in letter
            assert "8" not in letter


# ---------------------------------------------------------------------------
# 1b. Vocative guard + clarification language (production regressions 2026-07-21)
# ---------------------------------------------------------------------------

class TestVocativeGuardAndClarificationLanguage:
    """The live defect: a user whose profile.name was polluted by CV parsing
    (a CV headline — "Vip Relationship Manager") was greeted BY that title, in
    English, in reply to an Arabic request. The guard and the arabic param are
    global — any user, any language."""

    def _profile(self, name):
        return SimpleNamespace(
            name=name, target_roles=["Environmental Manager"], skills=[],
        )

    def test_role_like_name_never_used_as_vocative(self):
        assert RicoChatAPI._vocative_name(self._profile("Vip Relationship Manager")) == ""
        assert RicoChatAPI._vocative_name(self._profile("مدير علاقات كبار العملاء")) == ""

    def test_real_names_pass_the_guard(self):
        assert RicoChatAPI._vocative_name(self._profile("Roben Edwan")) == "Roben Edwan"
        assert RicoChatAPI._vocative_name(self._profile("روبن")) == "روبن"

    def test_clarification_omits_role_like_name(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        msg = api._cover_letter_clarification_message(
            self._profile("Vip Relationship Manager"), arabic=False
        )
        assert "Vip Relationship Manager" not in msg
        assert "I can write a cover letter for you." in msg

    def test_arabic_request_gets_arabic_clarification(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        msg = api._cover_letter_clarification_message(self._profile("روبن"), arabic=True)
        assert "يمكنني كتابة خطاب تقديم" in msg
        assert "I can write" not in msg

    def test_company_prefilled_arabic_clarification_asks_only_for_role(self):
        api = RicoChatAPI.__new__(RicoChatAPI)
        msg = api._cover_letter_clarification_message(
            self._profile("روبن"),
            {"company": "بنك دبي الاسلامي", "language": "ar"},
        )
        assert "بنك دبي الاسلامي" in msg
        assert "المسمى الوظيفي" in msg


# ---------------------------------------------------------------------------
# 2. End-to-end chat flow harness (mirrors test_cover_letter_context_isolation)
# ---------------------------------------------------------------------------

def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True,
        name="Ahmed Al-Rashid",
        preferred_cities=["Abu Dhabi"],
        location="Abu Dhabi",
        years_experience=8,
        skills=["ESG", "sustainability", "compliance"],
        certifications=[],
        target_roles=["ESG Manager"],
        current_role="ESG Specialist",
    )


def _agent() -> MagicMock:
    return MagicMock(
        openai_available=False,
        deepseek_available=False,
        hf_available=False,
        provider_available=False,
        model="",
    )


def _api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    api.memory.get_context.return_value = None
    api.memory.set_context.return_value = None
    return api


def _run(message: str, *, applications=None, profile=None) -> dict:
    api = _api()
    with (
        patch.object(api, "_resolve_profile", return_value=profile or _profile()),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
        patch("src.repositories.applications_repo.get_all", return_value=applications or []),
        # Force template (non-AI) cover letters so output is deterministic offline.
        patch("src.rico_env.get_ai_provider", return_value="none"),
        patch("src.rico_chat_api.agent_runtime.handle_action") as handle_action,
    ):
        result = api._handle_active_user_inner(USER, message)
    handle_action.assert_not_called()
    return result


class TestCoverLetterEndToEnd:

    def test_arabic_full_request_generates_arabic_letter_directly(self):
        result = _run(ARABIC_ALDAR)
        message = result["message"]
        assert result["type"] == "draft_message"
        assert "ESG Manager" in message
        assert "Aldar Properties" in message
        # Arabic script must be present (Arabic cover letter, not English fallback)
        assert _ARABIC_RE.search(message)
        # Must NOT re-ask for role/company
        assert "Which role" not in message
        assert "Which company" not in message
        assert "ما المسمى الوظيفي" not in message

    def test_english_full_request_generates_english_letter_directly(self):
        result = _run(ENGLISH_ALDAR)
        message = result["message"]
        assert result["type"] == "draft_message"
        assert "ESG Manager" in message
        assert "Aldar Properties" in message
        assert "Dear Hiring Manager" in message
        assert "Which role" not in message
        assert "Which company" not in message

    def test_arabic_role_only_asks_only_for_company(self):
        result = _run("اكتب لي خطاب تقديم لوظيفة ESG Manager")
        message = result["message"]
        assert result["type"] == "cover_letter_prompt"
        assert "ESG Manager" in message
        # Asks for the company (Arabic), not the role
        assert "الشركة" in message
        assert _ARABIC_RE.search(message)

    def test_arabic_company_only_asks_only_for_role(self):
        result = _run(
            "اكتب لي خطاب تقديم لشركة Aldar Properties في دبي",
            applications=[],
        )
        message = result["message"]
        assert result["type"] == "cover_letter_prompt"
        assert "Aldar Properties" in message
        # Asks for the role/title (Arabic), not the company
        assert "المسمى الوظيفي" in message
        assert _ARABIC_RE.search(message)


# ---------------------------------------------------------------------------
# 3. BUG-01 regression — cover letter for "role at Company" must not trigger
#    company job search (_COMPANY_SEARCH_RE matches "roles? at [A-Z]")
# ---------------------------------------------------------------------------

DUTCO_HSE = "Draft me a cover letter for the HSE MANAGER - DATA CENTERS role at Dutco Group"
HSE_ADNOC = "Write me a cover letter for the HSE Manager role at ADNOC"


class TestBug01CoverLetterCompanySearchGuard:

    def test_dutco_hse_slots_extracted(self):
        """Slot extractor must find company=Dutco Group in the BUG-01 message."""
        slots = RicoChatAPI._extract_explicit_draft_job_from_message(DUTCO_HSE)
        assert slots.get("company") == "Dutco Group"
        assert slots.get("title")  # title present (exact wording may vary)

    def test_company_search_re_matches_role_at_pattern(self):
        """Root-cause confirmation: 'role at Dutco Group' hits _COMPANY_SEARCH_RE."""
        from src.rico_chat_api import _COMPANY_SEARCH_RE
        assert _COMPANY_SEARCH_RE.search("HSE MANAGER - DATA CENTERS role at Dutco Group")

    def test_dutco_hse_routes_to_cover_letter_not_job_search(self):
        """BUG-01: cover letter request must return draft_message or cover_letter_prompt."""
        result = _run(DUTCO_HSE)
        assert result["type"] in ("draft_message", "cover_letter_prompt"), (
            f"Expected cover letter response, got type={result['type']!r}: {result}"
        )
        assert result.get("intent") != "company_search"

    def test_hse_adnoc_routes_to_cover_letter_not_job_search(self):
        """Variant: 'HSE Manager role at ADNOC' must also route to cover letter."""
        result = _run(HSE_ADNOC)
        assert result["type"] in ("draft_message", "cover_letter_prompt"), (
            f"Expected cover letter response, got type={result['type']!r}: {result}"
        )

    def test_dutco_hse_cover_letter_contains_company_name(self):
        """If fully generated, the letter body must reference Dutco Group."""
        result = _run(DUTCO_HSE)
        if result["type"] == "draft_message":
            assert "Dutco" in result["message"]
