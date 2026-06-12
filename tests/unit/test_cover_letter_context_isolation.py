from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_EMAIL", "rico-test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "ricopass123")
os.environ.setdefault("JWT_SECRET", "ricosecret" + "x" * 21)

from src.rico_chat_api import RicoChatAPI


USER_A = "user-a@example.com"
USER_B = "user-b@example.com"


def _systra_context() -> dict:
    job = {
        "title": "Environmental Manager",
        "company": "SYSTRA",
        "location": "UAE",
        "status": "prepared",
    }
    return {
        "_pending_application_send": {"job": dict(job), "draft": "old draft"},
        "recent_application": dict(job),
        "recent_job": "Environmental Manager",
        "recent_company": "SYSTRA",
    }


def _profile(current_role: str = "Technical Product Owner / Operations Manager") -> SimpleNamespace:
    return SimpleNamespace(
        has_cv=True,
        name="Smoke User",
        preferred_cities=["Dubai"],
        location="Dubai",
        years_experience=9,
        skills=["HSE leadership", "operations management", "compliance"],
        certifications=[],
        target_roles=["Operations Manager"],
        current_role=current_role,
    )


def _agent() -> MagicMock:
    return MagicMock(
        openai_available=False,
        deepseek_available=False,
        hf_available=False,
        provider_available=False,
        model="",
    )


def _api(contexts: dict[str, dict]) -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    api.memory.get_context.side_effect = (
        lambda user_id, key: contexts.setdefault(user_id, {}) if key == "recent_context" else None
    )
    api.memory.set_context.side_effect = (
        lambda user_id, key, value: contexts.__setitem__(user_id, dict(value))
        if key == "recent_context"
        else None
    )
    return api


def _run(
    message: str,
    *,
    user_id: str = USER_B,
    contexts: dict[str, dict] | None = None,
    applications: list[dict] | None = None,
    profile: SimpleNamespace | None = None,
) -> dict:
    api = _api(contexts or {})
    with (
        patch.object(api, "_resolve_profile", return_value=profile or _profile()),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
        patch("src.repositories.applications_repo.get_all", return_value=applications or []),
        patch("src.rico_chat_api.agent_runtime.handle_action") as handle_action,
    ):
        result = api._handle_active_user_inner(user_id, message)
    handle_action.assert_not_called()
    return result


def test_cross_user_context_does_not_leak_into_explicit_cover_letter() -> None:
    contexts = {USER_A: _systra_context(), USER_B: {}}

    result = _run(
        "Draft a short cover letter for HSE Manager at DP World in Dubai. "
        "Use what you know about me.",
        user_id=USER_B,
        contexts=contexts,
    )

    message = result["message"]
    assert "DP World" in message
    assert "HSE Manager" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message


def test_explicit_company_precedence_over_same_user_recent_context() -> None:
    contexts = {USER_B: _systra_context()}

    result = _run(
        "Draft a short cover letter for HSE Manager at DP World in Dubai.",
        user_id=USER_B,
        contexts=contexts,
    )

    message = result["message"]
    assert "DP World" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message


def test_same_user_saved_application_does_not_override_explicit_company() -> None:
    contexts = {USER_B: _systra_context()}
    applications = [
        {
            "title": "Compliance Manager (6 Month Contract)",
            "company": "Aventus",
            "status": "applied",
            "location": "Dubai",
        }
    ]

    result = _run(
        "Draft a short cover letter for HSE Manager at DP World in Dubai.",
        user_id=USER_B,
        contexts=contexts,
        applications=applications,
    )

    message = result["message"]
    assert "DP World" in message
    assert "Aventus" not in message
    assert "SYSTRA" not in message


def test_application_backed_drafting_uses_matching_saved_application_only() -> None:
    contexts = {USER_B: _systra_context()}
    applications = [
        {
            "title": "Compliance Manager (6 Month Contract)",
            "company": "Aventus",
            "status": "applied",
            "location": "Dubai",
        }
    ]

    result = _run(
        "Write me a cover letter to Aventus.",
        user_id=USER_B,
        contexts=contexts,
        applications=applications,
    )

    message = result["message"]
    assert "Aventus" in message
    assert "Compliance Manager (6 Month Contract)" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message


def test_company_only_without_saved_application_asks_for_role_without_recent_context() -> None:
    contexts = {USER_B: _systra_context()}

    result = _run(
        "Write me a cover letter to DP World.",
        user_id=USER_B,
        contexts=contexts,
        applications=[],
    )

    message = result["message"]
    assert result["type"] == "cover_letter_prompt"
    assert "DP World" in message
    assert "Which role should I target" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message


def test_uploaded_cv_profile_precedence_over_stale_current_job_context() -> None:
    contexts = {USER_B: _systra_context()}
    applications = [
        {
            "title": "Compliance Manager (6 Month Contract)",
            "company": "Aventus",
            "status": "applied",
            "location": "Dubai",
        }
    ]
    cv_profile = _profile("Technical Product Owner / Operations Manager")

    result = _run(
        "Write me a cover letter to Aventus.",
        user_id=USER_B,
        contexts=contexts,
        applications=applications,
        profile=cv_profile,
    )

    message = result["message"]
    assert "Aventus" in message
    assert "Technical Product Owner / Operations Manager" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message


def test_missing_company_asks_for_clarification_without_recent_context_fallback() -> None:
    result = _run("write me a cover letter", contexts={USER_B: {}})

    message = result["message"]
    assert result["type"] == "cover_letter_prompt"
    assert "Which role and company" in message
    assert "SYSTRA" not in message
    assert "Aventus" not in message
    assert "DP World" not in message


def test_generic_cover_letter_request_ignores_stale_same_user_recent_context() -> None:
    result = _run("write me a cover letter", contexts={USER_B: _systra_context()})

    message = result["message"]
    assert result["type"] == "cover_letter_prompt"
    assert "Which role and company" in message
    assert "SYSTRA" not in message
    assert "Environmental Manager" not in message
