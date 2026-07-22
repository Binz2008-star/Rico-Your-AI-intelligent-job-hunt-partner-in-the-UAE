"""Pin: option-button agentic_ui is a plain, JSON-serializable dict.

Regression tests for the production ``chat_stream_error err=TypeError``
(2026-07-19 23:21Z): ``_inject_option_buttons`` attached a raw ``RicoAgenticUi``
Pydantic model to ``result["agentic_ui"]``, which the SSE done-event serializes
with bare ``json.dumps`` (src/api/routers/rico_chat.py) — every letter-choice
response over /chat/stream crashed. The JSON /chat path masked the defect
because ``RicoChatResponse.agentic_ui`` accepts the model instance.

The repro profile is synthetic: seven target roles spanning multiple career
families (including the compound "Risk & Compliance Officer"). Since the
steps-to-apply change (#1294) the ambiguous profile-match branch no longer
emits a letter-choice clarification — it searches the top track immediately
(job_matches) and speaks the other tracks in ``track_alternatives``. The
serialization pins below cover that response shape end-to-end.
"""
import json

import pytest

from tests.harness.chat_harness import ChatHarness

SEVEN_ROLES = [
    "Environmental Manager",
    "Compliance Manager",
    "ESG Manager",
    "Audit Manager",
    "Environmental Compliance Manager",
    "Risk & Compliance Officer",
    "Operations Manager - Environmental Services",
]

USER = "option-buttons@test"


@pytest.fixture(scope="module")
def profile_match_response() -> dict:
    """One real process_message run: seven-role profile + 'find matching jobs'."""
    h = ChatHarness()
    h.seed(
        USER,
        cv_status="parsed",
        cv_filename="cv.pdf",
        target_roles=SEVEN_ROLES,
        skills=["environmental compliance", "iso 14001", "esg", "audit"],
        years_experience=10,
        preferred_cities=["Ajman"],
        current_role="Environmental Manager",
        current_company="Synthetic Co",
        salary_expectation_aed=15000,
    )
    return h.say(USER, "find matching jobs")


def test_seven_role_profile_match_is_json_dumpable(profile_match_response):
    """The search-first profile-match response survives the SSE done-event
    serialization exactly as the stream router performs it (bare json.dumps)."""
    assert profile_match_response.get("type") == "job_matches"
    payload = json.dumps({"type": "done", "response": profile_match_response})
    assert '"agentic_ui"' in payload


def test_agentic_ui_is_plain_dict_not_model(profile_match_response):
    from src.schemas.chat import RicoAgenticUi

    ui = profile_match_response.get("agentic_ui")
    assert isinstance(ui, dict)
    assert not isinstance(ui, RicoAgenticUi)


def test_search_first_single_refine_action_and_spoken_alternatives(profile_match_response):
    """#1294 search-first: the top track is searched immediately (job_matches),
    the response carries a single refine-search drawer action, and the other
    tracks are SPOKEN — not rendered as a button menu."""
    actions = profile_match_response["agentic_ui"]["actions"]
    assert len(actions) == 1
    assert actions[0]["id"] == "refine-search"
    assert actions[0]["payload"]["search_query"] == "Environmental Manager"
    assert profile_match_response.get("track_alternatives") == [
        "Compliance Manager", "ESG Manager", "Audit Manager",
    ]
    assert "Starting with your **Environmental Manager** track" in profile_match_response["message"]


def test_compound_role_never_split_into_fragments(profile_match_response):
    """'Risk & Compliance Officer' must never be split on '&'. Under #1294 it
    collapses into the 'Compliance Manager' track by canonical dedupe (same
    behaviour as test_dedup_collapses_canonical_variants_keeps_raw_text) — the
    invariant is that '&'-split fragments never surface as tracks."""
    alternatives = profile_match_response.get("track_alternatives") or []
    assert "Risk" not in alternatives
    assert "Compliance Officer" not in alternatives


def test_intent_stays_profile_match_not_unknown():
    from src.agent.intelligence.intent_classifier import classify_intent

    result = classify_intent("find matching jobs", has_cv_profile=True)
    assert result.intent == "job_search_profile_match"
    assert result.intent != "unknown"


def test_existing_model_ui_input_yields_serializable_output():
    """When a RicoAgenticUi instance is already attached, the merged output is
    still a plain dict that json.dumps accepts, with prior actions preserved."""
    from src.rico_chat_api import RicoChatAPI
    from src.schemas.chat import RicoActionKind, RicoAgenticUi, RicoChatAction

    existing = RicoAgenticUi(
        actions=[
            RicoChatAction(
                id="prior",
                label="Prior action",
                kind=RicoActionKind.chat_continue,
                payload={"message": "prior message"},
            )
        ]
    )
    result = RicoChatAPI._inject_option_buttons(
        {"type": "clarification", "message": "pick one", "agentic_ui": existing},
        [{"action": "search_role", "label": "ESG Manager",
          "message": "search ESG Manager jobs in UAE"}],
    )
    ui = result["agentic_ui"]
    assert isinstance(ui, dict)
    json.dumps(result)
    labels = [a["label"] for a in ui["actions"]]
    assert labels[0] == "Prior action"
    assert labels[1] == "A) ESG Manager"


def test_rest_response_contract_still_validates(profile_match_response):
    """The JSON /chat path (RicoChatResponse(**result)) must keep working with
    the plain-dict agentic_ui — Pydantic coerces it back into the model."""
    from src.schemas.chat import RicoAgenticUi, RicoChatResponse

    response = RicoChatResponse(**profile_match_response, trace_id="t-1")
    assert isinstance(response.agentic_ui, RicoAgenticUi)
    assert len(response.agentic_ui.actions) == 1
    assert response.type == "job_matches"
