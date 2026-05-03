import re
from src.profile import get_candidate_profile, get_skill_weights, get_negative_keywords, get_seniority_keywords, calculate_experience_match


def score_job(job):
    """
    CV-aware job scoring system that matches candidate profile with job requirements.
    Uses weighted scoring based on skills, experience, and preferences.
    """
    score = 0
    score_details = []

    # Extract job text for analysis
    title = str(job.get("title", "")).lower()
    description = str(job.get("description", "")).lower()
    job_text = f"{title} {description}"

    profile = get_candidate_profile()
    skill_weights = get_skill_weights()
    negative_keywords = get_negative_keywords()
    seniority_keywords = get_seniority_keywords()

    # 1. Negative keyword penalties
    negative_matches = [kw for kw in negative_keywords if kw in job_text]
    if negative_matches:
        penalty = len(negative_matches) * 20
        score -= penalty
        score_details.append(f"Negative keywords: {negative_matches} (-{penalty})")

    # 2. Skill-based scoring with weights
    matched_skills = []
    for skill_category, skill_data in profile["skills"].items():
        keywords = skill_data["keywords"]
        weight = skill_data["weight"]

        # Check for keyword matches
        skill_matches = [kw for kw in keywords if kw in job_text]
        if skill_matches:
            # Base score for skill match
            skill_score = len(skill_matches) * weight

            # Bonus for multiple keywords in same category
            if len(skill_matches) > 1:
                skill_score += (len(skill_matches) - 1) * (weight // 2)

            # Experience bonus
            exp_bonus = calculate_experience_match(skill_category, job_text)
            skill_score += exp_bonus

            score += skill_score
            matched_skills.append(f"{skill_category}: {skill_matches} (+{skill_score})")

    if matched_skills:
        score_details.extend(matched_skills)

    # 3. Seniority bonus
    seniority_matches = [kw for kw in seniority_keywords if kw in title]
    if seniority_matches:
        seniority_bonus = len(seniority_matches) * 5
        score += seniority_bonus
        score_details.append(f"Seniority: {seniority_matches} (+{seniority_bonus})")

    # 4. UAE location bonus
    uae_keywords = ["uae", "dubai", "abu dhabi", "sharjah", "ajman", "rak", "fujairah", "umm al quwain"]
    location = str(job.get("location", "")).lower()
    if any(uae_kw in location or uae_kw in job_text for uae_kw in uae_keywords):
        uae_bonus = 10
        score += uae_bonus
        score_details.append(f"UAE location (+{uae_bonus})")

    # 5. Title-specific scoring
    if "executive" in title and ("assistant" in title or "support" in title):
        exec_bonus = 15
        score += exec_bonus
        score_details.append(f"Executive assistant role (+{exec_bonus})")

    if "chief of staff" in title:
        cos_bonus = 20
        score += cos_bonus
        score_details.append(f"Chief of Staff role (+{cos_bonus})")

    # 6. Minimum score threshold
    if score < 0:
        score = 0

    # Store scoring details for debugging
    job["score_details"] = score_details

    return score


def get_score_explanation(job):
    """Return human-readable explanation of job score."""
    if "score_details" in job:
        return " | ".join(job["score_details"])
    return "No scoring details available"
