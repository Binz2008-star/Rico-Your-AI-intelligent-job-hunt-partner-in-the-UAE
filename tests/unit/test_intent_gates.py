"""Phase 1 gate-level tests for open-ended question routing."""
from __future__ import annotations

import pytest

from src.rico.intent.gates import (
    is_explicit_job_listing_request,
    is_open_ended_question,
)


@pytest.mark.parametrize("msg", [
    "how can you help me",
    "what can you do",
    "what is my name",
    "can you improve my CV",
    "tell me what you know about me",
    "why is this job a match",
    "anything?",
    "qué hay?",
    "结果如何？",
    "how do I apply",
    "what is the salary",
    "why no matches",
    "when will I hear back",
    "where are the jobs",
    "who is hiring",
    "can I get more",
    "could you check",
    "should I apply",
    "would you save this",
    "explain the match score",
    "do you have new jobs",
    "tell me about this role",
    "show me more",
    "",
    "   ",
])
def test_gate_rejects_open_ended(msg: str) -> None:
    is_open, reason = is_open_ended_question(msg)
    assert is_open is True, (msg, reason)
    assert reason != "ok"


@pytest.mark.parametrize("msg", [
    "HSE Manager",
    "Safety Officer",
    "Operations Manager",
    "ESG Specialist",
    "Software Engineer",
    "Chef",
    "Cardiologist",
    "find HSE Manager jobs",
    "show me jobs",
    "keep all",
    "both please",
    "asdf qwer zxcv",
])
def test_gate_lets_through_non_questions(msg: str) -> None:
    is_open, reason = is_open_ended_question(msg)
    assert is_open is False, (msg, reason)
    assert reason == "ok"


def test_show_me_routes_to_ai_by_phrase_opener() -> None:
    is_open, reason = is_open_ended_question("show me more details")
    assert is_open is True
    assert reason.startswith("phrase:")


@pytest.mark.parametrize("msg", [
    "what job i applied for so far?",
    "what jobs i applied for?",
    "what did i apply for?",
    "which jobs have i applied to?",
    "jobs i applied to?",
    "what job i applied for",
    "what jobs i applied for",
    "what did i apply for",
    "jobs i applied to",
    "jobs i applied for",
])
def test_application_status_questions_bypass_ai_gate(msg: str) -> None:
    """Application history questions must reach the legacy classifier (DB), not DeepSeek."""
    is_open, reason = is_open_ended_question(msg)
    assert is_open is False, f"Expected legacy route for {msg!r}, got reason={reason}"
    assert reason == "ok"


@pytest.mark.parametrize("msg", [
    # Live-QA 2026-07-19: the exact message that produced a hollow promise.
    "انظر المتوفر بسوق العمل لا يوجد لدي شيء محدد ببالي حاليا",
    "شوف المتوفر بالسوق",
    "ورني الوظائف المتوفرة",
    "وش المتاح من وظائف",
    "اعرض المتوفر من وظائف",
    "شوفلي وش متوفر بسوق العمل",
    "المتاح في السوق حالياً",
])
def test_arabic_browse_market_is_explicit_job_listing(msg: str) -> None:
    """Colloquial Arabic 'browse the market' asks must force the real search path.

    Without this, an authenticated user's browse request skips _force_real_search
    and falls to the AI path, which returns a hollow 'سأبحث الآن' promise.
    """
    assert is_explicit_job_listing_request(msg) is True, msg


@pytest.mark.parametrize("msg", [
    "ما هو وضع سوق العمل في دبي؟",   # market question, not a browse-for-listings ask
    "شوف سيرتي الذاتية",              # look at my CV — no market noun
    "شغلي الحالي صعب جداً",           # 'my job is hard' — bare شغل, no browse/avail
    "أنا موجود في دبي",              # availability word but no job/market noun
])
def test_arabic_conversational_not_flagged_as_listing(msg: str) -> None:
    """Genuine conversation must not be misrouted to the job-search path."""
    assert is_explicit_job_listing_request(msg) is False, msg


@pytest.mark.parametrize("msg", [
    "Tell me about HSE roles in the UAE",
    "What makes CVs strong for roles in the UAE?",
    "What are the visa requirements for jobs in Dubai?",
    "How do salaries for HSE roles in the UAE compare to Saudi?",
    "Why are openings for compliance roles in Dubai so competitive?",
])
def test_advice_question_with_embedded_job_noun_not_flagged_as_listing(msg: str) -> None:
    """The weak 'jobs/roles in/for/at' pattern must not fire inside a question.

    Live-tested on production 2026-07-23: these advice/informational questions
    were being misclassified as explicit job-listing requests (matching the
    verb-less second branch of the old combined listing-request regex purely
    because "roles in"/"jobs in" appeared as a prepositional phrase), and
    routed to the deterministic public CTA / legacy classifier instead of
    being answered — a real production quality regression, not a hypothetical.
    """
    assert is_explicit_job_listing_request(msg) is False, msg


@pytest.mark.parametrize("msg", [
    "jobs in Dubai",
    "show me jobs in Dubai",
    "Do you have HSE positions in Sharjah?",
    "roles in the UAE",
    "find HSE manager jobs",
])
def test_genuine_listing_requests_still_flagged(msg: str) -> None:
    """The advice-question carve-out must not weaken genuine listing requests —
    these must still be intercepted before the AI path to prevent hallucinated
    company names, roles, salaries, and links."""
    assert is_explicit_job_listing_request(msg) is True, msg
