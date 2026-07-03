"""
BUG-14 (remaining half): jobs_service.save_job / skip_job / block_company must
dedup against the SAME store they write to (applications_repo → DB for SaaS
users). Previously the dedup read the legacy JSON is_applied() while the write
went to the DB, so a repeat save/skip was never detected and the counter kept
incrementing.

All external I/O is mocked — no DB, no network.
"""
from unittest.mock import patch

import pytest

import src.services.jobs_service as js

_JOB = {"job_id": "jk-123", "title": "Data Analyst", "company": "Acme", "link": "https://x/y"}


# ── save_job ──────────────────────────────────────────────────────────────────

def test_save_job_first_time_persists():
    with patch("src.repositories.applications_repo.find_by_job_id", return_value=None) as find, \
         patch("src.repositories.applications_repo.create", return_value=True) as create:
        assert js.save_job(_JOB, user_id="u@e.com") is True
        create.assert_called_once()
        # dedup read and write use the SAME key
        assert find.call_args.args[0] == create.call_args.kwargs["job_id"]
        assert create.call_args.kwargs["status"] == "saved"


def test_save_job_second_time_is_deduped_no_write():
    with patch("src.repositories.applications_repo.find_by_job_id", return_value={"job_id": "jk-123"}), \
         patch("src.repositories.applications_repo.create") as create:
        assert js.save_job(_JOB, user_id="u@e.com") is False
        create.assert_not_called()


# ── skip_job ──────────────────────────────────────────────────────────────────

def test_skip_job_first_time_persists_decision_made():
    with patch("src.repositories.applications_repo.find_by_job_id", return_value=None), \
         patch("src.repositories.applications_repo.create", return_value=True) as create:
        assert js.skip_job(_JOB, user_id="u@e.com") is True
        assert create.call_args.kwargs["status"] == "decision_made"


def test_skip_job_second_time_is_deduped_no_write():
    with patch("src.repositories.applications_repo.find_by_job_id", return_value={"job_id": "jk-123"}), \
         patch("src.repositories.applications_repo.create") as create:
        assert js.skip_job(_JOB, user_id="u@e.com") is False
        create.assert_not_called()


# ── block_company ─────────────────────────────────────────────────────────────

def test_block_company_records_once_then_dedups():
    with patch("src.services.jobs_service._persist_blocked_company"), \
         patch("src.repositories.applications_repo.find_by_job_id", return_value=None), \
         patch("src.repositories.applications_repo.create", return_value=True) as create:
        assert js.block_company(_JOB, user_id="u@e.com") == "Acme"
        create.assert_called_once()

    with patch("src.services.jobs_service._persist_blocked_company"), \
         patch("src.repositories.applications_repo.find_by_job_id", return_value={"job_id": "jk-123"}), \
         patch("src.repositories.applications_repo.create") as create2:
        assert js.block_company(_JOB, user_id="u@e.com") == "Acme"
        create2.assert_not_called()  # already tracked → no duplicate decision_made


def test_block_company_requires_company():
    with pytest.raises(ValueError):
        js.block_company({"job_id": "x"}, user_id="u@e.com")


# ── auth guard preserved ──────────────────────────────────────────────────────

@pytest.mark.parametrize("fn", [js.save_job, js.skip_job])
def test_requires_user_id(fn):
    with pytest.raises(ValueError):
        fn(_JOB, user_id=None)
