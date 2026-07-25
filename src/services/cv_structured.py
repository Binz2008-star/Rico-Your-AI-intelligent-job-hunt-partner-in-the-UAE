"""The canonical ``rico_profiles.cv_structured`` document, and what makes it real.

``cv_structured`` is a JSONB column that existed but was never wired to the live
preview/confirm flow: no writer through the application path, and no reader
anywhere. That is why production profiles carry ``cv_status = "parsed"`` beside
``cv_structured = {}``. This module owns the shape that goes into that column and
the single rule for whether its contents are substantive enough to be called
``structured``.

Two rules govern everything here:

1. **Nothing is invented.** Every value is either a substring of the source CV
   or a count/flag derived from one. When the parser cannot split a section into
   entries, the section's verbatim text is kept instead — a readable section is
   real evidence, and discarding it would force the user to retype what the file
   already said.
2. **Substantive means professional content, not a filled-in form.** A name and
   a phone number are contact details, not a CV. ``structured`` requires work
   experience, education, or a credible set of skills — see
   ``is_substantive``. Schema validity alone never earns the label.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

SCHEMA_VERSION = 1

# Minimum number of extracted skills that counts as professional evidence on its
# own. One or two keyword hits are routinely incidental ("excel" appears in
# plenty of non-CV text); a handful together is a signal.
_MIN_STANDALONE_SKILLS = 3


def build_cv_structured(parsed: Any) -> Dict[str, Any]:
    """Assemble the ``cv_structured`` document from a ``ParsedCV``.

    Accepts the dataclass or any object exposing the same attributes, so a test
    can pass a stub without importing the parser. Missing attributes degrade to
    empty rather than raising: a partial parse must still produce a storable,
    honest document.
    """
    def _get(name: str, default: Any = None) -> Any:
        value = getattr(parsed, name, default)
        return default if value is None else value

    work_entries = list(_get("work_experience", []) or [])
    education_entries = list(_get("education", []) or [])
    work_text = _get("work_experience_text") or None
    education_text = _get("education_text") or None

    return {
        "schema_version": SCHEMA_VERSION,
        "name": _get("name") or None,
        "current_role": _get("current_role") or None,
        "skills": list(_get("skills", []) or []),
        "certifications": list(_get("certifications", []) or []),
        "languages": list(_get("languages", []) or []),
        # A HINT, never the authoritative value. rico_profiles.profile
        # .years_experience is the source of truth the product reads; this
        # records only what the document itself suggested, for reconciliation.
        "years_experience_hint": _get("years_experience_hint"),
        "work_experience": work_entries,
        "education": education_entries,
        # Verbatim section text, kept whenever the section was located — the
        # fallback that makes an unsplittable CV still usable.
        "work_experience_text": work_text,
        "education_text": education_text,
        # Records WHY the entry lists may be empty, so a reader can tell "no
        # section in this CV" from "section found but not splittable".
        "sections_found": {
            "work_experience": work_text is not None,
            "education": education_text is not None,
        },
        "extraction_quality": _get("extraction_quality", "unknown"),
        "extracted_chars": int(_get("extracted_chars", 0) or 0),
    }


def has_professional_content(structured: Optional[Dict[str, Any]]) -> bool:
    """True when the document carries substantive professional content.

    Contact details and a name are explicitly not enough. Any ONE of these
    qualifies, because CVs legitimately vary in what they emphasise:

      * at least one work-experience entry, or a located work-experience section
      * at least one education entry, or a located education section
      * a credible set of extracted skills (see ``_MIN_STANDALONE_SKILLS``)

    A current role on its own does not qualify: it is a single line that a
    signature block can produce.
    """
    if not isinstance(structured, dict) or not structured:
        return False
    if structured.get("work_experience") or structured.get("work_experience_text"):
        return True
    if structured.get("education") or structured.get("education_text"):
        return True
    skills = structured.get("skills") or []
    return isinstance(skills, (list, tuple)) and len(skills) >= _MIN_STANDALONE_SKILLS


def is_valid_schema(structured: Optional[Dict[str, Any]]) -> bool:
    """True when the document is shaped the way this module writes it.

    Deliberately permissive about MISSING optional keys (a document written by an
    earlier schema version must still be readable) and strict about the type of
    anything present, so a malformed blob can never be mistaken for a CV.
    """
    if not isinstance(structured, dict) or not structured:
        return False
    for key in ("skills", "certifications", "languages", "work_experience", "education"):
        if key in structured and not isinstance(structured[key], (list, tuple)):
            return False
    # Entry lists must contain entries, not scalars. A list of strings or Nones
    # under work_experience/education would otherwise satisfy the type check and
    # then earn `structured` in has_professional_content — a malformed blob
    # passing as a CV, which is exactly what this function exists to prevent.
    for key in ("work_experience", "education"):
        for entry in structured.get(key) or []:
            if not isinstance(entry, dict):
                return False
    for key in ("name", "current_role", "work_experience_text", "education_text"):
        if key in structured and structured[key] is not None and not isinstance(structured[key], str):
            return False
    hint = structured.get("years_experience_hint")
    if hint is not None and not isinstance(hint, (int, float)):
        return False
    return True


def is_substantive(structured: Optional[Dict[str, Any]]) -> bool:
    """The single gate for calling a stored document ``structured``.

    Both conditions, deliberately: a valid shape with nothing professional in it
    is the empty-``cv_structured`` failure wearing a schema, and professional
    content in a malformed blob cannot be read safely.
    """
    return is_valid_schema(structured) and has_professional_content(structured)
