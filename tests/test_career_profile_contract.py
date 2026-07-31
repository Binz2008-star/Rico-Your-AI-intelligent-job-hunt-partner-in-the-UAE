"""Career Profile typed read-only contract tests.

These tests prove the new PR exposes a bounded, typed read contract derived
from canonical legacy storage, does not enable nested writes, and sanitizes
upload preview items with server-owned provenance.
"""
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.routers.rico_chat import (
    _build_education_preview,
    _build_experience_preview,
)
from src.rico_agent import RicoProfile
from src.schemas.career_profile import (
    CareerProfile,
    EducationItem,
    ExperienceItem,
    ProvenanceState,
)


@pytest.fixture(scope="module")
def client():
    from src.api.app import app
    return TestClient(app, raise_server_exceptions=False)


def _auth(client, monkeypatch, email: str):
    """Authenticate the test client for the given email."""
    monkeypatch.setattr(
        "src.api.routers.rico_chat.get_current_user",
        lambda request: {"email": email},
    )
    monkeypatch.setattr(
        "src.api.routers.rico_chat.build_matching_guardrail_warnings",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "src.services.profile_context_resolver.resolve_profile_context",
        lambda user_id, profile: SimpleNamespace(career_profile_data=True),
    )
    monkeypatch.setattr(
        "src.services.profile_context_resolver.has_career_profile_data",
        lambda ctx: True,
    )
    monkeypatch.setattr(
        "src.agent.context.resolver.resolve_profile_context",
        lambda user_id: SimpleNamespace(completeness_score=0.5),
    )
    monkeypatch.setattr(
        "src.services.settings_service.get_settings",
        lambda **kwargs: {},
    )
    return email


class TestCareerProfileReadContract:
    def test_get_profile_derives_career_profile_from_legacy(self, client, monkeypatch):
        email = _auth(client, monkeypatch, "cp-derive@example.com")
        monkeypatch.setattr(
            "src.api.routers.rico_chat.get_profile",
            lambda user_id: RicoProfile(
                user_id=email,
                name="Test",
                skills=["Python", "Arabic", ""],
                certifications=["PMP"],
                languages=["Arabic", "English"],
            ),
        )

        res = client.get("/api/v1/rico/profile")
        assert res.status_code == 200
        body = res.json()
        assert body["career_profile"] is not None
        skills = [s["name"] for s in body["career_profile"]["skills"]]
        assert skills == ["Python", "Arabic"]
        assert body["career_profile"]["certifications"][0]["name"] == "PMP"
        langs = [l["name"] for l in body["career_profile"]["languages"]]
        assert "Arabic" in langs and "English" in langs

    def test_get_profile_returns_none_when_empty(self, client, monkeypatch):
        email = _auth(client, monkeypatch, "cp-empty@example.com")
        monkeypatch.setattr(
            "src.api.routers.rico_chat.get_profile",
            lambda user_id: RicoProfile(user_id=email, name="Empty"),
        )

        res = client.get("/api/v1/rico/profile")
        assert res.status_code == 200
        body = res.json()
        assert body["career_profile"] is None

    def test_get_profile_safely_ignores_malformed_legacy_entries(self, client, monkeypatch):
        email = _auth(client, monkeypatch, "cp-malformed@example.com")
        monkeypatch.setattr(
            "src.api.routers.rico_chat.get_profile",
            lambda user_id: RicoProfile(
                user_id=email,
                skills=["Go", 123, None, "  ", "Rust"],
                certifications=[{"name": "invalid"}, None, "AWS"],
                languages=["English", 0, "French"],
            ),
        )

        res = client.get("/api/v1/rico/profile")
        assert res.status_code == 200
        body = res.json()
        assert body["career_profile"] is not None
        assert [s["name"] for s in body["career_profile"]["skills"]] == ["Go", "Rust"]
        assert [c["name"] for c in body["career_profile"]["certifications"]] == ["AWS"]
        assert [l["name"] for l in body["career_profile"]["languages"]] == ["English", "French"]

    def test_patch_profile_preserves_legacy_payload(self, client, monkeypatch):
        email = _auth(client, monkeypatch, "cp-patch-compat@example.com")
        monkeypatch.setattr(
            "src.api.routers.rico_chat.upsert_profile",
            lambda *a, **k: None,
        )
        monkeypatch.setattr(
            "src.api.routers.rico_chat._profile_updates_visible",
            lambda *a, **k: True,
        )
        res = client.patch(
            "/api/v1/rico/profile",
            json={
                "name": "Updated",
                "skills": ["TypeScript"],
                "certifications": ["AWS"],
                "languages": ["English"],
            },
        )
        assert res.status_code == 200

    def test_patch_does_not_accept_or_persist_career_profile(self, client, monkeypatch):
        email = _auth(client, monkeypatch, "cp-no-write@example.com")
        monkeypatch.setattr(
            "src.api.routers.rico_chat.get_profile",
            lambda user_id: RicoProfile(
                user_id=email,
                skills=["Python"],
                certifications=[],
                languages=[],
            ),
        )

        res = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "skills": [{"name": "Forged"}],
                    "certifications": [{"name": "Forged"}],
                },
            },
        )
        assert res.status_code == 200

        get_res = client.get("/api/v1/rico/profile")
        body = get_res.json()
        assert body["career_profile"] is not None
        assert [s["name"] for s in body["career_profile"]["skills"]] == ["Python"]
        assert body["career_profile"]["certifications"] == []


