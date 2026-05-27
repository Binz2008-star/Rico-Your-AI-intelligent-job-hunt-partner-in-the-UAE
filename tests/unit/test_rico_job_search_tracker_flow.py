from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.intelligence.intent_classifier import IntentResult
from src.rico_chat_api import RicoChatAPI


USER = "flow-user@example.com"


def _api_with_context() -> tuple[RicoChatAPI, dict]:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    context: dict = {}
    api.memory.get_context.side_effect = lambda _user, key: context if key == "recent_context" else None
    def set_context(_user: str, key: str, value: dict) -> None:
        if key == "recent_context":
            next_value = dict(value)
            context.clear()
            context.update(next_value)
    api.memory.set_context.side_effect = set_context
    return api, context


def _profile() -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Engineer", "Manager"]
    profile.skills = ["HSE", "QHSE", "Environmental Compliance", "Sustainability", "ISO 14001"]
    profile.certifications = ["NEBOSH"]
    profile.industries = ["Environmental"]
    profile.years_experience = 10
    profile.current_role = "HSE Specialist"
    return profile


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.openai_available = False
    agent.deepseek_available = False
    agent.hf_available = False
    agent.provider_available = True
    agent.model = ""
    return agent


def _run(api: RicoChatAPI, message: str, profile: MagicMock, intent: IntentResult | None = None) -> dict:
    patches = [
        patch.object(api, "_resolve_profile", return_value=profile),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
    ]
    if intent is not None:
        patches.append(patch("src.rico_chat_api.classify_intent", return_value=intent))

    with patches[0], patches[1], patches[2], patches[3]:
        if intent is not None:
            with patches[4]:
                return api._handle_active_user(USER, message)
        return api._handle_active_user(USER, message)


def test_save_without_backend_persistence_does_not_claim_saved():
    api, context = _api_with_context()
    context["recent_search_matches"] = [
        {"title": "HSE Manager", "company": "Acme", "apply_url": "", "source_url": ""}
    ]
    intent = IntentResult(
        intent="job_action.save_job",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )

    with patch("src.repositories.applications_repo.create_manual", return_value=False):
        result = _run(api, "Save - HSE Manager at Acme", _profile(), intent)

    assert "could not save" in result["message"].lower()
    assert "Saved -" not in result["message"]
    assert "Saved as lead" not in result["message"]


def test_tracker_read_after_save_returns_saved_job_from_backend():
    api, _ = _api_with_context()
    profile = _profile()
    apps = [{"title": "HSE Manager", "company": "Acme", "status": "saved", "link": ""}]

    with (
        patch("src.repositories.applications_repo.get_all", return_value=apps) as get_all,
        patch("src.repositories.applications_repo.get_stats", return_value={"saved": 1}),
    ):
        result = _run(api, "what i have in my tracker", profile)

    get_all.assert_called_once_with(user_id=USER)
    assert result["type"] == "application_status"
    assert result["applications"][0]["title"] == "HSE Manager"
    assert "HSE Manager" in result["message"]


def test_generic_find_me_a_job_uses_profile_aligned_hse_roles_not_engineer_manager():
    api, _ = _api_with_context()
    profile = _profile()
    intent = IntentResult("job_search.profile_match", 1.0, "exact")
    seen: dict[str, str] = {}

    def fake_search(_user: str, role: str, _profile: MagicMock, **_kw) -> dict:
        seen["role"] = role
        return {"type": "job_matches", "message": role, "matches": []}

    with patch.object(api, "_target_role_search_response", side_effect=fake_search):
        result = _run(api, "find me a job", profile, intent)

    assert seen["role"] not in {"Engineer", "Manager"}
    assert seen["role"] in {
        "HSE Manager",
        "QHSE Manager",
        "Environmental Compliance Officer",
        "Sustainability Manager",
        "ESG/Compliance Manager",
    }
    assert result["message"] == seen["role"]


