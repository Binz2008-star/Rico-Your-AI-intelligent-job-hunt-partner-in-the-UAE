from __future__ import annotations

from unittest.mock import patch

import pytest

from src import job_sources
from src.jsearch_client import FetchResult


@pytest.fixture(autouse=True)
def _jsearch_env(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setattr(job_sources.time, "sleep", lambda *_: None)


def _job(
    job_id: str,
    title: str,
    description: str,
    link: str,
    *,
    company: str = "Example Corp",
    location: str = "Dubai, UAE",
) -> dict:
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "link": link,
        "apply_link": link,
        "source": "jsearch",
    }


def test_profile_driven_jsearch_scores_non_hse_role_without_legacy_scorer():
    software_job = _job(
        "software-1",
        "Senior Python Developer",
        "Build Python APIs and React dashboards.",
        "https://boards.greenhouse.io/example/jobs/1",
    )
    hse_job = _job(
        "hse-1",
        "HSE Manager",
        "Lead safety audits and environmental compliance.",
        "https://boards.greenhouse.io/example/jobs/2",
    )

    with (
        patch("src.jsearch_client.search", return_value=FetchResult(items=[hse_job, software_job])),
        patch("src.scoring.score_job", side_effect=AssertionError("legacy scorer should not run")),
    ):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=False,
            target_roles=["Senior Python Developer"],
            preferred_cities=[],
            skills=["python", "react"],
        )

    assert results[0]["title"] == "Senior Python Developer"
    assert results[0]["score_source"] == "profile_fit"
    assert results[0]["score"] > results[1]["score"]
    assert results[0]["score"] > 0


def test_profile_driven_positive_non_hse_job_is_saved():
    software_job = _job(
        "software-save-1",
        "Senior Python Developer",
        "Python, React, AWS, and backend API ownership.",
        "https://jobs.lever.co/example/software-1",
    )

    with (
        patch("src.jsearch_client.search", return_value=FetchResult(items=[software_job])),
        patch("src.scoring.score_job", side_effect=AssertionError("legacy scorer should not run")),
        patch("src.db.save_job") as save_job,
    ):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=True,
            target_roles=["Senior Python Developer"],
            preferred_cities=[],
            skills=["python", "react", "aws"],
        )

    assert results[0]["score"] > 0
    save_job.assert_called_once()
    assert save_job.call_args.args[0]["title"] == "Senior Python Developer"
    assert save_job.call_args.args[1] == results[0]["score"]


def test_profile_driven_scoring_prefers_direct_source_over_untrusted_aggregator():
    direct_job = _job(
        "direct-1",
        "Compliance Analyst",
        "Compliance controls and audit reporting.",
        "https://jobs.lever.co/example/compliance-1",
    )
    aggregator_job = _job(
        "aggregator-1",
        "Compliance Analyst",
        "Compliance controls and audit reporting.",
        "https://jooble.org/jobs/compliance-analyst",
        company="Aggregator Copy Corp",
    )

    with patch("src.jsearch_client.search", return_value=FetchResult(items=[aggregator_job, direct_job])):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=False,
            target_roles=["Compliance Analyst"],
            preferred_cities=[],
            skills=["compliance"],
        )

    by_id = {job["job_id"]: job for job in results}
    assert results[0]["job_id"] == "direct-1"
    assert by_id["direct-1"]["source_quality"] == "live_verified"
    assert by_id["aggregator-1"]["source_quality"] == "aggregator_untrusted"
    assert by_id["direct-1"]["score"] > by_id["aggregator-1"]["score"]


def test_profile_driven_scoring_prefers_direct_ats_over_generic_job_board():
    direct_job = _job(
        "direct-board-1",
        "Operations Manager",
        "Operations leadership and process improvement.",
        "https://jobs.lever.co/example/operations-1",
    )
    board_job = _job(
        "board-1",
        "Operations Manager",
        "Operations leadership and process improvement.",
        "https://ae.indeed.com/viewjob?jk=operations-1",
        company="Board Copy Corp",
    )

    with patch("src.jsearch_client.search", return_value=FetchResult(items=[board_job, direct_job])):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=False,
            target_roles=["Operations Manager"],
            preferred_cities=["Dubai"],
            skills=["operations"],
        )

    by_id = {job["job_id"]: job for job in results}
    assert results[0]["job_id"] == "direct-board-1"
    assert by_id["direct-board-1"]["source_quality"] == "live_verified"
    assert by_id["board-1"]["source_quality"] == "live_verified"
    assert by_id["direct-board-1"]["score"] > by_id["board-1"]["score"]


def test_profile_driven_scoring_dedupes_same_title_company_to_best_source():
    aggregator_job = _job(
        "duplicate-aggregator",
        "Compliance Analyst",
        "Compliance controls and audit reporting.",
        "https://jooble.org/jobs/compliance-analyst-duplicate",
    )
    direct_job = _job(
        "duplicate-direct",
        "Compliance Analyst",
        "Compliance controls and audit reporting.",
        "https://jobs.lever.co/example/compliance-duplicate",
    )

    with patch("src.jsearch_client.search", return_value=FetchResult(items=[aggregator_job, direct_job])):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=False,
            target_roles=["Compliance Analyst"],
            preferred_cities=[],
            skills=["compliance"],
        )

    assert len(results) == 1
    assert results[0]["job_id"] == "duplicate-direct"
    assert results[0]["source_quality"] == "live_verified"


def test_source_quality_does_not_rescue_zero_profile_fit_job():
    irrelevant_direct_job = _job(
        "irrelevant-direct",
        "Finance Manager",
        "Luxury retail finance reporting and controls.",
        "https://jobs.lever.co/example/finance-1",
    )

    with patch("src.jsearch_client.search", return_value=FetchResult(items=[irrelevant_direct_job])):
        results = job_sources.fetch_jsearch_jobs(
            save_to_db=False,
            target_roles=["Senior Python Developer"],
            preferred_cities=[],
            skills=["python", "react"],
        )

    assert results[0]["profile_fit_score"] == 0
    assert results[0]["source_quality"] == "live_verified"
    assert results[0]["score"] == 0


def test_legacy_jsearch_without_profile_uses_legacy_scorer():
    legacy_job = _job(
        "legacy-1",
        "HSE Manager",
        "Safety and environmental compliance.",
        "https://boards.greenhouse.io/example/jobs/legacy-1",
    )

    with (
        patch("src.jsearch_client.search", return_value=FetchResult(items=[legacy_job])),
        patch("src.scoring.score_job", return_value=42) as score_job,
    ):
        results = job_sources.fetch_jsearch_jobs(save_to_db=False)

    score_job.assert_called_once()
    assert results[0]["score"] == 42
    assert "profile_fit_score" not in results[0]
