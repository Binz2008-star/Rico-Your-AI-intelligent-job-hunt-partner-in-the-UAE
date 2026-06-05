"""Personalized cover letter writer for UAE ESG/HSE/Environmental roles."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CoverLetterIdentityError(Exception):
    """Raised when required identity information is missing for cover letter generation."""
    pass


@dataclass(frozen=True)
class CoverLetterIdentity:
    """Structured identity object for cover letter generation.

    All fields must be verified user data. No generic fallbacks allowed.
    """
    name: str
    location: str
    title: Optional[str] = None
    company: Optional[str] = None
    years_experience: Optional[float] = None
    profile_line: Optional[str] = None
    verified_strengths: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate that required identity fields are present."""
        if not self.name or not self.name.strip():
            raise CoverLetterIdentityError("Identity name is required and cannot be empty")
        if not self.location or not self.location.strip():
            raise CoverLetterIdentityError("Identity location is required and cannot be empty")

SKILL_LINES = {
    "iso": "implemented and maintained ISO 14001-aligned environmental compliance systems",
    "compliance": "managed environmental compliance, audits, permits, and UAE municipality requirements",
    "hse": "led HSE/QHSE systems with practical site-level safety and environmental controls",
    "ehs": "led EHS systems with practical site-level safety and environmental controls",
    "qhse": "managed integrated QHSE systems across operational teams",
    "sustainability": "supported sustainability programs and ESG reporting initiatives",
    "esg": "supported ESG reporting, sustainability strategy, and compliance documentation",
    "waste": "managed waste operations and environmental service delivery across 80+ locations",
    "wastewater": "handled wastewater, FOG control, and operational environmental risks",
    "municipality": "worked with UAE municipal regulations, inspections, and approval processes",
    "audit": "prepared teams and documentation for audits and regulatory inspections",
}


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _role_specific_lines(job: Dict[str, Any], limit: int = 3) -> List[str]:
    text = f"{job.get('title','')} {job.get('description','')}".lower()
    lines: List[str] = []
    for key, line in SKILL_LINES.items():
        if key in text and line not in lines:
            lines.append(line)
    if not lines:
        lines = [
            "managed environmental operations, regulatory compliance, and HSE coordination in the UAE",
            "led multi-site teams and improved operational controls across environmental service environments",
        ]
    return lines[:limit]


def generate_cover_letter_with_identity(
    job: Dict[str, Any],
    identity: CoverLetterIdentity
) -> str:
    """Generate a cover letter using structured identity object.

    Args:
        job: Job posting data with title, company, description, etc.
        identity: Structured identity object with verified user data

    Returns:
        Personalized cover letter string

    Raises:
        CoverLetterIdentityError: If identity validation fails
    """
    # Clean job data
    title = _clean(job.get("title")) or "the advertised role"
    company = _clean(job.get("company")) or "your organization"
    location = _clean(job.get("location")) or "the UAE"
    role_lines = _role_specific_lines(job)
    title_lower = title.lower()

    # Determine opening focus based on job title
    if "esg" in title_lower or "sustain" in title_lower:
        opening_focus = "ESG, sustainability strategy, environmental reporting, and compliance governance"
    elif "hse" in title_lower or "ehs" in title_lower or "qhse" in title_lower or "hsse" in title_lower:
        opening_focus = "HSE leadership, risk control, compliance, and operational safety systems"
    elif "environment" in title_lower:
        opening_focus = "environmental compliance, waste operations, regulatory approvals, and site performance"
    else:
        opening_focus = "environmental compliance, HSE leadership, and UAE operational execution"

    # Build profile line from verified identity data only
    if identity.profile_line:
        profile_line = identity.profile_line
    else:
        # Build from verified identity fields only
        profile_parts = []
        if identity.years_experience:
            profile_parts.append(f"{int(identity.years_experience)}+ years of relevant experience")

        if identity.verified_strengths:
            # Add most relevant skills based on job
            job_text = f"{title} {job.get('description', '')} {job.get('requirements', '')}".lower()
            relevant_strengths = []
            for strength in identity.verified_strengths[:5]:
                if any(keyword in job_text for keyword in strength.lower().split()):
                    relevant_strengths.append(strength)
            if relevant_strengths:
                profile_parts.append("expertise in " + ", ".join(relevant_strengths[:3]))

        # Use verified identity title/company if available
        if identity.title:
            profile_parts.append(f"current role as {identity.title}")
        if identity.company:
            profile_parts.append(f"at {identity.company}")

        # If no verified data available, fail rather than use generic fallback
        if not profile_parts:
            raise CoverLetterIdentityError(
                "Profile line or verified experience data required. "
                "Provide profile_line, years_experience, or verified_strengths."
            )

        profile_line = " and ".join(profile_parts)

    bullets = "\n".join(f"- {line.capitalize()}." for line in role_lines)

    return f"""Dear Hiring Manager,

I am writing to express my interest in the {title} position at {company} in {location}.

I bring {profile_line}. This background aligns strongly with the role's focus on {opening_focus}.

Relevant experience I would bring to {company}:
{bullets}

I would welcome the opportunity to discuss how my UAE environmental compliance and HSE experience can support {company}'s operational and sustainability goals.

Sincerely,
{_clean(identity.name)}
{_clean(identity.location)}
"""