def test_open_apply_link_action_only_when_apply_url_exists():
    profile = _profile()
    live = RicoChatAPI._format_match(
        {"title": "HSE Manager", "company": "Acme", "job_apply_link": "https://example.com/apply"},
        profile,
    )
    lead = RicoChatAPI._format_match(
        {"title": "HSE Manager", "company": "Acme", "job_google_link": "https://example.com/source"},
        profile,
    )

    assert "Open apply link" in live["actions"]
    assert "Open apply link" not in lead["actions"]
    assert "Apply link not captured" in lead["missing_facts"]


def test_why_after_missing_apply_link_explains_missing_source_url():
    api, context = _api_with_context()
    context["recent_search_matches"] = [
        {
            "title": "HSE Manager",
            "company": "Acme",
            "apply_url": "",
            "source_url": "",
            "verification_status": "lead_needs_verification",
        }
    ]
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )

    missing = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)
    why = _run(api, "why", _profile())

    assert "no verified apply link" in missing["message"].lower()
    assert why["type"] == "failure_explanation"
    assert "apply_url" in why["message"]
    assert "not include" in why["message"].lower()


# ── New DB-persistence tests ──────────────────────────────────────────────────

def test_store_search_matches_persists_to_db():
    """_store_search_matches_context must write matches to Neon via upsert_matches."""
    api, _ = _api_with_context()
    matches = [
        {"title": "HSE Manager", "company": "Acme", "apply_url": "https://acme.com/apply",
         "source_url": "https://acme.com/src", "verification_status": "live"},
    ]

    with patch(
        "src.repositories.user_job_context_repo.upsert_matches"
    ) as mock_upsert:
        api._store_search_matches_context(USER, matches)

    mock_upsert.assert_called_once_with(USER, matches)


def test_open_apply_link_finds_url_from_db():
    """open_apply_link must return the apply URL retrieved from user_job_context when memory/apps are empty."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )
    db_row = {
        "title": "HSE Manager",
        "company": "Acme",
        "apply_url": "https://acme.com/apply",
        "source_url": "https://acme.com/src",
        "verification_status": "live",
        "searched_at": None,
    }

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=db_row,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "https://acme.com/apply" in result["message"]
    assert result.get("apply_url") == "https://acme.com/apply"


def test_open_apply_link_falls_back_to_source_url():
    """When apply_url is absent but source_url exists in DB, Rico returns the source listing link."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )
    db_row = {
        "title": "HSE Manager",
        "company": "Acme",
        "apply_url": "",
        "source_url": "https://acme.com/src",
        "verification_status": "lead_needs_verification",
        "searched_at": None,
    }

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=db_row,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "https://acme.com/src" in result["message"]
    assert "official listing" in result["message"].lower()


def test_open_apply_link_does_not_tell_user_to_search_manually():
    """The old error 'Search for the role on the company website or LinkedIn' must be gone."""
    api, _ = _api_with_context()
    open_intent = IntentResult(
        intent="job_action.open_apply_link",
        confidence=1.0,
        source="exact",
        extracted_title="HSE Manager",
        extracted_company="Acme",
    )

    with (
        patch("src.repositories.applications_repo.get_all", return_value=[]),
        patch(
            "src.repositories.user_job_context_repo.find_by_title_company",
            return_value=None,
        ),
    ):
        result = _run(api, "open apply link for HSE Manager at Acme", _profile(), open_intent)

    assert "search for the role on the company website" not in result["message"].lower()
    assert "linkedin" not in result["message"].lower()
    assert "needs source verification" in result["message"].lower()


def test_saved_target_role_search_mentions_saved_role():
    """_build_role_search_message with from_saved_profile=True must include the transparency prefix."""
    api, _ = _api_with_context()
    message = api._build_role_search_message(
        normalized_role="HSE Manager",
        city_text=" in the UAE",
        basis_text=" using your CV profile",
        top_matches=[],
        role_intelligence_data=None,
        from_saved_profile=True,
    )

    assert message.startswith("Searching based on your saved target role: HSE Manager.")
