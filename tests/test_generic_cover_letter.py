"""Generic (untargeted) cover-letter flow — owner transcript 2026-07-21.

The user asked "اكتب واحد عام غير محدد" after the cover-letter clarification
and the deterministic layer re-asked for a role/company in a loop. The fix:
an explicit "general letter" request produces a general letter built only
from real profile data — in the user's language, Modern Standard Arabic,
no dialect, no vocatives — and never re-asks. "General Manager" as a ROLE
must NOT trigger the generic path (false-positive guard).
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import _GENERIC_COVER_LETTER_RE, RicoChatAPI


class TestGenericDetector:
    @pytest.mark.parametrize("phrase", [
        # The exact production transcript phrases
        "اكتب واحد عام غير محدد",
        "لاشيء محدد بصوره عامه",
        "لا شيء محدد بصورة عامة",
        # Common variants
        "اكتب خطاب عام",
        "رسالة عامة بدون شركة",
        "كفر لتر عام لأي شركة",
        "write a general cover letter",
        "make me a generic one",
        "a general letter please",
        "not for a specific company",
        "cover letter for any company",
    ])
    def test_generic_phrases_match(self, phrase: str):
        assert _GENERIC_COVER_LETTER_RE.search(phrase), phrase

    @pytest.mark.parametrize("phrase", [
        # "general/عام" as part of a ROLE title must NOT trigger
        "write a cover letter for a General Manager role at ADNOC",
        "اكتب خطاب تقديم لوظيفة مدير عام في أدنوك",
        "cover letter for the general accountant position",
        # Targeted requests must NOT trigger
        "write a cover letter for ADNOC",
        "اكتب خطاب تقديم لشركة الإمارات",
    ])
    def test_targeted_phrases_do_not_match(self, phrase: str):
        assert not _GENERIC_COVER_LETTER_RE.search(phrase), phrase


def _profile(**over):
    base = dict(
        name="Roben Edwan",
        years_experience=8,
        current_role="General Manager",
        skills=["iso 14001", "compliance", "environmental management"],
        certifications=["ISO 14001 Lead Auditor"],
        target_roles=["Environmental Manager"],
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestGenericLetterOutput:
    @pytest.fixture()
    def chat(self):
        return RicoChatAPI.__new__(RicoChatAPI)

    def test_arabic_letter_is_msa_no_dialect_no_vocative(self, chat):
        letter = chat._generic_cover_letter(_profile(), arabic=True)
        # Built from real profile data
        assert "8" in letter
        assert "iso 14001" in letter
        assert "Roben Edwan" in letter
        # MSA register: no dialect tokens, no vocative, no emoji
        for banned in ("شنو", "وش ", "تبي", "دلوقتي", "يا Roben", "😊", "🚀"):
            assert banned not in letter, banned
        # Invites targeting without re-asking as a blocker
        assert "محدد" in letter

    def test_english_letter_uses_real_profile_only(self, chat):
        letter = chat._generic_cover_letter(_profile(), arabic=False)
        assert "8 years" in letter
        assert "General Manager" in letter
        assert "iso 14001" in letter
        assert "Roben Edwan" in letter

    def test_empty_profile_letter_never_fabricates(self, chat):
        empty = SimpleNamespace(
            name=None, years_experience=None, current_role=None,
            skills=[], certifications=[], target_roles=[],
        )
        letter_ar = chat._generic_cover_letter(empty, arabic=True)
        letter_en = chat._generic_cover_letter(empty, arabic=False)
        for letter in (letter_ar, letter_en):
            # No invented numbers, roles, or names
            assert "None" not in letter
            assert "8" not in letter
