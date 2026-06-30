"""Unit tests for Phase 2 item 4: application-tracking intelligence.

Tests _enrich_applications and _build_tracking_message helpers, plus the
integrated response shape from _handle_application_tracking.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_api():
    patches = [
        patch("src.rico_memory.RicoMemoryStore"),
        patch("src.rico_agent.RicoAgent"),
        patch("src.rico_repo_adapter.RicoSystem"),
        patch("src.rico_openai_agent.RicoOpenAIAgent"),
    ]
    for p in patches:
        p.start()

    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    api.memory = MagicMock()
    api.memory.append_chat_message = MagicMock()
    api.system = MagicMock()
    api.openai_agent = MagicMock()
    api.openai_agent.provider_available = False

    for p in patches:
        p.stop()

    return api


def _iso(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def _app(status: str, applied_days_ago: int, updated_days_ago: int, **kw) -> dict:
    return {
        "job_id": "j1",
        "title": kw.get("title", "Analyst"),
        "company": kw.get("company", "Acme"),
        "status": status,
        "date_applied": _iso(applied_days_ago),
        "date_updated": _iso(updated_days_ago),
    }


# ── _enrich_applications ──────────────────────────────────────────────────────

def test_enrich_follow_up_flag_set_when_applied_and_stale():
    api = _make_api()
    apps = [_app("applied", applied_days_ago=14, updated_days_ago=10)]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["needs_follow_up"] is True
    assert enriched[0]["days_since_applied"] == 14
    assert enriched[0]["days_since_update"] == 10


def test_enrich_no_follow_up_when_recently_updated():
    api = _make_api()
    apps = [_app("applied", applied_days_ago=10, updated_days_ago=3)]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["needs_follow_up"] is False


def test_enrich_interview_status_never_needs_follow_up():
    api = _make_api()
    apps = [_app("interview", applied_days_ago=20, updated_days_ago=20)]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["needs_follow_up"] is False


def test_enrich_offer_status_never_needs_follow_up():
    api = _make_api()
    apps = [_app("offer", applied_days_ago=30, updated_days_ago=30)]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["needs_follow_up"] is False


def test_enrich_opened_status_flagged_when_stale():
    api = _make_api()
    apps = [_app("opened", applied_days_ago=8, updated_days_ago=8)]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["needs_follow_up"] is True


def test_enrich_none_dates_no_crash():
    api = _make_api()
    apps = [{"job_id": "x", "title": "Dev", "company": "Co", "status": "applied",
             "date_applied": None, "date_updated": None}]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["days_since_applied"] is None
    assert enriched[0]["days_since_update"] is None
    assert enriched[0]["needs_follow_up"] is False


def test_enrich_preserves_original_fields():
    api = _make_api()
    apps = [_app("saved", applied_days_ago=5, updated_days_ago=5, title="PM", company="Corp")]
    enriched = api._enrich_applications(apps)
    assert enriched[0]["title"] == "PM"
    assert enriched[0]["company"] == "Corp"
    assert enriched[0]["status"] == "saved"


# ── _build_tracking_message ───────────────────────────────────────────────────

def test_build_message_empty_list():
    api = _make_api()
    msg = api._build_tracking_message([], {})
    assert "no tracked applications" in msg.lower()


def test_build_message_single_applied_no_follow_up():
    api = _make_api()
    apps = api._enrich_applications([_app("applied", 3, 3, company="Noon")])
    msg = api._build_tracking_message(apps, {})
    assert "1 tracked application" in msg
    assert "1 applied" in msg
    assert "follow-up" not in msg.lower()
    # The summary now itemizes the actual applications instead of dead-ending with
    # "Ask me to 'list my applications'…" (P0-3 trust fix).
    assert "Noon" in msg
    assert "list my applications" not in msg.lower()


def test_build_message_follow_up_callout():
    api = _make_api()
    apps = api._enrich_applications([
        _app("applied", 15, 15, company="ADNOC"),
        _app("applied", 10, 10, company="Noon"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "follow-up" in msg.lower()
    assert "ADNOC" in msg
    assert "Noon" in msg


def test_build_message_active_interview_highlighted():
    api = _make_api()
    apps = api._enrich_applications([
        _app("interview", 5, 1, title="PM", company="Emirates"),
        _app("applied", 3, 3, company="Noon"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "Active" in msg
    assert "Emirates" in msg
    assert "PM" in msg


def test_build_message_offer_highlighted():
    api = _make_api()
    apps = api._enrich_applications([
        _app("offer", 20, 1, title="Lead Dev", company="Careem"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "Active" in msg
    assert "Careem" in msg
    assert "1 offer" in msg


def test_build_message_mixed_stages_counts():
    api = _make_api()
    apps = api._enrich_applications([
        _app("offer", 30, 1, company="A"),
        _app("interview", 10, 2, company="B"),
        _app("applied", 5, 5, company="C"),
        _app("saved", 2, 2, company="D"),
        _app("rejected", 20, 20, company="E"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "5 tracked applications" in msg
    assert "1 offer" in msg
    assert "1 interview" in msg
    assert "1 applied" in msg
    assert "1 saved" in msg
    assert "1 rejected" in msg


# ── _handle_application_tracking response shape ───────────────────────────────

def _mock_apps_repo(get_all_rv, get_stats_rv):
    """Return a sys.modules patch dict for src.repositories.applications_repo."""
    import sys

    mock = MagicMock()
    mock.get_all.return_value = get_all_rv
    mock.get_stats.return_value = get_stats_rv
    return patch.dict(sys.modules, {"src.repositories.applications_repo": mock})


def test_handle_tracking_response_has_follow_up_needed_key():
    api = _make_api()
    stale_app = _app("applied", 15, 15, company="ADNOC")
    fresh_app = _app("interview", 3, 1, company="Noon")
    with _mock_apps_repo([stale_app, fresh_app], {"total": 2, "by_status": {}}):
        result = api._handle_application_tracking("user@test.com")

    assert result["type"] == "application_status"
    assert "follow_up_needed" in result
    assert len(result["follow_up_needed"]) == 1
    assert result["follow_up_needed"][0]["company"] == "ADNOC"
    assert result["applications"][0].get("needs_follow_up") is not None


def test_handle_tracking_empty_returns_no_apps_message():
    api = _make_api()
    with _mock_apps_repo([], {"total": 0, "by_status": {}}):
        result = api._handle_application_tracking("user@test.com")

    assert result["type"] == "application_status"
    assert "no tracked applications" in result["message"].lower()
    assert result["follow_up_needed"] == []


# ── _build_tracking_message: opened vs applied accuracy ──────────────────────

def test_opened_not_counted_as_applied():
    """'link opened' status must NOT appear in the 'applied' count.

    Regression for: chat said '101 applied' when only 1 had status=applied and
    100 had status=opened (links the user clicked but didn't mark as submitted).
    """
    api = _make_api()
    apps = api._enrich_applications([
        _app("applied", 2, 2, company="Noon"),
        _app("opened", 1, 1, company="ADNOC"),
        _app("opened", 1, 1, company="Careem"),
        _app("opened", 1, 1, company="Talabat"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "1 applied" in msg, f"expected '1 applied', got: {msg}"
    assert "3 links opened" in msg or "links opened" in msg
    # Must NOT claim 4 applications were applied
    assert "4 applied" not in msg
    assert "3 applied" not in msg
    assert "2 applied" not in msg


def test_follow_up_due_status_shown_in_stage_line():
    """Applications with status=follow_up_due must appear in the stage summary."""
    api = _make_api()
    apps = api._enrich_applications([
        _app("applied", 2, 2, company="A"),
        _app("follow_up_due", 2, 2, company="B"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "1 follow-up due" in msg


def test_single_link_opened_singular_label():
    """1 link opened → 'link opened' (no trailing 's')."""
    api = _make_api()
    apps = api._enrich_applications([
        _app("opened", 1, 1, company="Solo"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "1 link opened" in msg
    assert "1 links opened" not in msg


def test_multiple_offers_plural_label():
    """2 offers → '2 offers' (plural)."""
    api = _make_api()
    apps = api._enrich_applications([
        _app("offer", 5, 1, company="A"),
        _app("offer", 5, 1, company="B"),
    ])
    msg = api._build_tracking_message(apps, {})
    assert "2 offers" in msg


def test_smoke_103_tracked_accurate_summary():
    """Mirrors the real production data from the 2026-06-30 smoke test:
    103 total — 1 applied, 2 follow_up_due, 100 opened.
    Chat must not say '101 applied'."""
    api = _make_api()
    apps_data = (
        [_app("applied", 2, 2, company=f"A{i}") for i in range(1)]
        + [_app("follow_up_due", 2, 2, company=f"FU{i}") for i in range(2)]
        + [_app("opened", 1, 1, company=f"O{i}") for i in range(100)]
    )
    apps = api._enrich_applications(apps_data)
    msg = api._build_tracking_message(apps, {"total": 103})
    assert "103 tracked applications" in msg
    assert "1 applied" in msg
    assert "1 follow-up due" not in msg or "2 follow-up due" in msg  # at least the plural
    assert "101 applied" not in msg
    assert "100 links opened" in msg or "links opened" in msg
