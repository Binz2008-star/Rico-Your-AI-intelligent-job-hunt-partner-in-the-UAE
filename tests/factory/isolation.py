# -*- coding: utf-8 -*-
"""Cross-user isolation fixture helpers built on top of ``tests.factory.personas``.

Provides ready-made "collision" pairs — two synthetic users who deliberately
share a filename, CV byte-content, display name, or target role — for tests
that assert isolation invariants (Journey E in the reliability test program).

No I/O, no network, no database access.
"""
from __future__ import annotations

from dataclasses import dataclass

from tests.factory.personas import CvFixture, Persona, build_cv_fixture, build_personas


@dataclass(frozen=True)
class CollisionPair:
    """Two distinct synthetic users who share one deliberately-colliding attribute."""

    user_a: Persona
    user_b: Persona
    collision_kind: str
    cv_a: CvFixture
    cv_b: CvFixture


def build_same_filename_pair(run_id: str) -> CollisionPair:
    """Two users uploading different content under the identical filename."""
    personas = build_personas(run_id, count=2)
    user_a, user_b = personas[0], personas[1]
    cv_a = build_cv_fixture(user_a, "single")
    cv_b = build_cv_fixture(user_b, "single")
    shared_name = "cv-shared-filename.txt"
    cv_a = CvFixture(
        persona=user_a, variant=cv_a.variant, filename=shared_name, content=cv_a.content, extension=cv_a.extension
    )
    cv_b = CvFixture(
        persona=user_b, variant=cv_b.variant, filename=shared_name, content=cv_b.content, extension=cv_b.extension
    )
    return CollisionPair(user_a=user_a, user_b=user_b, collision_kind="same_filename", cv_a=cv_a, cv_b=cv_b)


def build_same_cv_hash_pair(run_id: str) -> CollisionPair:
    """Two users uploading byte-identical CV content under different filenames."""
    personas = build_personas(run_id, count=2)
    user_a, user_b = personas[0], personas[1]
    shared_content = "CV\nIdentical synthetic content for hash-collision test.\n"
    cv_a = CvFixture(persona=user_a, variant="single", filename=f"cv-{user_a.fingerprint}.txt", content=shared_content)
    cv_b = CvFixture(persona=user_b, variant="single", filename=f"cv-{user_b.fingerprint}.txt", content=shared_content)
    assert cv_a.content_hash == cv_b.content_hash
    return CollisionPair(user_a=user_a, user_b=user_b, collision_kind="same_cv_hash", cv_a=cv_a, cv_b=cv_b)


def build_similar_name_pair(run_id: str) -> CollisionPair:
    """Two users whose synthetic display names are near-duplicates."""
    personas = build_personas(run_id, count=2)
    user_a, user_b = personas[0], personas[1]
    cv_a = build_cv_fixture(user_a, "single")
    cv_b = build_cv_fixture(user_b, "single")
    return CollisionPair(user_a=user_a, user_b=user_b, collision_kind="similar_display_name", cv_a=cv_a, cv_b=cv_b)


def build_same_target_role_pair(run_id: str) -> CollisionPair:
    """Two users targeting the same career persona/role for search-isolation tests."""
    personas = build_personas(run_id, count=len(build_personas(run_id)))
    same_career = [p for p in personas if p.career == personas[0].career]
    user_a, user_b = same_career[0], same_career[1]
    cv_a = build_cv_fixture(user_a, "single")
    cv_b = build_cv_fixture(user_b, "single")
    return CollisionPair(user_a=user_a, user_b=user_b, collision_kind="same_target_role", cv_a=cv_a, cv_b=cv_b)
