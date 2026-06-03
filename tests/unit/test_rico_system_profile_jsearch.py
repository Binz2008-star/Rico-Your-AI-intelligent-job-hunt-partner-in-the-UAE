from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.rico_agent import RicoProfile
from src.rico_repo_adapter import AdapterConfig, RicoSystem


def _system() -> RicoSystem:
    system = RicoSystem(
        config=AdapterConfig(
            enable_decision_engine=False,
            enable_learning_repo=False,
        )
    )
    system.repo.persist_jobs = MagicMock()
    system.repo.remove_applied_jobs = MagicMock(side_effect=lambda jobs: jobs)
    return system


def _profile() -> RicoProfile:
    return RicoProfile(
        user_id="profile-user",
        target_roles=["Senior Python Developer"],
        preferred_cities=["Dubai"],
        skills=["python", "react", "aws"],
        deal_breakers=["sales"],
    )


def _job(**overrides) -> dict:
    job = {
        "job_id": "python-1",
        "title": "Senior Python Developer",
        "company": "Example Corp",
        "location": "Dubai, UAE",
        "description": "Python, React, AWS, and backend API ownership.",
        "link": "https://jobs.lever.co/example/python-1",
        "apply_link": "https://jobs.lever.co/example/python-1",
        "alt_link": "https://google.com/search?q=python+developer+dubai",
        "source": "jsearch",
        "score": 82,
        "profile_fit_score": 72,
        "score_source": "profile_fit",
        "source_quality": "live_verified",
        "profile_explanation": "Target role: Senior Python Developer | Skills: python, react, aws",
    }
    job.update(overrides)
    return job


def test_run_for_profile_uses_profile_jsearch_and_bypasses_legacy_hse_decision():
    system = _system()
    system.repo.fetch_jobs = MagicMock(side_effect=AssertionError("legacy fetch should not run"))
    system.repo.score_jobs_with_existing_engine = MagicMock(
        side_effect=AssertionError("legacy scoring should not run")
    )
    system.repo.make_agent_decisions = MagicMock(
        side_effect=AssertionError("legacy HSE decision filter should not run")
    )

    with patch("src.job_sources.fetch_jsearch_jobs", return_value=[_job()]) as fetch_jsearch:
        result = system.run_for_profile(_profile(), limit=3)

    fetch_jsearch.assert_called_once()
    assert result["status"] == "completed"
    assert result["metrics"]["profile_driven_jsearch"] is True
    assert result["jobs_fetched"] == 1
    assert result["jobs_scored"] == 1
    assert result["matches_sent"] == 1

    match = result["matches"][0]
    assert match["title"] == "Senior Python Developer"
    assert match["score"] == 82
    assert match["score_source"] == "profile_fit"
    assert match["source_quality"] == "live_verified"
    assert match["rico_explanation"].startswith("Target role")
    assert match["link"] == "https://jobs.lever.co/example/python-1"
    assert match["apply_link"] == "https://jobs.lever.co/example/python-1"


def test_run_for_profile_falls_back_to_repo_pipeline_when_profile_jsearch_empty():
    system = _system()
    legacy_job = _job(title="HSE Manager", score=60, score_source=None)
    system.repo.fetch_jobs = MagicMock(return_value=[legacy_job])
    system.repo.score_jobs_with_existing_engine = MagicMock(return_value=[(legacy_job, 60)])
    system.repo.make_agent_decisions = MagicMock(
        return_value=[
            SimpleNamespace(
                decision="watch",
                job=legacy_job,
                final_score=62,
            )
        ]
    )

    with patch("src.job_sources.fetch_jsearch_jobs", return_value=[]):
        result = system.run_for_profile(_profile(), limit=3)

    system.repo.fetch_jobs.assert_called_once()
    system.repo.score_jobs_with_existing_engine.assert_called_once()
    system.repo.make_agent_decisions.assert_called_once()
    assert result["status"] == "completed"
    assert result["metrics"]["profile_driven_jsearch"] is False
    assert result["matches"][0]["score"] == 60
