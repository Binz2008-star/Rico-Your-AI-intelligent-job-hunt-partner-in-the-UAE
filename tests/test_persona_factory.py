# -*- coding: utf-8 -*-
"""Self-test for the synthetic persona/CV factory (PR1 of the reliability
test program). Verifies the factory's own guarantees before any other test
suite is allowed to depend on it:

  * determinism (same run_id -> same personas/fixtures);
  * no cross-run_id user_id collisions;
  * no PII / real-looking identifiers in generated content;
  * every declared CV variant kind is buildable;
  * failure-path fixtures are flagged as such;
  * isolation collision-pair helpers actually produce a genuine collision on
    exactly the declared attribute, and nothing else.
"""
from __future__ import annotations

import re

import pytest

from tests.factory.isolation import (
    build_same_cv_hash_pair,
    build_same_filename_pair,
    build_same_target_role_pair,
    build_similar_name_pair,
)
from tests.factory.personas import (
    CV_VARIANT_KINDS,
    CAREER_PERSONAS,
    DOCUMENT_STYLES,
    LANGUAGES,
    build_cv_fixture,
    build_cv_matrix,
    build_personas,
)


# --- Determinism -------------------------------------------------------------

def test_build_personas_is_deterministic():
    a = build_personas("run-1", count=20)
    b = build_personas("run-1", count=20)
    assert [p.user_id for p in a] == [p.user_id for p in b]
    assert [p.fingerprint for p in a] == [p.fingerprint for p in b]


def test_different_run_ids_never_collide_on_user_id():
    a = build_personas("run-a", count=50)
    b = build_personas("run-b", count=50)
    ids_a = {p.user_id for p in a}
    ids_b = {p.user_id for p in b}
    assert ids_a.isdisjoint(ids_b)


def test_personas_within_a_run_have_unique_user_ids():
    personas = build_personas("run-unique")
    ids = [p.user_id for p in personas]
    assert len(ids) == len(set(ids))


# --- No PII ------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    re.compile(r"\b\+?9715\d{8}\b"),  # UAE mobile-like pattern
    re.compile(r"\b\d{3}-\d{4}-\d{7}-\d\b"),  # Emirates ID-like pattern
    re.compile(r"@gmail\.com|@yahoo\.com|@hotmail\.com", re.IGNORECASE),
]


def test_synthetic_content_contains_no_pii_patterns():
    personas = build_personas("pii-check", count=10)
    for persona in personas:
        assert persona.user_id.endswith("@rico-synthetic-test.invalid")
        fixture = build_cv_fixture(persona, "single")
        for pattern in _FORBIDDEN_PATTERNS:
            assert not pattern.search(fixture.content), (pattern.pattern, fixture.content)
            assert not pattern.search(persona.display_name)


# --- CV variant coverage -------------------------------------------------------

@pytest.mark.parametrize("variant", CV_VARIANT_KINDS)
def test_every_declared_variant_is_buildable(variant):
    persona = build_personas("variant-check", count=1)[0]
    fixture = build_cv_fixture(persona, variant)
    assert fixture.variant == variant
    assert fixture.filename


def test_unknown_variant_rejected():
    persona = build_personas("bad-variant", count=1)[0]
    with pytest.raises(ValueError):
        build_cv_fixture(persona, "not_a_real_variant")


def test_failure_path_fixtures_are_flagged():
    persona = build_personas("failure-flags", count=1)[0]
    for variant in ("corrupted_pdf", "password_protected_pdf", "oversized_file", "unsupported_extension"):
        fixture = build_cv_fixture(persona, variant)
        assert fixture.expect_failure_path is True, variant
    healthy = build_cv_fixture(persona, "single")
    assert healthy.expect_failure_path is False


def test_build_cv_matrix_covers_all_requested_variants():
    personas = build_personas("matrix-check", count=3)
    variants = ("single", "docx", "arabic_pdf")
    fixtures = build_cv_matrix(personas, variants)
    assert len(fixtures) == len(personas) * len(variants)
    seen = {(f.persona.user_id, f.variant) for f in fixtures}
    assert len(seen) == len(fixtures)


def test_persona_matrix_covers_every_career_and_style():
    personas = build_personas("full-matrix")
    careers = {p.career for p in personas}
    styles = {p.document_style for p in personas}
    languages = {p.language for p in personas}
    assert careers == set(CAREER_PERSONAS)
    assert styles == set(DOCUMENT_STYLES)
    assert languages == set(LANGUAGES)


# --- Isolation collision-pair helpers ------------------------------------------

def test_same_filename_pair_shares_only_filename():
    pair = build_same_filename_pair("collision-filename")
    assert pair.cv_a.filename == pair.cv_b.filename
    assert pair.user_a.user_id != pair.user_b.user_id
    assert pair.cv_a.content_hash != pair.cv_b.content_hash


def test_same_cv_hash_pair_shares_only_content():
    pair = build_same_cv_hash_pair("collision-hash")
    assert pair.cv_a.content_hash == pair.cv_b.content_hash
    assert pair.cv_a.filename != pair.cv_b.filename
    assert pair.user_a.user_id != pair.user_b.user_id


def test_similar_name_pair_has_distinct_user_ids():
    pair = build_similar_name_pair("collision-name")
    assert pair.user_a.user_id != pair.user_b.user_id
    assert pair.user_a.display_name != pair.user_b.display_name


def test_same_target_role_pair_shares_career_but_not_identity():
    pair = build_same_target_role_pair("collision-role")
    assert pair.user_a.career == pair.user_b.career
    assert pair.user_a.user_id != pair.user_b.user_id
