"""_inject_option_buttons must emit a JSON-serializable agentic_ui (2026-07-20).

Root cause of the live profile-report failure: _inject_option_buttons runs
AFTER _finalize and overwrote ``agentic_ui`` with a raw RicoAgenticUi
Pydantic model. On the profile-match clarification path (ambiguous target
roles) that model reached the SSE done-only branch's ``json.dumps`` un-encoded
and raised TypeError, so the streamed reply died and the client fell back to
the generic error. Fix: serialize with ``model_dump(exclude_none=True)`` —
the same plain-dict shape every other agentic_ui producer (compose) emits.

Owner acceptance points 1-7 below.
"""
from __future__ import annotations

import json
import os
import sys

from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("ADMIN_EMAIL", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "TestPass123")
os.environ.setdefault("JWT_SECRET", "x" * 32)

from src.rico_chat_api import RicoChatAPI
from src.services.profile_context_resolver import ProfileContext
from src.schemas.chat import RicoAgenticUi, RicoChatAction, RicoActionKind

# Seven saved target roles spanning several career families — the exact shape
# that makes _resolve_profile_search_role return "ambiguous" and produce the
# clarification-with-options that the incident surfaced.
SEVEN_ROLES = [
    "Environmental Manager",
    "Compliance Manager",
    "ESG Manager",
    "Audit Manager",
    "Environmental Compliance Manager",
    "Risk & Compliance Officer",
    "Operations Manager - Environmental Services",
]

_FAKE_AGENT = type(
    "_Agent",
    (),
    {
        "available": True,
        "openai_available": True,
        "deepseek_available": True,
        "hf_available": False,
        "provider_available": True,
        "model": "test-model",
    },
)()


def _profile_ctx() -> ProfileContext:
    return ProfileContext(
        user_id="opt-buttons@test.com",
        target_roles=list(SEVEN_ROLES),
        skills=["iso 14001", "compliance", "environmental management"],
        preferred_cities=["Ajman"],
        years_experience=8,
        cv_filename="Roben_Edwan_Executive_Leadership_CV.pdf",
        cv_status="parsed",
    )


def _run_profile_match_clarification() -> dict:
    """Drive the REAL profile-match path through the button-injection wrapper.

    _handle_active_user_inner routes the job_search_profile_match intent to the
    ambiguous-roles clarification, then _handle_active_user injects the option
    buttons — reproducing the production code path end to end.
    """
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = True
    api.can_mutate_applications = True
    with patch.object(RicoChatAPI, "_resolve_profile", return_value=_profile_ctx()), \
         patch.object(RicoChatAPI, "_append_chat"), \
         patch.object(RicoChatAPI, "_save_pending_options"), \
         patch.object(RicoChatAPI, "_maybe_store_pending_job_search"), \
         patch.object(RicoChatAPI, "_get_recent_context", return_value={}), \
         patch.object(RicoChatAPI, "_store_recent_context"), \
         patch.object(RicoChatAPI, "_get_openai_agent", return_value=_FAKE_AGENT):
        return api._handle_active_user("opt-buttons@test.com", "jobs for my profile")


# ── 1. Seven-role profile-match clarification is json.dumps-serializable ──────

def test_profile_match_seven_roles_clarification_is_json_serializable():
    result = _run_profile_match_clarification()
    assert result.get("type") == "clarification"
    # THE regression guard: before the fix this raised
    # "Object of type RicoAgenticUi is not JSON serializable".
    json.dumps(result)


# ── 2. agentic_ui is a plain dict, never a Pydantic model ─────────────────────

def test_agentic_ui_is_plain_dict_not_pydantic_model():
    result = _run_profile_match_clarification()
    agentic_ui = result.get("agentic_ui")
    assert isinstance(agentic_ui, dict)
    assert not isinstance(agentic_ui, RicoAgenticUi)


# ── 3. Four buttons preserved with chat_continue kind + payload.message ───────

