"""
Rico Hunt — Resume Screener
============================
Isolated module: evaluates candidate resumes against a job description
and produces an evidence-based ranked shortlist for recruiters.

ISOLATION CONTRACT
------------------
- No imports from rico_agent, job-search ranking, JSearch, or application tracking.
- No AI provider names or secrets exposed in output.
- No final selection decisions — advisory rankings only.
- Protected characteristics (age, gender, ethnicity, nationality, religion,
  disability, marital status) are never scored or surfaced.
- Missing information is surfaced as "Not provided"; never inferred.

SCORING WEIGHTS
---------------
Core Job Match         : 40 pts
Relevant Experience    : 25 pts
GCC/UAE Readiness      : 15 pts
Achievements & Impact  : 10 pts
Education & Certs      : 10 pts
                        ------
Total                  : 100 pts
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class JDSummary:
    must_have_skills: list[str]
    preferred_skills: list[str]
    minimum_experience_years: int | str   # int or "Not provided"
    education_requirements: list[str]
    certification_requirements: list[str]
    gcc_uae_requirements: list[str]
    language_requirements: list[str]      # only if explicitly stated in JD
    other_criteria: list[str]


@dataclass
class EmploymentRecord:
    title: str
    employer: str
    start: str          # "YYYY-MM" or best approximation
    end: str            # "YYYY-MM" or "Present"
    tenure_months: int | str   # int or "Not provided"
    gcc_uae: bool


@dataclass
class CandidateProfile:
    candidate_name: str
    contact_info: str           # email / phone / LinkedIn — only what appears in CV
    years_of_relevant_experience: int | str
    skills_inventory: list[str]
    education: list[str]
    certifications: list[str]
    employment_history: list[EmploymentRecord]
    notable_achievements: list[str]
    gcc_uae_experience: str     # description or "Not provided"
    availability_visa_status: str  # only if explicitly present; else "Not provided"
    _raw_text: str = field(default="", repr=False)  # protected-stripped resume text for matching


@dataclass
class ScoreDimension:
    label: str
    weight: int
    score: int          # 0 – weight
    evidence: str       # short evidence excerpt or "Evidence not found"


@dataclass
class RedFlag:
    flag_type: str
    detail: str


@dataclass
class CandidateResult:
    candidate_name: str
    contact_info: str
    total_score: int             # 0–100
    fit_label: str               # Strong / Moderate / Weak Match
    interview_priority: str      # High / Medium / Low
    score_breakdown: list[ScoreDimension]
    strengths: list[str]
    concerns: list[str]
    red_flags: list[RedFlag]
    interview_questions: list[str]
    profile: CandidateProfile


@dataclass
class ScreeningResult:
    jd_summary: JDSummary
    candidates: list[CandidateResult]
    ranking_table: list[dict]    # [{rank, name, score, fit_label, priority}]
    executive_summary: str
    screened_at: str


# ---------------------------------------------------------------------------
# Protected-characteristic filter
# ---------------------------------------------------------------------------

# "local" and "expat" are intentionally excluded — they are UAE/GCC business
# terms (local hire, expat package, local compliance) and must not be stripped.
_PROTECTED_PATTERNS: list[re.Pattern] = [
    # Gender titles and pronouns
    re.compile(r"\b(mr|mrs|ms|miss)\b\.?", re.I),
    re.compile(r"\b(he|she|his|her|him)\b", re.I),
    re.compile(r"\b(male|female|man|woman|gentleman|lady)\b", re.I),
    # Ethnicity — \barab\b does NOT match "Arabic" (language), preserving that signal
    re.compile(r"\b(arab|asian|african|european|western|eastern|caucasian)\b", re.I),
    # Religion
    re.compile(r"\b(muslim|christian|hindu|jewish|sikh|buddhist|religion|religious)\b", re.I),
    # Age / date of birth
    re.compile(r"\b(born|dob|date\s+of\s+birth)\b", re.I),
    re.compile(r"\bage:?\s*\d+\b", re.I),
    re.compile(r"\b\d+\s*years?\s*old\b", re.I),
    # Marital status
    re.compile(r"\b(married|single|divorced|widowed|marital\s+status)\b", re.I),
    # Disability
    re.compile(r"\b(disability|disabled|impairment)\b", re.I),
]


def _strip_protected_content(text: str) -> str:
    """
    Redact protected-characteristic phrases using word-level replacement.

    This preserves sentence structure so UAE/GCC business-context sentences
    survive intact — e.g. "local compliance officer" and "expat visa package"
    are kept because "local" and "expat" are not in the protected list.
    """
    cleaned = text
    for pattern in _PROTECTED_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r" ([.,;:])", r"\1", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# JD Extraction
# ---------------------------------------------------------------------------

_EXPERIENCE_RE = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:relevant\s*)?experience",
    re.I,
)
_EDUCATION_TERMS = [
    "bachelor", "master", "phd", "doctorate", "degree", "diploma",
    "b.sc", "m.sc", "mba", "beng", "meng", "b.eng", "m.eng",
]
_CERT_KEYWORDS = [
    "pmp", "prince2", "iso", "nebosh", "iosh", "ielts", "toefl",
    "aws", "azure", "gcp", "cissp", "cpa", "cfa", "six sigma",
    "lean", "agile", "scrum", "cism", "ceh", "comptia",
]
_GCC_TERMS = [
    "uae", "gcc", "dubai", "abu dhabi", "sharjah", "ajman",
    "saudi", "qatar", "kuwait", "bahrain", "oman",
    "transferable visa", "noc", "visit visa", "employment visa",
    "mob", "municipality approval",
]
_LANGUAGE_MARKERS = [
    "arabic", "english", "french", "hindi", "urdu", "tagalog",
    "bilingual", "fluent in", "proficiency in",
]

# Headings that signal a new section — lines matching these are not skill items
_SECTION_HEADING_RE = re.compile(
    r"^(requirements?|required|must.?have|mandatory|essential|"
    r"preferred?|desirable|nice.to.have|advantage|"
    r"education|qualification|certific|responsibilities|"
    r"about the role|about us|what we offer|benefits|overview)\b",
    re.I,
)

_BULLET_STRIP_RE = re.compile(r"^[\-–—•·*\d.)\s]+")


def _clean_jd_item(line: str) -> str:
    """Strip leading bullets, numbers, and punctuation from a JD line."""
    return _BULLET_STRIP_RE.sub("", line).strip()


def extract_jd(jd_text: str) -> JDSummary:
    """
    Parse a job description string into structured JDSummary.
    Rules:
    - Only extract what is explicitly present.
    - Never infer or assume skills not stated.
    - Section headings are detected and skipped as skill items.
    - Language requirements extracted only if explicitly stated.
    """
    jd_text = _strip_protected_content(jd_text)
    lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]

    must_have: list[str] = []
    preferred: list[str] = []
    education: list[str] = []
    certs: list[str] = []
    gcc_reqs: list[str] = []
    languages: list[str] = []
    other: list[str] = []
    min_exp: int | str = "Not provided"

    section_map = {
        "must": "must_have",
        "required": "must_have",
        "mandatory": "must_have",
        "essential": "must_have",
        "prefer": "preferred",
        "nice to have": "preferred",
        "desirable": "preferred",
        "advantage": "preferred",
        "education": "education",
        "qualification": "education",
        "certif": "cert",
    }

    current_section = "other"

    for line in lines:
        lower = line.lower()
        cleaned = _clean_jd_item(line)

        # Detect and skip section headings — they are navigation markers, not skill items.
        # A line is a heading if it ends with ":" OR it starts with a heading keyword
        # AND is at most 3 words long (prevents "NEBOSH certification required" from matching).
        is_heading = False
        for kw, section in section_map.items():
            if kw in lower and len(line) < 80:
                looks_like_heading = (
                    line.rstrip().endswith(":")
                    or (bool(_SECTION_HEADING_RE.match(cleaned)) and len(cleaned.split()) <= 3)
                )
                if looks_like_heading:
                    current_section = section
                    is_heading = True
                    break
        if is_heading:
            continue

        if not cleaned:
            continue

        # Experience years
        m = _EXPERIENCE_RE.search(line)
        if m and min_exp == "Not provided":
            min_exp = int(m.group(1))

        # GCC/UAE requirements
        if any(t in lower for t in _GCC_TERMS):
            gcc_reqs.append(cleaned)
            continue

        # Language requirements (only if explicitly stated)
        if any(t in lower for t in _LANGUAGE_MARKERS):
            languages.append(cleaned)
            continue

        # Education
        if any(t in lower for t in _EDUCATION_TERMS):
            education.append(cleaned)
            continue

        # Certifications
        cert_matched = False
        for ck in _CERT_KEYWORDS:
            if ck in lower:
                certs.append(cleaned)
                cert_matched = True
                break
        if cert_matched:
            continue

        # Route to must_have / preferred / other
        if current_section == "must_have":
            must_have.append(cleaned)
        elif current_section == "preferred":
            preferred.append(cleaned)
        elif current_section not in ("must_have", "preferred", "education", "cert"):
            other.append(cleaned)

    return JDSummary(
        must_have_skills=_dedupe(must_have),
        preferred_skills=_dedupe(preferred),
        minimum_experience_years=min_exp,
        education_requirements=_dedupe(education),
        certification_requirements=_dedupe(certs),
        gcc_uae_requirements=_dedupe(gcc_reqs),
        language_requirements=_dedupe(languages),
        other_criteria=_dedupe(other)[:10],
    )


# ---------------------------------------------------------------------------
# Resume Extraction
# ---------------------------------------------------------------------------

_CONTACT_RE = re.compile(
    r"([\w.+-]+@[\w-]+\.\w{2,})|"             # email
    r"(\+?\d[\d\s\-().]{7,}\d)|"               # phone
    r"(linkedin\.com/in/[\w-]+)",
    re.I,
)
_TENURE_RE = re.compile(
    r"(?P<start>\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*\d{4}|\d{4})"
    r"\s*[-–—to]+\s*"
    r"(?P<end>Present|Current|Now|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*\d{4}|\d{4})",
    re.I,
)
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(s: str) -> datetime | None:
    s = s.strip()
    if re.match(r"present|current|now", s, re.I):
        now = datetime.now(timezone.utc)
        return datetime(now.year, now.month, now.day)
    m = re.match(r"(\w{3})\.?\s*(\d{4})", s, re.I)
    if m:
        mon = _MONTH_MAP.get(m.group(1).lower()[:3])
        if mon:
            return datetime(int(m.group(2)), mon, 1)
    m = re.match(r"(\d{4})$", s)
    if m:
        return datetime(int(m.group(1)), 1, 1)
    return None


def _calc_tenure(start_str: str, end_str: str) -> int | str:
    s = _parse_date(start_str)
    e = _parse_date(end_str)
    if s and e and e >= s:
        delta = (e.year - s.year) * 12 + (e.month - s.month)
        return max(delta, 0)
    return "Not provided"


def _calc_unique_months(employment: list[EmploymentRecord]) -> int | str:
    """
    Calculate total unique employment months, merging overlapping date ranges
    to avoid double-counting concurrent jobs.
    """
    intervals: list[tuple[datetime, datetime]] = []
    for rec in employment:
        s = _parse_date(rec.start)
        e = _parse_date(rec.end)
        if s and e and e >= s:
            intervals.append((s, e))

    if not intervals:
        return "Not provided"

    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[datetime, datetime]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    total = sum(
        (e.year - s.year) * 12 + (e.month - s.month)
        for s, e in merged
    )
    return max(0, total)


def extract_resume(resume_text: str) -> CandidateProfile:
    """
    Parse a resume/CV string into structured CandidateProfile.
    Rules:
    - Strip protected characteristics before processing.
    - Never infer facts not present in the text.
    - Empty or unreadable text returns a profile with "Not provided" fields.
    - GCC/UAE experience: only if explicitly mentioned.
    - Availability/visa: only if explicitly stated.
    """
    if not resume_text or not resume_text.strip():
        return CandidateProfile(
            candidate_name="Not provided",
            contact_info="Not provided",
            years_of_relevant_experience="Not provided",
            skills_inventory=[],
            education=[],
            certifications=[],
            employment_history=[],
            notable_achievements=[],
            gcc_uae_experience="Not provided",
            availability_visa_status="Not provided",
            _raw_text="",
        )

    clean_text = _strip_protected_content(resume_text)
    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]

    candidate_name = lines[0] if lines else "Not provided"

    contacts = _CONTACT_RE.findall(resume_text)
    contact_parts = []
    for groups in contacts:
        val = next((g for g in groups if g), "")
        if val:
            contact_parts.append(val.strip())
    contact_info = ", ".join(contact_parts) or "Not provided"

    # Employment history
    employment: list[EmploymentRecord] = []
    in_experience_section = False

    for i, line in enumerate(lines):
        lower = line.lower()
        if re.search(r"experience|employment|work history|career", lower):
            in_experience_section = True

        m = _TENURE_RE.search(line)
        if m and in_experience_section:
            start_str = m.group("start")
            end_str = m.group("end")
            tenure = _calc_tenure(start_str, end_str)
            title = lines[i - 1] if i > 0 else "Not provided"
            employer = lines[i + 1] if i + 1 < len(lines) else "Not provided"
            gcc = any(t in lower or t in title.lower() or t in employer.lower()
                      for t in _GCC_TERMS)
            employment.append(EmploymentRecord(
                title=title,
                employer=employer,
                start=start_str,
                end=end_str,
                tenure_months=tenure,
                gcc_uae=gcc,
            ))

    # Use merged intervals to avoid double-counting overlapping roles
    years_exp: int | str
    unique_months = _calc_unique_months(employment)
    if isinstance(unique_months, int) and unique_months > 0:
        years_exp = round(unique_months / 12)
    else:
        years_exp = "Not provided"

    # Skills extraction
    skills: list[str] = []
    in_skills = False
    for line in lines:
        lower = line.lower()
        if re.match(r"skills?|competenc|technical|tools?|software", lower):
            in_skills = True
            continue
        if in_skills:
            if len(line) < 3 or re.match(r"(education|experience|employment|certif|achievement|award)", lower):
                in_skills = False
            else:
                parts = re.split(r"[,|•·\t]", line)
                skills.extend(p.strip() for p in parts if 2 < len(p.strip()) < 60)

    if not skills:
        for line in lines:
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 3 and all(len(p) < 40 for p in parts):
                skills.extend(parts)

    # Education
    education_list: list[str] = []
    in_edu = False
    for line in lines:
        lower = line.lower()
        if re.match(r"education|academic|qualif", lower):
            in_edu = True
            continue
        if in_edu:
            if re.match(r"(experience|employment|skills?|certif|achievement)", lower):
                in_edu = False
            elif len(line) > 5:
                education_list.append(line)

    # Certifications
    cert_list: list[str] = []
    in_cert = False
    for line in lines:
        lower = line.lower()
        if re.match(r"certif|licens|accredit", lower):
            in_cert = True
            continue
        if in_cert:
            if re.match(r"(experience|employment|skills?|education|achievement)", lower):
                in_cert = False
            elif len(line) > 3:
                cert_list.append(line)
        for ck in _CERT_KEYWORDS:
            if ck in lower and line not in cert_list:
                cert_list.append(line)
                break

    # Notable achievements
    achievements: list[str] = []
    in_ach = False
    for line in lines:
        lower = line.lower()
        if re.match(r"achievement|award|recognit|accomplish|highlight", lower):
            in_ach = True
            continue
        if in_ach:
            if re.match(r"(experience|employment|skills?|education|certif)", lower):
                in_ach = False
            elif len(line) > 5:
                achievements.append(line)

    gcc_lines = [ln for ln in lines if any(t in ln.lower() for t in _GCC_TERMS)]
    gcc_uae_exp = "; ".join(gcc_lines[:3]) if gcc_lines else "Not provided"

    visa_lines = [
        ln for ln in lines
        if re.search(r"visa|work permit|availability|notice period|transferable|noc", ln, re.I)
    ]
    availability = "; ".join(visa_lines[:2]) if visa_lines else "Not provided"

    return CandidateProfile(
        candidate_name=candidate_name,
        contact_info=contact_info,
        years_of_relevant_experience=years_exp,
        skills_inventory=_dedupe(skills)[:30],
        education=_dedupe(education_list)[:10],
        certifications=_dedupe(cert_list)[:15],
        employment_history=employment,
        notable_achievements=_dedupe(achievements)[:10],
        gcc_uae_experience=gcc_uae_exp,
        availability_visa_status=availability,
        _raw_text=clean_text,
    )


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------

def _normalise_item(s: str) -> str:
    """Strip leading bullets, dashes, numbers from a JD requirement item."""
    return re.sub(r"^[\-•·*\d.)\s]+", "", s).strip().lower()


def _token_set(text: str, min_len: int = 4) -> set[str]:
    """Extract meaningful word tokens (length >= min_len) from text."""
    return {t for t in re.findall(r"\b[a-z][a-z0-9+#.]*\b", text.lower()) if len(t) >= min_len}


def _token_overlap_match(needle: str, haystack: str) -> bool:
    """
    Return True if a meaningful portion of needle's tokens appear in haystack.
    Requires at least one token of length >= 4 to match, avoiding false positives
    from very short or common words.
    """
    needle_tokens = _token_set(_normalise_item(needle))
    if not needle_tokens:
        return False
    haystack_lower = haystack.lower()
    matched = sum(1 for t in needle_tokens if t in haystack_lower)
    # At least half the meaningful tokens must be present
    return matched >= max(1, len(needle_tokens) * 0.5)


def _overlap_score(
    candidate_items: list[str],
    jd_items: list[str],
    full_text: str = "",
) -> tuple[float, str]:
    """
    Return fraction 0–1 of jd_items found in candidate evidence, plus an evidence excerpt.
    Uses token-overlap matching to avoid false positives from short substrings.
    """
    if not jd_items:
        return 1.0, "No JD requirements specified"

    search_corpus = " ".join(candidate_items)
    if full_text:
        search_corpus = search_corpus + " " + full_text

    matched = [
        item for item in jd_items
        if _token_overlap_match(item, search_corpus)
    ]

    if not matched:
        return 0.0, "Evidence not found"

    evidence = "; ".join(matched[:3])
    return len(matched) / len(jd_items), evidence


def score_core_job_match(profile: CandidateProfile, jd: JDSummary) -> ScoreDimension:
    """40 pts: must-have skills coverage."""
    weight = 40
    fraction, evidence = _overlap_score(profile.skills_inventory, jd.must_have_skills, profile._raw_text)
    cert_fraction, cert_ev = _overlap_score(profile.certifications, jd.certification_requirements, profile._raw_text)
    combined = (fraction * 0.7 + cert_fraction * 0.3) if jd.certification_requirements else fraction
    score = min(weight, round(combined * weight))
    _no_ev = {"Evidence not found", "No JD requirements specified"}
    full_ev = "; ".join(e for e in [evidence, cert_ev] if e and e not in _no_ev) or "Evidence not found"
    return ScoreDimension("Core Job Match", weight, score, full_ev[:200])


def score_relevant_experience(profile: CandidateProfile, jd: JDSummary) -> ScoreDimension:
    """25 pts: years of experience vs JD minimum."""
    weight = 25
    min_exp = jd.minimum_experience_years
    candidate_exp = profile.years_of_relevant_experience

    if isinstance(candidate_exp, str) or isinstance(min_exp, str):
        return ScoreDimension("Relevant Experience", weight, 0, "Evidence not found")

    if min_exp == 0:
        score = weight
        evidence = f"No minimum specified; candidate has {candidate_exp} years"
    elif candidate_exp >= min_exp:
        ratio = min(candidate_exp / min_exp, 2.0)
        score = min(weight, round((0.7 + 0.15 * (ratio - 1)) * weight))
        evidence = f"{candidate_exp} years experience vs {min_exp} years required"
    else:
        ratio = candidate_exp / min_exp
        score = round(ratio * weight * 0.7)
        evidence = f"{candidate_exp} years experience vs {min_exp} years required — below minimum"

    return ScoreDimension("Relevant Experience", weight, score, evidence)


def score_gcc_uae_readiness(profile: CandidateProfile, jd: JDSummary) -> ScoreDimension:
    """15 pts: GCC/UAE market experience and relevant work authorisation signals."""
    weight = 15
    score = 0
    evidence_parts: list[str] = []

    if profile.gcc_uae_experience != "Not provided":
        score += 10
        evidence_parts.append(profile.gcc_uae_experience[:100])

    gcc_roles = [e for e in profile.employment_history if e.gcc_uae]
    if gcc_roles:
        score = min(weight, score + 5)
        evidence_parts.append(f"{len(gcc_roles)} GCC/UAE role(s) in history")

    if profile.availability_visa_status != "Not provided" and jd.gcc_uae_requirements:
        evidence_parts.append(f"Visa/availability: {profile.availability_visa_status[:60]}")

    if not evidence_parts:
        return ScoreDimension("GCC/UAE Readiness", weight, 0, "Evidence not found")

    return ScoreDimension("GCC/UAE Readiness", weight, min(score, weight), "; ".join(evidence_parts)[:200])


def score_achievements(profile: CandidateProfile, _jd: JDSummary) -> ScoreDimension:
    """10 pts: quantified or notable achievements."""
    weight = 10
    if not profile.notable_achievements:
        return ScoreDimension("Achievements & Impact", weight, 0, "Evidence not found")

    quantified = [a for a in profile.notable_achievements if re.search(r"\d+[%$]?|\bAED\b", a)]
    base = min(weight, len(profile.notable_achievements) * 2)
    bonus = min(3, len(quantified))
    score = min(weight, base + bonus)
    evidence = profile.notable_achievements[0][:150]
    return ScoreDimension("Achievements & Impact", weight, score, evidence)


def score_education_certs(profile: CandidateProfile, jd: JDSummary) -> ScoreDimension:
    """10 pts: education and certifications against JD requirements."""
    weight = 10
    edu_fraction, edu_ev = _overlap_score(profile.education, jd.education_requirements, profile._raw_text)
    cert_fraction, cert_ev = _overlap_score(profile.certifications, jd.certification_requirements, profile._raw_text)

    if jd.education_requirements and jd.certification_requirements:
        combined = (edu_fraction + cert_fraction) / 2
    elif jd.education_requirements:
        combined = edu_fraction
    elif jd.certification_requirements:
        combined = cert_fraction
    else:
        combined = 1.0

    score = min(weight, round(combined * weight))
    evidence = "; ".join(filter(lambda s: s != "Evidence not found", [edu_ev, cert_ev])) or "Evidence not found"
    return ScoreDimension("Education & Certifications", weight, score, evidence[:200])


def _extract_cert_keywords(text: str) -> set[str]:
    """Extract known certification keywords present in a text string."""
    lower = text.lower()
    return {ck for ck in _CERT_KEYWORDS if ck in lower}


def detect_red_flags(profile: CandidateProfile, jd: JDSummary) -> list[RedFlag]:
    """
    Flag issues without rejecting the candidate.
    Flags: employment gaps >6m, short tenures <12m, missing mandatory certs,
    seniority mismatch, missing work authorisation if required.
    """
    flags: list[RedFlag] = []

    # Employment gaps > 6 months
    history = sorted(
        [e for e in profile.employment_history if _parse_date(e.start)],
        key=lambda e: _parse_date(e.start),  # type: ignore[arg-type, return-value]
    )
    for i in range(1, len(history)):
        prev_end = _parse_date(history[i - 1].end)
        curr_start = _parse_date(history[i].start)
        if prev_end and curr_start:
            gap_months = (curr_start.year - prev_end.year) * 12 + (curr_start.month - prev_end.month)
            if gap_months > 6:
                flags.append(RedFlag(
                    "employment_gap",
                    f"Gap of ~{gap_months} months between "
                    f"{history[i-1].employer} and {history[i].employer}",
                ))

    # Short tenures < 12 months
    short = [e for e in profile.employment_history
             if isinstance(e.tenure_months, int) and e.tenure_months < 12]
    if len(short) >= 2:
        flags.append(RedFlag(
            "multiple_short_tenures",
            f"{len(short)} role(s) with tenure under 12 months",
        ))

    # Missing mandatory certifications — compare extracted cert keywords, not raw substrings
    profile_cert_kws: set[str] = set()
    for cert_line in profile.certifications:
        profile_cert_kws |= _extract_cert_keywords(cert_line)
    # Also scan raw text for cert keywords
    if profile._raw_text:
        profile_cert_kws |= _extract_cert_keywords(profile._raw_text)

    missing_cert_labels: list[str] = []
    for jd_cert_line in jd.certification_requirements:
        jd_cert_kws = _extract_cert_keywords(jd_cert_line)
        if not jd_cert_kws:
            continue
        missing = jd_cert_kws - profile_cert_kws
        if missing:
            missing_cert_labels.append(", ".join(kw.upper() for kw in sorted(missing)))

    if missing_cert_labels:
        flags.append(RedFlag(
            "missing_mandatory_certifications",
            f"Mandatory cert(s) not found in CV: {'; '.join(missing_cert_labels[:3])}",
        ))

    # Seniority mismatch
    seniority_claimed = any(
        re.search(r"senior|manager|director|head|lead|principal", e.title, re.I)
        for e in profile.employment_history
    )
    exp = profile.years_of_relevant_experience
    if seniority_claimed and isinstance(exp, int) and exp < 3:
        flags.append(RedFlag(
            "seniority_mismatch",
            f"Senior/management title claimed but only {exp} years experience found",
        ))

    # Missing work authorisation if explicitly required by JD
    if jd.gcc_uae_requirements and profile.availability_visa_status == "Not provided":
        flags.append(RedFlag(
            "missing_work_authorisation",
            "JD specifies GCC/UAE requirements but visa/work authorisation not stated in CV",
        ))

    return flags


def _generate_interview_questions(
    profile: CandidateProfile,
    jd: JDSummary,
    red_flags: list[RedFlag],
) -> list[str]:
    """Generate role-specific, evidence-based interview questions."""
    questions: list[str] = []

    for skill in jd.must_have_skills[:3]:
        questions.append(f"Can you walk us through a specific project where you applied {skill}?")

    if jd.gcc_uae_requirements:
        questions.append(
            "What is your experience operating within UAE regulatory and compliance frameworks?"
        )

    if isinstance(profile.years_of_relevant_experience, int):
        questions.append(
            f"With {profile.years_of_relevant_experience} years of experience, "
            "what is the most complex challenge you have solved in this field?"
        )

    if profile.notable_achievements:
        questions.append(
            f"You mentioned: '{profile.notable_achievements[0][:80]}' — "
            "what was your specific role and what was the measured outcome?"
        )

    for flag in red_flags:
        if flag.flag_type == "employment_gap":
            questions.append(f"Could you explain the gap in your employment history? ({flag.detail})")
        elif flag.flag_type == "multiple_short_tenures":
            questions.append("Several of your roles were under 12 months — can you help us understand the context?")

    return questions[:7]


# ---------------------------------------------------------------------------
# Fit label & priority
# ---------------------------------------------------------------------------

def _fit_label(total: int) -> str:
    if total >= 75:
        return "Strong Match"
    if total >= 50:
        return "Moderate Match"
    return "Weak Match"


def _interview_priority(total: int, flags: list[RedFlag]) -> str:
    if total >= 75 and not flags:
        return "High"
    if total >= 50:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Strengths & Concerns summary
# ---------------------------------------------------------------------------

def _derive_strengths(profile: CandidateProfile, dims: list[ScoreDimension]) -> list[str]:
    strengths = []
    for dim in dims:
        if dim.score >= round(dim.weight * 0.75) and dim.evidence != "Evidence not found":
            strengths.append(f"{dim.label}: {dim.evidence[:100]}")
    if not strengths:
        strengths.append("No notable strengths identified from provided evidence")
    return strengths


def _derive_concerns(dims: list[ScoreDimension], flags: list[RedFlag]) -> list[str]:
    concerns = []
    for dim in dims:
        if dim.score < round(dim.weight * 0.5):
            concerns.append(f"Low {dim.label} score — {dim.evidence[:80]}")
    for flag in flags:
        concerns.append(f"[Flag] {flag.flag_type}: {flag.detail}")
    if not concerns:
        concerns.append("No significant concerns identified")
    return concerns


# ---------------------------------------------------------------------------
# Main screener entry point
# ---------------------------------------------------------------------------

def screen_resumes(
    jd_text: str,
    resumes: list[str],
) -> ScreeningResult:
    """
    Screen a list of resume strings against a job description.

    Parameters
    ----------
    jd_text : str   — Plain text of the job description.
    resumes : list[str] — Each element is the plain text of one candidate resume.

    Returns
    -------
    ScreeningResult — Fully structured, ranked advisory output.
    No final hire/reject decision is produced.

    Raises
    ------
    ValueError — If jd_text is empty or whitespace-only.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Job description is required")

    jd = extract_jd(jd_text)

    if not resumes:
        return ScreeningResult(
            jd_summary=jd,
            candidates=[],
            ranking_table=[],
            executive_summary=(
                "Screened 0 candidate(s) against the provided job description. "
                "This is an advisory ranking only — no final selection decision is produced."
            ),
            screened_at=datetime.now(timezone.utc).isoformat(),
        )

    results: list[CandidateResult] = []

    for resume_text in resumes:
        profile = extract_resume(resume_text)

        dims = [
            score_core_job_match(profile, jd),
            score_relevant_experience(profile, jd),
            score_gcc_uae_readiness(profile, jd),
            score_achievements(profile, jd),
            score_education_certs(profile, jd),
        ]
        total = sum(d.score for d in dims)
        flags = detect_red_flags(profile, jd)
        fit = _fit_label(total)
        priority = _interview_priority(total, flags)
        questions = _generate_interview_questions(profile, jd, flags)
        strengths = _derive_strengths(profile, dims)
        concerns = _derive_concerns(dims, flags)

        results.append(CandidateResult(
            candidate_name=profile.candidate_name,
            contact_info=profile.contact_info,
            total_score=total,
            fit_label=fit,
            interview_priority=priority,
            score_breakdown=dims,
            strengths=strengths,
            concerns=concerns,
            red_flags=flags,
            interview_questions=questions,
            profile=profile,
        ))

    results.sort(key=lambda r: r.total_score, reverse=True)

    ranking_table = [
        {
            "rank": i + 1,
            "name": r.candidate_name,
            "score": r.total_score,
            "fit_label": r.fit_label,
            "interview_priority": r.interview_priority,
        }
        for i, r in enumerate(results)
    ]

    top = results[0] if results else None
    exec_summary = (
        f"Screened {len(results)} candidate(s) against the provided job description. "
        + (
            f"Top candidate: {top.candidate_name} ({top.total_score}/100, {top.fit_label}). "
            if top else ""
        )
        + f"{sum(1 for r in results if r.fit_label == 'Strong Match')} strong match(es), "
        + f"{sum(1 for r in results if r.fit_label == 'Moderate Match')} moderate match(es), "
        + f"{sum(1 for r in results if r.fit_label == 'Weak Match')} weak match(es). "
        + "This is an advisory ranking only — no final selection decision is produced."
    )

    return ScreeningResult(
        jd_summary=jd,
        candidates=results,
        ranking_table=ranking_table,
        executive_summary=exec_summary,
        screened_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------

def screening_result_to_dict(result: ScreeningResult) -> dict:
    """Convert ScreeningResult to a plain dict suitable for JSON output."""
    def emp_to_dict(e: EmploymentRecord) -> dict:
        return {
            "title": e.title,
            "employer": e.employer,
            "start": e.start,
            "end": e.end,
            "tenure_months": e.tenure_months,
            "gcc_uae": e.gcc_uae,
        }

    def profile_to_dict(p: CandidateProfile) -> dict:
        return {
            "candidate_name": p.candidate_name,
            "contact_info": p.contact_info,
            "years_of_relevant_experience": p.years_of_relevant_experience,
            "skills_inventory": p.skills_inventory,
            "education": p.education,
            "certifications": p.certifications,
            "employment_history": [emp_to_dict(e) for e in p.employment_history],
            "notable_achievements": p.notable_achievements,
            "gcc_uae_experience": p.gcc_uae_experience,
            "availability_visa_status": p.availability_visa_status,
            # _raw_text intentionally excluded from public output
        }

    def dim_to_dict(d: ScoreDimension) -> dict:
        return {"label": d.label, "weight": d.weight, "score": d.score, "evidence": d.evidence}

    def flag_to_dict(f: RedFlag) -> dict:
        return {"flag_type": f.flag_type, "detail": f.detail}

    def candidate_to_dict(c: CandidateResult) -> dict:
        return {
            "candidate_name": c.candidate_name,
            "contact_info": c.contact_info,
            "total_score": c.total_score,
            "fit_label": c.fit_label,
            "interview_priority": c.interview_priority,
            "score_breakdown": [dim_to_dict(d) for d in c.score_breakdown],
            "strengths": c.strengths,
            "concerns": c.concerns,
            "red_flags": [flag_to_dict(f) for f in c.red_flags],
            "interview_questions": c.interview_questions,
            "profile": profile_to_dict(c.profile),
        }

    jd = result.jd_summary
    return {
        "jd_summary": {
            "must_have_skills": jd.must_have_skills,
            "preferred_skills": jd.preferred_skills,
            "minimum_experience_years": jd.minimum_experience_years,
            "education_requirements": jd.education_requirements,
            "certification_requirements": jd.certification_requirements,
            "gcc_uae_requirements": jd.gcc_uae_requirements,
            "language_requirements": jd.language_requirements,
            "other_criteria": jd.other_criteria,
        },
        "candidates": [candidate_to_dict(c) for c in result.candidates],
        "ranking_table": result.ranking_table,
        "executive_summary": result.executive_summary,
        "screened_at": result.screened_at,
    }


# ---------------------------------------------------------------------------
# Chat intent helper (hooks into rico_nlu if present)
# ---------------------------------------------------------------------------

RESUME_SCREENING_PHRASES = [
    "screen these cvs",
    "screen cv",
    "rank candidates",
    "compare resumes",
    "compare cvs",
    "evaluate resume",
    "evaluate cv",
    "shortlist applicants",
    "shortlist candidates",
    "review resumes",
    "review cvs",
    "score candidates",
    "rank applicants",
    "screen applicants",
]


def is_resume_screening_intent(message: str) -> bool:
    """
    Return True if the user's message maps to a resume_screening intent.
    Safe to call from rico_nlu.py without creating a circular import.
    """
    lower = message.lower()
    return any(phrase in lower for phrase in RESUME_SCREENING_PHRASES)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out
