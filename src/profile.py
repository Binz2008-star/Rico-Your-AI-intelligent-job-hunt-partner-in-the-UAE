"""
Candidate Profile System
Stores professional background, skills, and preferences for intelligent job matching.
"""

CANDIDATE_PROFILE = {
    "name": "Executive Operations Professional",
    "experience_years": 8,
    "location": "UAE",
    "skills": {
        "executive_support": {
            "keywords": ["executive assistant", "chief of staff", "executive operations", "ceo support", "board support"],
            "weight": 10,
            "experience_years": 5
        },
        "operations": {
            "keywords": ["operations manager", "business operations", "process improvement", "operational excellence"],
            "weight": 8,
            "experience_years": 6
        },
        "compliance": {
            "keywords": ["compliance", "regulatory", "risk management", "audit", "governance"],
            "weight": 7,
            "experience_years": 3
        },
        "project_management": {
            "keywords": ["project manager", "program manager", "pmp", "agile", "scrum"],
            "weight": 6,
            "experience_years": 4
        },
        "uae_experience": {
            "keywords": ["uae", "dubai", "abu dhabi", "middle east", "gcc"],
            "weight": 9,
            "experience_years": 4
        }
    },
    "negative_keywords": [
        "intern", "junior", "entry level", "trainee", "fresh graduate",
        "software engineer", "developer", "programmer", "it support",
        "sales", "marketing", "recruitment", "hr", "teacher", "nurse"
    ],
    "seniority_keywords": [
        "senior", "lead", "head", "manager", "director", "vp", "vice president",
        "executive", "chief", "c-level", "strategic", "leadership"
    ],
    "preferred_companies": [],
    "blacklisted_companies": [],
    "salary_range": {
        "min": 15000,
        "max": 50000,
        "currency": "AED"
    }
}


def get_candidate_profile():
    """Return the candidate profile."""
    return CANDIDATE_PROFILE


def get_skill_weights():
    """Return skill categories with their weights."""
    profile = get_candidate_profile()
    return {skill: data["weight"] for skill, data in profile["skills"].items()}


def get_negative_keywords():
    """Return keywords that should result in penalties."""
    return get_candidate_profile()["negative_keywords"]


def get_seniority_keywords():
    """Return keywords indicating senior-level positions."""
    return get_candidate_profile()["seniority_keywords"]


def calculate_experience_match(skill_category, job_text):
    """Calculate experience bonus for matching skill category."""
    profile = get_candidate_profile()
    if skill_category not in profile["skills"]:
        return 0
    
    skill_data = profile["skills"][skill_category]
    required_years = skill_data["experience_years"]
    candidate_years = profile["experience_years"]
    
    # Bonus if candidate has sufficient experience
    if candidate_years >= required_years:
        return min(5, candidate_years - required_years)
    return 0
