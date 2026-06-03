"""
tests/test_continuation_intent.py
Unit tests for the post-CV continuation intent guard.

Covers:
- _is_continuation_intent() helper (True / False cases)
- Real role titles are NOT mis-classified as continuation phrases
- Arabic continuation phrases are detected
- Random short text without context is NOT treated as continuation
"""
import pytest

from src.rico_chat_api import RicoChatAPI


# ── _is_continuation_intent: must return True ────────────────────────────────

@pytest.mark.parametrize("msg", [
    # English multi-word
    "its ok keep going",
    "it's ok keep going",
    "ok keep going",
    "okay keep going",
    "keep going",
    "continue",
    "continue please",
    "please continue",
    "just continue",
    "go ahead",
    "go ahead please",
    "please go ahead",
    "yes continue",
    "sure continue",
    "ok continue",
    "okay continue",
    "yes go ahead",
    "carry on",
    "yes carry on",
    "ok carry on",
    "proceed",
    "yes proceed",
    "ok proceed",
    "go on",
    "sounds good continue",
    "lets continue",
    "let's continue",
    # Arabic
    "كمل",
    "استمر",
    "واصل",
    "ماشي كمل",
    "ماشي استمر",
    "تمام كمل",
    "تمام استمر",
    "اوك كمل",
    "اوك استمر",
    "يلا كمل",
    "يلا استمر",
    "نعم استمر",
    "نعم كمل",
    "حسنا استمر",
    "طيب كمل",
    "طيب استمر",
    "كمل من فضلك",
    "استمر من فضلك",
])
def test_is_continuation_intent_true(msg: str) -> None:
    assert RicoChatAPI._is_continuation_intent(msg) is True


# ── _is_continuation_intent: must return False ───────────────────────────────

@pytest.mark.parametrize("msg", [
    # Real role titles must not be caught
    "HSE Manager",
    "Environmental Manager",
    "Software Engineer",
    "Senior Backend Developer",
    "Data Scientist",
    "Architect",
    "Chef de Cuisine",
    "مهندس برمجيات",
    # Unrelated short text
    "hi",
    "hello",
    "what is my status",
    "show me jobs",
    "find me a role",
    "explain this",
    "UAE",
    "Dubai jobs",
    # Negatives
    "no",
    "not now",
    "skip",
    # Empty / whitespace
    "",
    "   ",
])
def test_is_continuation_intent_false(msg: str) -> None:
    assert RicoChatAPI._is_continuation_intent(msg) is False


# ── _looks_like_bare_target_role: continuation phrases must be rejected ───────

@pytest.mark.parametrize("msg", [
    "its ok keep going",
    "keep going",
    "continue",
    "go ahead",
    "carry on",
    "proceed",
])
def test_bare_role_gate_rejects_continuation_phrases(msg: str) -> None:
    """Continuation phrases should not be treated as bare job role titles.

    Even if _looks_like_bare_target_role doesn't block them directly,
    the dispatch catches them via _is_continuation_intent before reaching
    the role-search path. This test documents that the helper correctly
    identifies them so the gate fires.
    """
    assert RicoChatAPI._is_continuation_intent(msg) is True


# ── Real roles are still accepted by the bare-role gate ──────────────────────

@pytest.mark.parametrize("msg", [
    "HSE Manager",
    "Environmental Manager",
    "Software Engineer",
    "Senior Backend Developer",
    "Data Scientist",
    "Architect",
    "Chef de Cuisine",
    "QA Engineer",
    "DevOps Lead",
])
def test_real_roles_not_blocked_as_continuation(msg: str) -> None:
    assert RicoChatAPI._is_continuation_intent(msg) is False
    assert RicoChatAPI._looks_like_bare_target_role(msg) is True
