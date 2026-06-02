from __future__ import annotations

from types import SimpleNamespace

from src.jsearch_client import FetchResult
from src.rico_chat_api import RicoChatAPI
from src.schemas.chat import RicoSessionContext
from src.services import chat_service
from src.services.operation_state import (
    build_status_response,
    get_latest_job_search_operation,
    get_operation,
    mark_completed,
    mark_failed,
    reset_for_tests,
    start_job_search_operation,
)


def _profile(**overrides):
    data = {
        "has_cv": True,
        "target_roles": ["HSE Manager"],
        "skills": ["HSE", "NEBOSH", "risk assessment"],
        "certifications": ["NEBOSH"],
        "years_experience": 10,
        "industries": ["construction"],
        "preferred_cities": ["Dubai"],
        "current_role": "HSE Officer",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_broad_manager_asks_for_narrowing(monkeypatch):
    reset_for_tests()
    api = RicoChatAPI(persist=False)
    monkeypatch.setattr(api, "_append_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api,
        "_search_jsearch_direct",
        lambda role: (_ for _ in ()).throw(AssertionError("search should not run")),
    )

    response = api._classified_role_search("user-ops", "Manager", _profile())

    assert response["type"] == "clarification"
    assert response["next_action"] == "narrow_job_search"
    assert "too broad" in response["message"]
    assert [opt["role"] for opt in response["options"]] == [
        "HSE Manager",
        "Operations Manager",
        "HR Manager",
        "Environmental Manager",
        "General Manager",
    ]
    assert get_latest_job_search_operation("user-ops") is None


def test_specific_hse_manager_continues_to_job_search(monkeypatch):
    reset_for_tests()
    api = RicoChatAPI(persist=False)
    api._current_operation_id = "op_test_hse_manager"
    monkeypatch.setattr(api, "_append_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api,
        "_search_jsearch_meta",
        lambda role, profile=None: FetchResult(items=[
            {
                "title": "HSE Manager",
                "company": "ACME",
                "location": "Dubai, UAE",
                "link": "https://example.test/apply",
                "description": "Lead HSE operations.",
                "score": 88,
            }
        ]),
    )
    monkeypatch.setattr(
        api.system,
        "run_for_profile",
        lambda profile: (_ for _ in ()).throw(AssertionError("fallback search should not run")),
    )

    response = api._classified_role_search("user-hse", "HSE Manager", _profile())

    assert response["type"] == "job_matches"
    assert response["operation_id"] == "op_test_hse_manager"
    assert response["operation_status"] == "completed"
    assert response["result_count"] == 1
    latest = get_latest_job_search_operation("user-hse")
    assert latest is not None
    assert latest["status"] == "completed"
    assert latest["result_count"] == 1


def test_timeout_operation_id_is_preserved_for_followup():
    reset_for_tests()
    start_job_search_operation(
        user_id="user-timeout",
        role_or_query="HSE Manager",
        operation_id="op_web_timeout",
    )
    ctx = RicoSessionContext.for_authenticated("user-timeout")

    response = chat_service.send_message(ctx=ctx, message="are you done")

    assert response["type"] == "operation_status"
    assert response["operation_id"] == "op_web_timeout"
    assert response["operation_status"] == "running"
    assert "Still searching" in response["message"]


def test_arabic_followup_checks_latest_operation_status():
    reset_for_tests()
    start_job_search_operation(
        user_id="user-arabic",
        role_or_query="HSE Manager",
        operation_id="op_arabic_status",
    )
    ctx = RicoSessionContext.for_authenticated("user-arabic")

    response = chat_service.send_message(ctx=ctx, message="خلصت؟")

    assert response["type"] == "operation_status"
    assert response["operation_id"] == "op_arabic_status"
    assert response["operation_status"] == "running"


def test_completed_operation_status_is_reported():
    reset_for_tests()
    api = RicoChatAPI(persist=False)
    api._current_operation_id = "op_done"
    operation = api._begin_job_search_operation("user-done", "HSE Manager")

    mark_completed("user-done", operation["operation_id"], 3)
    ctx = RicoSessionContext.for_authenticated("user-done")

    response = chat_service.send_message(ctx=ctx, message="is it finished")

    assert response["operation_status"] == "completed"
    assert response["result_count"] == 3
    assert "completed with 3 result" in response["message"]


def test_operation_read_requires_matching_user():
    reset_for_tests()
    start_job_search_operation(
        user_id="owner-user",
        role_or_query="HSE Manager",
        operation_id="op_shared_client_id",
    )

    assert get_operation("other-user", "op_shared_client_id") is None
    assert build_status_response("other-user") is None


def test_failed_status_response_is_sanitized():
    reset_for_tests()
    operation = start_job_search_operation(
        user_id="user-failed",
        role_or_query="HSE Manager",
        operation_id="op_failed",
    )

    mark_failed("user-failed", operation["operation_id"], "postgres://secret-host internal stack")
    response = build_status_response("user-failed")

    assert response is not None
    assert response["operation_status"] == "failed"
    assert response["error"] == "job_search_failed"
    assert "postgres" not in response["message"]
    assert "secret-host" not in response["message"]


def test_mark_failed_does_not_overwrite_completed_operation():
    reset_for_tests()
    operation = start_job_search_operation(
        user_id="user-complete",
        role_or_query="HSE Manager",
        operation_id="op_complete_then_error",
    )

    mark_completed("user-complete", operation["operation_id"], 2)
    mark_failed("user-complete", operation["operation_id"], "late formatting error")
    latest = get_latest_job_search_operation("user-complete")

    assert latest is not None
    assert latest["status"] == "completed"
    assert latest["result_count"] == 2
