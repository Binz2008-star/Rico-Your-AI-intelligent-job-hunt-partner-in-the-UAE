"""Test application lifecycle persistence for open_apply_link, prepare_application."""
import pytest
from unittest.mock import patch, MagicMock


def test_persist_application_lifecycle_event_calls_repo():
    """Verify _persist_application_lifecycle_event calls applications_repo.create with correct args."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    user_id = "test@example.com"
    title = "Senior Manager"
    company = "Test Company"
    status = "opened_external"
    url = "https://example.com/apply"

    # Mock the applications_repo.create function
    create_calls = []

    def mock_create(*, job_id, title, company, location, url, status, source, user_id):
        create_calls.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "status": status,
            "source": source,
            "user_id": user_id,
        })
        return True

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        api._persist_application_lifecycle_event(
            user_id=user_id,
            title=title,
            company=company,
            status=status,
            url=url,
        )

    assert len(create_calls) == 1
    assert create_calls[0]["status"] == status
    assert create_calls[0]["title"] == title
    assert create_calls[0]["company"] == company
    assert create_calls[0]["url"] == url
    assert create_calls[0]["source"] == "chat"
    assert create_calls[0]["user_id"] == user_id


def test_persist_application_lifecycle_event_handles_db_failure():
    """Verify _persist_application_lifecycle_event does not raise on DB failure."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()

    # Mock applications_repo.create to raise an exception
    def mock_create_failure(**kwargs):
        raise Exception("DB unavailable")

    with patch("src.repositories.applications_repo.create", side_effect=mock_create_failure):
        # Should not raise
        api._persist_application_lifecycle_event(
            user_id="test@example.com",
            title="Engineer",
            company="Corp",
            status="prepared",
        )


def test_persist_application_lifecycle_event_without_url():
    """Verify _persist_application_lifecycle_event works without URL (for prepare_application)."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(*, job_id, title, company, location, url, status, source, user_id):
        create_calls.append({"url": url, "status": status})
        return True

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        api._persist_application_lifecycle_event(
            user_id="test@example.com",
            title="Engineer",
            company="Corp",
            status="prepared",
            url="",  # No URL for prepare_application
        )

    assert len(create_calls) == 1
    assert create_calls[0]["url"] == ""
    assert create_calls[0]["status"] == "prepared"


def test_valid_statuses_includes_new_statuses():
    """Verify VALID_STATUSES includes prepared and follow_up_due."""
    from src.applications import VALID_STATUSES

    assert "prepared" in VALID_STATUSES
    assert "follow_up_due" in VALID_STATUSES
    assert "opened_external" in VALID_STATUSES
    # Ensure existing statuses are still present
    assert "saved" in VALID_STATUSES
    assert "applied" in VALID_STATUSES
    assert "interview" in VALID_STATUSES


def test_duplicate_prevention_via_job_key():
    """Verify job_key derivation is stable for duplicate prevention."""
    from src.applications import get_job_id

    job1 = {"title": "Engineer", "company": "Google", "link": "https://google.com/jobs/1"}
    job2 = {"title": "Engineer", "company": "Google", "link": "https://google.com/jobs/1"}

    key1 = get_job_id(job1)
    key2 = get_job_id(job2)

    assert key1 == key2
    assert len(key1) == 16  # SHA-256[:16]

    # Different job should have different key
    job3 = {"title": "Engineer", "company": "Google", "link": "https://google.com/jobs/2"}
    key3 = get_job_id(job3)
    assert key3 != key1


def test_job_key_fallback_without_link():
    """Verify job_key falls back to title|company|location when link is missing."""
    from src.applications import get_job_id

    job = {"title": "Manager", "company": "Corp", "location": "Dubai"}
    key = get_job_id(job)

    assert len(key) == 16
    assert key != ""

    # Same job data should produce same key
    job2 = {"title": "Manager", "company": "Corp", "location": "Dubai"}
    key2 = get_job_id(job2)
    assert key == key2
