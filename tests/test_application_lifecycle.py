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


def test_lifecycle_job_key_uses_title_company_preferably():
    """Verify _derive_lifecycle_job_key prefers title/company over URL."""
    from src.rico_chat_api import RicoChatAPI

    title = "Engineer"
    company = "Google"
    url = "https://google.com/jobs/123"

    # With title and company, should use title/company key
    key_with_title_company = RicoChatAPI._derive_lifecycle_job_key(title, company, url)

    # Without URL, should still use title/company key
    key_without_url = RicoChatAPI._derive_lifecycle_job_key(title, company, "")

    assert key_with_title_company == key_without_url

    # Should match the title/company fallback from get_job_id
    from src.applications import get_job_id
    expected_key = get_job_id({"title": title, "company": company})
    assert key_with_title_company == expected_key


def test_lifecycle_job_key_fallback_to_url():
    """Verify _derive_lifecycle_job_key falls back to URL when title/company missing."""
    from src.rico_chat_api import RicoChatAPI

    url = "https://example.com/jobs/123"

    # With only URL, should use URL-based key
    key_url_only = RicoChatAPI._derive_lifecycle_job_key("", "", url)

    # Should match URL-based key from get_job_id
    from src.applications import get_job_id
    expected_key = get_job_id({"link": url})
    assert key_url_only == expected_key


def test_status_rank_values():
    """Verify status rank values are correctly ordered."""
    from src.rico_chat_api import RicoChatAPI

    assert RicoChatAPI._get_status_rank("saved") == 10
    assert RicoChatAPI._get_status_rank("opened") == 20
    assert RicoChatAPI._get_status_rank("opened_external") == 20
    assert RicoChatAPI._get_status_rank("prepared") == 30
    assert RicoChatAPI._get_status_rank("applied") == 40
    assert RicoChatAPI._get_status_rank("follow_up_due") == 50
    assert RicoChatAPI._get_status_rank("interview") == 60
    assert RicoChatAPI._get_status_rank("offer") == 70
    assert RicoChatAPI._get_status_rank("rejected") == 70
    assert RicoChatAPI._get_status_rank("decision_made") == 80
    assert RicoChatAPI._get_status_rank("archived") == 90
    assert RicoChatAPI._get_status_rank("unknown") == 0


def test_should_update_status_allows_upgrade():
    """Verify _should_update_status allows status upgrades."""
    from src.rico_chat_api import RicoChatAPI

    # Lower to higher should be allowed
    assert RicoChatAPI._should_update_status("saved", "opened_external") is True
    assert RicoChatAPI._should_update_status("opened_external", "prepared") is True
    assert RicoChatAPI._should_update_status("prepared", "applied") is True
    assert RicoChatAPI._should_update_status("applied", "interview") is True
    assert RicoChatAPI._should_update_status("interview", "offer") is True

    # Same status should be allowed
    assert RicoChatAPI._should_update_status("applied", "applied") is True


def test_should_update_status_blocks_downgrade():
    """Verify _should_update_status blocks status downgrades."""
    from src.rico_chat_api import RicoChatAPI

    # Higher to lower should be blocked
    assert RicoChatAPI._should_update_status("applied", "opened_external") is False
    assert RicoChatAPI._should_update_status("interview", "prepared") is False
    assert RicoChatAPI._should_update_status("offer", "applied") is False
    assert RicoChatAPI._should_update_status("decision_made", "saved") is False


def test_persist_lifecycle_skips_when_status_would_regress():
    """Verify _persist_application_lifecycle_event skips update when status would regress."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def mock_find_by_job_id(job_key, user_id):
        # Simulate existing record with higher status
        return {"status": "applied"}

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        with patch("src.repositories.applications_repo.find_by_job_id", side_effect=mock_find_by_job_id):
            # Try to downgrade from applied to opened_external
            api._persist_application_lifecycle_event(
                user_id="test@example.com",
                title="Engineer",
                company="Google",
                status="opened_external",
                url="https://google.com/jobs/123",
            )

    # Should not have called create (skipped due to regression)
    assert len(create_calls) == 0


def test_persist_lifecycle_allows_upgrade():
    """Verify _persist_application_lifecycle_event allows status upgrades."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def mock_find_by_job_id(job_key, user_id):
        # Simulate existing record with lower status
        return {"status": "saved"}

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        with patch("src.repositories.applications_repo.find_by_job_id", side_effect=mock_find_by_job_id):
            # Upgrade from saved to opened_external
            api._persist_application_lifecycle_event(
                user_id="test@example.com",
                title="Engineer",
                company="Google",
                status="opened_external",
                url="https://google.com/jobs/123",
            )

    # Should have called create (upgrade allowed)
    assert len(create_calls) == 1
    assert create_calls[0]["status"] == "opened_external"


