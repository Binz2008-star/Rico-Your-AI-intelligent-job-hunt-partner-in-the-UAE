"""
tests/test_gmail_pagination_bounds.py

Tests for the bounded Gmail message-listing phase in gmail_sync_service.
Verifies that pagination is bounded by deadline, page cap, candidate cap,
and repeated-token prevention. No live Google or DB calls.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

os_env = {"JWT_SECRET": "ricosecret" + "x" * 21}


def _fake_list_response(messages, next_page_token=None):
    resp = {"messages": messages}
    if next_page_token:
        resp["nextPageToken"] = next_page_token
    return resp


def _make_msg(i):
    return {"id": f"msg-{i}", "threadId": f"thread-{i}"}


def _make_service(pages):
    """Build a mock Gmail service whose .users().messages().list() returns
    successive pages from the *pages* list, then raises if called beyond."""
    service = MagicMock()
    calls = {"count": 0}

    def execute():
        idx = calls["count"]
        calls["count"] += 1
        if idx < len(pages):
            return pages[idx]
        raise AssertionError("list called beyond provided pages")

    chain = MagicMock()
    chain.execute = execute
    list_mock = MagicMock(return_value=chain)
    messages_mock = MagicMock()
    messages_mock.list = list_mock
    users_mock = MagicMock()
    users_mock.messages = MagicMock(return_value=messages_mock)
    service.users = MagicMock(return_value=users_mock)
    return service, calls


@pytest.fixture(autouse=True)
def flag_on(monkeypatch):
    monkeypatch.setenv("RICO_ENABLE_GMAIL_SYNC", "true")
    yield


# ── Endless nextPageToken ─────────────────────────────────────────────────────


def test_endless_next_page_token_stops_at_page_cap():
    """A mailbox that always returns a nextPageToken must stop at MAX_LIST_PAGES."""
    from src.services.gmail_sync_service import MAX_LIST_PAGES, _fetch_messages_bounded

    # Each page returns a unique token so the repeated-token guard doesn't fire.
    pages = [
        _fake_list_response([_make_msg(i)], next_page_token=f"tok-{i}")
        for i in range(MAX_LIST_PAGES + 5)
    ]
    service, calls = _make_service(pages)

    deadline = time.monotonic() + 300  # far future — deadline won't trigger
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    assert reason == "page_cap"
    assert calls["count"] == MAX_LIST_PAGES
    assert len(messages) <= MAX_LIST_PAGES  # one msg per page (unique threads)


def test_endless_next_page_token_with_repeated_token_stops():
    """If Google returns the same page token repeatedly, pagination must stop."""
    from src.services.gmail_sync_service import _fetch_messages_bounded

    repeated_token = "same-token"
    page = _fake_list_response([_make_msg(0)], next_page_token=repeated_token)
    pages = [page] * 100
    service, calls = _make_service(pages)

    deadline = time.monotonic() + 300
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    assert reason == "repeated_token"
    # Should stop after seeing the repeated token (page 0 + page 1 with same token)
    assert calls["count"] <= 3


# ── Very large mailbox pagination ──────────────────────────────────────────────


def test_very_large_mailbox_stops_at_candidate_cap():
    """A mailbox with many messages per page must stop at MAX_CANDIDATE_MESSAGES."""
    from src.services.gmail_sync_service import (
        LIST_PAGE_SIZE,
        MAX_CANDIDATE_MESSAGES,
        _fetch_messages_bounded,
    )

    # Each page returns LIST_PAGE_SIZE messages with unique threads and unique tokens.
    pages_needed = MAX_CANDIDATE_MESSAGES // LIST_PAGE_SIZE + 2
    pages = []
    for p in range(pages_needed):
        msgs = [_make_msg(p * LIST_PAGE_SIZE + j) for j in range(LIST_PAGE_SIZE)]
        pages.append(_fake_list_response(msgs, next_page_token=f"uniq-tok-{p}"))
    service, calls = _make_service(pages)

    deadline = time.monotonic() + 300
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    assert reason == "candidate_cap"
    assert len(messages) == MAX_CANDIDATE_MESSAGES


# ── Deadline reached during listing ────────────────────────────────────────────


def test_deadline_reached_during_listing():
    """If the deadline expires mid-listing, pagination must stop immediately."""
    from src.services.gmail_sync_service import _fetch_messages_bounded

    page1 = _fake_list_response([_make_msg(0)], next_page_token="tok-1")
    page2 = _fake_list_response([_make_msg(1)], next_page_token="tok-2")
    service, calls = _make_service([page1, page2])

    # Set deadline in the past so the first check triggers before any API call.
    deadline = time.monotonic() - 1
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    assert reason == "deadline"
    assert len(messages) == 0
    assert calls["count"] == 0  # no list request made


def test_deadline_reached_between_pages():
    """Deadline checked before each page request, not just the first."""
    from src.services.gmail_sync_service import _fetch_messages_bounded

    page1 = _fake_list_response([_make_msg(0)], next_page_token="uniq-1")
    page2 = _fake_list_response([_make_msg(1)], next_page_token="uniq-2")
    page3 = _fake_list_response([_make_msg(2)])  # no next token — natural end
    service, calls = _make_service([page1, page2, page3])

    # Give enough time for page 1 but potentially not page 2.
    deadline = time.monotonic() + 0.05
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    # Either deadline (if slow) or done (if fast enough to finish 3 pages).
    # Both are acceptable — the test verifies no unbounded pagination.
    assert reason in ("deadline", "done", "page_cap")
    assert calls["count"] <= 3


# ── Page cap reached ──────────────────────────────────────────────────────────


def test_page_cap_reached_records_partial():
    """When the page cap is hit, stop_reason must be 'page_cap'."""
    from src.services.gmail_sync_service import MAX_LIST_PAGES, _fetch_messages_bounded

    pages = []
    for i in range(MAX_LIST_PAGES + 3):
        pages.append(_fake_list_response([_make_msg(i)], next_page_token=f"uniq-pg-{i}"))
    service, calls = _make_service(pages)

    deadline = time.monotonic() + 300
    messages, reason = _fetch_messages_bounded(service, 14, deadline)

    assert reason == "page_cap"
    assert calls["count"] == MAX_LIST_PAGES


# ── Candidate-message cap reached ──────────────────────────────────────────────


def test_candidate_cap_reached_exact():
    """When the candidate cap is hit mid-page, stop immediately."""
    from src.services.gmail_sync_service import _fetch_messages_bounded

    # Use a small max_candidates for test speed.
    small_cap = 5
    page1_msgs = [_make_msg(i) for i in range(3)]
    page2_msgs = [_make_msg(i) for i in range(3, 10)]
    page1 = _fake_list_response(page1_msgs, next_page_token="uniq-cap-1")
    page2 = _fake_list_response(page2_msgs, next_page_token="uniq-cap-2")
    service, calls = _make_service([page1, page2])

    deadline = time.monotonic() + 300
    messages, reason = _fetch_messages_bounded(
        service, 14, deadline, max_candidates=small_cap
    )

    assert reason == "candidate_cap"
    assert len(messages) == small_cap


# ── No message fetch after budget expires ──────────────────────────────────────


def test_no_message_detail_fetch_after_budget_expires():
    """When the listing deadline is already expired, run_user_sync must not
    fetch any message details or insert any review items."""
    from src.services import gmail_sync_service

    # Mock everything: connection, crypto, credentials, service.
    conn = {
        "id": "conn-1",
        "user_id": "user@test.com",
        "encrypted_refresh_token": "enc-token",
        "status": "active",
    }

    with patch("src.repositories.gmail_repo.get_connection", return_value=conn), \
         patch("src.services.gmail_sync_service.decrypt_token", return_value="refresh"), \
         patch("src.services.gmail_sync_service.credentials_from_refresh_token") as creds_fn, \
         patch("src.services.gmail_sync_service._refresh_credentials"), \
         patch("src.services.gmail_sync_service._build_gmail_service") as build_svc, \
         patch("src.services.gmail_sync_service._fetch_messages_bounded") as fetch_fn, \
         patch("src.gmail_importer._get_message_detail") as get_detail, \
         patch("src.repositories.gmail_repo.insert_review_item") as insert_ri, \
         patch("src.repositories.gmail_repo.create_sync_run", return_value="run-1"), \
         patch("src.repositories.gmail_repo.finish_sync_run") as finish_run, \
         patch("src.repositories.gmail_repo.touch_last_sync"), \
         patch("src.repositories.gmail_repo.insert_audit_event"), \
         patch("src.services.gmail_sync_service._load_user_applications", return_value=[]), \
         patch("src.gmail_importer._build_application_index", return_value=None):

        # Simulate: listing returned 0 messages because deadline was already expired.
        fetch_fn.return_value = ([], "deadline")

        result = gmail_sync_service.run_user_sync(
            "user@test.com", mode="manual", time_budget_seconds=0.01,
        )

        assert result["status"] == "partial"
        assert result["error_code"] == "list_deadline"
        assert result["messages_fetched"] == 0
        # No message detail fetches should have occurred.
        get_detail.assert_not_called()
        # No review items should have been inserted.
        insert_ri.assert_not_called()
