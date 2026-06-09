from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.intelligence.intent_classifier import IntentResult, classify_intent
from src.rico_chat_api import RicoChatAPI


USER = "test@rico.ai"


def _make_api() -> RicoChatAPI:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api._memory = {}
    api.system = MagicMock()
    api.system.run_for_profile.side_effect = AssertionError("job search must not run")
    return api


def _make_profile() -> MagicMock:
    profile = MagicMock()
    profile.has_cv = True
    profile.target_roles = ["Environmental Manager"]
    profile.skills = []
    profile.name = "Test User"
    profile.email = USER
    return profile


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.openai_available = False
    agent.deepseek_available = False
    agent.hf_available = False
    agent.provider_available = True
    agent.model = ""
    return agent


def _recent_context() -> dict:
    return {
        "recent_search_matches": [
            {
                "title": "Environmental Manager - Railway Construction Project",
                "company": "Confidential Jobs",
                "location": "Dubai",
                "apply_url": "https://example.com/apply",
                "source_url": "https://example.com/job",
            }
        ]
    }


@pytest.mark.parametrize(
    "phrase",
    [
        "قمت بتقديم الطلب",
        "قدمت الطلب",
        "قدمت على الوظيفة",
        "تم التقديم بنجاح",
        "ارسلت الطلب",
        "قدمت عليه",
        "قدمت عليها",
        "كلا انا ارفقت النص السابق لكي اخبرك انني قمت بتقديم الطلب بنجاح لتلك الوظيفه",
    ],
)
def test_arabic_applied_status_phrases_do_not_classify_as_job_search(phrase: str) -> None:
    result = classify_intent(phrase, has_cv_profile=True)

    assert result.intent == "application_status_update"
    assert result.intent != "job_search_explicit"


def test_arabic_that_job_resolves_recent_context_and_marks_applied() -> None:
    api = _make_api()
    create_calls: list[dict] = []
    lifecycle_calls: list[dict] = []
    stored_contexts: list[dict] = []

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def fake_lifecycle(**kwargs):
        lifecycle_calls.append(kwargs)
        return True

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value=_recent_context()),
        patch.object(api, "_store_recent_context", side_effect=lambda uid, ctx: stored_contexts.append(ctx)),
        patch.object(api, "_classified_role_search", side_effect=AssertionError("job search must not run")),
        patch.object(api, "_target_role_search_response", side_effect=AssertionError("job search must not run")),
        patch("src.repositories.applications_repo.find_by_job_id", return_value=None),
        patch("src.repositories.applications_repo.create", side_effect=fake_create),
        patch("src.repositories.user_job_context_repo.set_lifecycle_status", side_effect=fake_lifecycle),
    ):
        result = api.process_message(
            USER,
            "كلا انا ارفقت النص السابق لكي اخبرك انني قمت بتقديم الطلب بنجاح لتلك الوظيفه",
        )

    assert result["type"] == "application_status_update"
    assert result["job_status"] == "applied"
    assert "تم تسجيل التقديم بنجاح" in result["message"]
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert create_calls[0]["status"] == "applied"
    assert create_calls[0]["user_id"] == USER
    assert not str(create_calls[0]["user_id"]).startswith("public:")
    assert lifecycle_calls[0]["status"] == "applied"
    assert lifecycle_calls[0]["user_id"] == USER
    assert stored_contexts


def test_arabic_applied_status_failure_does_not_claim_saved() -> None:
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value=_recent_context()),
        patch.object(api, "_store_recent_context"),
        patch("src.repositories.applications_repo.find_by_job_id", return_value=None),
        patch("src.repositories.applications_repo.create", return_value=False),
    ):
        result = api.process_message(USER, "قدمت الطلب بنجاح لتلك الوظيفة")

    assert result["type"] == "application_status_update_failed"
    assert "لم أستطع حفظها الآن" in result["message"]
    assert "تم تسجيل" not in result["message"]


def test_arabic_applied_status_without_recent_context_asks_which_job() -> None:
    api = _make_api()

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_get_recent_context", return_value={}),
        patch("src.repositories.applications_repo.create", side_effect=AssertionError("must not write")),
        patch("src.repositories.user_job_context_repo.get_recently_interacted", return_value=[]),
        patch("src.repositories.user_job_context_repo.get_recently_discussed", return_value=[]),
    ):
        result = api.process_message(USER, "تم التقديم بنجاح")

    assert result["type"] == "clarification"
    assert result["intent"] == "application_status_update"
    assert "أي وظيفة تقصد" in result["message"]
    assert "تم تسجيل" not in result["message"]


def test_mark_applied_card_write_failure_does_not_claim_applied() -> None:
    api = _make_api()
    intent = IntentResult(
        intent="job_action.mark_applied",
        confidence=1.0,
        source="exact",
        extracted_title="Environmental Manager - Railway Construction Project",
        extracted_company="Confidential Jobs",
    )

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(
            api,
            "_get_recent_context",
            return_value={
                "recent_application": {
                    "title": "Environmental Manager - Railway Construction Project",
                    "company": "Confidential Jobs",
                    "link": "https://example.com/apply",
                }
            },
        ),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.create_manual", return_value=False),
    ):
        result = api.process_message(
            USER,
            "Mark as applied — Environmental Manager - Railway Construction Project at Confidential Jobs",
        )

    assert result["type"] == "application_status_update_failed"
    assert result["job_status"] is None
    # Accept both "couldn't" and "could not" phrasings
    assert ("couldn't save it right now" in result["message"] or "could not save it right now" in result["message"])
    assert "marked as applied" not in result["message"]
    assert result["target_route"] == "/applications"


