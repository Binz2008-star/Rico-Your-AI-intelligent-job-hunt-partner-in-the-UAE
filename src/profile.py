"""
Roben Edwan's Candidate Profile System
Optimized for executive operations and founder office roles in UAE.
"""

CANDIDATE_PROFILE = {
    "name": "Roben Edwan - Executive Operations Professional",
    "experience_years": 8,
    "location": "UAE",
    "target_roles": [
        "Executive Assistant to CEO",
        "Founder Office Manager",
        "Chief of Staff",
        "Executive Operations Manager",
        "Operations Manager",
        "Compliance Operations Manager",
        "VIP Relationship Manager",
        "Private Office Executive Assistant"
    ],
    "skills": {
        "executive_support": {
            "keywords": ["executive assistant to ceo", "ceo support", "executive support", "founder office", "private office", "chief of staff"],
            "weight": 15,
            "experience_years": 5
        },
        "executive_operations": {
            "keywords": ["executive operations", "operations management", "founder-led operations", "business operations", "operational excellence"],
            "weight": 12,
            "experience_years": 6
        },
        "compliance_governance": {
            "keywords": ["compliance", "governance", "audit", "risk management", "municipality approvals", "regulatory"],
            "weight": 10,
            "experience_years": 3
        },
        "stakeholder_coordination": {
            "keywords": ["stakeholder coordination", "vip clients", "relationship management", "board support", "investor relations"],
            "weight": 11,
            "experience_years": 4
        },
        "uae_experience": {
            "keywords": ["uae", "dubai", "abu dhabi", "middle east", "gcc", "local market"],
            "weight": 13,
            "experience_years": 4
        },
        "financial_operations": {
            "keywords": ["p&l", "financial operations", "budget management", "financial reporting", "cost control"],
            "weight": 8,
            "experience_years": 3
        }
    },
    "negative_keywords": [
        "junior", "entry level", "intern", "trainee", "fresh graduate",
        "software engineer", "developer", "programmer", "it support", "technical support",
        "sales executive", "call center", "telesales", "business development",
        "receptionist", "front desk", "admin assistant", "office assistant",
        "driver", "warehouse", "technician", "maintenance", "cleaner",
        "teacher", "nurse", "doctor", "healthcare", "medical"
    ],
    "seniority_keywords": [
        "senior", "lead", "head", "manager", "director", "vp", "vice president",
        "executive", "chief", "c-level", "strategic", "leadership"
    ],
    "location_preferences": {
        "dubai": 25,
        "abu dhabi": 20,
        "sharjah": 15,
        "ajman": 15,
        "uae remote": 10,
        "uae hybrid": 10
    },
    "salary_range": {
        "min": 25000,
        "max": 30000,
        "currency": "AED",
        "preferred_keywords": ["25k", "30k", "25000", "30000"]
    },
    "preferred_companies": [],
    "blacklisted_companies": []
}


def get_candidate_profile():
    """Return Roben Edwan's candidate profile."""
    return CANDIDATE_PROFILE


def get_target_roles():
    """Return Roben's target roles list."""
    return get_candidate_profile()["target_roles"]


def get_skill_weights():
    """Return skill categories with their weights."""
    profile = get_candidate_profile()
    return {skill: data["weight"] for skill, data in profile["skills"].items()}


def get_negative_keywords():
    """Return keywords that should result in heavy penalties."""
    return get_candidate_profile()["negative_keywords"]


def get_seniority_keywords():
    """Return keywords indicating senior-level positions."""
    return get_candidate_profile()["seniority_keywords"]


def get_location_preferences():
    """Return location-based scoring preferences."""
    return get_candidate_profile()["location_preferences"]


def get_salary_preferences():
    """Return salary-based scoring preferences."""
    return get_candidate_profile()["salary_range"]


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


def get_profile_match_explanation(job, score_details):
    """Generate profile-specific explanation for why job matches Roben's profile."""
    title = str(job.get('title', '')).lower()
    description = str(job.get('description', '')).lower()

    explanations = []

    # Check for target role matches
    for role in get_target_roles():
        if role.lower() in title:
            explanations.append(f"Direct match for target role: {role}")
            break

    # Check for key skill matches
    if "executive" in title and "assistant" in title:
        explanations.append("Strong executive support alignment")

    if "ceo" in title or "chief of staff" in title:
        explanations.append("Senior executive leadership role")

    if "operations" in title and "manager" in title:
        explanations.append("Operations management expertise match")

    if "compliance" in title:
        explanations.append("Compliance and governance experience")

    if "uae" in description or "dubai" in description:
        explanations.append("UAE market experience required")

    if not explanations:
        explanations.append("Relevant executive operations experience")

    return " | ".join(explanations[:3])  # Limit to top 3 reasons
