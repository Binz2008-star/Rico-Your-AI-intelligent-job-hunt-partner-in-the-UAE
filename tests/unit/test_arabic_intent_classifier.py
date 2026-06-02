"""
Regression tests for Arabic and mixed-language intent classification.

Arabic text was previously flagged as nonsense (no Latin letters → matched
_NONSENSE_RE) and never reached job-search detection.  These tests verify:
  1. Pure Arabic job-search messages → job_search_explicit
  2. Mixed Arabic+English (role name in English) → job_search_explicit + extracted_role
  3. Arabic confirmations → follow_up_confirmation (not nonsense)
  4. Arabic greetings → smalltalk (not nonsense)
  5. English standalone "jobs please" / "any jobs?" → job_search_explicit
  6. Pure Arabic is never returned as "unknown" for clear job-search requests
"""

import pytest
from src.agent.intelligence.intent_classifier import classify_intent, IntentResult


class TestArabicJobSearch:
    """Pure Arabic job-search messages must classify as job_search_explicit."""

    @pytest.mark.parametrize("msg", [
        "إبحث لي عن وظيفة",
        "ابحث لي عن وظيفة",
        "دور لي على شغل",
        "ابي فرص عمل",
        "محتاج وظيفة",
        "شوف لي وظائف",
    ])
    def test_arabic_job_search_explicit(self, msg):
        result = classify_intent(msg)
        assert result.intent == "job_search_explicit", (
            f"Expected job_search_explicit for '{msg}', got {result.intent!r}"
        )
        assert result.intent != "unknown"
        assert result.intent != "nonsense"

    def test_arabic_job_search_never_unknown(self):
        """إبحث لي عن وظيفة must not fall through to unknown."""
        result = classify_intent("إبحث لي عن وظيفة")
        assert result.intent != "unknown"

    @pytest.mark.parametrize("msg", [
        "أسعى لوظيفة",
        "أرغب في مسمى وظيفي",
        "هل هناك وظائف",
    ])
    def test_msa_job_search_forms(self, msg):
        result = classify_intent(msg)
        assert result.intent == "job_search_explicit"

    @pytest.mark.parametrize("msg", [
        "هل يوجد تحديث للتطبيق",
        "اريد مجال تعلم اللغات",
    ])
    def test_generic_arabic_questions_are_not_job_search_with_cv(self, msg):
        result = classify_intent(msg, has_cv_profile=True)
        assert result.intent != "job_search_explicit"


class TestMixedArabicEnglishJobSearch:
    """Mixed Arabic+English messages should yield job_search_explicit with extracted_role."""

    def test_arabic_request_english_role_hse_manager(self):
        result = classify_intent("ابحث لي عن وظيفة HSE Manager")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is not None
        assert "HSE Manager" in result.extracted_role

    def test_arabic_request_english_role_safety_officer(self):
        result = classify_intent("دور لي safety officer")
        assert result.intent == "job_search_explicit"
        assert result.extracted_role is not None
        assert "safety officer" in result.extracted_role.lower()


class TestArabicConfirmations:
    """Arabic confirmation/follow-up words must not crash and should not be nonsense."""

    @pytest.mark.parametrize("msg", [
        "تمام",
        "اوكي",
        "نعم",
        "موافق",
        "كمل",
        "استمر",
    ])
    def test_arabic_confirmation_not_nonsense(self, msg):
        result = classify_intent(msg)
        assert result.intent != "nonsense", (
            f"Arabic confirmation '{msg}' must not be nonsense"
        )

    def test_tamam_is_follow_up_confirmation(self):
        """تمام (okay/done) post-profile confirmation must not crash the system."""
        result = classify_intent("تمام")
        # Acceptable as follow_up_confirmation, smalltalk, or acknowledgement — must not be nonsense/unknown
        assert result.intent in {"follow_up_confirmation", "smalltalk", "acknowledgement"}


class TestArabicSmallTalk:
    """Arabic greetings must resolve to smalltalk, not nonsense."""

    @pytest.mark.parametrize("msg", [
        "مرحبا",
        "اهلا",
    ])
    def test_arabic_greeting_is_smalltalk(self, msg):
        result = classify_intent(msg)
        assert result.intent == "smalltalk", (
            f"Arabic greeting '{msg}' should be smalltalk, got {result.intent!r}"
        )

    def test_arabic_thanks_is_acknowledgement(self):
        result = classify_intent("شكرا")
        assert result.intent == "acknowledgement", (
            f"Arabic 'شكرا' should be acknowledgement, got {result.intent!r}"
        )


