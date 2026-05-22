import json

from src.agent.intelligence.intent_classifier import classify_intent
from src.rico_chat_api import RicoChatAPI


class FakeMemory:
    def __init__(self, history):
        self._history = history

    def load_chat_history(self, user_id, limit=None):
        return self._history[-limit:] if limit else self._history


def _api_with_recent_job(job):
    api = RicoChatAPI()
    api.memory = FakeMemory([
        {
            "role": "assistant",
            "message": json.dumps({
                "type": "job_matches",
                "matches": [job],
            }),
        }
    ])
    return api


def test_prepare_application_uses_selected_job_context():
    job = {
        "job_key": "job-1",
        "title": "Environment Manager",
        "company": "TECCODD",
        "location": "UAE",
        "source": "jsearch",
        "match_reasons": ["Your environment management background fits this role."],
    }
    api = _api_with_recent_job(job)

    response = api._handle_prepare_application(
        "user@example.com",
        "prepare application for Environment Manager at TECCODD",
        {"skills": ["environmental compliance", "audits", "stakeholder management"]},
    )

    assert response["type"] == "application_prep"
    assert "Environment Manager at TECCODD" in response["message"]
    assert "Why this job fits" in response["message"]
    assert "Tailored CV bullets" in response["message"]
    assert "Cover note draft" in response["message"]
    assert "Application checklist" in response["message"]
    assert "I do not have a direct apply link for this listing yet" in response["message"]


def test_save_job_then_applications_list_contains_it(monkeypatch):
    apps = []

    def fake_create(job_id, title, company, location="", url="", status="opened", source="manual", user_id=None):
        apps.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "link": url,
            "status": status,
            "user_id": user_id,
        })
        return True

    monkeypatch.setattr("src.repositories.applications_repo.create", fake_create)
    monkeypatch.setattr("src.repositories.applications_repo.get_all", lambda user_id=None: apps)
    monkeypatch.setattr("src.repositories.applications_repo.get_stats", lambda user_id=None: {"total_applied": len(apps)})

    job = {
        "job_key": "job-2",
        "title": "Environment Manager",
        "company": "TECCODD",
        "location": "UAE",
    }
    api = _api_with_recent_job(job)

    assert api._track_job_status("user@example.com", job, "saved", "Saved via test") is True
    response = api._handle_application_tracking("user@example.com")

    assert response["type"] == "application_status"
    assert response["applications"][0]["title"] == "Environment Manager"
    assert response["applications"][0]["company"] == "TECCODD"
    assert response["applications"][0]["status"] == "saved"


def test_mark_as_applied_confirmation_updates_exact_job(monkeypatch):
    tracked = {}

    job = {
        "job_key": "job-3",
        "title": "Environment Manager",
        "company": "TECCODD",
        "location": "UAE",
    }
    api = _api_with_recent_job(job)

    def fake_track(user_id, selected_job, status, notes):
        tracked.update({"user_id": user_id, "job": selected_job, "status": status, "notes": notes})
        return True

    monkeypatch.setattr(api, "_track_job_status", fake_track)

    response = api._confirm_pending_apply(
        "user@example.com",
        {"type": "confirmation_required", "intent": "apply_job", "pending_action": "mark_applied", "job": job},
    )

    assert response["type"] == "application_tracked"
    assert response["status"] == "applied"
    assert "Environment Manager at TECCODD" in response["message"]
    assert tracked["job"] == job
    assert tracked["status"] == "applied"


def test_duplicate_job_filtering_by_title_company_location_source():
    jobs = [
        {"title": "Environment Manager", "company": "TECCODD", "location": "UAE", "source": "jsearch", "link": "https://a.example"},
        {"title": " Environment  Manager ", "company": "teccodd", "location": "UAE", "source": "jsearch", "link": "https://b.example"},
        {"title": "Environment Manager", "company": "TECCODD", "location": "Dubai", "source": "jsearch", "link": "https://c.example"},
    ]

    deduped = RicoChatAPI._dedupe_jobs(jobs)

    assert len(deduped) == 2
    assert deduped[0]["link"] == "https://a.example"
    assert deduped[1]["location"] == "Dubai"


def test_show_me_how_to_apply_returns_application_instructions():
    result = classify_intent("show me how to apply for Environment Manager at TECCODD")
    assert result.intent == "prepare_application"

    job = {
        "job_key": "job-4",
        "title": "Environment Manager",
        "company": "TECCODD",
        "location": "UAE",
        "apply_url": "https://jobs.example/apply",
    }
    api = _api_with_recent_job(job)

    response = api._handle_prepare_application(
        "user@example.com",
        "show me how to apply for Environment Manager at TECCODD",
        {"skills": ["environmental compliance"]},
    )

    assert response["type"] == "application_prep"
    assert "Application checklist" in response["message"]
    assert "Apply link: https://jobs.example/apply" in response["message"]
