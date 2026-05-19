from __future__ import annotations

from src.services.job_match_explanation import build_match_explanation


def test_strong_fit_with_matching_skills():
    job = {
        "score": 88,
        "title": "Senior Python Developer",
        "company": "Acme",
        "location": "Dubai",
        "salary": "AED 25k",
        "skills": ["Python", "SQL", "Docker"],
    }
    profile = {
        "skills": ["Python", "SQL", "AWS"],
        "target_roles": ["Python Developer"],
        "years_experience": 6,
    }

    explanation = build_match_explanation(job, profile)

    assert explanation["verdict"] == "strong_fit"
    assert explanation["confidence"] == "high"
    assert explanation["summary"].startswith("Strong fit for Senior Python Developer")
    assert any("Matches your skills" in item for item in explanation["why_this_fits"])
    assert explanation["worth_checking"]
    assert explanation["recommended_next_step"].startswith("Apply")


def test_worth_checking_with_partial_data():
    job = {
        "score": 60,
        "title": "Business Analyst",
        "skills": ["Excel", "Stakeholder Management"],
    }
    profile = {
        "skills": ["Excel", "SQL"],
        "target_roles": ["Business Analyst"],
        "years_experience": 4,
    }

    explanation = build_match_explanation(job, profile)

    assert explanation["verdict"] == "worth_checking"
    assert explanation["confidence"] == "medium"
    assert "Location is missing or unclear." in explanation["worth_checking"]
    assert "Salary is not listed." in explanation["worth_checking"]
    assert "Company information is missing." in explanation["worth_checking"]


def test_weak_fit():
    job = {
        "score": 25,
        "title": "Civil Engineer",
        "company": "BuildCo",
        "location": "Abu Dhabi",
        "skills": ["AutoCAD"],
    }
    profile = {
        "skills": ["Python", "SQL"],
        "target_roles": ["Backend Engineer"],
        "years_experience": 7,
    }

    explanation = build_match_explanation(job, profile)

    assert explanation["verdict"] == "weak_fit"
    assert explanation["confidence"] == "low"
    assert explanation["recommended_next_step"].startswith("Skip")


def test_missing_fields_does_not_crash():
    explanation = build_match_explanation({}, None)

    assert explanation["verdict"] == "weak_fit"
    assert explanation["why_this_fits"]
    assert explanation["worth_checking"]
    assert explanation["recommended_next_step"]


def test_deterministic_for_same_inputs():
    job = {
        "score": 80,
        "title": "Manager - Engineering",
        "company": "Tech Corp",
        "location": "Dubai, UAE",
        "salary_range": "AED 22-30k/mo",
        "skills": ["Python", "Management"],
    }
    profile = {
        "skills": ["Python", "Management"],
        "target_roles": ["Engineering Manager"],
        "years_experience": 9,
    }

    explanation1 = build_match_explanation(job, profile)
    explanation2 = build_match_explanation(job, profile)

    assert explanation1 == explanation2
