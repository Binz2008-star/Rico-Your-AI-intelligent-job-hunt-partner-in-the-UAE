from unittest.mock import MagicMock, patch


def _make_api():
    patches = [
        patch("src.rico_memory.RicoMemoryStore"),
        patch("src.rico_agent.RicoAgent"),
        patch("src.rico_repo_adapter.RicoSystem"),
        patch("src.rico_openai_agent.RicoOpenAIAgent"),
    ]
    for item in patches:
        item.start()

    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    api.memory = MagicMock()
    api.memory.append_chat_message = MagicMock()
    api.system = MagicMock()
    api.system.run_for_profile = MagicMock(return_value={"matches": []})
    api.openai_agent = MagicMock()
    api.openai_agent.model = "gpt-4o"
    api.openai_agent.openai_available = True
    api.openai_agent.deepseek_available = False
    api.openai_agent.hf_available = False
    api.openai_agent.provider_available = True
    api.openai_agent.provider_state = None

    for item in patches:
        item.stop()

    return api


def _banking_cv_profile(**kwargs):
    profile = {
        "cv_status": "parsed",
        "cv_filename": "banking-fit-cv.pdf",
        "skills": ["compliance", "risk", "ESG", "sustainability", "HSE", "facilities"],
        "certifications": ["ISO 14001 Lead Auditor"],
        "years_experience": 10,
        "industries": ["operations", "compliance"],
        "target_roles": ["Compliance Manager", "ESG Manager"],
        "preferred_cities": ["Dubai"],
        "manual_profile_wizard_disabled": True,
    }
    profile.update(kwargs)
    return profile


def _run_with_profile(message: str, profile: dict | None = None) -> dict:
    api = _make_api()
    route_mock = MagicMock(tool_name=None, entities={}, tool_args={}, confirmation_prompt=None, source="keyword")
    with patch("src.rico_chat_api.get_profile", return_value=profile or _banking_cv_profile()), \
         patch("src.rico_chat_api.is_onboarding_complete", return_value=True), \
         patch("src.rico_chat_api.upsert_profile", side_effect=lambda user_id, updates: profile or _banking_cv_profile()), \
         patch("src.rico_chat_api._route", return_value=route_mock), \
         patch.object(api, "_search_jsearch_direct", return_value=[]):
        return api._handle_active_user("career-execution-user", message)


class TestCareerExecutionStateMachine:
    def test_cv_exists_banking_request_builds_executable_search(self):
        result = _run_with_profile("Analyze my CV and find me a career in banking.")

        assert result["intent"] == "career_execution"
        assert result["execution_state"] == "SEARCH_RUNNING"
        assert result["active_profile"] is True
        assert result["next_action"] == "search_jobs"
        assert "banking" in result["industry_targets"]
        assert any("Banking UAE" in query for query in result["last_search_queries"])
        assert "upload your CV" not in result["message"]
        assert "what career are you interested in" not in result["message"].lower()

    def test_user_challenges_manual_search_triggers_refinement(self):
        result = _run_with_profile("Why should I search? You are here to help me find a career.")

        assert result["intent"] == "career_execution"
        assert result["next_action"] == "search_jobs"
        assert result["last_search_queries"]
        assert "what career are you interested in" not in result["message"].lower()

    def test_subscription_trust_complaint_proves_value_without_free_claim(self):
        result = _run_with_profile("I will not subscribe if you cannot find me a career.")

        assert result["intent"] == "career_execution"
        assert result["active_profile"] is True
        assert "service is free" not in result["message"].lower()
        assert "upload your CV" not in result["message"]

    def test_suggested_titles_become_search_queries(self):
        result = _run_with_profile("Analyze my CV and find me a career in banking.")

        queries = result["last_search_queries"]
        assert any("Compliance Manager Banking UAE" == query for query in queries)
        assert any("ESG Manager Banking UAE" == query for query in queries)
        assert any("Operational Risk Manager Banking UAE" == query for query in queries)

    def test_active_execution_prevents_generic_fallback(self):
        profile = _banking_cv_profile(target_roles=[])
        result = _run_with_profile("career in banking", profile)

        assert result["intent"] == "career_execution"
        assert result["execution_state"] in {"SEARCH_RUNNING", "MATCHES_SCORED"}
        assert result["type"] == "job_matches"
        assert result["next_action"] == "search_jobs"
