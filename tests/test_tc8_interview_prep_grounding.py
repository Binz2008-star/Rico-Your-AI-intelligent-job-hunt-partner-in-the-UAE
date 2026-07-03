"""Regression tests for TC-8 interview-prep grounding.

Root cause (2026-07-03 live QA): "prepare me for an interview for the Retail
Operations Manager role at Richemont" did not prepare for that role — it drifted
to generic tips / unrelated company openings. Trace findings:

  - The intent classifier already returns `interview_prep` (correct).
  - The chat dispatch sent the raw message straight to the AI provider with NO
    grounding: it never parsed the role/company and never checked tracked
    applications.
  - Two `_handle_interview_prep` methods existed; the later one shadowed the
    earlier (dead) one.

Fix: a deterministic resolver extracts the role + company, matches a tracked
application when one exists, and builds a grounded prompt that pins the exact
role/company and forbids listing job openings. The dead duplicate handler was
removed. These tests cover the deterministic grounding; the final AI text still
needs a live provider to verify.
"""

import inspect

import pytest

from src.rico_chat_api import RicoChatAPI


# --- 1. Role/company extraction -------------------------------------------------

@pytest.mark.parametrize("message,expected", [
    ("prepare me for an interview for the Retail Operations Manager role at Richemont",
     ("Retail Operations Manager", "Richemont")),
    ("prepare me for an interview for a Compliance Manager at ADNOC",
     ("Compliance Manager", "ADNOC")),
    ("prepare me for an interview for Retail Operations Manager position at Richemont",
     ("Retail Operations Manager", "Richemont")),
    ("prepare me for an interview at Richemont", ("", "Richemont")),
    ("help me prepare for my interview", ("", "")),
])
def test_extract_interview_context(message, expected):
    assert RicoChatAPI._extract_interview_context(message) == expected


# --- 2. Tracked-application matching --------------------------------------------

def test_match_tracked_application_prefers_company_and_role():
    apps = [
        {"title": "ServiceNow Developer", "company": "TechCo", "status": "saved"},
        {"role": "Retail Operations Manager", "company": "Richemont", "status": "applied"},
    ]
    m = RicoChatAPI._match_tracked_application(apps, "Retail Operations Manager", "Richemont")
    assert m and m["company"] == "Richemont"


def test_match_tracked_application_none_when_no_overlap():
    apps = [{"title": "ServiceNow Developer", "company": "TechCo"}]
    assert RicoChatAPI._match_tracked_application(apps, "Retail Operations Manager", "Richemont") is None


# --- 3. Grounded prompt construction --------------------------------------------

def test_prompt_forbids_openings_and_pins_role_company():
    p = RicoChatAPI._build_interview_prompt_override(
        "prepare me for an interview for the Retail Operations Manager role at Richemont",
        "Retail Operations Manager", "Richemont", None,
    )
    assert "Retail Operations Manager" in p
    assert "Richemont" in p
    assert "Do NOT list" in p  # never list openings — coaching, not search
    assert "NOT currently tracking" in p  # explicit fallback when not tracked


def test_prompt_tailors_to_tracked_application():
    tracked = {"role": "Retail Operations Manager", "company": "Richemont", "status": "applied"}
    p = RicoChatAPI._build_interview_prompt_override(
        "...", "Retail Operations Manager", "Richemont", tracked,
    )
    assert "already tracking" in p
    assert "status: applied" in p
    assert "Do NOT list" in p


# --- 4. End-to-end resolver (tracked vs. not) with a stubbed repo ---------------

def _resolve(monkeypatch, message, apps):
    import src.repositories.applications_repo as ar
    monkeypatch.setattr(ar, "get_all", lambda user_id=None, **kw: apps)
    api = RicoChatAPI()
    profile = {"target_roles": ["Operations Manager"]}
    return api._resolve_interview_prep_target("u1", message, profile)


def test_resolver_uses_message_role_over_stale_profile(monkeypatch):
    out = _resolve(
        monkeypatch,
        "prepare me for an interview for the Retail Operations Manager role at Richemont",
        [],  # no tracked apps
    )
    # Must use the role from the message, not the stale profile target.
    assert out["target_role"] == "Retail Operations Manager"
    assert out["company"] == "Richemont"
    assert out["tracked"] is False
    assert "Do NOT list" in out["prompt_override"]


def test_resolver_flags_tracked_application(monkeypatch):
    out = _resolve(
        monkeypatch,
        "prepare me for an interview for the Retail Operations Manager role at Richemont",
        [{"role": "Retail Operations Manager", "company": "Richemont", "status": "applied"}],
    )
    assert out["tracked"] is True
    assert "already tracking" in out["prompt_override"]


# --- 5. Only one interview-prep handler remains (no dead shadow) -----------------

def test_single_interview_prep_handler():
    src = inspect.getsource(RicoChatAPI)
    assert src.count("def _handle_interview_prep(") == 1, (
        "the duplicate/shadowed _handle_interview_prep must be removed"
    )
