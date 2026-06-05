"""
tests/test_cover_letter_generation.py

Regression tests for cover letter generation fix.

Covers:
  1. generate_message with full profile → real cover letter, not one-line stub
  2. generate_message with partial profile → asks for missing fields
  3. generate_message with no profile → graceful prompt
  4. No hardcoded identity in output
  5. Stub response "I am interested in the this role" never returned
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


def _job(**kw):
    defaults = {"title": "HSE Manager", "company": "DEWA", "location": "Dubai"}
    defaults.update(kw)
    return defaults


def _full_profile():
    return SimpleNamespace(
        name="Ahmed Al-Rashid",
        preferred_cities=["Dubai", "Abu Dhabi"],
        years_experience=8.0,
        skills=["ISO 14001", "HSE management", "risk assessment"],
        current_role="Senior HSE Officer",
        target_roles=["HSE Manager", "EHS Lead"],
        location=None,
        city=None,
    )


def _no_name_profile():
    return SimpleNamespace(
        name="",
        preferred_cities=["Dubai"],
        years_experience=5.0,
        skills=["compliance"],
        current_role=None,
        target_roles=[],
        location=None,
        city=None,
    )


def _no_city_profile():
    return SimpleNamespace(
        name="Sara Al-Mansoori",
        preferred_cities=[],
        years_experience=3.0,
        skills=["EHS"],
        current_role=None,
        target_roles=[],
        location="",
        city="",
    )


class TestGenerateMessage:

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.message_generator import generate_message
        self.generate = generate_message

    def test_full_profile_returns_real_cover_letter(self):
        result = self.generate(_job(), profile=_full_profile())
        # Must use the user's verified name
        assert "Ahmed Al-Rashid" in result
        # Must mention the job/company
        assert "DEWA" in result or "HSE Manager" in result
        # Must NOT be the old stub
        assert result != "I am interested in the HSE Manager role and would like to apply."
        assert "I am interested in the" not in result

    def test_no_name_profile_asks_for_name(self):
        result = self.generate(_job(), profile=_no_name_profile())
        assert "name" in result.lower()
        # Should not generate a cover letter with a blank name
        assert "I am interested in the" not in result

    def test_no_city_profile_asks_for_city(self):
        result = self.generate(_job(), profile=_no_city_profile())
        assert "city" in result.lower() or "location" in result.lower() or "dubai" in result.lower()

    def test_no_profile_returns_graceful_prompt(self):
        result = self.generate(_job(), profile=None)
        assert "cover letter" in result.lower() or "name" in result.lower()
        assert "I am interested in the" not in result

    def test_no_hardcoded_roben_identity(self):
        result = self.generate(_job(), profile=_full_profile())
        assert "Roben Edwan" not in result
        assert "Ajman, UAE" not in result
        assert "80+ locations" not in result
        assert "10+ years in environmental management" not in result

    def test_cover_letter_mentions_job_details(self):
        job = _job(title="ESG Specialist", company="Masdar", location="Abu Dhabi")
        result = self.generate(job, profile=_full_profile())
        assert "Masdar" in result or "ESG" in result

    def test_cover_letter_uses_profile_city(self):
        result = self.generate(_job(), profile=_full_profile())
        assert "Dubai" in result or "Ahmed" in result
