from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

_SENIOR_TERMS = ("senior", "lead", "principal", "staff", "manager", "director", "head")
_JUNIOR_TERMS = ("junior", "assistant", "associate", "intern", "trainee", "entry")


def _to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)

    data: Dict[str, Any] = {}
    for key in dir(value):
        if key.startswith("_"):
            continue
        try:
            attr = getattr(value, key)
        except Exception:
            continue
        if not callable(attr):
            data[key] = attr
    return data


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace(";", ",").replace("|", ",").split(",")
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        result: List[str] = []
        for item in value:
            text = _text(item)
            if text:
                result.append(text)
        return result
    text = _text(value)
    return [text] if text else []


def _ordered_unique(values: List[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _coerce_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _subject(title: str, company: str) -> str:
    if title and company:
        return f"{title} at {company}"
    if title:
        return title
    if company:
        return f"role at {company}"
    return "this role"


def _target_roles(profile_data: Dict[str, Any]) -> List[str]:
    roles = _ordered_unique(_as_list(profile_data.get("target_roles")))
    current_role = _text(profile_data.get("current_role"))
    if current_role and current_role.lower() not in {role.lower() for role in roles}:
        roles.insert(0, current_role)
    return roles


def _job_skills(job_data: Dict[str, Any]) -> List[str]:
    return _ordered_unique(_as_list(job_data.get("skills") or job_data.get("required_skills")))


def _profile_skills(profile_data: Dict[str, Any]) -> List[str]:
    return _ordered_unique(_as_list(profile_data.get("skills")))


def _matched_skills(job_data: Dict[str, Any], profile_data: Dict[str, Any]) -> List[str]:
    job_skills = _job_skills(job_data)
    if not job_skills:
        return []

    profile_map = {skill.lower(): skill for skill in _profile_skills(profile_data)}
    matches: List[str] = []
    for skill in job_skills:
        matched = profile_map.get(skill.lower())
        if matched:
            matches.append(matched)
    return _ordered_unique(matches)


def _title_matches_target(title: str, target_roles: List[str]) -> bool:
    title_l = title.lower()
    return any(role.lower() in title_l or title_l in role.lower() for role in target_roles if role)


def _seniority_note(job_data: Dict[str, Any], profile_data: Dict[str, Any]) -> str | None:
    years = _coerce_float(
        profile_data.get("years_experience")
        or profile_data.get("years_experience_hint")
        or profile_data.get("experience_years")
    )
    if years is None:
        return None

    seniority_text = " ".join(
        part
        for part in [
            _text(job_data.get("seniority")),
            _text(job_data.get("experience")),
            _text(job_data.get("experience_level")),
            _text(job_data.get("title")),
        ]
        if part
    ).lower()

    if any(term in seniority_text for term in _SENIOR_TERMS) and years < 3:
        return "The role looks more senior than your recorded experience."
    if any(term in seniority_text for term in _JUNIOR_TERMS) and years >= 8:
        return "The role may be more junior than your background."
    return None


def build_match_explanation(job: dict, profile: dict | None = None) -> dict:
    job_data = _to_dict(job)
    profile_data = _to_dict(profile)

    score = _coerce_int(job_data.get("match_score") or job_data.get("score") or 0)
    title = _text(job_data.get("title"))
    company = _text(job_data.get("company"))
    location = _text(job_data.get("location"))
    salary = _text(job_data.get("salary") or job_data.get("salary_range"))
    subject = _subject(title, company)

    if score >= 80:
        verdict = "strong_fit"
        confidence = "high"
        summary = f"Strong fit for {subject} based on the current profile overlap and score."
        next_step = "Apply or ask Rico to tailor your CV for this role."
    elif score >= 55:
        verdict = "worth_checking"
        confidence = "medium"
        summary = f"{subject.capitalize()} shows enough overlap to review more closely."
        next_step = "Review the role details, then save it or refine your search."
    else:
        verdict = "weak_fit"
        confidence = "low"
        summary = f"{subject.capitalize()} looks weaker against your current profile signals."
        next_step = "Skip this role or ask Rico to refine your target role."

    target_roles = _target_roles(profile_data)
    matched_skills = _matched_skills(job_data, profile_data)
    job_skills = _job_skills(job_data)
    title_matches_target = _title_matches_target(title, target_roles) if title and target_roles else False

    why: List[str] = []
    if matched_skills:
        why.append("Matches your skills: " + ", ".join(matched_skills[:5]) + ".")
    if title and title_matches_target:
        why.append(f"Role title aligns with your target role: {title}.")
    elif title:
        why.append(f"Role title appears relevant enough to review: {title}.")
    if score:
        why.append(f"Match score is {score}%.")

    if not why:
        why.append(
            f"{subject.capitalize()} was surfaced with limited signals, so the current ranking is the main reason to review it."
        )

    checks: List[str] = []
    if not location:
        checks.append("Location is missing or unclear.")
    if not salary:
        checks.append("Salary is not listed.")
    if not company:
        checks.append("Company information is missing.")
    if not matched_skills:
        if job_skills:
            checks.append("Explicit skill overlap is limited in the available job data.")
        else:
            checks.append("Required skills are not clearly listed in the job data.")
    if target_roles and not title_matches_target:
        checks.append("Role title does not clearly match your target role yet.")

    seniority_note = _seniority_note(job_data, profile_data)
    if seniority_note:
        checks.append(seniority_note)

    if not checks:
        checks.append("Confirm the full role details before applying.")

    return {
        "verdict": verdict,
        "summary": summary,
        "why_this_fits": why[:4],
        "worth_checking": checks[:4],
        "recommended_next_step": next_step,
        "confidence": confidence,
    }