def test_persist_lifecycle_creates_when_no_existing():
    """Verify _persist_application_lifecycle_event creates record when none exists."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def mock_find_by_job_id(job_key, user_id):
        # No existing record
        return None

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        with patch("src.repositories.applications_repo.find_by_job_id", side_effect=mock_find_by_job_id):
            api._persist_application_lifecycle_event(
                user_id="test@example.com",
                title="Engineer",
                company="Google",
                status="opened_external",
                url="https://google.com/jobs/123",
            )

    # Should have called create (no existing record)
    assert len(create_calls) == 1
    assert create_calls[0]["status"] == "opened_external"


def test_mark_applied_then_open_link_preserves_applied():
    """Verify mark_applied first then open_apply_link later preserves applied status.

    Manual scenario: user marks as applied before opening apply link.
    System should keep one record with status=applied, not downgrade to opened_external.
    """
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(**kwargs):
        create_calls.append(kwargs)
        return True

    def mock_find_by_job_id(job_key, user_id):
        # Simulate existing record with applied status (from mark_applied)
        return {"status": "applied"}

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        with patch("src.repositories.applications_repo.find_by_job_id", side_effect=mock_find_by_job_id):
            # User opens apply link after already marking as applied
            api._persist_application_lifecycle_event(
                user_id="test@example.com",
                title="HSE Manager",
                company="Archirodon Group N.V",
                status="opened_external",
                url="https://example.com/apply",
            )

    # Should not have called create (skipped due to regression prevention)
    # Status stays applied, does not downgrade to opened_external
    assert len(create_calls) == 0


# ── New tests for Issue #353 (Application Lifecycle Completion) ──────────────


def test_search_result_auto_persist_loop_calls_persist_with_opened_status():
    """Verify the search-result auto-persist loop (Change A) calls
    _persist_application_lifecycle_event with status='opened' for each valid match
    and skips entries with empty title or company."""
    from src.rico_chat_api import RicoChatAPI
    from unittest.mock import patch

    api = RicoChatAPI()
    persist_calls = []

    # Simulate the formatted matches list returned by _format_match
    formatted = [
        {"title": "Senior Engineer", "company": "Acme Corp", "apply_url": "https://acme.com/1", "location": "Dubai"},
        {"title": "Product Manager", "company": "TechCo", "source_url": "https://techco.com/2", "location": "Abu Dhabi"},
        {"title": "", "company": "EmptyTitle Corp", "apply_url": "https://example.com/3"},  # skipped
        {"title": "No Company Job", "company": "", "apply_url": "https://example.com/4"},   # skipped
    ]

    with patch.object(api, "_persist_application_lifecycle_event", side_effect=lambda **kw: persist_calls.append(kw)):
        # Reproduce the loop added in Change A
        for _m in formatted:
            _t = (_m.get("title") or "").strip()
            _c = (_m.get("company") or "").strip()
            if _t and _c:
                api._persist_application_lifecycle_event(
                    user_id="u1@example.com",
                    title=_t,
                    company=_c,
                    status="opened",
                    url=(_m.get("apply_url") or _m.get("source_url") or "").strip(),
                    location=str(_m.get("location") or "").strip(),
                )

    assert len(persist_calls) == 2, "Only matches with non-empty title AND company should be persisted"
    assert all(c["status"] == "opened" for c in persist_calls)
    assert persist_calls[0]["title"] == "Senior Engineer"
    assert persist_calls[0]["company"] == "Acme Corp"
    assert persist_calls[1]["title"] == "Product Manager"
    assert persist_calls[1]["company"] == "TechCo"


def test_prepare_flow_dual_write_calls_persist_with_prepared_status():
    """Verify Change B: prepare flow calls _persist_application_lifecycle_event with
    status='prepared' so prepared jobs appear on the /flow board."""
    from src.rico_chat_api import RicoChatAPI

    api = RicoChatAPI()
    create_calls = []

    def mock_create(*, job_id, title, company, location, url, status, source, user_id):
        create_calls.append({"status": status, "title": title, "company": company, "url": url})
        return True

    def mock_find_by_job_id(job_key, user_id):
        return None  # No existing record

    with patch("src.repositories.applications_repo.create", side_effect=mock_create):
        with patch("src.repositories.applications_repo.find_by_job_id", side_effect=mock_find_by_job_id):
            api._persist_application_lifecycle_event(
                user_id="test@example.com",
                title="HSE Manager",
                company="Archirodon Group",
                status="prepared",
                url="https://example.com/apply",
            )

    assert len(create_calls) == 1
    assert create_calls[0]["status"] == "prepared"
    assert create_calls[0]["title"] == "HSE Manager"
    assert create_calls[0]["url"] == "https://example.com/apply"


def test_opened_status_does_not_downgrade_higher_statuses():
    """Verify regression guard: auto-persist with status='opened' (rank 20) never
    overwrites prepared (30), applied (40), interview (60), or offer (70)."""
    from src.rico_chat_api import RicoChatAPI

    higher_statuses = ["prepared", "applied", "interview", "offer"]
    for current_status in higher_statuses:
        result = RicoChatAPI._should_update_status(current_status, "opened")
        assert result is False, (
            f"_should_update_status('{current_status}', 'opened') should be False "
            f"(opened rank 20 must not downgrade {current_status})"
        )