class TestEnglishStandaloneJobRequests:
    """Short English job-request phrases must classify as job_search_explicit."""

    @pytest.mark.parametrize("msg", [
        "jobs please",
        "any jobs?",
    ])
    def test_english_standalone_job_request(self, msg):
        result = classify_intent(msg)
        assert result.intent == "job_search_explicit", (
            f"Expected job_search_explicit for '{msg}', got {result.intent!r}"
        )


class TestArabicNonsenseSafeguard:
    """Arabic text must never be flagged as nonsense by the Latin-only nonsense gate."""

    def test_arabic_text_not_flagged_nonsense(self):
        result = classify_intent("ابحث لي عن وظيفة")
        assert result.intent != "nonsense"

    def test_pure_arabic_digits_only_still_nonsense(self):
        """Pure digit-only strings are nonsense regardless of language context."""
        result = classify_intent("12345")
        assert result.intent == "nonsense"


class TestArabicApplicationHistory:
    """Arabic application-history questions must route to the application tracker,
    NOT to a brand-new job search.

    Regression: production saved an ADNOC application correctly, but when the
    user asked in Arabic where to follow it and how many jobs they had applied
    to, Rico misrouted to job search and reported "no live UAE matches found".
    The substring "طلب" (request) inside "الطلب" (the application) plus the job
    noun "وظيفة" tripped the Arabic job-search heuristic.
    """

    def test_full_application_history_question_routes_to_tracker(self):
        """The exact production message must classify as application_tracking."""
        msg = (
            "انت قمت بحفظ الطلب ولكن اين استطيع متابعته "
            "وكم وظيفة قمت بالتقديم عليها للان"
        )
        result = classify_intent(msg, has_cv_profile=True)
        assert result.intent == "application_tracking", (
            f"Arabic application-history question must route to application_tracking, "
            f"got {result.intent!r}"
        )
        assert result.intent != "job_search_explicit"

    @pytest.mark.parametrize("msg", [
        "كم وظيفة قمت بالتقديم عليها",          # how many jobs have I applied to
        "اين استطيع متابعة طلباتي",             # where can I follow up my applications
        "ما هي الوظائف التي تقدمت لها",          # what jobs did I apply for
        "اريد متابعة طلب التوظيف الذي قدمته",    # follow the application I submitted
        "كيف اتابع تقديمي على الوظيفة",          # how do I track my application
    ])
    def test_arabic_application_history_variants(self, msg):
        result = classify_intent(msg, has_cv_profile=True)
        assert result.intent == "application_tracking", (
            f"Expected application_tracking for '{msg}', got {result.intent!r}"
        )

    def test_genuine_arabic_job_search_still_works(self):
        """The guard must not steal genuine Arabic job-search requests."""
        result = classify_intent("ابحث لي عن وظيفة", has_cv_profile=True)
        assert result.intent == "job_search_explicit"


class TestArabicStandaloneRequestVerb:
    """Standalone Arabic request verb + has_cv_profile must classify as job_search_explicit."""

    def test_ibhath_alone_with_cv(self):
        """'ابحث' (search) alone with CV profile = job search request."""
        result = classify_intent("ابحث", has_cv_profile=True)
        assert result.intent == "job_search_explicit", (
            f"Expected job_search_explicit for 'ابحث' with CV, got {result.intent!r}"
        )

    def test_ibhath_alone_without_cv(self):
        """'ابحث' alone without CV profile = unknown (ambiguous without context)."""
        result = classify_intent("ابحث", has_cv_profile=False)
        assert result.intent != "nonsense", "Arabic request verb must never be nonsense"

    def test_dawer_alone_with_cv(self):
        """'دور' (look/find) alone with CV profile = job search request."""
        result = classify_intent("دور", has_cv_profile=True)
        assert result.intent == "job_search_explicit"

    def test_arabic_verb_not_nonsense_either_way(self):
        """Arabic request verbs must never be classified as nonsense."""
        for msg in ["ابحث", "دور", "شوف", "جيب"]:
            result = classify_intent(msg)
            assert result.intent != "nonsense", f"'{msg}' must not be nonsense"
