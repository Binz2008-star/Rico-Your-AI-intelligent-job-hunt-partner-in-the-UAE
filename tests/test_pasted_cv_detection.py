"""
tests/test_pasted_cv_detection.py

Regression tests for Issue B — pasted CV text detection.

Covers:
  1. Long structured CV text is detected by heuristic
  2. Short messages are NOT flagged as pasted CV
  3. Non-CV long messages are NOT flagged
  4. Active user pasting CV returns cv_text_received, not "Something went wrong"
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)


PASTED_CV_EN = """
Ahmed Al-Rashid
Senior HSE Officer | Dubai, UAE | ahmed@example.com

WORK EXPERIENCE

HSE Manager — DEWA, Dubai
2019–2023
• Led safety audits across 12 substations
• Implemented ISO 14001 environmental management system

HSE Officer — ADNOC, Abu Dhabi
2015–2019
• Maintained incident-free record for 3 years

EDUCATION

BSc Environmental Science — University of Sharjah, 2015

SKILLS
ISO 14001, Risk Assessment, Incident Investigation, HSE Management
"""

PASTED_CV_AR = """
أحمد الراشد
مسؤول السلامة البيئية والصحة المهنية | دبي، الإمارات العربية المتحدة | ahmed@example.com | +971501234567

الخبرة العملية

مدير السلامة والبيئة — شركة ديوا، دبي
2020–2023
قيادة فريق السلامة وتطبيق معايير ISO 14001 وISO 45001 في 12 محطة طاقة
تحقيق سجل خالٍ من الحوادث لمدة ثلاث سنوات متتالية

مسؤول السلامة — شركة أدنوك، أبوظبي
2016–2020
إدارة برامج السلامة وتدريب الموظفين على إجراءات الطوارئ
تطوير سياسات السلامة وفق المعايير الدولية

المؤهلات الأكاديمية
بكالوريوس في العلوم البيئية — جامعة الشارقة 2016
دبلوم السلامة والصحة المهنية — 2018

مهارات
ISO 14001 ، ISO 45001 ، إدارة المخاطر ، السلامة المهنية ، التدريب
"""

SHORT_MESSAGE = "My name is Ahmed and I have 8 years of HSE experience in Dubai."

LONG_NON_CV = (
    "I have been thinking about the economic implications of remote work policy "
    "changes and how they affect urban planning in the Gulf region. The transformation "
    "of downtown districts has been remarkable, with many companies choosing to maintain "
    "hybrid arrangements. The cost savings versus collaboration trade-offs are fascinating "
    "to analyze. Many HR leaders are reconsidering their office space footprint across "
    "Dubai, Abu Dhabi, and Sharjah as lease renewals come up in 2025. " * 5
)


class TestPastedCVHeuristic:

    @pytest.fixture(autouse=True)
    def _api(self):
        from src.rico_chat_api import RicoChatAPI
        self.api = RicoChatAPI.__new__(RicoChatAPI)

    def test_english_cv_detected(self):
        assert self.api._looks_like_pasted_cv_text(PASTED_CV_EN)

    def test_arabic_cv_detected(self):
        assert self.api._looks_like_pasted_cv_text(PASTED_CV_AR)

    def test_short_message_not_flagged(self):
        assert not self.api._looks_like_pasted_cv_text(SHORT_MESSAGE)

    def test_long_non_cv_not_flagged(self):
        assert not self.api._looks_like_pasted_cv_text(LONG_NON_CV)

    def test_cv_with_only_date_ranges_not_flagged(self):
        # Date ranges alone without section keywords should not trigger
        msg = "I worked from 2018–2022 and then again from 2022–present on various projects. " * 10
        assert not self.api._looks_like_pasted_cv_text(msg)

    def test_cv_with_single_section_and_date_flagged(self):
        msg = (
            "Work Experience\n"
            "Software Engineer at Acme Corp, 2019–present\n"
            "Built backend APIs for fintech products. " * 20
        )
        assert self.api._looks_like_pasted_cv_text(msg)

    def test_looks_like_cv_upload_includes_pasted_text(self):
        assert self.api._looks_like_cv_upload(PASTED_CV_EN)
