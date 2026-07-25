"""The ONE builder for the CV upload preview.

The preview shown after an upload and the preview replayed for a pending upload
must be the same object built by the same code. Two parallel constructions would
drift — which is exactly the debt that left ``cv_structured`` written by one path
and read by none.

The preview is deliberately NOT stored. ``cv_upload_artifacts`` keeps the parsed
``cv_text``; anything that needs the preview later rebuilds it from that text
through ``build_preview_from_text`` below, so a replay can never describe a
different document than the upload did.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def build_cv_preview(
    parsed: Dict[str, Any],
    *,
    existing_skills: Optional[List[str]] = None,
    target_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Assemble the preview payload from a parsed-CV mapping.

    Field-for-field the shape the upload response has always returned; callers
    must not add keys of their own, or the two surfaces diverge again.
    """
    existing = list(existing_skills or [])
    detected = list(parsed.get("skills") or [])
    emails = parsed.get("emails") or []
    phones = parsed.get("phones") or []
    return {
        "name": parsed.get("name"),
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "current_role": parsed.get("current_role"),
        "experience_years": parsed.get("years_experience_hint"),
        "target_roles": list(target_roles or []),
        "skills_detected": detected,
        "existing_skills": existing,
        # Back-compat: detected skills when present, else whatever the profile
        # already had. Unchanged from the original upload-response behaviour.
        "skills": detected if detected else existing,
        "certifications": list(parsed.get("certifications") or []),
        "languages": list(parsed.get("languages") or []),
    }


def build_preview_from_text(
    cv_text: str,
    *,
    existing_skills: Optional[List[str]] = None,
    role_extractor: Optional[Callable[[str], List[str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Rebuild the preview from stored CV text. ``None`` when it cannot be built.

    ``None`` is a real answer and must be reported as "preview unavailable" — it
    is NOT the same as "no pending upload". Collapsing the two would tell a user
    their upload vanished when in fact only the replay failed.
    """
    if not cv_text or not str(cv_text).strip():
        return None
    try:
        from src.cv_parser import CVParser

        parsed = CVParser().parse_text(str(cv_text)).to_dict()
        roles: List[str] = []
        if role_extractor is not None:
            try:
                roles = list(role_extractor(str(cv_text)) or [])
            except Exception:
                roles = []
        return build_cv_preview(parsed, existing_skills=existing_skills, target_roles=roles)
    except Exception:
        return None
