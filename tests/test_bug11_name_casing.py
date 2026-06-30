"""
tests/test_bug11_name_casing.py

Regression tests for BUG-11 — "name casing inconsistency in profile" found in
the 2026-06-30 smoke test.

Problem:
  ``CVParser._extract_name`` returned the candidate name line completely
  verbatim. CV headers are routinely styled ALL CAPS (e.g. "ROBEN EDWAN") by
  the candidate's chosen template, so the casing of the ``name`` written to
  the profile depended entirely on how that particular CV happened to be
  formatted — producing a name that read inconsistently (e.g.
  "Hi ROBEN EDWAN," in one chat reply) against the same person's
  properly-cased, manually-typed signup name elsewhere in the product.

Fix:
  ``_extract_name`` now normalizes the candidate line with ``.title()``
  before returning it, mirroring the casing convention ``_extract_current_role``
  already applies in this same file. This guarantees a consistent Title Case
  name regardless of how the source CV was styled.
"""
from __future__ import annotations

from src.cv_parser import CVParser


class TestExtractedNameCasingNormalized:
    """A CV-derived name must always come back in consistent Title Case."""

    def _parser(self):
        return CVParser()

    def test_all_caps_cv_header_normalized(self):
        parser = self._parser()
        text = "ROBEN EDWAN\nHSE MANAGER\nroben@email.com"
        assert parser._extract_name(text) == "Roben Edwan"

    def test_already_title_case_name_unaffected(self):
        parser = self._parser()
        text = "John Smith\nSoftware Engineer\njohn@email.com"
        assert parser._extract_name(text) == "John Smith"

    def test_hyphenated_name_normalized(self):
        parser = self._parser()
        text = "JEAN-PAUL SARTRE\nPhilosopher\njp@email.com"
        assert parser._extract_name(text) == "Jean-Paul Sartre"

    def test_partially_capitalized_header_normalized(self):
        parser = self._parser()
        text = "ROBEN edwan\nHSE Manager\nroben@email.com"
        assert parser._extract_name(text) == "Roben Edwan"
