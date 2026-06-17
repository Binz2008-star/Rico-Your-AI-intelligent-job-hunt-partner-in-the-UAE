import os
import re
from src.profile import (
    get_candidate_profile, get_skill_weights, get_hard_reject_keywords,
    get_seniority_keywords, calculate_experience_match, get_location_preferences,
    get_salary_preferences, get_target_roles, get_profile_match_explanation
)
from src.repositories.profile_repo import get_profile as get_user_profile

_GENERIC_ROLE_TOKENS = {
    "senior", "junior", "mid", "lead", "head", "manager", "director",
    "officer", "specialist", "engineer", "developer", "analyst",
    "consultant", "coordinator", "supervisor", "assistant", "principal",
    "staff", "associate",
}


def _role_conflicting_excludes(exclude_keywords, target_roles, title):
    """Excluded keywords to *suppress* for this job because they overlap a target role.

    Contextual filtering for the excluded-keyword vs target-role conflict: if a user
    excludes "manager" but targets "Environmental Manager", a job titled
    "Environmental Manager" must not be silently hard-rejected by the "manager"
    exclusion. Suppression only applies when the job title actually matches the
    overlapping target role — the exclusion is still honored for unrelated jobs and
    for text outside the role, preserving the user's filtering intent.
    """
    if not exclude_keywords or not target_roles:
        return set()
    title_l = (title or "").lower()
    suppressed = set()
    for raw_role in target_roles:
        role = str(raw_role or "").strip().lower()
        if not role or role not in title_l:
            continue
        role_tokens = {t for t in re.split(r"[^a-z0-9+#]+", role) if t}
        for kw in exclude_keywords:
            k = str(kw or "").strip().lower()
            if not k:
                continue
            # single-word exclude that is a token of the role, or a multi-word
            # exclude phrase contained in the role
            if k in role_tokens or (" " in k and k in role):
                suppressed.add(k)
    return suppressed


