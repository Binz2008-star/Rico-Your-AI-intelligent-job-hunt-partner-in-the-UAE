from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.rico_chat_api import RicoChatAPI


USER = "application-channel@example.com"


def _api_with_recent_job() -> tuple[RicoChatAPI, dict]:
    api = RicoChatAPI.__new__(RicoChatAPI)
    api._persist = False
    api._current_operation_id = None
    api.system = MagicMock()
    api.memory = MagicMock()
    context: dict = {
        "recent_application": {
            "title": "ISO 14001 Lead Auditor",
            "company": "Certification Body",
            "location": "Abu Dhabi",
            "salary": "AED 14,000-18,000",
            "status": "prepared",
            "status_label": "prepared",
            "link": "https://www.linkedin.com/jobs/view/123",
            "route": "/command",
            "last_action": "prepare_application",
        },
        "recent_job": "ISO 14001 Lead Auditor",
        "recent_company": "Certification Body",
        "recent_status": "prepared",
        "recent_status_label": "prepared",
    }
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
    profile.target_roles = ["ISO 14001 Lead Auditor"]
    profile.skills = ["ISO 14001", "Lead Auditor", "Environmental Compliance"]
    profile.certifications = ["ISO 14001 Lead Auditor"]
    profile.industries = ["Certification Body"]
    profile.years_experience = 10
    profile.current_role = "HSE Specialist"
    return profile


def _agent() -> MagicMock:
    return MagicMock(
        openai_available=False,
        deepseek_available=False,
        hf_available=False,
        provider_available=False,
        model="",
    )


def _run(message: str) -> tuple[dict, dict]:
    api, context = _api_with_recent_job()
    with (
        patch.object(api, "_resolve_profile", return_value=_profile()),
        patch.object(api, "_get_openai_agent", return_value=_agent()),
        patch.object(api, "_looks_like_career_execution_request", return_value=False),
    ):
        return api._handle_active_user(USER, message), context


def _assert_job_context_preserved(message: str) -> None:
    assert "ISO 14001 Lead Auditor" in message
    assert "Certification Body" in message
    assert "Abu Dhabi" in message
    assert "AED 14,000-18,000" in message


def test_go_ahead_without_favorite_asks_for_channel_and_does_not_save() -> None:
    with patch("src.rico_chat_api.agent_runtime.handle_action") as handle_action:
        result, _ = _run("ya go ahead but don't set it as favorite thou")

    msg = result["message"]
    assert result["type"] == "application_channel_clarification"
    assert "will not save or favorite" in msg
    assert "Send where?" in msg
    assert "recruiter email" in msg
    assert "copy/paste text" in msg
    assert "cannot send through LinkedIn directly" in msg
    assert "For job portals" in msg
    assert not result.get("options")
    assert all(marker not in msg for marker in ("A)", "B)", "C)"))
    _assert_job_context_preserved(msg)
    handle_action.assert_not_called()


def test_arabic_draft_and_send_request_drafts_and_asks_for_recruiter_email() -> None:
    result, context = _run("صيغ رسالة نراجعها وارسلها عني")

    msg = result["message"]
    assert result["type"] == "draft_message"
    assert "هذه صياغة نراجعها" in msg
    assert "إيميل الـ recruiter" in msg
    assert "للنسخ واللصق" in msg
    assert "لا أستطيع إرسالها عبر LinkedIn مباشرة" in msg
    assert "بوابة توظيف" in msg
    assert "Send where" not in msg
    assert "Current job context" not in msg
    assert all(marker not in msg for marker in ("A)", "B)", "C)"))
    _assert_job_context_preserved(msg)
    assert context["_pending_application_send"]["needs_destination"] is True
    assert "ISO 14001 Lead Auditor" in context["_pending_application_send"]["draft"]


def test_arabic_send_without_destination_asks_for_missing_destination() -> None:
    result, _ = _run("ارسلها")

    msg = result["message"]
    assert result["type"] == "application_channel_clarification"
    assert "أعطني إيميل الـ recruiter أو رابط/طريقة الإرسال" in msg
    assert "لا أستطيع إرسالها عبر LinkedIn مباشرة" in msg
    assert "بوابة توظيف" in msg
    assert "آسف" not in msg
    assert "cannot" not in msg.lower()
    assert not result.get("options")
    _assert_job_context_preserved(msg)


def test_linkedin_send_claim_is_never_positive() -> None:
    result, _ = _run("send it through LinkedIn")

    msg = result["message"]
    assert "I can only give you copy/paste text" in msg
    assert "cannot send through LinkedIn directly" in msg
    assert "can send through LinkedIn" not in msg