class TestUploadPreviewSanitation:
    def test_experience_preview_truncates_and_overwrites_metadata(self):
        raw = [
            {
                "role": "Senior Software Engineer" + "x" * 500,
                "company": "Rico " * 60,
                "description": "Built " + "things " * 1000,
                "location": "Dubai " * 60,
                "provenance": "client_forged",
                "id": "client-id",
                "confidence": 0.95,
            },
            {"role": "Junior", "company": "OldCo"},
        ]

        preview = _build_experience_preview(raw)
        assert len(preview) == 2
        first = preview[0]
        assert len(first["role"]) <= 200
        assert len(first["company"]) <= 200
        assert len(first["description"]) <= 2000
        assert len(first["location"]) <= 200
        assert first["provenance"] == ProvenanceState.EXTRACTED_FROM_CV.value
        assert first["id"] is None
        assert first["source_document_id"] is None
        assert first["confidence"] is None
        assert first["confirmed_at"] is None
        assert first["updated_at"] is None

    def test_experience_preview_caps_count(self):
        raw = [{"role": f"Role {i}"} for i in range(60)]
        preview = _build_experience_preview(raw)
        assert len(preview) == 50

    def test_education_preview_overwrites_parser_metadata(self):
        raw = [
            {
                "institution": "University",
                "degree": "BSc",
                "field": "CS",
                "provenance": "suggested_by_rico",
                "id": "parser-id",
                "source_document_id": "doc-id",
                "confirmed_at": "2020-01-01",
            }
        ]

        preview = _build_education_preview(raw)
        assert len(preview) == 1
        first = preview[0]
        assert first["provenance"] == ProvenanceState.EXTRACTED_FROM_CV.value
        assert first["id"] is None
        assert first["source_document_id"] is None
        assert first["confirmed_at"] is None

    def test_education_preview_caps_count(self):
        raw = [{"institution": f"School {i}"} for i in range(25)]
        preview = _build_education_preview(raw)
        assert len(preview) == 20


class TestCareerProfileSchemas:
    def test_experience_item_bounds(self):
        with pytest.raises(Exception):
            ExperienceItem(role="x" * 201)

    def test_education_item_bounds(self):
        with pytest.raises(Exception):
            EducationItem(institution="x" * 201)

    def test_career_profile_coerces_from_legacy_lists(self):
        cp = CareerProfile(
            skills=[{"name": "Python"}],
            certifications=[{"name": "PMP"}],
            languages=[{"name": "Arabic", "proficiency": "Native"}],
        )
        assert cp.skills[0].name == "Python"
        assert cp.certifications[0].name == "PMP"
        assert cp.languages[0].proficiency == "Native"
