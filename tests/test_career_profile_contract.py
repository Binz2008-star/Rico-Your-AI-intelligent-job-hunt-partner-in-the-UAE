"""Contract tests for the Rico Career Profile data model (PR 1).

These tests exercise the typed schema, server-owned provenance, and the
storage round-trip. They run against whatever storage Rico is configured to
use (JSON mirror or Postgres) so the contract is valid for both backends.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.rico_agent import RicoProfile
from src.schemas.career_profile import (
    CareerProfile,
    CertificationItem,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    ProvenanceState,
    SkillItem,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_career_profile():
    return CareerProfile(
        summary="Backend engineer focused on distributed systems.",
        experience=[
            ExperienceItem(
                id="exp-1",
                role="Backend Engineer",
                company="Rico",
                provenance=ProvenanceState.CONFIRMED_BY_USER,
                confirmed_at="2026-07-31T00:00:00+00:00",
                updated_at="2026-07-31T00:00:00+00:00",
            )
        ],
        skills=[SkillItem(id="sk-1", name="Python")],
        languages=[LanguageItem(id="lang-1", name="English", proficiency="Native")],
    )


def _mock_current_user(request):
    user = {"email": "contract-test@example.com", "role": "user"}
    request.state.current_user = user
    request.state.user_id = user["email"]
    return user


def _mock_get_settings(user_id=None):
    from src.rico_agent import RicoAgentSettings
    return RicoAgentSettings()


def _mock_profile_context(user_id):
    return SimpleNamespace(
        profile=None,
        canonical_user_id=user_id,
        completeness_score=0.42,
        missing_required=["target_roles"],
        missing_optional=["summary"],
    )


def _mock_svc_ctx(user_id, profile):
    return SimpleNamespace(completeness_score=0.42, missing=[], unconfirmed=[])


def _mock_has_career_data(ctx):
    return True


class TestGetProfileContract:
    def test_get_profile_backward_compatible_when_career_profile_absent(
        self, client, monkeypatch
    ):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo
        import src.services.settings_service as settings_service
        import src.services.profile_context_resolver as svc
        import src.agent.context.resolver as agent_ctx

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)
        monkeypatch.setattr(profile_repo, "get_profile", lambda user_id: RicoProfile(
            user_id=user_id,
            email=user_id,
            name="Test User",
            target_roles=["Engineer"],
            preferred_cities=["Dubai"],
            years_experience=5.0,
            skills=["Python"],
        ))
        monkeypatch.setattr(settings_service, "get_settings", _mock_get_settings)
        monkeypatch.setattr(agent_ctx, "resolve_profile_context", _mock_profile_context)
        monkeypatch.setattr(svc, "resolve_profile_context", _mock_svc_ctx)
        monkeypatch.setattr(svc, "has_career_profile_data", _mock_has_career_data)

        response = client.get("/api/v1/rico/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["career_profile"] is None
        assert data["completeness"]["score"] == 0.42
        assert all(s["section"] for s in data["completeness"]["sections"])
        assert data["completeness"]["sections"][0]["missing"] is not None

    def test_get_profile_returns_typed_career_profile_and_completeness(
        self, client, monkeypatch, sample_career_profile
    ):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo
        import src.services.settings_service as settings_service
        import src.services.profile_context_resolver as svc
        import src.agent.context.resolver as agent_ctx

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)
        monkeypatch.setattr(profile_repo, "get_profile", lambda user_id: RicoProfile(
            user_id=user_id,
            email=user_id,
            career_profile=sample_career_profile.model_dump(),
            cv_status="parsed",
        ))
        monkeypatch.setattr(settings_service, "get_settings", _mock_get_settings)
        monkeypatch.setattr(agent_ctx, "resolve_profile_context", _mock_profile_context)
        monkeypatch.setattr(svc, "resolve_profile_context", _mock_svc_ctx)
        monkeypatch.setattr(svc, "has_career_profile_data", _mock_has_career_data)

        response = client.get("/api/v1/rico/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["career_profile"]["summary"] == "Backend engineer focused on distributed systems."
        assert data["career_profile"]["experience"][0]["provenance"] == "confirmed_by_user"
        assert data["career_profile"]["skills"][0]["name"] == "Python"


class TestPatchProfileContract:
    def test_patch_rejects_unknown_provenance_state(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [
                        {"provenance": "hacked", "role": "CEO"}
                    ]
                }
            },
        )

        assert response.status_code == 422

    def test_patch_rejects_client_confirmation_timestamps(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [
                        {"confirmed_at": "2020-01-01T00:00:00Z", "role": "CEO"}
                    ]
                }
            },
        )

        assert response.status_code == 422

    def test_patch_rejects_invalid_structured_item_shape(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [
                        {"not_a_valid_field": "value"}
                    ]
                }
            },
        )

        assert response.status_code == 422

    def test_patch_preserves_existing_profile_fields(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        captured = {}

        def mock_upsert_profile(user_id, updates, **kwargs):
            captured["updates"] = updates
            return RicoProfile(user_id=user_id, email=user_id, **updates)

        def mock_visible(*args, **kwargs):
            return True

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)
        monkeypatch.setattr(rico_chat, "upsert_profile", mock_upsert_profile)
        monkeypatch.setattr(rico_chat, "_profile_updates_visible", mock_visible)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "phone": "+971501234567",
                "career_profile": {
                    "summary": "Updated summary",
                    "skills": [{"name": "Go"}],
                },
            },
        )

        assert response.status_code == 200
        assert captured["updates"]["phone"] == "+971501234567"
        assert "career_profile" in captured["updates"]


class TestUploadPreviewContract:
    def test_upload_cv_preview_returns_typed_experience_and_education(
        self, client, monkeypatch
    ):
        import src.services.chat_service as chat_service

        def mock_parse_cv(data, filename):
            return {
                "text": "Senior Python developer at Rico for 5 years.",
                "document_type": "cv",
                "extraction_quality": "high",
                "extracted_chars": 120,
                "skills": ["Python", "PostgreSQL"],
                "work_experience": [
                    {
                        "role": "Senior Python Developer",
                        "company": "Rico",
                        "start_date": "2021-01",
                        "end_date": "2026-07",
                    }
                ],
                "education": [
                    {
                        "institution": "University of Dubai",
                        "degree": "BSc",
                        "field": "Computer Science",
                    }
                ],
            }

        monkeypatch.setattr(chat_service, "parse_cv", mock_parse_cv)

        response = client.post(
            "/api/v1/rico/upload-cv",
            data={"user_id": "public:contracttest"},
            files={"file": ("cv.txt", b"Senior Python developer at Rico for 5 years.", "text/plain")},
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["status"] == "preview_ready"
        assert data["preview"]["work_experience"][0]["provenance"] == "extracted_from_cv"
        assert data["preview"]["work_experience"][0]["role"] == "Senior Python Developer"
        assert data["preview"]["education"][0]["institution"] == "University of Dubai"

    def test_upload_cv_sanitizes_malformed_experience_entries(
        self, client, monkeypatch
    ):
        import src.services.chat_service as chat_service

        def mock_parse_cv(data, filename):
            return {
                "text": "Senior Python developer with extensive backend experience.",
                "document_type": "cv",
                "extraction_quality": "high",
                "extracted_chars": 120,
                "skills": [],
                "work_experience": [
                    {
                        "role": None,
                        "unexpected_key": "ignored",
                    }
                ],
                "education": [],
            }

        monkeypatch.setattr(chat_service, "parse_cv", mock_parse_cv)

        response = client.post(
            "/api/v1/rico/upload-cv",
            data={"user_id": "public:contracttest"},
            files={"file": ("cv.txt", b"Senior Python developer with extensive backend experience.", "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        # malformed/extra keys are ignored, the entry still becomes a typed ExperienceItem
        assert data["preview"]["work_experience"][0]["provenance"] == "extracted_from_cv"
        assert data["preview"]["work_experience"][0].get("unexpected_key") is None


class TestRepoContract:
    def test_career_profile_round_trips_through_storage(self):
        from src.repositories.profile_repo import upsert_profile, get_profile

        user_id = f"contract-roundtrip-{id(self)}@example.com"
        career = CareerProfile(
            summary="Round-trip test",
            skills=[SkillItem(name="Rust")],
        )

        upsert_profile(user_id, {"career_profile": career.model_dump()})
        stored = get_profile(user_id)

        assert stored is not None
        assert stored.career_profile["summary"] == "Round-trip test"
        assert stored.career_profile["skills"][0]["name"] == "Rust"


class TestPreviewSanitization:
    def test_upload_cv_preview_overwrites_parser_server_owned_fields(self, client, monkeypatch):
        import src.services.chat_service as chat_service

        def mock_parse_cv(data, filename):
            return {
                "text": "Senior Python developer with extensive backend and cloud experience.",
                "document_type": "cv",
                "extraction_quality": "high",
                "extracted_chars": 120,
                "skills": [],
                "work_experience": [
                    {
                        "id": "parser-exp-id",
                        "provenance": "hacked",
                        "source_document_id": "parser-doc-id",
                        "confidence": 0.95,
                        "confirmed_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "role": "CEO",
                        "company": "ParserCo",
                    }
                ],
                "education": [
                    {
                        "id": "parser-edu-id",
                        "provenance": "hacked",
                        "source_document_id": "parser-doc-id",
                        "confidence": 0.9,
                        "confirmed_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "institution": "Parser U",
                        "degree": "PhD",
                    }
                ],
            }

        monkeypatch.setattr(chat_service, "parse_cv", mock_parse_cv)

        response = client.post(
            "/api/v1/rico/upload-cv",
            data={"user_id": "public:contracttest"},
            files={"file": ("cv.txt", b"test", "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        exp = data["preview"]["work_experience"][0]
        edu = data["preview"]["education"][0]
        assert exp["id"] != "parser-exp-id"
        assert exp["provenance"] == "extracted_from_cv"
        assert exp["source_document_id"] is None
        assert exp["confidence"] is None
        assert exp["confirmed_at"] is None
        assert exp["updated_at"] is None
        assert exp["role"] == "CEO"
        assert exp["company"] == "ParserCo"
        assert edu["id"] != "parser-edu-id"
        assert edu["provenance"] == "extracted_from_cv"
        assert edu["source_document_id"] is None
        assert edu["confidence"] is None


class TestMalformedStorageRead:
    def test_get_profile_with_malformed_career_profile_returns_200(self, client, monkeypatch, caplog):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo
        import src.services.settings_service as settings_service
        import src.services.profile_context_resolver as svc
        import src.agent.context.resolver as agent_ctx

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)
        monkeypatch.setattr(profile_repo, "get_profile", lambda user_id: RicoProfile(
            user_id=user_id,
            email=user_id,
            name="Test User",
            target_roles=["Engineer"],
            career_profile={
                "provenance": "totally_invalid_state",
                "experience": [{"provenance": "also_invalid", "role": "Dev"}],
            },
        ))
        monkeypatch.setattr(settings_service, "get_settings", _mock_get_settings)
        monkeypatch.setattr(agent_ctx, "resolve_profile_context", _mock_profile_context)
        monkeypatch.setattr(svc, "resolve_profile_context", _mock_svc_ctx)
        monkeypatch.setattr(svc, "has_career_profile_data", _mock_has_career_data)

        with caplog.at_level("WARNING"):
            response = client.get("/api/v1/rico/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["career_profile"] is None
        assert data["name"] == "Test User"
        assert data["completeness"]["score"] == 0.42
        assert "totally_invalid_state" not in caplog.text
        assert "also_invalid" not in caplog.text


class TestPatchReadAfterWrite:
    def test_patch_career_profile_persists_and_verifies(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old summary",
            experience=[ExperienceItem(id="exp-1", role="Dev", company="OldCo")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        profile_repo.upsert_profile(
            user_id,
            {"name": "Test", "career_profile": existing.model_dump()},
            require_db=False,
        )

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "summary": "New summary",
                    "skills": [{"id": "sk-1", "name": "Go"}],
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] == "New summary"
        assert stored.career_profile["experience"][0]["role"] == "Dev"
        assert stored.career_profile["skills"][0]["name"] == "Go"
        assert stored.career_profile["skills"][0]["provenance"] == "edited_by_user"

    def test_profile_updates_visible_detects_genuine_mismatch(self, client, monkeypatch):
        import src.repositories.profile_repo as profile_repo
        from src.api.routers.rico_chat import _profile_updates_visible

        def fake_get(user_id):
            return RicoProfile(
                user_id=user_id,
                email=user_id,
                career_profile={"summary": "A", "experience": []},
            )

        monkeypatch.setattr(profile_repo, "get_profile", fake_get)

        assert _profile_updates_visible("x", {"career_profile": {"summary": "B"}}) is False


class TestPatchPartialUpdate:
    def test_patch_summary_only_preserves_every_list(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            education=[EducationItem(id="edu-1", institution="U")],
            skills=[SkillItem(id="sk-1", name="Python")],
            languages=[LanguageItem(id="lang-1", name="English")],
            certifications=[CertificationItem(id="cert-1", name="AWS")],
        )
        profile_repo.upsert_profile(
            user_id,
            {"career_profile": existing.model_dump()},
            require_db=False,
        )

        response = client.patch(
            "/api/v1/rico/profile",
            json={"career_profile": {"summary": "New"}},
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] == "New"
        assert stored.career_profile["experience"][0]["id"] == "exp-1"
        assert stored.career_profile["education"][0]["id"] == "edu-1"
        assert stored.career_profile["skills"][0]["id"] == "sk-1"
        assert stored.career_profile["languages"][0]["id"] == "lang-1"
        assert stored.career_profile["certifications"][0]["id"] == "cert-1"

    def test_patch_skills_only_preserves_other_sections(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        profile_repo.upsert_profile(
            user_id,
            {"career_profile": existing.model_dump()},
            require_db=False,
        )

        response = client.patch(
            "/api/v1/rico/profile",
            json={"career_profile": {"skills": [{"name": "Go"}]}},
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] == "Old"
        assert stored.career_profile["experience"][0]["role"] == "Dev"
        assert stored.career_profile["skills"][0]["name"] == "Go"

    def test_patch_explicit_empty_list_clears_only_that_section(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        profile_repo.upsert_profile(
            user_id,
            {"career_profile": existing.model_dump()},
            require_db=False,
        )

        response = client.patch(
            "/api/v1/rico/profile",
            json={"career_profile": {"experience": []}},
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] == "Old"
        assert stored.career_profile["experience"] == []
        assert stored.career_profile["skills"][0]["name"] == "Python"

    def test_patch_explicit_null_clears_summary(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        profile_repo.upsert_profile(
            user_id,
            {"career_profile": existing.model_dump()},
            require_db=False,
        )

        response = client.patch(
            "/api/v1/rico/profile",
            json={"career_profile": {"summary": None}},
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] is None
        assert stored.career_profile["skills"][0]["name"] == "Python"

    def test_patch_unknown_item_id_is_rejected(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "does-not-exist", "role": "CEO"}],
                }
            },
        )

        assert response.status_code == 422


class TestIdOwnershipAndUniqueness:
    def _seed_user(self, user_id, career):
        from src.repositories import profile_repo
        profile_repo.upsert_profile(
            user_id,
            {"name": "Test", "career_profile": career.model_dump()},
            require_db=False,
        )

    def test_patch_skill_id_submitted_as_experience_is_rejected(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "sk-1", "role": "CEO"}],
                }
            },
        )

        assert response.status_code == 422

    def test_patch_education_id_submitted_as_certification_is_rejected(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            education=[EducationItem(id="edu-1", institution="U")],
            certifications=[CertificationItem(id="cert-1", name="AWS")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "certifications": [{"id": "edu-1", "name": "PMP"}],
                }
            },
        )

        assert response.status_code == 422

    def test_patch_same_id_submitted_twice_in_one_section_is_rejected(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            experience=[ExperienceItem(id="exp-1", role="Dev")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [
                        {"id": "exp-1", "role": "CEO"},
                        {"id": "exp-1", "role": "CTO"},
                    ],
                }
            },
        )

        assert response.status_code == 422

    def test_patch_same_id_submitted_in_two_sections_is_rejected(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "exp-1", "role": "CEO"}],
                    "skills": [{"id": "exp-1", "name": "Go"}],
                }
            },
        )

        assert response.status_code == 422

    def test_career_profile_model_rejects_duplicate_ids(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CareerProfile(
                experience=[ExperienceItem(id="dup-1", role="Dev")],
                skills=[SkillItem(id="dup-1", name="Python")],
            )

    def test_get_profile_safe_when_duplicate_ids_in_storage(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo
        import src.services.settings_service as settings_service
        import src.services.profile_context_resolver as svc
        import src.agent.context.resolver as agent_ctx

        user_id = "contract-dupe@example.com"
        profile_repo.upsert_profile(
            user_id,
            {
                "career_profile": {
                    "experience": [{"id": "dup-1", "role": "Dev"}],
                    "skills": [{"id": "dup-1", "name": "Python"}],
                }
            },
            require_db=False,
        )

        def mock_current_user(request):
            user = {"email": user_id, "role": "user"}
            request.state.current_user = user
            request.state.user_id = user["email"]
            return user

        def mock_get_settings(user_id=None):
            from src.rico_agent import RicoAgentSettings
            return RicoAgentSettings()

        monkeypatch.setattr(rico_chat, "get_current_user", mock_current_user)
        monkeypatch.setattr(settings_service, "get_settings", mock_get_settings)
        monkeypatch.setattr(agent_ctx, "resolve_profile_context", _mock_profile_context)
        monkeypatch.setattr(svc, "resolve_profile_context", _mock_svc_ctx)
        monkeypatch.setattr(svc, "has_career_profile_data", _mock_has_career_data)

        response = client.get("/api/v1/rico/profile")

        assert response.status_code == 200
        assert response.json()["career_profile"] is None

    def test_patch_valid_same_section_edit_succeeds(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "exp-1", "role": "Senior Dev"}],
                }
            },
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["experience"][0]["role"] == "Senior Dev"
        assert stored.career_profile["experience"][0]["provenance"] == "edited_by_user"
        assert stored.career_profile["skills"][0]["name"] == "Python"

    def test_patch_valid_same_section_edit_preserves_omitted_sections(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            summary="Old",
            experience=[ExperienceItem(id="exp-1", role="Dev")],
            education=[EducationItem(id="edu-1", institution="U")],
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "exp-1", "role": "Senior Dev"}],
                }
            },
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        assert stored.career_profile["summary"] == "Old"
        assert stored.career_profile["experience"][0]["role"] == "Senior Dev"
        assert stored.career_profile["education"][0]["id"] == "edu-1"
        assert stored.career_profile["skills"][0]["id"] == "sk-1"

    def test_patch_rejected_request_never_calls_upsert(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def boom(*args, **kwargs):
            raise AssertionError("upsert_profile should not be called for rejected input")

        monkeypatch.setattr(rico_chat, "upsert_profile", boom)

        user_id = "contract-test@example.com"
        existing = CareerProfile(
            skills=[SkillItem(id="sk-1", name="Python")],
        )
        self._seed_user(user_id, existing)

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [{"id": "sk-1", "role": "CEO"}],
                }
            },
        )

        assert response.status_code == 422

    def test_new_items_receive_unique_server_generated_ids(self, client, monkeypatch):
        import src.api.routers.rico_chat as rico_chat
        import src.repositories.profile_repo as profile_repo

        monkeypatch.setattr(rico_chat, "get_current_user", _mock_current_user)

        def _patched_upsert(user_id, updates, *, require_db=True, clear_fields=(), **kwargs):
            return profile_repo.upsert_profile(
                user_id, updates, require_db=False, clear_fields=clear_fields, **kwargs
            )

        monkeypatch.setattr(rico_chat, "upsert_profile", _patched_upsert)

        user_id = "contract-test@example.com"

        response = client.patch(
            "/api/v1/rico/profile",
            json={
                "career_profile": {
                    "experience": [
                        {"role": "A"},
                        {"role": "B"},
                    ],
                }
            },
        )

        assert response.status_code == 200
        stored = profile_repo.get_profile(user_id)
        ids = [e["id"] for e in stored.career_profile["experience"]]
        assert len(ids) == 2
        assert all(ids)
        assert ids[0] != ids[1]