def test_mark_applied_card_success_points_to_applications_not_queue() -> None:
    api = _make_api()
    intent = IntentResult(
        intent="job_action.mark_applied",
        confidence=1.0,
        source="exact",
        extracted_title="Environmental Manager - Railway Construction Project",
        extracted_company="Confidential Jobs",
    )

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(
            api,
            "_get_recent_context",
            return_value={
                "recent_application": {
                    "title": "Environmental Manager - Railway Construction Project",
                    "company": "Confidential Jobs",
                    "link": "https://example.com/apply",
                }
            },
        ),
        patch.object(api, "_store_recent_context"),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.create_manual", return_value=True),
    ):
        result = api.process_message(
            USER,
            "Mark as applied — Environmental Manager - Railway Construction Project at Confidential Jobs",
        )

    assert result["type"] == "mark_applied"
    assert result["job_status"] == "applied"
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert result["target_route"] == "/applications"


def test_pending_mark_applied_confirmation_write_failure_does_not_claim_applied() -> None:
    api = _make_api()
    intent = IntentResult(intent="follow_up_confirmation", confidence=1.0, source="exact")

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(
            api,
            "_get_recent_context",
            return_value={
                "_pending_confirm_apply": {
                    "title": "Environmental Manager - Railway Construction Project",
                    "company": "Confidential Jobs",
                }
            },
        ),
        patch.object(api, "_store_recent_context"),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.create_manual", return_value=False),
    ):
        result = api.process_message(USER, "yes")

    assert result["type"] == "application_status_update_failed"
    assert result["job_status"] is None
    # Accept both "couldn't" and "could not" phrasings
    assert ("couldn't save it right now" in result["message"] or "could not save it right now" in result["message"])
    assert "marked as applied" not in result["message"]
    assert "treat" not in result["message"].lower()
    assert result["target_route"] == "/applications"


def test_pending_mark_applied_confirmation_success_points_to_applications_not_queue() -> None:
    api = _make_api()
    intent = IntentResult(intent="follow_up_confirmation", confidence=1.0, source="exact")

    with (
        patch("src.rico_chat_api.is_onboarding_complete", return_value=True),
        patch.object(api, "_resolve_profile", return_value=_make_profile()),
        patch.object(api, "_append_chat"),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(
            api,
            "_get_recent_context",
            return_value={
                "_pending_confirm_apply": {
                    "title": "Environmental Manager - Railway Construction Project",
                    "company": "Confidential Jobs",
                }
            },
        ),
        patch.object(api, "_store_recent_context"),
        patch("src.rico_chat_api.classify_intent", return_value=intent),
        patch("src.repositories.applications_repo.create_manual", return_value=True),
    ):
        result = api.process_message(USER, "yes")

    assert result["type"] == "mark_applied"
    assert result["job_status"] == "applied"
    assert "/applications" in result["message"]
    assert "/queue" not in result["message"]
    assert result["target_route"] == "/applications"


def test_saved_applied_record_is_returned_by_applications_api(monkeypatch) -> None:
    from src.api.routers import applications as applications_router
    from src.repositories import applications_repo

    class FakeCursor:
        def execute(self, sql, params=None):
            return None

        def fetchone(self):
            return {"id": "auth-uuid"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    class FakeDB:
        _exact_auth_lookup_enabled = True

        def __init__(self):
            self.records: list[dict] = []
            self.db_user_ids: list[str] = []

        def connect(self):
            return FakeConn()

        def upsert_recommendation(self, *, user_id, job_key, job_data, status):
            self.db_user_ids.append(user_id)
            self.records = [
                {
                    "job_id": job_key,
                    "title": job_data["title"],
                    "company": job_data["company"],
                    "location": job_data["location"],
                    "link": job_data["link"],
                    "status": status,
                }
            ]
            return True

        def get_recommendations(self, user_id, limit=200):
            self.db_user_ids.append(user_id)
            return list(self.records)

    fake_db = FakeDB()
    monkeypatch.setattr(applications_repo, "_db", lambda: fake_db)

    ok = applications_repo.create(
        job_id="job-123",
        title="Environmental Manager - Railway Construction Project",
        company="Confidential Jobs",
        location="Dubai",
        url="https://example.com/apply",
        status="applied",
        source="chat",
        user_id=USER,
    )
    response = applications_router.list_applications(status=None, page=1, limit=50, user_id=USER)

    assert ok is True
    assert response["total"] == 1
    assert response["applications"][0]["status"] == "applied"
    assert response["applications"][0]["title"] == "Environmental Manager - Railway Construction Project"
    assert fake_db.db_user_ids == ["auth-uuid", "auth-uuid"]
