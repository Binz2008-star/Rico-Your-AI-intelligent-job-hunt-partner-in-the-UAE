"""Focused regression tests for authenticated profile-based job scoring."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.scoring import score_job_for_user, score_jobs_for_user


def _profile(*, skills, target_roles, years_experience, preferred_cities, current_role=None):
    return SimpleNamespace(
        skills=skills,
        target_roles=target_roles,
        years_experience=years_experience,
        preferred_cities=preferred_cities,
        current_role=current_role,
        name="Test User",
    )


def _job(title: str, description: str, location: str) -> dict:
    return {
        "title": title,
        "company": "Example Corp",
        "location": location,
        "description": description,
    }


class TestProfileSpecificScoring:
    def test_hse_profile_scores_hse_higher_than_software(self):
        hse_job = _job(
            "Senior HSE Manager",
            "Lead HSE, safety, environmental compliance, and ISO 14001 programs.",
            "Dubai, UAE",
        )
        software_job = _job(
            "Software Developer",
            "Build Python APIs and React applications.",
            "Remote",
        )
        hse_profile = _profile(
            skills=["hse", "safety", "environmental compliance", "iso 14001"],
            target_roles=["HSE Manager", "Environmental Manager"],
            years_experience=8,
            preferred_cities=["Dubai", "Abu Dhabi"],
        )

        with patch("src.scoring.get_user_profile", return_value=hse_profile):
            hse_score = score_job_for_user(hse_job.copy(), "hse_user@test.com")
            software_score = score_job_for_user(software_job.copy(), "hse_user@test.com")

        assert hse_score > software_score
        assert hse_score > 30

    def test_software_profile_scores_software_higher_than_hse(self):
        hse_job = _job(
            "HSE Manager",
            "Environmental compliance, safety leadership, and NEBOSH reporting.",
            "Dubai, UAE",
        )
        software_job = _job(
            "Senior Python Developer",
            "Python, React, AWS, and backend API ownership.",
            "Remote",
        )
        software_profile = _profile(
            skills=["python", "react", "aws", "backend api"],
            target_roles=["Senior Python Developer", "Backend Engineer"],
            years_experience=6,
            preferred_cities=["Remote"],
        )

        with patch("src.scoring.get_user_profile", return_value=software_profile):
            hse_score = score_job_for_user(hse_job.copy(), "software_user@test.com")
            software_score = score_job_for_user(software_job.copy(), "software_user@test.com")

        assert software_score > hse_score
        assert software_score > 30

    def test_updating_same_user_profile_changes_ranking_order(self):
        jobs = [
            _job("HSE Manager", "Safety leadership and environmental compliance.", "Dubai, UAE"),
            _job("Senior Python Developer", "Python, FastAPI, React, AWS.", "Remote"),
            _job("Data Scientist", "Machine learning, SQL, experimentation.", "Remote"),
        ]
        hse_profile = _profile(
            skills=["hse", "safety", "environmental"],
            target_roles=["HSE Manager"],
            years_experience=7,
            preferred_cities=["Dubai"],
        )
        software_profile = _profile(
            skills=["python", "machine learning", "sql"],
            target_roles=["Data Scientist", "Senior Python Developer"],
            years_experience=5,
            preferred_cities=["Remote"],
        )

        with patch("src.scoring.get_user_profile", return_value=hse_profile):
            hse_ranked = sorted(
                score_jobs_for_user([job.copy() for job in jobs], "same_user@test.com"),
                key=lambda job: job["score"],
                reverse=True,
            )

        with patch("src.scoring.get_user_profile", return_value=software_profile):
            software_ranked = sorted(
                score_jobs_for_user([job.copy() for job in jobs], "same_user@test.com"),
                key=lambda job: job["score"],
                reverse=True,
            )

        assert hse_ranked[0]["title"] == "HSE Manager"
        assert software_ranked[0]["title"] in {"Data Scientist", "Senior Python Developer"}
        assert [job["title"] for job in hse_ranked] != [job["title"] for job in software_ranked]

    def test_missing_profile_stays_low_and_neutral_without_roben_defaults(self):
        jobs = [
            _job("Professional Manager", "Leadership and operations oversight.", "Dubai"),
            _job("Software Engineer", "Python and React product delivery.", "Remote"),
            _job("Compliance Analyst", "Audit support and governance controls.", "Abu Dhabi"),
        ]

        with patch("src.scoring.get_user_profile", return_value=None):
            scored_jobs = score_jobs_for_user([job.copy() for job in jobs], "missing@test.com")

        scores = [job["score"] for job in scored_jobs]
        assert all(score < 50 for score in scores)
        assert max(scores) - min(scores) < 20
        assert all("HSE Manager" not in job.get("profile_explanation", "") for job in scored_jobs)
        assert all("Relevant HSE/Compliance experience" not in job.get("profile_explanation", "") for job in scored_jobs)

    def test_score_explanations_use_actual_profile_roles_and_skills(self):
        software_profile = _profile(
            skills=["python", "react", "aws"],
            target_roles=["Senior Python Developer", "Full Stack Engineer"],
            years_experience=5,
            preferred_cities=["Remote"],
        )
        software_job = _job(
            "Senior Python Developer",
            "Own Python services, React UI integrations, and AWS deployment.",
            "Remote",
        )

        with patch("src.scoring.get_user_profile", return_value=software_profile):
            score_job_for_user(software_job, "software_user@test.com")

        explanation = software_job.get("profile_explanation", "").lower()
        assert "senior python developer" in explanation
        assert "python" in explanation or "react" in explanation or "aws" in explanation
        assert "hse" not in explanation
        assert "safety" not in explanation
