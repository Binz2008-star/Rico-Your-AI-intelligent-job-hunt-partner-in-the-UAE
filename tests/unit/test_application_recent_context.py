from datetime import datetime, timedelta, timezone

from src.rico_chat_api import RicoChatAPI


def test_recent_application_context_uses_application_flow_route():
    api = RicoChatAPI(persist=False)

    ctx = api._build_recent_application_context(
        title="Safety And Health Environment Manager",
        company="Global Corporation",
        status="applied",
        action="mark_applied",
    )

    assert ctx["recent_route"] == "/command"
    assert ctx["recent_application"]["route"] == "/command"
    assert ctx["recent_application"]["status_label"] == "applied"
    assert ctx["timeline"][0]["action"] == "mark_applied"


def test_recent_context_message_includes_next_step_for_applied_job():
    api = RicoChatAPI(persist=False)
    ctx = api._build_recent_application_context(
        title="Safety And Health Environment Manager",
        company="Global Corporation",
        status="applied",
        action="mark_applied",
    )

    message = api._build_recent_context_message(ctx)

    assert "Safety And Health Environment Manager" in message
    assert "Global Corporation" in message
    assert "follow up" in message.lower()


def test_recent_application_fallback_selects_latest_updated_record():
    api = RicoChatAPI(persist=False)
    now = datetime.now(timezone.utc)
    older = {
        "title": "Older Role",
        "company": "Older Company",
        "status": "saved",
        "date_updated": (now - timedelta(days=3)).isoformat(),
    }
    newer = {
        "title": "Newer Role",
        "company": "Newer Company",
        "status": "applied",
        "date_updated": now.isoformat(),
    }

    sorted_apps = api._sort_applications_recent([older, newer])

    assert sorted_apps[0]["title"] == "Newer Role"
