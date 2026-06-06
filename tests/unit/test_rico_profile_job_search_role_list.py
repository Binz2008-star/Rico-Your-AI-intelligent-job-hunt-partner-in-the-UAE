from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.jsearch_client import FetchResult
from src.rico_chat_api import RicoChatAPI


def test_as_list_splits_profile_text_blobs() -> None:
    raw_roles = [
        "Environmental Manager, Environmental Compliance Manager\nEnvironmental Operations Manager",
        " Sustainability Manager ; ESG Manager ",
    ]

    assert RicoChatAPI._as_list(raw_roles) == [
        "Environmental Manager",
        "Environmental Compliance Manager",
        "Environmental Operations Manager",
        "Sustainability Manager",
        "ESG Manager",
    ]


def test_profile_job_search_does_not_use_giant_target_role_blob(monkeypatch) -> None:
    profile = SimpleNamespace(
        user_id="roben@example.com",
        has_cv=True,
        target_roles=(
            "Environmental Manager, Environmental Compliance Manager, "
            "Environmental Operations Manager, Sustainability Manager, ESG Manager"
        ),
        skills=["ISO 14001"],
        certifications=[],
        years_experience=10,
        industries=[],
        preferred_cities=[],
        current_role="Founder",
    )

    api = RicoChatAPI(persist=False)
    api.memory = MagicMock()
    api.system = MagicMock()
    api.system.run_for_profile.return_value = {"matches": []}
    api.openai_agent = MagicMock()

    searched_roles: list[str] = []

    def fake_jsearch(role: str) -> FetchResult:
        searched_roles.append(role)
        return FetchResult(items=[])

    monkeypatch.setattr(api, "_resolve_profile", lambda _user_id: profile)
    monkeypatch.setattr(api, "_resolve_pending_field", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "_search_jsearch_meta", fake_jsearch)
    monkeypatch.setattr(api, "_enrich_with_role_intelligence", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        api,
        "_begin_job_search_operation",
        lambda _user_id, _role: {"operation_id": "op-test"},
    )
    monkeypatch.setattr("src.rico_chat_api.mark_completed", lambda *_args, **_kwargs: None)

    response = api._handle_active_user(
        "roben@example.com",
        "Find UAE jobs that match my CV and experience.",
    )

    assert searched_roles == ["Environmental Manager"]
    assert response["type"] == "job_matches"
    assert response["search_query"] == "Environmental Manager"
    assert "Environmental Manager roles" in response["message"]
    assert "Environmental Compliance Manager" not in response["search_query"]
    assert "Environmental Compliance Manager" not in response["message"]