def test_four_buttons_preserved_with_chat_continue_and_payload_message():
    result = _run_profile_match_clarification()
    # Round-trip through JSON so we assert the ON-THE-WIRE shape, incl. the
    # str-enum serializing to the plain string "chat_continue".
    wire = json.loads(json.dumps(result))
    actions = wire["agentic_ui"]["actions"]
    assert len(actions) == 4
    for action in actions:
        assert action["kind"] == "chat_continue"
        assert action["payload"]["message"]
    # The buttons mirror the first four clarification options as real searches.
    messages = [a["payload"]["message"] for a in actions]
    assert messages == [
        "search Environmental Manager jobs in UAE",
        "search Compliance Manager jobs in UAE",
        "search ESG Manager jobs in UAE",
        "search Audit Manager jobs in UAE",
    ]


# ── 4. "Risk & Compliance Officer" stays ONE role, never split on "&" ─────────

def test_risk_and_compliance_officer_stays_single_role():
    result = _run_profile_match_clarification()
    option_labels = [o.get("label") for o in (result.get("options") or [])]
    assert "Risk & Compliance Officer" in option_labels
    # It must never be fractured into standalone "Risk" / "Compliance Officer".
    assert "Risk" not in option_labels
    assert "Compliance Officer" not in option_labels


# ── 5. Intent stays job_search_profile_match ──────────────────────────────────

def test_intent_stays_job_search_profile_match():
    from src.agent.intelligence.intent_classifier import classify_intent

    decision = classify_intent("jobs for my profile", has_cv_profile=True)
    assert decision.intent == "job_search_profile_match"


# ── 6. An EXISTING RicoAgenticUi in the result also serializes cleanly ────────

def test_existing_agentic_ui_input_produces_serializable_output():
    existing = RicoAgenticUi(
        actions=[
            RicoChatAction(
                id="pre-existing",
                label="Existing action",
                kind=RicoActionKind.navigate,
                payload={"href": "/jobs"},
            )
        ]
    )
    result = {"type": "clarification", "message": "pick", "agentic_ui": existing}
    options = [
        {"label": "Environmental Manager", "message": "search Environmental Manager jobs in UAE"},
        {"label": "Compliance Manager", "message": "search Compliance Manager jobs in UAE"},
    ]

    injected = RicoChatAPI._inject_option_buttons(result, options)

    agentic_ui = injected["agentic_ui"]
    assert isinstance(agentic_ui, dict)
    json.dumps(injected)  # must not raise
    kinds = [a["kind"] for a in agentic_ui["actions"]]
    # Pre-existing action kept, two new chat_continue buttons appended.
    assert kinds == ["navigate", "chat_continue", "chat_continue"]


# ── 7. REST /chat contract does not regress ───────────────────────────────────

def test_rest_chat_contract_does_not_regress():
    from fastapi.testclient import TestClient
    from src.api.app import app
    from src.api.auth import create_access_token
    from src.rico_agent import RicoProfile
    import src.rico_chat_api as rca

    rp = RicoProfile(
        user_id="opt-buttons@test.com",
        target_roles=list(SEVEN_ROLES),
        skills=["iso 14001", "compliance"],
        preferred_cities=["Ajman"],
        years_experience=8,
        cv_status="parsed",
        cv_filename="cv.pdf",
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(
        "access_token", create_access_token({"sub": "opt-buttons@test.com", "role": "user"})
    )
    with patch("src.repositories.profile_repo.get_profile", return_value=rp), \
         patch.object(rca.RicoChatAPI, "_resolve_profile", return_value=_profile_ctx()), \
         patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
         patch("src.rico_chat_api.evaluate_minimum_profile", return_value=(True, [])), \
         patch.object(rca.RicoChatAPI, "_append_chat"), \
         patch.object(rca.RicoChatAPI, "_get_openai_agent", return_value=_FAKE_AGENT):
        res = client.post("/api/v1/rico/chat", json={"message": "jobs for my profile"})

    assert res.status_code == 200
    body = res.json()
    assert body.get("type") == "clarification"
    agentic_ui = body.get("agentic_ui")
    assert isinstance(agentic_ui, dict)
    actions = agentic_ui["actions"]
    assert len(actions) == 4
    assert all(a["kind"] == "chat_continue" for a in actions)
    assert all(a["payload"]["message"] for a in actions)