def score_job(job):
    """
    Roben Edwan's CV-aware job scoring system.
    Optimized for HSE / QHSE / EHS / ESG / Compliance roles in UAE.

    Pipeline: type-guard → ENV excludes → hard reject → title gate → scoring → floor 0
    """
    # Guard: reject non-dict input gracefully instead of raising AttributeError
    if not isinstance(job, dict):
        return 0

    score = 0
    score_details = []

    # Extract job text for analysis
    title = str(job.get("title", "") or "").lower()
    description = str(job.get("description", "") or "").lower()
    job_text = f"{title} {description}"

    # STEP 0: ENV excludes - immediate disqualification
    exclude_keywords_str = os.getenv("EXCLUDE_KEYWORDS", "")
    exclude_keywords = [kw.strip().lower() for kw in exclude_keywords_str.split(",") if kw.strip()]
    if exclude_keywords:
        # Contextual filtering: don't let an excluded keyword that overlaps the user's
        # own target role silently block a job that matches that role (e.g. excluding
        # "manager" must not drop "Environmental Manager").
        try:
            _target_roles = get_target_roles()
        except Exception:
            _target_roles = []
        suppressed = _role_conflicting_excludes(exclude_keywords, _target_roles, title)
        effective_excludes = [kw for kw in exclude_keywords if kw not in suppressed]
        exclude_matches = [kw for kw in effective_excludes if kw in job_text]
        if exclude_matches:
            job["score"] = 0
            job["score_details"] = [f"Hard reject (ENV): {exclude_matches}"]
            job["hard_reject_reason"] = f"ENV exclude: {exclude_matches}"
            return 0
        if suppressed:
            score_details.append(
                f"Kept despite exclude {sorted(suppressed)}: matches your target role"
            )

    # STEP 1: Hard reject keywords - immediate disqualification
    # These keywords only reject when found in the job title, not the description
    TITLE_ONLY_REJECT_KEYWORDS = {"civil engineer", "site engineer", "quantity surveyor", "architect"}
    hard_reject_keywords = get_hard_reject_keywords()
    hard_reject_matches = []
    for kw in hard_reject_keywords:
        text = title if kw in TITLE_ONLY_REJECT_KEYWORDS else job_text
        if f" {kw} " in f" {text} ":
            hard_reject_matches.append(kw)
    if hard_reject_matches:
        job["score"] = 0
        job["score_details"] = [f"Hard reject: {hard_reject_matches[:3]}"]
        job["hard_reject_reason"] = f"Hard reject: {hard_reject_matches[:3]}"
        return 0

    # STEP 2: Title gate - Primary HSE vs Secondary governance signals
    PRIMARY_HSE_SIGNALS = [
        "hse", "qhse", "ehs", "hsse", "safety", "environmental", "environment",
        "esg", "sustainability"
    ]

    SECONDARY_SIGNALS = [
        "compliance", "risk", "audit", "quality", "qms", "iso"
    ]

    primary_hit = any(k in title for k in PRIMARY_HSE_SIGNALS)
    secondary_hit = any(k in title for k in SECONDARY_SIGNALS)

    profile = get_candidate_profile()
    skill_weights = get_skill_weights()
    seniority_keywords = get_seniority_keywords()
    location_preferences = get_location_preferences()
    salary_preferences = get_salary_preferences()
    target_roles = [role.lower() for role in get_target_roles()]

    # STEP 3: Target role matching (highest priority)
    for role in target_roles:
        if role in title:
            role_bonus = 25
            score += role_bonus
            score_details.append(f"Target role: {role} (+{role_bonus})")
            break

    # STEP 4: Skill-based scoring with Roben's weights
    matched_skills = []
    for skill_category, skill_data in profile["skills"].items():
        keywords = skill_data["keywords"]
        weight = skill_data["weight"]

        # Skip operations_management if no primary HSE signal
        if skill_category == "leadership" and not primary_hit:
            continue

        # Check for keyword matches (use set to avoid keyword explosion)
        skill_matches = list(set(kw for kw in keywords if kw in job_text))
        if skill_matches:
            # Base score for skill match
            skill_score = len(skill_matches) * weight

            # Bonus for multiple keywords in same category
            if len(skill_matches) > 1:
                skill_score += (len(skill_matches) - 1) * (weight // 2)

            # Cap to prevent score explosion
            skill_score = min(skill_score, weight * 4)

            # Experience bonus
            exp_bonus = calculate_experience_match(skill_category, job_text)
            skill_score += exp_bonus

            score += skill_score
            matched_skills.append(f"{skill_category}: {skill_matches} (+{skill_score})")

    if matched_skills:
        score_details.extend(matched_skills)

    # STEP 5: Seniority bonus
    seniority_matches = [kw for kw in seniority_keywords if kw in title]
    if seniority_matches:
        seniority_bonus = len(seniority_matches) * 8
        score += seniority_bonus
        score_details.append(f"Seniority: {seniority_matches} (+{seniority_bonus})")

    # STEP 6: Location-based scoring (UAE preference)
    location = str(job.get("location", "")).lower()
    location_bonus = 0
    for loc, bonus in location_preferences.items():
        if loc in location or loc in job_text:
            location_bonus = bonus
            score_details.append(f"Location: {loc} (+{bonus})")
            break

    if location_bonus:
        score += location_bonus

    # STEP 7: Salary preference bonus
    salary_keywords = salary_preferences["preferred_keywords"]
    salary_matches = [kw for kw in salary_keywords if kw in job_text]
    if salary_matches:
        salary_bonus = 10
        score += salary_bonus
        score_details.append(f"Salary preference: {salary_matches} (+{salary_bonus})")

    # STEP 8: Apply multiplier based on title signal type
    if primary_hit:
        # Full score for primary HSE signals
        pass
    elif secondary_hit:
        # Heavy penalty for secondary-only signals (compliance/risk/audit without HSE)
        score = int(score * 0.25)
        score_details.append(f"Secondary signal only (0.25× multiplier)")
    else:
        # No relevant signals
        score = int(score * 0.1)
        score_details.append(f"No relevant signals (0.1× multiplier)")

    # STEP 9: Floor at 0
    if score < 0:
        score = 0

    # Store scoring details and profile explanation
    job["score_details"] = score_details
    job["profile_explanation"] = get_profile_match_explanation(job, score_details)

    return score


def get_score_explanation(job):
    """Return human-readable explanation of job score."""
    if "score_details" in job:
        return " | ".join(job["score_details"])
    return "No scoring details available"


def get_profile_explanation(job):
    """Return profile-specific explanation for why job matches Roben."""
    return job.get("profile_explanation", "Relevant HSE/Compliance experience")


def _convert_user_profile_to_scoring_format(user_profile):
    """Convert RicoProfile from database to the format expected by scoring system."""
    if not user_profile:
        # Return minimal neutral profile for missing user - no HSE defaults
        return {
            "name": "Unknown User",
            "experience_years": 0,
            "location": "Unknown",
            "target_roles": [],
            "skills": {
                "general": {
                    "keywords": [],
                    "weight": 1,
                    "experience_years": 0
                }
            },
            "hard_reject_keywords": [],
            "seniority_keywords": ["senior", "lead", "head", "manager", "director"],
            "location_preferences": {},
            "preferred_cities": [],
            "salary_range": {"preferred_keywords": []},
        }

    user_skills = _clean_profile_strings(getattr(user_profile, "skills", []))
    user_target_roles = _clean_profile_strings(getattr(user_profile, "target_roles", []))
    current_role = str(getattr(user_profile, "current_role", "") or "").strip()
    if current_role and current_role not in user_target_roles:
        user_target_roles.insert(0, current_role)

    preferred_cities = _clean_profile_strings(getattr(user_profile, "preferred_cities", []))

    years_experience = getattr(user_profile, "years_experience", 0)
    if years_experience is None:
        years_experience = 0

    # Create skills structure from user's skills list
    skills_dict = {
        "user_skills": {
            "keywords": user_skills,
            "weight": 10,  # Base weight for user's own skills
            "experience_years": years_experience
        }
    }

    # Create location preferences from user's preferred cities
    location_preferences = {}
    for i, city in enumerate(preferred_cities[:5]):  # Limit to top 5
        location_preferences[city.lower()] = max(20 - i * 5, 5)  # Decreasing bonus

    return {
        "name": getattr(user_profile, 'name', 'User'),
        "experience_years": years_experience,
        "location": preferred_cities[0] if preferred_cities else 'Unknown',
        "target_roles": user_target_roles,
        "skills": skills_dict,
        "hard_reject_keywords": [],  # No hard rejects for user-specific scoring
        "seniority_keywords": ["senior", "lead", "head", "manager", "director"],
        "location_preferences": location_preferences,
        "preferred_cities": preferred_cities,
        "salary_range": {"preferred_keywords": []},
    }


def score_job_for_user(job, user_id):
    """Score a job using a specific user's profile."""
    # Get user profile from database
    user_profile = get_user_profile(user_id)

    # Convert to scoring format
    candidate_profile = _convert_user_profile_to_scoring_format(user_profile)

    # Use the existing scoring logic with user's profile
    return _score_job_with_profile(job, candidate_profile)


def _score_job_with_profile(job, candidate_profile):
    """Internal scoring function that accepts a candidate profile parameter."""
    # Guard: reject non-dict input gracefully
    if not isinstance(job, dict):
        return 0

    score = 0
    score_details = []

    # Extract job text for analysis
    title = str(job.get("title", "") or "").lower()
    description = str(job.get("description", "") or "").lower()
    job_text = f"{title} {description}"

    # STEP 0: ENV excludes - immediate disqualification
    exclude_keywords_str = os.getenv("EXCLUDE_KEYWORDS", "")
    exclude_keywords = [kw.strip().lower() for kw in exclude_keywords_str.split(",") if kw.strip()]
    if exclude_keywords:
        # Contextual filtering: don't let an excluded keyword that overlaps this user's
        # own target role silently block a job that matches that role (e.g. excluding
        # "manager" must not drop "Environmental Manager").
        _target_roles = candidate_profile.get("target_roles") or []
        suppressed = _role_conflicting_excludes(exclude_keywords, _target_roles, title)
        effective_excludes = [kw for kw in exclude_keywords if kw not in suppressed]
        exclude_matches = [kw for kw in effective_excludes if kw in job_text]
        if exclude_matches:
            job["score"] = 0
            job["score_details"] = [f"Hard reject (ENV): {exclude_matches}"]
            job["hard_reject_reason"] = f"ENV exclude: {exclude_matches}"
            return 0
        if suppressed:
            score_details.append(
                f"Kept despite exclude {sorted(suppressed)}: matches your target role"
            )

    # STEP 1: Hard reject keywords - immediate disqualification
    TITLE_ONLY_REJECT_KEYWORDS = {"civil engineer", "site engineer", "quantity surveyor", "architect"}
    hard_reject_keywords = candidate_profile["hard_reject_keywords"]
    hard_reject_matches = []
    for kw in hard_reject_keywords:
        text = title if kw in TITLE_ONLY_REJECT_KEYWORDS else job_text
        if f" {kw} " in f" {text} ":
            hard_reject_matches.append(kw)
    if hard_reject_matches:
        job["score"] = 0
        job["score_details"] = [f"Hard reject: {hard_reject_matches[:3]}"]
        job["hard_reject_reason"] = f"Hard reject: {hard_reject_matches[:3]}"
        return 0

    # STEP 2: Dynamic signal gate based on this user's actual roles and skills
    user_signal_keywords = _build_profile_signal_keywords(candidate_profile)
    primary_hit = any(signal in job_text for signal in user_signal_keywords)

    skill_weights = {skill: data["weight"] for skill, data in candidate_profile["skills"].items()}
    seniority_keywords = candidate_profile["seniority_keywords"]
    location_preferences = candidate_profile["location_preferences"]
    salary_preferences = candidate_profile["salary_range"]
    target_roles = [role.lower() for role in candidate_profile["target_roles"]]

    # STEP 3: Target role matching (highest priority)
    for role in target_roles:
        if role in title:
            role_bonus = 25
            score += role_bonus
            score_details.append(f"Target role: {role} (+{role_bonus})")
            break

    # STEP 4: Skill-based scoring with user's weights
    matched_skills = []
    for skill_category, skill_data in candidate_profile["skills"].items():
        keywords = skill_data["keywords"]
        weight = skill_data["weight"]

        # Skip operations_management if no primary HSE signal
        if skill_category == "leadership" and not primary_hit:
            continue

        # Check for keyword matches
        skill_matches = list(set(kw for kw in keywords if kw in job_text))
        if skill_matches:
            # Base score for skill match
            skill_score = len(skill_matches) * weight

            # Bonus for multiple keywords in same category
            if len(skill_matches) > 1:
                skill_score += (len(skill_matches) - 1) * (weight // 2)

            # Cap to prevent score explosion
            skill_score = min(skill_score, weight * 4)

            # Experience bonus
            exp_bonus = _calculate_experience_match_for_profile(skill_category, job_text, candidate_profile)
            skill_score += exp_bonus

            score += skill_score
            matched_skills.append(f"{skill_category}: {skill_matches} (+{skill_score})")

    if matched_skills:
        score_details.extend(matched_skills)

    # STEP 5: Seniority bonus
    seniority_matches = [kw for kw in seniority_keywords if kw in title]
    if seniority_matches:
        seniority_bonus = len(seniority_matches) * 8
        score += seniority_bonus
        score_details.append(f"Seniority: {seniority_matches} (+{seniority_bonus})")

    # STEP 6: Location-based scoring
    location = str(job.get("location", "")).lower()
    location_bonus = 0
    for loc, bonus in location_preferences.items():
        if loc in location or loc in job_text:
            location_bonus = bonus
            score_details.append(f"Location: {loc} (+{bonus})")
            break

    if location_bonus:
        score += location_bonus

    # STEP 7: Salary preference bonus
    salary_keywords = salary_preferences["preferred_keywords"]
    salary_matches = [kw for kw in salary_keywords if kw in job_text]
    if salary_matches:
        salary_bonus = 10
        score += salary_bonus
        score_details.append(f"Salary preference: {salary_matches} (+{salary_bonus})")

    # STEP 8: Apply neutral multiplier without domain defaults
    if primary_hit:
        # Full score for user-relevant signals
        pass
    else:
        # Small penalty for no relevant signals, but not harsh
        score = int(score * 0.5)
        score_details.append(f"No user-relevant signals (0.5× multiplier)")

    # STEP 9: Floor at 0
    if score < 0:
        score = 0

    # Store scoring details and score on job object
    job["score"] = score
    job["score_details"] = score_details
    job["profile_explanation"] = _get_profile_match_explanation_for_user(job, score_details, candidate_profile)

    return score


def _calculate_experience_match_for_profile(skill_category, job_text, candidate_profile):
    """Calculate experience bonus for matching skill category using user's profile."""
    if skill_category not in candidate_profile["skills"]:
        return 0

    skill_data = candidate_profile["skills"][skill_category]
    required_years = skill_data.get("experience_years", 3)
    candidate_years = candidate_profile.get("experience_years", 5)

    # Bonus if candidate has sufficient experience
    if candidate_years >= required_years:
        return min(5, candidate_years - required_years)
    return 0


def _get_profile_match_explanation_for_user(job, score_details, candidate_profile):
    """Generate profile-specific explanation for why job matches user's profile."""
    title = str(job.get('title', '')).lower()
    description = str(job.get('description', '')).lower()
    job_text = f"{title} {description}"

    explanations = []

    # Check for target role matches
    for role in candidate_profile["target_roles"]:
        if role.lower() in job_text:
            explanations.append(f"Direct match for target role: {role}")
            break

    # Check for skill matches based on user's actual skills
    matched_skills = []
    for skill_data in candidate_profile["skills"].values():
        for keyword in skill_data.get("keywords", []):
            keyword_text = str(keyword).strip()
            if keyword_text and keyword_text.lower() in job_text:
                matched_skills.append(keyword_text)
    if matched_skills:
        unique_skills = []
        seen = set()
        for skill in matched_skills:
            skill_key = skill.lower()
            if skill_key in seen:
                continue
            seen.add(skill_key)
            unique_skills.append(skill)
        explanations.append(f"Skills match: {', '.join(unique_skills[:2])}")

    # Location preference
    preferred_cities = candidate_profile.get("preferred_cities", [])
    for loc in preferred_cities:
        if loc.lower() in job_text:
            explanations.append(f"Preferred location: {loc}")
            break

    if not explanations:
        if score_details:
            explanations.append(score_details[0].split(" (+", 1)[0])
        else:
            explanations.append("General profile alignment")

    return " | ".join(explanations[:3])


def score_jobs_for_user(jobs, user_id):
    """Score a list of jobs using a specific user's profile."""
    for job in jobs:
        score_job_for_user(job, user_id)
    return jobs


def _clean_profile_strings(values):
    """Normalize profile lists into unique, non-empty strings."""
    cleaned = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _build_profile_signal_keywords(candidate_profile):
    """Build a user-specific keyword set without falling back to Roben/HSE defaults."""
    signal_keywords = set()

    for role in candidate_profile.get("target_roles", []):
        role_text = str(role or "").strip().lower()
        if not role_text:
            continue
        signal_keywords.add(role_text)
        for token in re.split(r"[^a-z0-9+#]+", role_text):
            if len(token) >= 3 and token not in _GENERIC_ROLE_TOKENS:
                signal_keywords.add(token)

    for skill_data in candidate_profile.get("skills", {}).values():
        for keyword in skill_data.get("keywords", []):
            keyword_text = str(keyword or "").strip().lower()
            if not keyword_text:
                continue
            signal_keywords.add(keyword_text)
            for token in re.split(r"[^a-z0-9+#]+", keyword_text):
                if len(token) >= 3 and token not in _GENERIC_ROLE_TOKENS:
                    signal_keywords.add(token)

    return signal_keywords