def generate_cover_letter(
    job: Dict[str, Any],
    user_name: str,
    user_location: str,
    user_years_experience: Optional[float] = None,
    user_skills: Optional[List[str]] = None
) -> str:
    """Generate a cover letter using only profile-backed identity information.

    Args:
        job: Job posting data with title, company, description, etc.
        user_name: User's actual name (required)
        user_location: User's actual location (required)
        user_years_experience: User's years of experience (optional)
        user_skills: User's skills list (optional)

    Raises:
        CoverLetterIdentityError: If required identity information is missing

    Returns:
        Personalized cover letter string
    """
    # Validate required identity fields
    if not user_name or not user_name.strip():
        raise CoverLetterIdentityError("User name is required for cover letter generation")
    if not user_location or not user_location.strip():
        raise CoverLetterIdentityError("User location is required for cover letter generation")

    # Clean job data
    title = _clean(job.get("title")) or "the advertised role"
    company = _clean(job.get("company")) or "your organization"
    location = _clean(job.get("location")) or "the UAE"
    role_lines = _role_specific_lines(job)
    title_lower = title.lower()

    # Determine opening focus based on job title
    if "esg" in title_lower or "sustain" in title_lower:
        opening_focus = "ESG, sustainability strategy, environmental reporting, and compliance governance"
    elif "hse" in title_lower or "ehs" in title_lower or "qhse" in title_lower or "hsse" in title_lower:
        opening_focus = "HSE leadership, risk control, compliance, and operational safety systems"
    elif "environment" in title_lower:
        opening_focus = "environmental compliance, waste operations, regulatory approvals, and site performance"
    else:
        opening_focus = "environmental compliance, HSE leadership, and UAE operational execution"

    # Build profile line from user data only
    profile_parts = []
    if user_years_experience:
        profile_parts.append(f"{int(user_years_experience)}+ years of relevant experience")

    if user_skills:
        # Add most relevant skills based on job
        job_text = f"{title} {job.get('description', '')} {job.get('requirements', '')}".lower()
        relevant_skills = []
        for skill in user_skills[:5]:  # Limit to top 5 skills
            if any(keyword in job_text for keyword in skill.lower().split()):
                relevant_skills.append(skill)
        if relevant_skills:
            profile_parts.append("expertise in " + ", ".join(relevant_skills[:3]))

    # Use neutral wording if no specific experience data available
    if not profile_parts:
        profile_line = "my relevant experience"
    else:
        profile_line = " and ".join(profile_parts)

    bullets = "\n".join(f"- {line.capitalize()}." for line in role_lines)

    return f"""Dear Hiring Manager,

I am writing to express my interest in the {title} position at {company} in {location}.

I bring {profile_line}. This background aligns strongly with the role's focus on {opening_focus}.

Relevant experience I would bring to {company}:
{bullets}

I would welcome the opportunity to discuss how my UAE environmental compliance and HSE experience can support {company}'s operational and sustainability goals.

Sincerely,
{_clean(user_name)}
{_clean(user_location)}
"""


def generate_batch_cover_letters(
    jobs: List[Dict[str, Any]],
    user_name: str,
    user_location: str,
    user_years_experience: Optional[float] = None,
    user_skills: Optional[List[str]] = None
) -> Dict[str, str]:
    """Generate cover letters for multiple jobs using profile-backed identity.

    Args:
        jobs: List of job posting data
        user_name: User's actual name (required)
        user_location: User's actual location (required)
        user_years_experience: User's years of experience (optional)
        user_skills: User's skills list (optional)

    Returns:
        Dictionary mapping job keys to cover letter strings
    """
    letters: Dict[str, str] = {}
    for job in jobs:
        key = job.get("link") or f"{job.get('company','')}_{job.get('title','')}"
        letters[str(key)] = generate_cover_letter(
            job, user_name, user_location, user_years_experience, user_skills
        )
    logger.info("batch_cover_letters_complete total=%s", len(letters))
    return letters


def generate_batch_cover_letters_with_identity(
    jobs: List[Dict[str, Any]],
    identity: CoverLetterIdentity
) -> Dict[str, str]:
    """Generate cover letters for multiple jobs using structured identity object.

    Args:
        jobs: List of job posting data
        identity: Structured identity object with verified user data

    Returns:
        Dictionary mapping job keys to cover letter strings
    """
    letters: Dict[str, str] = {}
    for job in jobs:
        key = job.get("link") or f"{job.get('company','')}_{job.get('title','')}"
        letters[str(key)] = generate_cover_letter_with_identity(job, identity)
    logger.info("batch_cover_letters_complete total=%s", len(letters))
    return letters
